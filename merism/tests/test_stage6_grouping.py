"""Tests for stage6_semantic_merge — grouping heuristic (no LLM)."""

from __future__ import annotations

from merism.cleaning.stages.stage6_semantic_merge import _group_mergeable_runs


class TestGrouping:
    def test_single_turn_single_group(self) -> None:
        turns = [{"role": "p", "text": "hi", "ts_start_ms": 0, "ts_end_ms": 500}]
        groups = _group_mergeable_runs(turns)
        assert groups == [[0]]

    def test_consecutive_same_speaker_close_gap_merged(self) -> None:
        turns = [
            {"role": "p", "text": "So", "ts_start_ms": 0, "ts_end_ms": 500},
            {"role": "p", "text": "I think", "ts_start_ms": 1000, "ts_end_ms": 2000},
            {"role": "p", "text": "maybe", "ts_start_ms": 2500, "ts_end_ms": 3000},
        ]
        groups = _group_mergeable_runs(turns)
        assert groups == [[0, 1, 2]]

    def test_different_speakers_not_merged(self) -> None:
        turns = [
            {"role": "p", "text": "hi", "ts_start_ms": 0, "ts_end_ms": 500},
            {"role": "a", "text": "hello", "ts_start_ms": 800, "ts_end_ms": 1200},
            {"role": "p", "text": "yeah", "ts_start_ms": 1500, "ts_end_ms": 1800},
        ]
        groups = _group_mergeable_runs(turns)
        assert groups == [[0], [1], [2]]

    def test_large_gap_splits_group(self) -> None:
        turns = [
            {"role": "p", "text": "first thought", "ts_start_ms": 0, "ts_end_ms": 1000},
            # 10s gap → new group
            {"role": "p", "text": "new thought", "ts_start_ms": 11000, "ts_end_ms": 12000},
        ]
        groups = _group_mergeable_runs(turns)
        assert groups == [[0], [1]]

    def test_combined_length_limit(self) -> None:
        long_text = "x" * 800
        turns = [
            {"role": "p", "text": long_text, "ts_start_ms": 0, "ts_end_ms": 1000},
            {"role": "p", "text": long_text, "ts_start_ms": 1500, "ts_end_ms": 2500},
        ]
        groups = _group_mergeable_runs(turns)
        # Combined would exceed 1000 chars → split
        assert len(groups) == 2
