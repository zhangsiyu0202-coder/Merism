"""2-node voice moderator: coverage_steer (decide) → generate (stream).

Push-to-talk mode gives us ~1s latency budget before the first TTS
chunk, so we can afford a short awaited decision call BEFORE streaming
the reply. This makes decision-making a first-class, structured step
instead of a tool_call hidden inside a streaming reply.

Flow:

    participant sends message
        │
        ▼
    resolve execution state + guide cursor + coverage gaps
        │
        ▼
    ┌───────────────────────────────────┐
    │ coverage_steer (non-streaming)    │ ~400-800ms
    │ → ModeratorDecision               │
    └───────────────────────────────────┘
        │
        ▼
    ┌───────────────────────────────────┐
    │ generate (streaming)              │ ~300-500ms first token
    │ → yields str chunks to TTS        │
    └───────────────────────────────────┘
        │
        ▼
    post-stream persistence (unchanged)

No fallback: if either phase errors out, ``stream_turn`` propagates the
exception. SSE/voice consumers already handle errors via the wire format
they use.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from merism.conductor.decision_prompt import build_decision_prompt
from merism.conductor.decision_validator import validate_decision
from merism.conductor.generation_prompt import build_generation_prompt
from merism.conductor.guide_cursor import find_question, followup_budget, next_question
from merism.conductor.prompts import ModeratorDecision, format_concept_context
from merism.conductor.state import ExecutionState
from merism.llm_gateway.client import get_client
from merism.models import InterviewSession

logger = logging.getLogger(__name__)


async def stream_turn(
    session: InterviewSession,
    *,
    participant_message: str,
    vision_context: str = "",
) -> AsyncIterator[str]:
    """Run one moderator turn.

    Yields streamed text chunks from the generate phase. The structured
    decision lands in ``session.decision_log`` + ``session.moderator_state``
    after the stream closes.

    Signature + semantics unchanged from the previous single-call
    implementation; internally it's now a 2-node pipeline.
    """
    state, current_question, current_section, effective_sections = await _resolve_state(session)
    probes_done = state.probes_done_for(state.current_question_id)
    current_question_text = (current_question or {}).get("text", "")
    current_stimulus_text = _resolve_stimulus_description(
        session, (current_question or {}).get("linked_stimulus_ids", [])
    )
    concept_info = state.concept_by_question_id.get(state.current_question_id) or {}
    concept_context_text = format_concept_context(concept_info)

    # Coverage context (gap list) — best-effort
    try:
        from merism.conductor.adaptive_probing import build_coverage_context
        coverage_context_text = await build_coverage_context(session.study_id)
    except Exception:
        coverage_context_text = ""

    recent_turns_text = _format_recent_turns(session, limit=8)

    # ── Node 1: coverage_steer — await a structured decision ──
    qinfo = _question_info(current_question)
    decision = await _coverage_steer_node(
        session=session,
        research_goal=session.study.research_goal or "",
        question_id=qinfo["id"],
        question_text=qinfo["text"],
        intent=qinfo["intent"],
        probe_policy=qinfo["probe_policy"],
        probes_done=probes_done,
        max_probes=qinfo["max_probes"],
        current_stimulus=current_stimulus_text,
        concept_context=concept_context_text,
        coverage_context=coverage_context_text,
        recent_turns=recent_turns_text,
        participant_message=participant_message,
    )

    # Server-side enforcement (probe_policy caps, etc)
    validation = validate_decision(
        decision,
        question=current_question,
        probes_done=probes_done,
        sections=effective_sections,
    )
    decision = validation.decision if validation.overridden else decision

    # Resolve text for the (possibly next) question + target goal — used
    # by the generation prompt
    next_q_text = ""
    if decision and decision.next_action == "move_on" and decision.next_question_id:
        _, next_q = find_question(effective_sections, decision.next_question_id)
        if next_q:
            next_q_text = next_q.get("text", "") or ""

    target_goal_text = ""
    if decision and decision.target_goal_id:
        target_goal_text = await _resolve_goal_text(session.study_id, decision.target_goal_id)

    # ── Node 2: generate — stream the spoken reply ──
    text_buffer = ""
    async for chunk in _generate_node(
        session=session,
        decision=decision,
        current_question_text=current_question_text,
        next_question_text=next_q_text,
        target_goal_text=target_goal_text,
        recent_turns=recent_turns_text,
        participant_message=participant_message,
    ):
        text_buffer += chunk
        yield chunk

    # ── Post-stream: same persistence as before ──
    _apply_decision_to_state(state, decision, effective_sections)
    session.moderator_state = state.model_dump(mode="json")

    qid_at_turn = state.current_question_id
    concept_info = state.concept_by_question_id.get(qid_at_turn) or {}
    concept_id_at_turn = concept_info.get("concept_id")
    transcript = list(session.transcript or [])
    transcript.append(
        {
            "role": "participant",
            "text": participant_message,
            "question_id": qid_at_turn,
            "concept_id": concept_id_at_turn,
        }
    )
    transcript.append(
        {
            "role": "agent",
            "text": text_buffer,
            "question_id": qid_at_turn,
            "concept_id": concept_id_at_turn,
        }
    )
    session.transcript = transcript

    decision_log = list(session.decision_log or [])
    if decision is not None:
        decision_log.append(
            {
                "turn": state.turn_count,
                "next_action": decision.next_action,
                "next_question_id": decision.next_question_id,
                "probe_type": decision.probe_type,
                "probe_triggered_by": decision.probe_triggered_by,
                "matches_rule": decision.matches_rule,
                "think_notes": decision.think_notes,
                "target_goal_id": decision.target_goal_id,
                "off_topic": decision.off_topic,
                "steering_strategy": decision.steering_strategy,
                "validator_overridden": validation.overridden,
                "validator_reason": validation.reason,
            }
        )
    session.decision_log = decision_log
    await _asave_session(session)

    await _alog_turn_events(
        session,
        participant_message=participant_message,
        assistant_text=text_buffer,
        decision=decision,
        validator_overridden=validation.overridden,
        validator_reason=validation.reason,
        qid_at_turn=qid_at_turn,
    )

    await _acheck_closure(session)


# ── Node 1: coverage_steer ─────────────────────────────────


async def _coverage_steer_node(
    *,
    session: InterviewSession,
    research_goal: str,
    question_id: str,
    question_text: str,
    intent: str,
    probe_policy: str,
    probes_done: int,
    max_probes: int,
    current_stimulus: str,
    concept_context: str,
    coverage_context: str,
    recent_turns: str,
    participant_message: str,
) -> ModeratorDecision | None:
    """Call the LLM gateway to produce a structured decision. Awaited."""
    messages = build_decision_prompt(
        research_goal=research_goal,
        question_id=question_id,
        question_text=question_text,
        intent=intent,
        probe_policy=probe_policy,
        probes_done=probes_done,
        max_probes=max_probes,
        current_stimulus=current_stimulus,
        concept_context=concept_context,
        coverage_context=coverage_context,
        recent_turns=recent_turns,
        participant_latest=participant_message,
    )
    try:
        client = await get_client("chat", team=session.study.team, trace_id=session.trace_id)
        response = await client.complete(
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        raw = response.choices[0].message.content or "{}"
    except Exception:
        logger.exception("moderator.coverage_steer.llm_failed")
        return None

    try:
        payload = json.loads(raw)
        return ModeratorDecision.model_validate(payload)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("moderator.coverage_steer.parse_failed", extra={"error": str(exc), "raw": raw[:200]})
        return None


# ── Node 2: generate ────────────────────────────────────────


async def _generate_node(
    *,
    session: InterviewSession,
    decision: ModeratorDecision | None,
    current_question_text: str,
    next_question_text: str,
    target_goal_text: str,
    recent_turns: str,
    participant_message: str,
) -> AsyncIterator[str]:
    """Stream the spoken reply, informed by the upstream decision."""
    # If decision failed entirely, fall back to a safe acknowledgement
    # (not an LLM fallback — a one-liner so the session isn't stuck silent)
    if decision is None:
        for token in "Got it. ".split():
            yield token + " "
        return

    messages = build_generation_prompt(
        decision_next_action=decision.next_action,
        decision_probe_type=decision.probe_type,
        decision_target_goal_id=decision.target_goal_id,
        decision_off_topic=decision.off_topic or False,
        decision_steering_strategy=decision.steering_strategy or "advance",
        decision_think_notes=decision.think_notes or "",
        current_question_text=current_question_text,
        next_question_text=next_question_text,
        target_goal_text=target_goal_text,
        recent_turns=recent_turns,
        participant_latest=participant_message,
    )

    try:
        client = await get_client("chat", team=session.study.team, trace_id=session.trace_id)
        async for chunk in client.stream(messages=messages, temperature=0.5):
            choice = chunk.choices[0] if chunk.choices else None
            if choice is None:
                continue
            delta = choice.delta
            if delta.content:
                yield delta.content
    except Exception:
        logger.exception("moderator.generate.llm_failed")
        # Emit a safe acknowledgement so the session doesn't silently freeze
        yield "I see. "


# ── State resolution helpers (extracted from the old single-call) ──


async def _resolve_state(
    session: InterviewSession,
) -> tuple[ExecutionState, dict[str, Any] | None, dict[str, Any] | None, list[dict[str, Any]]]:
    """Load + expand state, resolve current question + section."""
    state = ExecutionState.model_validate(session.moderator_state or {})
    guide_sections: list[dict[str, Any]] = session.guide.sections or []

    if not state.expanded_sections:
        try:
            state.expanded_sections, state.concept_by_question_id = await _expand_if_needed(
                session, guide_sections
            )
        except Exception:
            state.expanded_sections = []
            state.concept_by_question_id = {}
    effective_sections = state.expanded_sections or guide_sections

    current_section, current_question = find_question(effective_sections, state.current_question_id)
    if current_question is None:
        first_section, first_q = next_question(effective_sections, current_question_id="")
        if first_q is not None:
            current_section = first_section
            current_question = first_q
            state.current_section_id = (first_section or {}).get("id", "")
            state.current_question_id = first_q.get("id", "")
            state.followups_used[first_q["id"]] = {
                "asked": 0,
                "budget": int(first_q.get("followup_depth", 0)),
            }

    return state, current_question, current_section, effective_sections


def _question_info(q: dict[str, Any] | None) -> dict[str, Any]:
    if q is None:
        return {
            "id": "",
            "text": "",
            "intent": "",
            "probe_policy": "light",
            "max_probes": 0,
        }
    return {
        "id": q.get("id", ""),
        "text": q.get("text", ""),
        "intent": q.get("intent", ""),
        "probe_policy": q.get("probe_policy", "light"),
        "max_probes": int(q.get("max_probes", q.get("followup_depth", 3))),
    }


def _format_recent_turns(session: InterviewSession, *, limit: int = 8) -> str:
    """Render the last N transcript turns as plain text for the decision prompt."""
    history = (session.transcript or [])[-limit:]
    if not history:
        return ""
    lines = []
    for turn in history:
        role = turn.get("role", "")
        prefix = "Participant" if role == "participant" else "Moderator"
        text = (turn.get("text_clean") or turn.get("text") or "").strip()
        if text:
            lines.append(f"{prefix}: {text}")
    return "\n".join(lines)


async def _resolve_goal_text(study_id: Any, goal_id: str) -> str:
    """Look up StudyGoal.text by id. Returns '' on miss."""
    from asgiref.sync import sync_to_async

    from merism.models import StudyGoal

    @sync_to_async
    def _fetch() -> str:
        try:
            return StudyGoal.objects.get(id=goal_id, study_id=study_id).text
        except StudyGoal.DoesNotExist:
            return ""
        except Exception:
            return ""

    return await _fetch()


# ── State application, save, events (kept from single-call impl) ──


def _apply_decision_to_state(
    state: ExecutionState,
    decision: ModeratorDecision | None,
    sections: list[dict[str, Any]],
) -> None:
    state.turn_count += 1
    if decision is None:
        return
    state.last_action = decision.next_action

    if decision.next_action == "followup":
        state.mark_followup_used(state.current_question_id)
    elif decision.next_action == "move_on":
        state.mark_answered(state.current_question_id)
        target_id = decision.next_question_id
        if target_id:
            section, question = find_question(sections, target_id)
            if question is not None:
                old_qid = state.current_question_id
                state.current_section_id = (section or {}).get("id", "")
                state.current_question_id = target_id
                state.followups_used[target_id] = {
                    "asked": 0,
                    "budget": followup_budget(sections, target_id),
                }
                from merism.conductor.concept_plan import concept_transition_payload

                payload = concept_transition_payload(
                    state.concept_by_question_id,
                    old_qid,
                    target_id,
                )
                if payload is not None:
                    concept_id = state.concept_by_question_id.get(target_id, {}).get("concept_id")
                    if concept_id and concept_id not in state.concepts_shown:
                        state.concepts_shown.append(concept_id)
                    state.pending_stimulus_events.append(payload)
    elif decision.next_action == "close":
        state.phase = "ended"


def _resolve_stimulus_description(
    session: InterviewSession, stimulus_ids: list[str]
) -> str:
    if not stimulus_ids:
        return ""
    from asgiref.sync import sync_to_async

    from merism.models import Stimulus

    @sync_to_async
    def _load() -> str:
        parts: list[str] = []
        for s in Stimulus.objects.filter(id__in=stimulus_ids):
            parts.append(f"{s.kind}: {s.title or ''} — {s.description or ''}")
        return "\n".join(parts).strip()

    import asyncio

    return asyncio.get_event_loop().run_until_complete(_load())


async def _asave_session(session: InterviewSession) -> None:
    asave = getattr(session, "asave", None)
    if callable(asave):
        await asave(
            update_fields=[
                "moderator_state",
                "transcript",
                "decision_log",
                "updated_at",
            ]
        )
    else:  # pragma: no cover
        from asgiref.sync import sync_to_async

        await sync_to_async(session.save)(
            update_fields=[
                "moderator_state",
                "transcript",
                "decision_log",
                "updated_at",
            ]
        )


async def _expand_if_needed(
    session: InterviewSession,
    raw_sections: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    if not any(s.get("scope") == "per_concept" for s in raw_sections):
        return [], {}

    from asgiref.sync import sync_to_async
    from django.db.models import F

    from merism.conductor.concept_plan import expand_guide
    from merism.models import ConceptBlock, ConceptRotationCursor

    @sync_to_async
    def _load_blocks() -> dict[str, dict[str, Any]]:
        qs = ConceptBlock.objects.filter(study=session.study).prefetch_related(
            "concepts__stimulus"
        )
        result: dict[str, dict[str, Any]] = {}
        for block in qs:
            result[str(block.id)] = {
                "title": block.title,
                "rotation": block.rotation,
                "concepts": [
                    {
                        "id": str(c.id),
                        "stimulus_id": str(c.stimulus_id),
                        "label": c.label,
                        "notes": c.notes,
                        "rank": c.rank,
                    }
                    for c in block.concepts.all()
                ],
            }
        return result

    @sync_to_async
    def _advance_cursor(block_id: str) -> int:
        ConceptRotationCursor.objects.get_or_create(block_id=block_id)
        ConceptRotationCursor.objects.filter(block_id=block_id).update(
            position=F("position") + 1
        )
        return ConceptRotationCursor.objects.get(block_id=block_id).position

    blocks = await _load_blocks()
    overrides: dict[str, str] = {}
    for block_id, block in blocks.items():
        if block.get("rotation") == "latin_square":
            overrides[block_id] = str(await _advance_cursor(block_id))
    return expand_guide(raw_sections, blocks, str(session.id), overrides)


async def _alog_turn_events(
    session: InterviewSession,
    *,
    participant_message: str,
    assistant_text: str,
    decision,
    validator_overridden: bool,
    validator_reason,
    qid_at_turn: str,
) -> None:
    from asgiref.sync import sync_to_async

    from merism.conductor.event_log import append_events

    payload_events = [
        ("user_turn", {"text": participant_message, "question_id": qid_at_turn}),
        ("model_reply", {"text": assistant_text, "question_id": qid_at_turn}),
    ]
    if decision is not None:
        payload_events.append(
            (
                "decision",
                {
                    "decision": {
                        "next_action": decision.next_action,
                        "next_question_id": decision.next_question_id,
                        "probe_type": decision.probe_type,
                        "matches_rule": decision.matches_rule,
                        "think_notes": decision.think_notes,
                        "target_goal_id": decision.target_goal_id,
                        "off_topic": decision.off_topic,
                        "steering_strategy": decision.steering_strategy,
                    },
                    "validator_overridden": validator_overridden,
                    "validator_reason": validator_reason,
                },
            )
        )

    trace_id = getattr(session, "trace_id", None)
    await sync_to_async(append_events)(session, payload_events, trace_id=trace_id)


async def _acheck_closure(session: InterviewSession) -> None:
    from asgiref.sync import sync_to_async

    from merism.conductor.closure import check_completion, complete_session

    @sync_to_async
    def _check_and_complete() -> None:
        fresh = type(session).objects.select_related("study", "participation").get(id=session.id)
        signal = check_completion(fresh)
        if signal is not None:
            complete_session(fresh, signal)

    try:
        await _check_and_complete()
    except Exception:
        logger.exception("moderator.closure_check_failed")
