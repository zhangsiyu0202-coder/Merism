"""TextChunker — priority-based text splitter for streaming TTS.

Borrowed from asiff00/On-Device-Speech-to-Speech (MIT license). Adapted
for zh+en mixed interview transcripts.

Problem: LLM streams tokens one at a time. Piping each token to TTS is
wasteful (per-call network overhead) and produces choppy prosody. But
waiting for the whole response before TTS defeats streaming.

Solution: buffer LLM deltas and emit **complete natural-language
phrases** to TTS as soon as a good break appears.

Priority ladder (higher wins; earlier break at that priority wins):

    5. Sentence-final punctuation   .  !  ?  。  !  ?
    4. Strong transitions / strong  ; :  however / therefore /
       punctuation                  furthermore / 然而 / 因此 / 此外
    3. Medium                       , 、  while / although / 虽然 / 但是
    2. Weak                         - —  and / but / then / 和 / 而
    fallback. Force-split           max_words (EN) / max_chars (ZH)

First-chunk trick: if the LLM is prompted to start with a filler token
("好" / "Got it" / "I see"), this chunker will split at the first
punctuation and emit that tiny chunk immediately → TTS plays it while
the rest of the reply streams, reducing perceived latency 50-70%.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


_PRIORITY_5_PUNCT = {".", "!", "?", "。", "!", "?"}
_PRIORITY_4_PUNCT = {";", ":", ";", ":"}
_PRIORITY_3_PUNCT = {",", ",", "、"}
_PRIORITY_2_PUNCT = {"-", "—"}

_PRIORITY_4_WORDS_EN = {"however", "therefore", "furthermore", "moreover", "nevertheless"}
_PRIORITY_3_WORDS_EN = {"while", "although", "unless", "since"}
_PRIORITY_2_WORDS_EN = {"and", "but", "because", "then", "so"}

_PRIORITY_4_WORDS_ZH = {"然而", "因此", "此外", "而且", "不过"}
_PRIORITY_3_WORDS_ZH = {"虽然", "但是", "所以", "因为"}
_PRIORITY_2_WORDS_ZH = {"和", "而", "就", "也"}


@dataclass
class _Break:
    pos: int       # character index in buffer (exclusive — punctuation included)
    priority: int


class TextChunker:
    """Streaming text splitter.

    Usage::

        chunker = TextChunker()
        async for delta in llm_stream:
            for phrase in chunker.feed(delta):
                await tts.speak(phrase)
        for phrase in chunker.flush():
            await tts.speak(phrase)
    """

    def __init__(
        self,
        *,
        min_chars: int = 2,
        max_words: int = 14,
        max_chars: int = 20,
    ) -> None:
        self._buf: str = ""
        self.min_chars = min_chars
        self.max_words = max_words
        self.max_chars = max_chars

    def feed(self, delta: str) -> list[str]:
        """Append ``delta`` and return any complete phrases ready for TTS."""
        if not delta:
            return []
        self._buf += delta
        out: list[str] = []
        while True:
            p = self._extract_phrase()
            if p is None:
                break
            out.append(p)
        return out

    def flush(self) -> list[str]:
        """Emit remaining buffered text as the final phrase."""
        remainder = self._buf.strip()
        self._buf = ""
        return [remainder] if remainder else []

    # ── Internal ─────────────────────────────────────────────

    def _extract_phrase(self) -> str | None:
        if len(self._buf) < self.min_chars:
            return None

        best = self._find_best_break(self._buf)
        if best is None:
            forced = self._forced_split_pos(self._buf)
            if forced is None:
                return None
            best = _Break(pos=forced, priority=0)

        phrase = self._buf[: best.pos].strip()
        self._buf = self._buf[best.pos :]
        if not phrase:
            return self._extract_phrase()
        return phrase

    def _find_best_break(self, buf: str) -> _Break | None:
        for priority in (5, 4, 3, 2):
            pos = self._find_break_at_priority(buf, priority)
            if pos is not None:
                return _Break(pos=pos, priority=priority)
        return None

    def _find_break_at_priority(self, buf: str, priority: int) -> int | None:
        if priority == 5:
            return _find_first_char(buf, _PRIORITY_5_PUNCT)
        if priority == 4:
            pos1 = _find_first_char(buf, _PRIORITY_4_PUNCT)
            pos2 = _find_first_word(buf, _PRIORITY_4_WORDS_EN | _PRIORITY_4_WORDS_ZH)
            return _earlier(pos1, pos2)
        if priority == 3:
            pos1 = _find_first_char(buf, _PRIORITY_3_PUNCT)
            pos2 = _find_first_word(buf, _PRIORITY_3_WORDS_EN | _PRIORITY_3_WORDS_ZH)
            return _earlier(pos1, pos2)
        if priority == 2:
            pos1 = _find_first_char(buf, _PRIORITY_2_PUNCT)
            pos2 = _find_first_word(buf, _PRIORITY_2_WORDS_EN | _PRIORITY_2_WORDS_ZH)
            return _earlier(pos1, pos2)
        return None

    def _forced_split_pos(self, buf: str) -> int | None:
        """Return split index if buffer exceeds word/char limits, else None."""
        zh_chars = sum(1 for c in buf if _is_cjk(c))
        if zh_chars >= self.max_chars:
            return len(buf)
        words = buf.split()
        if len(words) >= self.max_words:
            count = 0
            for m in re.finditer(r"\S+\s*", buf):
                count += 1
                if count >= self.max_words:
                    return m.end()
        return None


# ── Module-level helpers ──────────────────────────────────────


def _find_first_char(buf: str, chars: set[str]) -> int | None:
    for i, ch in enumerate(buf):
        if ch in chars:
            return i + 1
    return None


def _find_first_word(buf: str, words: set[str]) -> int | None:
    """Find earliest start of any word in ``words``. EN uses word boundary,
    CJK uses substring match."""
    earliest: int | None = None
    for w in words:
        if _is_ascii(w):
            pat = re.compile(r"\b" + re.escape(w) + r"\b", flags=re.IGNORECASE)
            m = pat.search(buf)
            if m is not None:
                pos = m.start()
                if earliest is None or pos < earliest:
                    earliest = pos
        else:
            idx = buf.find(w)
            if idx >= 0 and (earliest is None or idx < earliest):
                earliest = idx
    return earliest


def _is_ascii(s: str) -> bool:
    try:
        s.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def _is_cjk(ch: str) -> bool:
    return (
        "\u4e00" <= ch <= "\u9fff"
        or "\u3040" <= ch <= "\u30ff"
        or "\uac00" <= ch <= "\ud7af"
    )


def _earlier(a: int | None, b: int | None) -> int | None:
    if a is None:
        return b
    if b is None:
        return a
    return min(a, b)
