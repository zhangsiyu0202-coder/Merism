from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import UUID

import pytest

from merism.conductor.moderator_eval import (
    ManualScore,
    ModeratorEvalCase,
    ModeratorEvalRunner,
    attach_manual_scores,
    render_manual_scorecard,
    run_eval_report,
)


class _FakeUsage(SimpleNamespace):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class _FakeChunk(SimpleNamespace):
    choices: list[SimpleNamespace]
    usage: _FakeUsage | None = None


class _FakeResponse(SimpleNamespace):
    choices: list[SimpleNamespace]
    usage: _FakeUsage | None = None


class _FakeEvalClient:
    def __init__(
        self,
        *,
        complete_payloads: list[str] | None = None,
        stream_payloads: list[list[str]] | None = None,
        complete_usage: tuple[int, int, int] = (10, 5, 15),
        stream_usage: tuple[int, int, int] = (12, 8, 20),
    ) -> None:
        self._complete_payloads = list(complete_payloads or [])
        self._stream_payloads = list(stream_payloads or [])
        self._complete_usage = _FakeUsage(
            prompt_tokens=complete_usage[0],
            completion_tokens=complete_usage[1],
            total_tokens=complete_usage[2],
        )
        self._stream_usage = _FakeUsage(
            prompt_tokens=stream_usage[0],
            completion_tokens=stream_usage[1],
            total_tokens=stream_usage[2],
        )

    async def complete(self, messages, **overrides):
        payload = self._complete_payloads.pop(0)
        message = SimpleNamespace(content=payload)
        return _FakeResponse(
            choices=[SimpleNamespace(message=message)],
            usage=self._complete_usage,
        )

    async def stream(self, messages, **overrides):
        chunks = self._stream_payloads.pop(0)
        for chunk in chunks:
            yield _FakeChunk(
                choices=[SimpleNamespace(delta=SimpleNamespace(content=chunk))],
                usage=None,
            )
        yield _FakeChunk(
            choices=[SimpleNamespace(delta=SimpleNamespace(content=""))],
            usage=self._stream_usage,
        )


def _base_case(**overrides) -> ModeratorEvalCase:
    payload = {
        "case_id": "case-1",
        "research_goal": "Understand snack buying habits.",
        "guide_sections": [
            {
                "id": "s1",
                "title": "Warm-up",
                "questions": [
                    {
                        "id": "q1",
                        "text": "Tell me about your last snack purchase.",
                        "probe_policy": "light",
                        "max_probes": 2,
                        "probe_directions": ["channel", "specific example"],
                        "dynamic_probe": {
                            "enabled": True,
                            "max_extra_rounds": 1,
                            "triggers": ["new_theme", "strong_emotion"],
                        },
                    },
                    {"id": "q2", "text": "What happened next?", "probe_policy": "light", "max_probes": 2},
                ],
            }
        ],
        "moderator_state": {
            "current_section_id": "s1",
            "current_question_id": "q1",
            "phase": "active",
            "followups_used": {"q1": {"asked": 0, "budget": 2}},
            "dynamic_probes_used": {"q1": {"asked": 0, "budget": 1}},
        },
        "transcript": [{"role": "participant", "text": "I bought chips after work."}],
        "participant_message": "I also started ordering snacks with a spreadsheet budget.",
        "expectation": {
            "expected_action": "followup",
            "expected_probe_kind": "dynamic",
            "expected_dynamic_trigger": "new_theme",
        },
    }
    payload.update(overrides)
    return ModeratorEvalCase.model_validate(payload)


