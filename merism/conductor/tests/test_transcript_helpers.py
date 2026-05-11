"""Tests for :mod:`merism.conductor.transcript_helpers`."""

from __future__ import annotations

from merism.conductor.transcript_helpers import (
    get_transcript_text,
    get_turn_text,
    has_clean_transcript,
)


class TestGetTurnText:
    def test_prefers_clean(self):
        turn = {"text_raw": "嗯嗯我觉得", "text_clean": "我觉得", "text": "legacy"}
        assert get_turn_text(turn, "clean") == "我觉得"

    def test_raw_mode(self):
        turn = {"text_raw": "嗯嗯我觉得", "text_clean": "我觉得"}
        assert get_turn_text(turn, "raw") == "嗯嗯我觉得"

    def test_legacy_only_text_field(self):
        turn = {"text": "legacy only"}
        assert get_turn_text(turn, "clean") == "legacy only"
        assert get_turn_text(turn, "raw") == "legacy only"

    def test_fallback_when_clean_missing(self):
        turn = {"text_raw": "嗯嗯我觉得"}
        assert get_turn_text(turn, "clean") == "嗯嗯我觉得"

    def test_empty_turn_returns_empty_string(self):
        assert get_turn_text({}, "clean") == ""
        assert get_turn_text({}, "raw") == ""

    def test_empty_strings_skipped(self):
        turn = {"text_clean": "", "text_raw": "fallback"}
        assert get_turn_text(turn, "clean") == "fallback"


class TestGetTranscriptText:
    def _transcript(self):
        return [
            {"role": "agent", "text_clean": "Welcome"},
            {"role": "participant", "text_clean": "Thanks"},
            {"role": "system", "text_clean": "Session started"},
        ]

    def test_excludes_system_by_default(self):
        out = get_transcript_text(self._transcript())
        assert "Welcome" in out
        assert "Thanks" in out
        assert "Session started" not in out

    def test_include_system_explicit(self):
        out = get_transcript_text(
            self._transcript(), include_roles=("agent", "participant", "system")
        )
        assert "Session started" in out

    def test_empty_transcript(self):
        assert get_transcript_text([]) == ""

    def test_legacy_transcript_renders(self):
        transcript = [
            {"role": "agent", "text": "Hi"},
            {"role": "participant", "text": "Hello"},
        ]
        out = get_transcript_text(transcript)
        assert "[agent] Hi" in out
        assert "[participant] Hello" in out


class TestHasCleanTranscript:
    def test_all_clean(self):
        t = [
            {"role": "agent", "text_clean": "Hi"},
            {"role": "participant", "text_clean": "Hello"},
        ]
        assert has_clean_transcript(t) is True

    def test_mixed_legacy_fails(self):
        t = [
            {"role": "agent", "text_clean": "Hi"},
            {"role": "participant", "text": "Hello"},  # no text_clean
        ]
        assert has_clean_transcript(t) is False

    def test_empty_list(self):
        assert has_clean_transcript([]) is False

    def test_skips_non_conversation_roles(self):
        t = [
            {"role": "agent", "text_clean": "Hi"},
            {"role": "system", "text": "meta"},  # ignored
            {"role": "participant", "text_clean": "Hello"},
        ]
        assert has_clean_transcript(t) is True
