"""Moderator evaluation harness.

Compares the current two-call moderator against an eval-only single-call
variant on the same canned turn fixtures.
"""

from __future__ import annotations

import csv
import json
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from merism.conductor.decision_prompt import build_decision_prompt
from merism.conductor.decision_validator import ValidationResult, validate_decision
from merism.conductor.generation_prompt import build_generation_prompt
from merism.conductor.guide_cursor import dynamic_probe_config, find_question, followup_budget, next_question
from merism.conductor.prompts import ModeratorDecision, format_concept_context
from merism.conductor.state import ExecutionState

JsonDict = dict[str, object]
ChatMessages = list[dict[str, str]]

SINGLE_CALL_EVAL_SYSTEM_PROMPT = """\
You are an interview moderator. In ONE response, do both jobs:

1. Write the exact spoken reply the participant should hear next.
2. Decide the next moderator action as JSON matching the schema below.

Reply in this exact envelope:

<spoken_reply>
...spoken language only...
</spoken_reply>
<decision_json>
{ ...decision json... }
</decision_json>

Decision JSON schema:
{
  "next_action": "followup" | "move_on" | "clarify" | "close",
  "next_question_id": "<question id if move_on, else null>",
  "probe_type": "expansion" | "clarification" | "feeling" | "reasoning" | null,
  "probe_kind": "preset" | "dynamic" | null,
  "dynamic_trigger": "new_theme" | "contradiction" | "strong_emotion" | "surprise_finding" | null,
  "probe_triggered_by": "<short human reason if followup, else null>",
  "target_goal_id": "<study goal id you are steering toward, or null>",
  "off_topic": <true if participant's last message is off-topic, else false>,
  "steering_strategy": "deepen_current" | "redirect_to_goal" | "advance" | "close_now",
  "think_notes": "<1-2 sentences: what did the answer reveal? why this action?>",
  "matches_rule": <1..3 — which DECISION RULE below you followed>
}

DECISION RULES (non-negotiable):
1. Respect probe_policy:
   - "none":  NEVER followup. Always move_on (or close if guide ends).
   - "light": Only followup when the reply is vague/short/contradictory.
   - "deep":  Must followup at least once per question.
2. If probes_done >= max_probes AND probe_kind != "dynamic" → MUST move_on.
3. Dynamic probes (probe_kind="dynamic") require ALL of:
   - dynamic_probe_enabled == true
   - dynamic_trigger matches one of dynamic_probe_triggers
   - dynamic_probe_remaining > 0

SPOKEN REPLY RULES:
- Keep replies short and natural.
- If next_action=followup, ask exactly one follow-up question.
- If probe_kind="preset", prefer the supplied probe_directions.
- If probe_kind="dynamic", make the wording reflect dynamic_trigger.
- If next_action="move_on", acknowledge briefly and ask the next question.
- Output no markdown outside the required XML-like envelope.
"""

SINGLE_CALL_EVAL_USER_TEMPLATE = """\
<research_goal>
{research_goal}
</research_goal>

<current_question_state>
id:             {question_id}
text:           {question_text}
intent:         {intent}
probe_policy:   {probe_policy}
probes_done:    {probes_done}
max_probes:     {max_probes}
remaining:      {remaining}
probe_directions:        {probe_directions}
dynamic_probe_enabled:   {dynamic_probe_enabled}
dynamic_probe_remaining: {dynamic_probe_remaining}
dynamic_probe_triggers:  {dynamic_probe_triggers}
dynamic_probes_done:     {dynamic_probes_done}
</current_question_state>

<current_stimulus>
{current_stimulus}
</current_stimulus>

<concept_context>
{concept_context}
</concept_context>

<coverage_context>
{coverage_context}
</coverage_context>

<recent_turns>
{recent_turns}
</recent_turns>

<participant_latest>
{participant_latest}
</participant_latest>
"""


class ModeratorEvalExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_action: str
    expected_next_question_id: str | None = None
    expected_probe_kind: str | None = None
    expected_dynamic_trigger: str | None = None


class ModeratorEvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    research_goal: str
    guide_sections: list[JsonDict]
    moderator_state: JsonDict = Field(default_factory=dict)
    transcript: list[JsonDict] = Field(default_factory=list)
    participant_message: str
    current_stimulus: str = ""
    concept_context: JsonDict = Field(default_factory=dict)
    coverage_context: str = ""
    vision_context: str = ""
    expectation: ModeratorEvalExpectation
    notes: str = ""


class TokenUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    source: str = "estimated"


class ManualScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    naturalness: float | None = None
    goal_alignment: float | None = None
    probe_quality: float | None = None
    notes: str = ""


class ModeratorEvalResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    variant: str
    spoken_reply: str
    decision: ModeratorDecision
    validator_overridden: bool
    validator_reason: str = ""
    rule_adherent: bool
    dynamic_probe_hit: bool | None = None
    move_on_correct: bool
    first_token_latency_ms: float | None = None
    total_latency_ms: float
    token_usage: TokenUsage
    manual_score: ManualScore = Field(default_factory=ManualScore)


class ModeratorEvalSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variant: str
    cases_run: int
    rule_adherence_rate: float
    dynamic_probe_hit_rate: float | None = None
    move_on_accuracy: float
    avg_first_token_latency_ms: float | None = None
    avg_total_latency_ms: float
    avg_total_tokens: float
    avg_manual_naturalness: float | None = None
    avg_manual_goal_alignment: float | None = None
    avg_manual_probe_quality: float | None = None


class ModeratorEvalReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summaries: list[ModeratorEvalSummary]
    results: list[ModeratorEvalResult]