class TestModeratorEvalRunner:
    @pytest.mark.asyncio
    async def test_two_call_runner_computes_metrics(self):
        decision = json.dumps(
            {
                "next_action": "followup",
                "probe_type": "reasoning",
                "probe_kind": "dynamic",
                "dynamic_trigger": "new_theme",
                "probe_triggered_by": "participant introduced a new workflow",
                "target_goal_id": None,
                "off_topic": False,
                "steering_strategy": "deepen_current",
                "think_notes": "This is novel and relevant.",
                "matches_rule": 3,
            }
        )
        client = _FakeEvalClient(
            complete_payloads=[decision],
            stream_payloads=[["Can you ", "walk me through that budget system?"]],
        )

        async def _factory(_trace_id: UUID):
            return client

        runner = ModeratorEvalRunner(variant="two_call", client_factory=_factory)
        result = await runner.run_case(_base_case())

        assert result.variant == "two_call"
        assert result.rule_adherent is True
        assert result.dynamic_probe_hit is True
        assert result.move_on_correct is True
        assert result.token_usage.total_tokens == 35
        assert result.spoken_reply == "Can you walk me through that budget system?"

    @pytest.mark.asyncio
    async def test_single_call_runner_parses_envelope(self):
        envelope = [
            "<spoken_reply>Can you say more about that new budgeting workflow?</spoken_reply>",
            "<decision_json>",
            json.dumps(
                {
                    "next_action": "followup",
                    "probe_type": "reasoning",
                    "probe_kind": "dynamic",
                    "dynamic_trigger": "new_theme",
                    "probe_triggered_by": "participant introduced a new workflow",
                    "target_goal_id": None,
                    "off_topic": False,
                    "steering_strategy": "deepen_current",
                    "think_notes": "This opens a useful new topic.",
                    "matches_rule": 3,
                }
            ),
            "</decision_json>",
        ]
        client = _FakeEvalClient(stream_payloads=[envelope])

        async def _factory(_trace_id: UUID):
            return client

        runner = ModeratorEvalRunner(variant="single_call", client_factory=_factory)
        result = await runner.run_case(_base_case())

        assert result.variant == "single_call"
        assert result.dynamic_probe_hit is True
        assert result.rule_adherent is True
        assert result.spoken_reply == "Can you say more about that new budgeting workflow?"

    @pytest.mark.asyncio
    async def test_run_eval_report_summarizes_and_merges_manual_scores(self):
        two_call_client = _FakeEvalClient(
            complete_payloads=[
                json.dumps(
                    {
                        "next_action": "move_on",
                        "next_question_id": "q2",
                        "probe_type": None,
                        "probe_kind": None,
                        "dynamic_trigger": None,
                        "probe_triggered_by": None,
                        "target_goal_id": None,
                        "off_topic": False,
                        "steering_strategy": "advance",
                        "think_notes": "Enough detail already.",
                        "matches_rule": 2,
                    }
                )
            ],
            stream_payloads=[["Thanks. ", "What happened next?"]],
        )
        single_call_client = _FakeEvalClient(
            stream_payloads=[
                [
                    "<spoken_reply>Thanks. What happened next?</spoken_reply>",
                    "<decision_json>",
                    json.dumps(
                        {
                            "next_action": "move_on",
                            "next_question_id": "q2",
                            "probe_type": None,
                            "probe_kind": None,
                            "dynamic_trigger": None,
                            "probe_triggered_by": None,
                            "target_goal_id": None,
                            "off_topic": False,
                            "steering_strategy": "advance",
                            "think_notes": "Enough detail already.",
                            "matches_rule": 2,
                        }
                    ),
                    "</decision_json>",
                ]
            ]
        )

        async def _two_call_factory(_trace_id: UUID):
            return two_call_client

        async def _single_call_factory(_trace_id: UUID):
            return single_call_client

        case = _base_case(
            case_id="case-2",
            participant_message="I usually just grab whatever is nearby.",
            expectation={"expected_action": "move_on", "expected_next_question_id": "q2"},
        )
        report = await run_eval_report(
            cases=[case],
            variants=["single_call", "two_call"],
            client_factories={
                "single_call": _single_call_factory,
                "two_call": _two_call_factory,
            },
            manual_scores={
                ("case-2", "single_call"): ManualScore(
                    naturalness=4.0,
                    goal_alignment=5.0,
                    probe_quality=4.0,
                )
            },
        )

        summaries = {summary.variant: summary for summary in report.summaries}
        assert summaries["single_call"].move_on_accuracy == 1.0
        assert summaries["two_call"].move_on_accuracy == 1.0
        assert summaries["single_call"].avg_manual_goal_alignment == 5.0
        assert report.results[0].manual_score.goal_alignment == 5.0

        rows = attach_manual_scores(
            report.results,
            {("case-2", "two_call"): ManualScore(naturalness=3.0)},
        )
        assert rows[-1].manual_score.naturalness == 3.0

        csv_text = render_manual_scorecard(report.results)
        assert "case_id,variant,naturalness,goal_alignment,probe_quality,notes" in csv_text
        assert "case-2,single_call" in csv_text
