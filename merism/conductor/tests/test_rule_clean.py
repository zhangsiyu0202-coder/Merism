"""Tests for :mod:`merism.conductor.rule_clean`."""

from __future__ import annotations

import pytest

from merism.conductor.rule_clean import is_mostly_fillers, rule_clean


class TestChineseFillers:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("嗯，我觉得这个产品还不错", "我觉得这个产品还不错"),
            ("啊，就是说这个界面有点乱", "这个界面有点乱"),
            ("嗯嗯嗯嗯，对", "对"),
            ("呃，我没用过这个功能", "我没用过这个功能"),
            ("对对对，我也是这么想的", "我也是这么想的"),
            ("然后呢，我就点了那个按钮", "我就点了那个按钮"),
            ("那个那个，价格太贵了", "价格太贵了"),
        ],
    )
    def test_strips_chinese_fillers(self, raw: str, expected: str):
        assert rule_clean(raw) == expected

    def test_preserves_content_word_like_filler(self):
        # "嗯" inside a real word must NOT be stripped.
        assert rule_clean("嗯心地做事") == "嗯心地做事"

    def test_strips_trailing_filler(self):
        assert rule_clean("我觉得挺好用的，啊") == "我觉得挺好用的"


class TestEnglishFillers:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("Um, I think the checkout is confusing.", "I think the checkout is confusing."),
            ("Uh, yeah, I agree.", "yeah, I agree."),
            ("I mean, the price is too high.", "the price is too high."),
            ("It's, like, really slow.", "It's, really slow."),
            ("Sort of the same issue I had before.", "the same issue I had before."),
        ],
    )
    def test_strips_english_fillers(self, raw: str, expected: str):
        assert rule_clean(raw) == expected

    def test_preserves_content_word_like(self):
        # "like" as a verb must stay.
        assert rule_clean("I like it a lot.") == "I like it a lot."

    def test_case_insensitive(self):
        assert rule_clean("UM, yes.") == "yes."


class TestFalseStarts:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("I, I went there yesterday.", "I went there yesterday."),
            ("我 我 去了商场", "我 去了商场"),
            ("She, she said no.", "She said no."),
        ],
    )
    def test_collapses_false_starts(self, raw: str, expected: str):
        assert rule_clean(raw) == expected

    def test_triple_false_start(self):
        assert rule_clean("I, I, I can't remember.") == "I can't remember."


class TestEdgeCases:
    def test_empty(self):
        assert rule_clean("") == ""
        assert rule_clean("   ") == ""

    def test_all_fillers_returns_empty(self):
        assert rule_clean("嗯 啊 呃") == ""
        assert rule_clean("um uh") == ""

    def test_idempotent(self):
        raw = "嗯，我，我觉得 um 还不错"
        once = rule_clean(raw)
        twice = rule_clean(once)
        assert once == twice

    def test_preserves_punctuation_meaning(self):
        # Question marks / exclamation should survive.
        result = rule_clean("嗯，真的吗？")
        assert "？" in result or "?" in result

    def test_preserves_real_content(self):
        # A full, filler-free sentence comes out unchanged.
        original = "这个功能对我来说非常有用，我每天都在用。"
        assert rule_clean(original) == original


class TestIsMostlyFillers:
    def test_heavy_filler_detected(self):
        raw = "嗯嗯嗯 啊 就是说 然后呢"
        cleaned = rule_clean(raw)
        assert is_mostly_fillers(raw, cleaned) is True

    def test_content_not_flagged(self):
        raw = "我觉得这个产品的价格太贵了"
        cleaned = rule_clean(raw)
        assert is_mostly_fillers(raw, cleaned) is False

    def test_empty_raw_not_flagged(self):
        assert is_mostly_fillers("", "") is False