class TeamLike(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    id: object


@dataclass(frozen=True)
class RuntimeQuestionContext:
    state: ExecutionState
    current_question: JsonDict
    current_section: JsonDict | None
    effective_sections: list[JsonDict]


class ChatClientProtocol:
    async def complete(self, messages: ChatMessages, **overrides: object) -> object: ...

    async def stream(self, messages: ChatMessages, **overrides: object) -> object: ...


class ModeratorEvalRunner:
    def __init__(
        self,
        *,
        variant: str,
        client_factory: Callable[[UUID], Awaitable[ChatClientProtocol]],
    ) -> None:
        self.variant = variant
        self._client_factory = client_factory

    async def run_case(self, case: ModeratorEvalCase) -> ModeratorEvalResult:
        if self.variant == "two_call":
            return await self._run_two_call(case)
        if self.variant == "single_call":
            return await self._run_single_call(case)
        raise ValueError(f"Unsupported variant: {self.variant}")

    async def _run_two_call(self, case: ModeratorEvalCase) -> ModeratorEvalResult:
        context = _resolve_case_context(case)
        question_info = _question_info(context.current_question)
        dynamic_probes_done = context.state.dynamic_probes_done_for(context.state.current_question_id)
        dynamic_probe = question_info["dynamic_probe"]

        decision_messages = build_decision_prompt(
            research_goal=case.research_goal,
            question_id=question_info["id"],
            question_text=question_info["text"],
            intent=question_info["intent"],
            probe_policy=question_info["probe_policy"],
            probes_done=context.state.probes_done_for(context.state.current_question_id),
            max_probes=question_info["max_probes"],
            current_stimulus=case.current_stimulus,
            concept_context=format_concept_context(case.concept_context),
            coverage_context=case.coverage_context,
            recent_turns=_render_recent_turns(case.transcript),
            participant_latest=case.participant_message,
            probe_directions=question_info["probe_directions"],
            dynamic_probe_enabled=bool(dynamic_probe["enabled"]),
            dynamic_probe_remaining=max(0, int(dynamic_probe["max_extra_rounds"]) - dynamic_probes_done),
            dynamic_probe_triggers=list(dynamic_probe["triggers"]),
            dynamic_probes_done=dynamic_probes_done,
        )

        started = time.monotonic()
        client = await self._client_factory(uuid4())
        decision_response = await client.complete(
            messages=decision_messages,
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        decision_elapsed_ms = (time.monotonic() - started) * 1000
        raw_decision = _extract_message_content(decision_response)
        decision = ModeratorDecision.model_validate_json(raw_decision)

        validation = validate_decision(
            decision,
            question=context.current_question,
            probes_done=context.state.probes_done_for(context.state.current_question_id),
            sections=context.effective_sections,
            dynamic_probes_done=dynamic_probes_done,
        )
        final_decision = validation.decision if validation.overridden else decision

        next_question_text = ""
        if final_decision.next_action == "move_on" and final_decision.next_question_id:
            _, next_question = find_question(context.effective_sections, final_decision.next_question_id)
            if next_question is not None:
                next_question_text = str(next_question.get("text", "") or "")

        generation_messages = build_generation_prompt(
            decision_next_action=final_decision.next_action,
            decision_probe_type=final_decision.probe_type,
            decision_probe_kind=final_decision.probe_kind,
            decision_dynamic_trigger=final_decision.dynamic_trigger,
            decision_target_goal_id=final_decision.target_goal_id,
            decision_off_topic=bool(final_decision.off_topic),
            decision_steering_strategy=final_decision.steering_strategy or "advance",
            decision_think_notes=final_decision.think_notes or "",
            current_question_text=question_info["text"],
            next_question_text=next_question_text,
            target_goal_text="",
            recent_turns=_render_recent_turns(case.transcript),
            participant_latest=case.participant_message,
            probe_directions=question_info["probe_directions"],
        )

        stream_started = time.monotonic()
        first_chunk_ms: float | None = None
        generated = ""
        generation_usage = TokenUsage()
        async for chunk in client.stream(
            messages=generation_messages,
            temperature=0.5,
            max_tokens=_max_tokens_for_action(final_decision.next_action),
        ):
            if first_chunk_ms is None:
                first_chunk_ms = (time.monotonic() - started) * 1000
            generated += _extract_stream_text(chunk)
            generation_usage = _merge_usage(generation_usage, _extract_usage(chunk))
        total_latency_ms = (time.monotonic() - started) * 1000

        decision_usage = _extract_usage(decision_response)
        combined_usage = _combine_usage(
            decision_usage,
            generation_usage,
            fallback_messages=decision_messages + generation_messages,
            fallback_completion=raw_decision + generated,
        )
        if first_chunk_ms is None:
            first_chunk_ms = decision_elapsed_ms

        return _build_eval_result(
            case=case,
            variant=self.variant,
            spoken_reply=generated.strip(),
            decision=final_decision,
            validation=validation,
            first_token_latency_ms=first_chunk_ms,
            total_latency_ms=total_latency_ms,
            token_usage=combined_usage,
        )

    async def _run_single_call(self, case: ModeratorEvalCase) -> ModeratorEvalResult:
        context = _resolve_case_context(case)
        question_info = _question_info(context.current_question)
        dynamic_probes_done = context.state.dynamic_probes_done_for(context.state.current_question_id)
        dynamic_probe = question_info["dynamic_probe"]
        messages = _build_single_call_eval_prompt(
            case=case,
            question_info=question_info,
            probes_done=context.state.probes_done_for(context.state.current_question_id),
            dynamic_probes_done=dynamic_probes_done,
            dynamic_probe=dynamic_probe,
        )

        started = time.monotonic()
        client = await self._client_factory(uuid4())
        first_chunk_ms: float | None = None
        raw_stream = ""
        usage = TokenUsage()
        async for chunk in client.stream(messages=messages, temperature=0.3):
            if first_chunk_ms is None:
                first_chunk_ms = (time.monotonic() - started) * 1000
            raw_stream += _extract_stream_text(chunk)
            usage = _merge_usage(usage, _extract_usage(chunk))
        total_latency_ms = (time.monotonic() - started) * 1000

        spoken_reply, raw_decision = _parse_single_call_envelope(raw_stream)
        decision = ModeratorDecision.model_validate_json(raw_decision)
        validation = validate_decision(
            decision,
            question=context.current_question,
            probes_done=context.state.probes_done_for(context.state.current_question_id),
            sections=context.effective_sections,
            dynamic_probes_done=dynamic_probes_done,
        )
        final_decision = validation.decision if validation.overridden else decision
        combined_usage = _finalize_usage(
            usage,
            fallback_messages=messages,
            fallback_completion=raw_stream,
        )
        return _build_eval_result(
            case=case,
            variant=self.variant,
            spoken_reply=spoken_reply.strip(),
            decision=final_decision,
            validation=validation,
            first_token_latency_ms=first_chunk_ms,
            total_latency_ms=total_latency_ms,
            token_usage=combined_usage,
        )


def load_eval_cases(path: str | Path) -> list[ModeratorEvalCase]:
    raw = json.loads(Path(path).read_text())
    if not isinstance(raw, list):
        raise ValueError("Moderator eval fixture must be a JSON array")
    return [ModeratorEvalCase.model_validate(item) for item in raw]


def load_manual_scores(path: str | Path) -> dict[tuple[str, str], ManualScore]:
    rows: dict[tuple[str, str], ManualScore] = {}
    with Path(path).open(newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            key = (row["case_id"], row["variant"])
            rows[key] = ManualScore(
                naturalness=_parse_optional_float(row.get("naturalness")),
                goal_alignment=_parse_optional_float(row.get("goal_alignment")),
                probe_quality=_parse_optional_float(row.get("probe_quality")),
                notes=row.get("notes", "") or "",
            )
    return rows


def attach_manual_scores(
    results: Sequence[ModeratorEvalResult],
    manual_scores: dict[tuple[str, str], ManualScore],
) -> list[ModeratorEvalResult]:
    merged: list[ModeratorEvalResult] = []
    for result in results:
        key = (result.case_id, result.variant)
        manual = manual_scores.get(key, ManualScore())
        merged.append(result.model_copy(update={"manual_score": manual}))
    return merged


def summarize_results(results: Sequence[ModeratorEvalResult]) -> list[ModeratorEvalSummary]:
    by_variant: dict[str, list[ModeratorEvalResult]] = {}
    for result in results:
        by_variant.setdefault(result.variant, []).append(result)

    summaries: list[ModeratorEvalSummary] = []
    for variant, rows in by_variant.items():
        first_token_values = [row.first_token_latency_ms for row in rows if row.first_token_latency_ms is not None]
        dynamic_values = [row.dynamic_probe_hit for row in rows if row.dynamic_probe_hit is not None]
        naturalness = [row.manual_score.naturalness for row in rows if row.manual_score.naturalness is not None]
        goal_alignment = [row.manual_score.goal_alignment for row in rows if row.manual_score.goal_alignment is not None]
        probe_quality = [row.manual_score.probe_quality for row in rows if row.manual_score.probe_quality is not None]
        summaries.append(
            ModeratorEvalSummary(
                variant=variant,
                cases_run=len(rows),
                rule_adherence_rate=sum(1 for row in rows if row.rule_adherent) / len(rows),
                dynamic_probe_hit_rate=(
                    sum(1 for value in dynamic_values if value) / len(dynamic_values)
                    if dynamic_values
                    else None
                ),
                move_on_accuracy=sum(1 for row in rows if row.move_on_correct) / len(rows),
                avg_first_token_latency_ms=(
                    sum(first_token_values) / len(first_token_values)
                    if first_token_values
                    else None
                ),
                avg_total_latency_ms=sum(row.total_latency_ms for row in rows) / len(rows),
                avg_total_tokens=sum(row.token_usage.total_tokens for row in rows) / len(rows),
                avg_manual_naturalness=(
                    sum(naturalness) / len(naturalness) if naturalness else None
                ),
                avg_manual_goal_alignment=(
                    sum(goal_alignment) / len(goal_alignment) if goal_alignment else None
                ),
                avg_manual_probe_quality=(
                    sum(probe_quality) / len(probe_quality) if probe_quality else None
                ),
            )
        )
    return sorted(summaries, key=lambda summary: summary.variant)


def render_markdown_report(report: ModeratorEvalReport) -> str:
    lines = [
        "# Moderator Eval",
        "",
        "## Summary",
        "",
        "| Variant | Cases | Rule Adherence | Dynamic Hit | Move-on Accuracy | Avg First Token (ms) | Avg Total Latency (ms) | Avg Tokens | Manual Naturalness | Manual Goal Alignment | Manual Probe Quality |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for summary in report.summaries:
        lines.append(
            "| {variant} | {cases} | {rule:.1%} | {dynamic} | {move_on:.1%} | {first_token} | {latency:.1f} | {tokens:.1f} | {naturalness} | {goal_alignment} | {probe_quality} |".format(
                variant=summary.variant,
                cases=summary.cases_run,
                rule=summary.rule_adherence_rate,
                dynamic=_format_optional_percent(summary.dynamic_probe_hit_rate),
                move_on=summary.move_on_accuracy,
                first_token=_format_optional_number(summary.avg_first_token_latency_ms),
                latency=summary.avg_total_latency_ms,
                tokens=summary.avg_total_tokens,
                naturalness=_format_optional_number(summary.avg_manual_naturalness),
                goal_alignment=_format_optional_number(summary.avg_manual_goal_alignment),
                probe_quality=_format_optional_number(summary.avg_manual_probe_quality),
            )
        )

    lines.extend(["", "## Cases", ""])
    for result in report.results:
        lines.append(f"### {result.case_id} · {result.variant}")
        lines.append("")
        lines.append(f"- `spoken_reply`: {result.spoken_reply}")
        lines.append(f"- `next_action`: {result.decision.next_action}")
        lines.append(f"- `probe_kind`: {result.decision.probe_kind}")
        lines.append(f"- `dynamic_trigger`: {result.decision.dynamic_trigger}")
        lines.append(f"- `validator_overridden`: {result.validator_overridden}")
        lines.append(f"- `rule_adherent`: {result.rule_adherent}")
        lines.append(f"- `dynamic_probe_hit`: {result.dynamic_probe_hit}")
        lines.append(f"- `move_on_correct`: {result.move_on_correct}")
        lines.append(f"- `first_token_latency_ms`: {_format_optional_number(result.first_token_latency_ms)}")
        lines.append(f"- `total_latency_ms`: {result.total_latency_ms:.1f}")
        lines.append(
            f"- `total_tokens`: {result.token_usage.total_tokens} ({result.token_usage.source})"
        )
        if result.manual_score.notes:
            lines.append(f"- `manual_notes`: {result.manual_score.notes}")
        lines.append("")
    return "\n".join(lines)


def render_manual_scorecard(results: Sequence[ModeratorEvalResult]) -> str:
    lines = [
        "case_id,variant,naturalness,goal_alignment,probe_quality,notes",
    ]
    for result in results:
        lines.append(f"{result.case_id},{result.variant},,,,")
    return "\n".join(lines) + "\n"


async def run_eval_report(
    *,
    cases: Sequence[ModeratorEvalCase],
    variants: Sequence[str],
    client_factories: dict[str, Callable[[UUID], Awaitable[ChatClientProtocol]]],
    manual_scores: dict[tuple[str, str], ManualScore] | None = None,
) -> ModeratorEvalReport:
    results: list[ModeratorEvalResult] = []
    for variant in variants:
        runner = ModeratorEvalRunner(variant=variant, client_factory=client_factories[variant])
        for case in cases:
            results.append(await runner.run_case(case))
    if manual_scores:
        results = attach_manual_scores(results, manual_scores)
    return ModeratorEvalReport(
        summaries=summarize_results(results),
        results=results,
    )


def _resolve_case_context(case: ModeratorEvalCase) -> RuntimeQuestionContext:
    state = ExecutionState.model_validate(case.moderator_state or {})
    effective_sections = case.guide_sections
    current_section, current_question = find_question(effective_sections, state.current_question_id)
    if current_question is None:
        first_section, first_question = next_question(effective_sections, current_question_id="")
        if first_question is None:
            raise ValueError(f"Case {case.case_id} has no current or first question")
        current_section = first_section
        current_question = first_question
        state.current_section_id = str((first_section or {}).get("id", ""))
        state.current_question_id = str(first_question.get("id", ""))
    return RuntimeQuestionContext(
        state=state,
        current_question=current_question,
        current_section=current_section,
        effective_sections=effective_sections,
    )


def _question_info(question: JsonDict) -> dict[str, object]:
    question_id = str(question.get("id", "") or "")
    return {
        "id": question_id,
        "text": str(question.get("text", "") or ""),
        "intent": str(question.get("intent", "") or ""),
        "probe_policy": str(question.get("probe_policy", "light") or "light"),
        "max_probes": int(question.get("max_probes", question.get("followup_depth", 3)) or 3),
        "probe_directions": [str(item) for item in list(question.get("probe_directions", []) or [])],
        "dynamic_probe": dynamic_probe_config([{"id": "_", "questions": [question]}], question_id),
    }


def _build_single_call_eval_prompt(
    *,
    case: ModeratorEvalCase,
    question_info: dict[str, object],
    probes_done: int,
    dynamic_probes_done: int,
    dynamic_probe: dict[str, object],
) -> ChatMessages:
    max_probes = int(question_info["max_probes"])
    remaining = max(0, max_probes - probes_done)
    dynamic_probe_remaining = max(
        0,
        int(dynamic_probe["max_extra_rounds"]) - dynamic_probes_done,
    )
    user_message = SINGLE_CALL_EVAL_USER_TEMPLATE.format(
        research_goal=case.research_goal.strip() or "(not set)",
        question_id=question_info["id"],
        question_text=question_info["text"],
        intent=question_info["intent"] or "(not specified)",
        probe_policy=question_info["probe_policy"],
        probes_done=probes_done,
        max_probes=max_probes,
        remaining=remaining,
        probe_directions="; ".join(question_info["probe_directions"]) or "(none)",
        dynamic_probe_enabled=str(bool(dynamic_probe["enabled"])).lower(),
        dynamic_probe_remaining=dynamic_probe_remaining,
        dynamic_probe_triggers=", ".join(str(item) for item in list(dynamic_probe["triggers"])) or "(none)",
        dynamic_probes_done=dynamic_probes_done,
        current_stimulus=case.current_stimulus or "(none)",
        concept_context=format_concept_context(case.concept_context),
        coverage_context=case.coverage_context or "(none)",
        recent_turns=_render_recent_turns(case.transcript) or "(none — first turn)",
        participant_latest=case.participant_message,
    )
    return [
        {"role": "system", "content": SINGLE_CALL_EVAL_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]


def _render_recent_turns(transcript: Sequence[JsonDict]) -> str:
    lines: list[str] = []
    for turn in transcript[-8:]:
        role = str(turn.get("role", "") or "")
        label = "Participant" if role == "participant" else "Moderator"
        text = str(turn.get("text_clean", "") or turn.get("text", "") or "").strip()
        if text:
            lines.append(f"{label}: {text}")
    return "\n".join(lines)


def _parse_single_call_envelope(payload: str) -> tuple[str, str]:
    spoken_start = payload.find("<spoken_reply>")
    spoken_end = payload.find("</spoken_reply>")
    decision_start = payload.find("<decision_json>")
    decision_end = payload.find("</decision_json>")
    if min(spoken_start, spoken_end, decision_start, decision_end) == -1:
        raise ValueError("Single-call payload missing required envelope tags")
    spoken_reply = payload[spoken_start + len("<spoken_reply>"):spoken_end].strip()
    decision_json = payload[decision_start + len("<decision_json>"):decision_end].strip()
    return spoken_reply, decision_json


def _extract_message_content(response: object) -> str:
    if isinstance(response, dict):
        choices = response.get("choices", [])
        if isinstance(choices, list) and choices:
            message = choices[0].get("message", {})
            if isinstance(message, dict):
                return str(message.get("content", "") or "")
    choices = getattr(response, "choices", [])
    if choices:
        message = getattr(choices[0], "message", None)
        if message is not None:
            return str(getattr(message, "content", "") or "")
    raise ValueError("Unable to extract completion content")


def _extract_stream_text(chunk: object) -> str:
    if isinstance(chunk, dict):
        choices = chunk.get("choices", [])
        if isinstance(choices, list) and choices:
            delta = choices[0].get("delta", {})
            if isinstance(delta, dict):
                return str(delta.get("content", "") or "")
    choices = getattr(chunk, "choices", [])
    if choices:
        delta = getattr(choices[0], "delta", None)
        if delta is not None:
            return str(getattr(delta, "content", "") or "")
    return ""


def _extract_usage(payload: object) -> TokenUsage:
    usage_obj: object | None = None
    if isinstance(payload, dict):
        usage_obj = payload.get("usage")
    else:
        usage_obj = getattr(payload, "usage", None)
    if usage_obj is None:
        return TokenUsage()
    if isinstance(usage_obj, dict):
        prompt_tokens = int(usage_obj.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage_obj.get("completion_tokens", 0) or 0)
        total_tokens = int(usage_obj.get("total_tokens", prompt_tokens + completion_tokens) or 0)
        return TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            source="reported",
        )
    prompt_tokens = int(getattr(usage_obj, "prompt_tokens", 0) or 0)
    completion_tokens = int(getattr(usage_obj, "completion_tokens", 0) or 0)
    total_tokens = int(getattr(usage_obj, "total_tokens", prompt_tokens + completion_tokens) or 0)
    return TokenUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        source="reported",
    )


def _merge_usage(left: TokenUsage, right: TokenUsage) -> TokenUsage:
    source = left.source if left.total_tokens > 0 else right.source
    if left.total_tokens > 0 and right.total_tokens > 0 and left.source != right.source:
        source = "mixed"
    return TokenUsage(
        prompt_tokens=left.prompt_tokens + right.prompt_tokens,
        completion_tokens=left.completion_tokens + right.completion_tokens,
        total_tokens=left.total_tokens + right.total_tokens,
        source=source,
    )


def _combine_usage(
    decision_usage: TokenUsage,
    generation_usage: TokenUsage,
    *,
    fallback_messages: Sequence[dict[str, str]],
    fallback_completion: str,
) -> TokenUsage:
    combined = _merge_usage(decision_usage, generation_usage)
    if combined.total_tokens > 0:
        if decision_usage.source != generation_usage.source:
            return combined.model_copy(update={"source": "mixed"})
        return combined
    return _estimate_usage(fallback_messages, fallback_completion)


def _finalize_usage(
    usage: TokenUsage,
    *,
    fallback_messages: Sequence[dict[str, str]],
    fallback_completion: str,
) -> TokenUsage:
    if usage.total_tokens > 0:
        return usage
    return _estimate_usage(fallback_messages, fallback_completion)


def _estimate_usage(messages: Sequence[dict[str, str]], completion_text: str) -> TokenUsage:
    prompt_chars = sum(len(message.get("content", "")) for message in messages)
    completion_chars = len(completion_text)
    prompt_tokens = _estimate_tokens_from_chars(prompt_chars)
    completion_tokens = _estimate_tokens_from_chars(completion_chars)
    return TokenUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        source="estimated",
    )


def _estimate_tokens_from_chars(char_count: int) -> int:
    if char_count <= 0:
        return 0
    return max(1, (char_count + 3) // 4)


def _build_eval_result(
    *,
    case: ModeratorEvalCase,
    variant: str,
    spoken_reply: str,
    decision: ModeratorDecision,
    validation: ValidationResult,
    first_token_latency_ms: float | None,
    total_latency_ms: float,
    token_usage: TokenUsage,
) -> ModeratorEvalResult:
    expected = case.expectation
    expected_move_on = expected.expected_action == "move_on"
    actual_move_on = decision.next_action == "move_on"
    dynamic_expected = expected.expected_probe_kind == "dynamic"
    dynamic_probe_hit: bool | None = None
    if dynamic_expected or decision.probe_kind == "dynamic":
        dynamic_probe_hit = (
            decision.probe_kind == expected.expected_probe_kind
            and decision.dynamic_trigger == expected.expected_dynamic_trigger
        )
    return ModeratorEvalResult(
        case_id=case.case_id,
        variant=variant,
        spoken_reply=spoken_reply,
        decision=decision,
        validator_overridden=validation.overridden,
        validator_reason=validation.reason,
        rule_adherent=not validation.overridden,
        dynamic_probe_hit=dynamic_probe_hit,
        move_on_correct=(actual_move_on == expected_move_on),
        first_token_latency_ms=first_token_latency_ms,
        total_latency_ms=total_latency_ms,
        token_usage=token_usage,
    )


def _format_optional_number(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.1f}"


def _format_optional_percent(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.1%}"


def _max_tokens_for_action(next_action: str) -> int:
    return {
        "followup": 60,
        "clarify": 60,
        "move_on": 120,
        "close": 80,
    }.get(next_action, 80)


def _parse_optional_float(raw: str | None) -> float | None:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    return float(text)

