"""Concept dimension scoring (MVP heuristic).

Computes 4 standard dimensions for every concept, using keyword
dictionaries + length signals against the bucketed participant turns:

- ``sentiment``       (-1 … +1) — balance of positive vs. negative markers
- ``purchase_intent`` (0 … 10)  — frequency of purchase-intent phrases
- ``appeal``          (0 … 10)  — frequency of appeal / delight phrases
- ``comprehension``   (0 … 10)  — inverse of confusion markers, capped

All functions are pure + synchronous — easy to unit test, no external
service calls. When the real NLP pipeline lands, replace
:func:`score_turns` with an LLM call; the surrounding aggregation +
wire shape stay identical.
"""

from __future__ import annotations

from typing import Iterable


# ── Lexicons (zh + en) ──────────────────────────────────────────────

_POSITIVE = {
    # zh
    "喜欢", "棒", "不错", "好", "漂亮", "舒服", "惊艳", "高级",
    "有质感", "有意思", "有趣", "愿意", "会买", "想买", "值得",
    "推荐", "吸引", "酷", "好看", "清爽",
    # en
    "love", "like", "great", "good", "nice", "beautiful", "attractive",
    "cool", "appealing", "premium", "would buy", "worth", "amazing",
}

_NEGATIVE = {
    # zh
    "不喜欢", "不行", "差", "丑", "奇怪", "土", "便宜", "廉价",
    "不买", "不会买", "别扭", "看不懂", "看不出", "没意思", "无感",
    "随便", "一般", "普通",
    # en
    "hate", "dislike", "ugly", "cheap", "weird", "confusing", "meh",
    "boring", "bland", "would not buy", "not my style",
}

_PURCHASE = {
    "会买", "想买", "愿意买", "要买", "考虑买", "下单", "买回家",
    "购买", "买单", "值得买", "付钱", "would buy", "i'd buy",
    "purchase", "pay for", "i'd pick",
}

_APPEAL = {
    "喜欢", "爱", "超喜欢", "真不错", "太棒", "很棒", "太好了",
    "惊艳", "打动", "有感觉", "戳中", "love it", "adore", "fall in love",
    "amazing", "wow",
}

_CONFUSION = {
    "看不懂", "不明白", "不清楚", "搞不懂", "迷糊", "什么意思",
    "怎么", "confused", "unclear", "don't get it", "doesn't make sense",
}


# ── Core scorer ─────────────────────────────────────────────────────


def _count_any(text: str, vocab: Iterable[str]) -> int:
    t = text.lower()
    return sum(t.count(w.lower()) for w in vocab)


def score_turns(texts: Iterable[str]) -> dict[str, float]:
    """Score a bucket of participant turns across 4 dimensions.

    Empty or whitespace-only input returns all zeros so callers get a
    safe numeric payload regardless of session activity.
    """
    joined = " ".join(t for t in texts if t).strip()
    if not joined:
        return {
            "sentiment": 0.0,
            "purchase_intent": 0.0,
            "appeal": 0.0,
            "comprehension": 0.0,
        }

    pos = _count_any(joined, _POSITIVE)
    neg = _count_any(joined, _NEGATIVE)
    pur = _count_any(joined, _PURCHASE)
    appeal = _count_any(joined, _APPEAL)
    conf = _count_any(joined, _CONFUSION)

    # Sentiment: balance in [-1, +1].
    total_polarity = pos + neg
    sentiment = (pos - neg) / total_polarity if total_polarity else 0.0

    # 0..10 scale: each keyword hit worth ~1.5, capped at 10.
    purchase_intent = min(10.0, pur * 1.5)
    appeal_score = min(10.0, appeal * 1.5)

    # Comprehension: 10 minus (confusion × 2), floored at 0.
    comprehension = max(0.0, 10.0 - conf * 2.0)

    return {
        "sentiment": round(sentiment, 2),
        "purchase_intent": round(purchase_intent, 2),
        "appeal": round(appeal_score, 2),
        "comprehension": round(comprehension, 2),
    }


def aggregate_concept_dimensions(
    sessions_transcripts: Iterable[Iterable[dict]],
    concept_id: str,
) -> list[dict]:
    """Aggregate dimension scores across many sessions for one concept.

    Parameters
    ----------
    sessions_transcripts
        Iterable of session transcripts (each a list of turn dicts
        with ``role``, ``text``, optional ``concept_id``).
    concept_id
        The concept whose turns to aggregate.

    Returns
    -------
    ``[{"name": "sentiment", "value": float}, ...]`` — one entry per
    dimension, computed from concatenated participant turns across
    all sessions that discussed this concept. Empty list when no
    matching turns exist.
    """
    texts: list[str] = []
    for transcript in sessions_transcripts:
        for turn in transcript or []:
            if turn.get("concept_id") != concept_id:
                continue
            if turn.get("role") != "participant":
                continue
            text = turn.get("text")
            if text:
                texts.append(text)

    if not texts:
        return []

    scores = score_turns(texts)
    return [{"name": k, "value": v} for k, v in scores.items()]
