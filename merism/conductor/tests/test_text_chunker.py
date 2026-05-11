"""Tests for TextChunker — priority-based splitter for streaming TTS."""

from __future__ import annotations

from merism.conductor.text_chunker import TextChunker


class TestSentenceBreaks:
    def test_english_period_splits(self) -> None:
        c = TextChunker()
        out = c.feed("Hello world.")
        assert out == ["Hello world."]

    def test_chinese_period_splits(self) -> None:
        c = TextChunker()
        out = c.feed("你好。")
        assert out == ["你好。"]

    def test_multiple_sentences_same_feed(self) -> None:
        c = TextChunker()
        out = c.feed("First. Second. Third.")
        assert out == ["First.", "Second.", "Third."]

    def test_question_mark(self) -> None:
        c = TextChunker()
        out = c.feed("What do you mean?")
        assert out == ["What do you mean?"]


class TestStreamingIncremental:
    def test_tokens_build_up_until_break(self) -> None:
        c = TextChunker()
        assert c.feed("Hel") == []
        assert c.feed("lo wor") == []
        assert c.feed("ld") == []
        assert c.feed(".") == ["Hello world."]

    def test_multi_delta_chinese(self) -> None:
        c = TextChunker()
        assert c.feed("你") == []
        assert c.feed("好") == []
        assert c.feed("。") == ["你好。"]


class TestFallback:
    def test_force_split_after_max_chars_zh(self) -> None:
        c = TextChunker(max_chars=10)
        text = "一二三四五六七八九十一二三四五"
        out = c.feed(text)
        assert len(out) >= 1
        assert "".join(out + c.flush()) == text

    def test_force_split_after_max_words_en(self) -> None:
        c = TextChunker(max_words=5)
        text = "one two three four five six seven"
        out = c.feed(text)
        assert len(out) >= 1


class TestFlush:
    def test_flush_empty_buffer_returns_nothing(self) -> None:
        c = TextChunker()
        assert c.flush() == []

    def test_flush_returns_incomplete_phrase(self) -> None:
        c = TextChunker()
        c.feed("incomplete text without break")
        rest = c.flush()
        assert rest == ["incomplete text without break"]

    def test_feed_then_flush_chinese_no_break(self) -> None:
        c = TextChunker(max_chars=100)
        c.feed("这是一个没有标点的句子")
        assert c.flush() == ["这是一个没有标点的句子"]


class TestFillerOptimization:
    """Leading filler ('好,' / 'I see,') should emit early for low latency."""

    def test_leading_filler_en_comma(self) -> None:
        c = TextChunker()
        out = c.feed("I see,")
        assert out == ["I see,"]

    def test_leading_filler_en_comma_then_more(self) -> None:
        c = TextChunker()
        first = c.feed("Got it,")
        second = c.feed(" can you say more?")
        # "Got it," emits immediately; the rest emits at "?"
        assert "Got it," in first
        assert any("can you say more?" in p for p in second)


class TestEdgeCases:
    def test_empty_feed(self) -> None:
        c = TextChunker()
        assert c.feed("") == []

    def test_whitespace_only(self) -> None:
        c = TextChunker()
        c.feed("   ")
        assert c.flush() == []
