"""Unit tests for concept_plan.expand_guide."""

from __future__ import annotations

from merism.conductor.concept_plan import expand_guide


def _block(block_id: str, n: int, rotation: str = "fixed") -> dict:
    return {
        "title": f"Block {block_id}",
        "rotation": rotation,
        "concepts": [
            {
                "id": f"{block_id}-c{i}",
                "stimulus_id": f"stim-{block_id}-c{i}",
                "label": f"Concept {chr(ord('A') + i)}",
                "notes": f"notes for {i}",
                "rank": i,
            }
            for i in range(n)
        ],
    }


def test_global_sections_pass_through():
    sections = [
        {"id": "warmup", "title": "Warm-up", "scope": "global", "questions": [{"id": "q1"}]},
    ]
    expanded, mapping = expand_guide(sections, {}, "seed")
    assert len(expanded) == 1
    assert expanded[0]["id"] == "warmup"
    assert mapping["q1"]["concept_id"] is None


def test_per_concept_section_expands_once_per_concept_fixed_order():
    sections = [
        {
            "id": "reactions",
            "title": "Reactions",
            "scope": "per_concept",
            "concept_block_id": "B1",
            "questions": [{"id": "q1", "text": "First impression?", "followup_depth": 1}],
        }
    ]
    blocks = {"B1": _block("B1", 3, rotation="fixed")}
    expanded, mapping = expand_guide(sections, blocks, "seed")

    assert len(expanded) == 3
    assert expanded[0]["id"] == "reactions__c0"
    assert expanded[0]["concept_id"] == "B1-c0"
    assert expanded[0]["concept_index"] == 0
    assert expanded[0]["concept_count"] == 3
    assert expanded[0]["questions"][0]["id"] == "q1__c0"
    assert expanded[0]["questions"][0]["text"] == "First impression?"

    # Concept mapping for every expanded question.
    assert mapping["q1__c0"]["concept_id"] == "B1-c0"
    assert mapping["q1__c0"]["concept_index"] == 0
    assert mapping["q1__c2"]["concept_id"] == "B1-c2"
    assert mapping["q1__c2"]["concept_index"] == 2


def test_random_rotation_is_seed_reproducible():
    sections = [
        {
            "id": "reactions",
            "title": "Reactions",
            "scope": "per_concept",
            "concept_block_id": "B1",
            "questions": [{"id": "q1"}],
        }
    ]
    blocks = {"B1": _block("B1", 4, rotation="random_per_session")}
    a, _ = expand_guide(sections, blocks, "session-42")
    b, _ = expand_guide(sections, blocks, "session-42")
    assert [s["concept_id"] for s in a] == [s["concept_id"] for s in b]


def test_missing_block_falls_back_to_global():
    sections = [
        {
            "id": "reactions",
            "title": "Reactions",
            "scope": "per_concept",
            "concept_block_id": "MISSING",
            "questions": [{"id": "q1"}],
        }
    ]
    expanded, mapping = expand_guide(sections, {}, "seed")
    assert len(expanded) == 1
    assert mapping["q1"]["concept_id"] is None


def test_mixed_sections_preserve_order():
    sections = [
        {"id": "warmup", "scope": "global", "questions": [{"id": "w1"}]},
        {
            "id": "reactions",
            "scope": "per_concept",
            "concept_block_id": "B1",
            "questions": [{"id": "q1"}],
        },
        {"id": "closing", "scope": "comparative", "questions": [{"id": "c1"}]},
    ]
    blocks = {"B1": _block("B1", 2, rotation="fixed")}
    expanded, _ = expand_guide(sections, blocks, "seed")
    assert [s["id"] for s in expanded] == [
        "warmup",
        "reactions__c0",
        "reactions__c1",
        "closing",
    ]


def test_latin_square_respects_block_seed_override():
    """With the persistent cursor providing 0, 1, 2, 3 over four
    participations, each session sees a different cyclic rotation."""
    sections = [
        {
            "id": "reactions",
            "scope": "per_concept",
            "concept_block_id": "B1",
            "questions": [{"id": "q1"}],
        }
    ]
    blocks = {"B1": _block("B1", 3, rotation="latin_square")}

    orders = []
    for cursor_pos in range(4):
        exp, _ = expand_guide(
            sections,
            blocks,
            session_seed="ignored",
            block_seed_override={"B1": str(cursor_pos)},
        )
        orders.append([s["concept_id"] for s in exp])

    # Cycle positions 0, 1, 2, 0 for 4 participations of 3 concepts.
    # Just assert order 0 differs from order 1 differs from order 2.
    assert orders[0] != orders[1]
    assert orders[1] != orders[2]
    # Order 3 = order 0 (cyclic).
    assert orders[0] == orders[3]


def test_concept_transition_payload_detects_new_concept():
    from merism.conductor.concept_plan import concept_transition_payload

    mapping = {
        "q1__c0": {
            "concept_id": "B1-c0",
            "concept_index": 0,
            "concept_count": 2,
            "block_id": "B1",
            "block_title": "Designs",
            "stimulus_id": "s-A",
            "label": "A",
            "notes": "",
        },
        "q1__c1": {
            "concept_id": "B1-c1",
            "concept_index": 1,
            "concept_count": 2,
            "block_id": "B1",
            "block_title": "Designs",
            "stimulus_id": "s-B",
            "label": "B",
            "notes": "",
        },
    }
    stimulus_lookup = {
        "s-A": {"kind": "image", "content": {"url": "a.png"}},
        "s-B": {"kind": "image", "content": {"url": "b.png"}},
    }

    payload = concept_transition_payload(mapping, "q1__c0", "q1__c1", stimulus_lookup)
    assert payload == {
        "stimulus_id": "s-B",
        "kind": "image",
        "content": {"url": "b.png"},
        "concept_index": 1,
        "concept_count": 2,
        "block_title": "Designs",
    }


def test_concept_transition_payload_returns_none_on_same_concept():
    from merism.conductor.concept_plan import concept_transition_payload

    mapping = {
        "q1__c0": {
            "concept_id": "B1-c0",
            "concept_index": 0,
            "concept_count": 2,
            "stimulus_id": "s-A",
            "block_title": "",
        },
        "q2__c0": {
            "concept_id": "B1-c0",  # same concept
            "concept_index": 0,
            "concept_count": 2,
            "stimulus_id": "s-A",
            "block_title": "",
        },
    }
    assert concept_transition_payload(mapping, "q1__c0", "q2__c0") is None


def test_concept_transition_payload_returns_none_for_global():
    from merism.conductor.concept_plan import concept_transition_payload

    mapping = {
        "warmup-q1": {"concept_id": None, "stimulus_id": None, "scope": "global"},
    }
    assert concept_transition_payload(mapping, "q1__c0", "warmup-q1") is None
