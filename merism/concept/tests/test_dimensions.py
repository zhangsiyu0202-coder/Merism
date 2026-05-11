"""Unit tests for concept dimension scoring."""

from __future__ import annotations

from merism.concept.dimensions import (
    aggregate_concept_dimensions,
    score_turns,
)


def test_empty_input_returns_zero_vector():
    result = score_turns([])
    assert result == {
        "sentiment": 0.0,
        "purchase_intent": 0.0,
        "appeal": 0.0,
        "comprehension": 0.0,
    }


def test_positive_sentiment():
    result = score_turns(["这个包装很漂亮，我很喜欢"])
    assert result["sentiment"] > 0


def test_negative_sentiment():
    result = score_turns(["这个太丑了，不喜欢"])
    assert result["sentiment"] < 0


def test_purchase_intent_captured():
    result = score_turns(["我会买这个，肯定想买"])
    assert result["purchase_intent"] > 0
    assert result["purchase_intent"] <= 10.0


def test_comprehension_drops_with_confusion():
    clean = score_turns(["我觉得这个挺清楚的"])
    confused = score_turns(["我看不懂这是什么意思"])
    assert clean["comprehension"] > confused["comprehension"]


def test_aggregate_filters_by_concept_id():
    transcripts = [
        [
            {"role": "agent", "text": "A-agent ignored", "concept_id": "A"},
            {"role": "participant", "text": "我喜欢这个", "concept_id": "A"},
            {"role": "participant", "text": "B 不喜欢", "concept_id": "B"},
        ],
        [
            {"role": "participant", "text": "我会买", "concept_id": "A"},
        ],
    ]
    dims_a = aggregate_concept_dimensions(transcripts, "A")
    assert {d["name"] for d in dims_a} == {
        "sentiment",
        "purchase_intent",
        "appeal",
        "comprehension",
    }
    pi_a = next(d["value"] for d in dims_a if d["name"] == "purchase_intent")
    assert pi_a > 0


def test_aggregate_returns_empty_when_no_matching_turns():
    transcripts = [
        [{"role": "participant", "text": "somewhere", "concept_id": "OTHER"}]
    ]
    assert aggregate_concept_dimensions(transcripts, "A") == []


def test_aggregate_ignores_agent_turns():
    transcripts = [
        [{"role": "agent", "text": "agent says buy buy buy", "concept_id": "A"}]
    ]
    assert aggregate_concept_dimensions(transcripts, "A") == []
