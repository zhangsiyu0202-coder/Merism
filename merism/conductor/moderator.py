"""Single-call interview moderator runner (PRODUCT.md §5.2 / platform Req 14).

One LLM call per participant turn. Returns streaming text + a structured
``next_action`` via function calling. No macro/meso/micro layers, no
policies — the spec explicitly forbids them.

Usage::

    async for text_chunk in stream_turn(session, participant_message="Hi"):
        ...  # send to TTS + captions

    # After the stream closes, call moderator_decision(session) to read
    # the structured decision that arrived alongside the text.

The streaming protocol is deliberately thin: this function yields
``str`` chunks. Callers (SSE view, WebSocket consumer) are responsible
for wrapping them in the wire format they need.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from merism.conductor.decision_validator import validate_decision
from merism.conductor.guide_cursor import find_question, followup_budget, next_question
from merism.conductor.prompts import (
    ModeratorDecision,
    build_system_prompt,
    current_question_state,
    format_concept_context,
)
from merism.conductor.state import ExecutionState
from merism.llm_gateway.client import get_client
from merism.memai.llm import default_model, get_llm
from merism.models import InterviewSession

logger = logging.getLogger(__name__)


_TOOL_NAME = "submit_next_action"
_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": _TOOL_NAME,
        "description": (
            "Record the moderator's decision for the next turn. Required "
            "after every reply. Exactly one of followup / move_on / clarify / close."
        ),
        "parameters": ModeratorDecision.model_json_schema(),
    },
}


async def stream_turn(
    session: InterviewSession,
    *,
    participant_message: str,
    vision_context: str = "",
) -> AsyncIterator[str]:
    """Yield text chunks from one moderator LLM call.

    The LLM is asked to (a) reply to the participant in natural spoken
    language and (b) emit a function call recording the decision. The
    function call lands on ``session.moderator_state['last_decision']``
    when the stream closes.
    """
    state = ExecutionState.model_validate(session.moderator_state or {})
    guide_sections: list[dict[str, Any]] = session.guide.sections or []

    # Concept Testing 2.0: on first turn, expand any per_concept sections
    # using the study's ConceptBlocks + this session's id as the seed.
    if not state.expanded_sections:
        try:
            state.expanded_sections, state.concept_by_question_id = await _expand_if_needed(
                session, guide_sections
            )
        except Exception:  # pragma: no cover — defensive, never break the turn
            state.expanded_sections = []
            state.concept_by_question_id = {}
    # Downstream cursor code uses the expanded sections when available.
    effective_sections = state.expanded_sections or guide_sections

    # Resolve current-question / stimulus / remaining-followups context.
    current_section, current_question = find_question(
        effective_sections, state.current_question_id
    )
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

    current_question_text = (current_question or {}).get("text", "")
    current_stimulus_text = _resolve_stimulus_description(
        session, (current_question or {}).get("linked_stimulus_ids", [])
    )
    probes_done = state.probes_done_for(state.current_question_id)

    # Concept Testing 2.0: inject concept context into the system prompt
    # when the current question belongs to an expanded per_concept section.
    concept_info = state.concept_by_question_id.get(state.current_question_id) or {}
    concept_context_text = format_concept_context(concept_info)

    prompt_kwargs = current_question_state(current_question, probes_done=probes_done)
    system_prompt = build_system_prompt(
        research_goal=session.study.research_goal,
        current_stimulus=current_stimulus_text,
        vision_context=vision_context,
        concept_context=concept_context_text,
        **prompt_kwargs,
    )

    messages = _build_chat_messages(session, system_prompt, participant_message)

    text_buffer = ""
    tool_args_buffer = ""
    tool_call_seen = False

    try:
        client = await get_client("chat", team=session.study.team, trace_id=session.trace_id)
    except Exception:
        # Fallback to legacy get_llm() if no route configured or DB unavailable
        client = None

    if client is not None:
        # Gateway path: LiteLLMClient.stream() yields OpenAI-compatible chunks
        async for chunk in client.stream(
            messages=messages,
            tools=[_TOOL_SCHEMA],
            tool_choice={"type": "function", "function": {"name": _TOOL_NAME}},
        ):
            choice = chunk.choices[0] if chunk.choices else None
            if choice is None:
                continue

            delta = choice.delta
            if delta.content:
                text_buffer += delta.content
                yield delta.content

            if delta.tool_calls:
                tool_call_seen = True
                for tool_call in delta.tool_calls:
                    if tool_call.function and tool_call.function.arguments:
                        tool_args_buffer += tool_call.function.arguments
    else:
        # Legacy path: direct OpenAI client
        legacy_client = get_llm(async_=True)
        completion = await legacy_client.chat.completions.create(
            model=default_model(),
            messages=messages,
            tools=[_TOOL_SCHEMA],
            tool_choice={"type": "function", "function": {"name": _TOOL_NAME}},
            stream=True,
        )

        async for chunk in completion:
            choice = chunk.choices[0] if chunk.choices else None
            if choice is None:
                continue

            delta = choice.delta
            if delta.content:
                text_buffer += delta.content
                yield delta.content

            if delta.tool_calls:
                tool_call_seen = True
                for tool_call in delta.tool_calls:
                    if tool_call.function and tool_call.function.arguments:
                        tool_args_buffer += tool_call.function.arguments

    # Post-stream: parse the decision, mutate state, persist.
    decision = _parse_decision(tool_args_buffer) if tool_call_seen else None
    # Sprint 1: server-side enforcement of probe_policy / max_probes.
    validation = validate_decision(
        decision,
        question=current_question,
        probes_done=probes_done,
        sections=effective_sections,
    )
    decision = validation.decision if validation.overridden else decision
    _apply_decision_to_state(state, decision, effective_sections)

    session.moderator_state = state.model_dump(mode="json")
    # Attribute turns to the question + concept they addressed — lets
    # the report aggregator bucket answers by concept without guessing.
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
                "validator_overridden": validation.overridden,
                "validator_reason": validation.reason,
            }
        )
    session.decision_log = decision_log
    # Saving in the view is ideal (async-to-sync bridge); callers that want
    # to batch multiple turns can defer by calling save() themselves.
    await _asave_session(session)

    # Event-sourced log — each turn writes user_turn / model_reply /
    # decision rows so any worker can rebuild state from events alone.
    await _alog_turn_events(
        session,
        participant_message=participant_message,
        assistant_text=text_buffer,
        decision=decision,
        validator_overridden=validation.overridden,
        validator_reason=validation.reason,
        qid_at_turn=qid_at_turn,
    )

    # 6-signal closure check. If any signal fires, mark the session
    # COMPLETED now so the post_save → Celery pipeline kicks off.
    await _acheck_closure(session)


def _build_chat_messages(
    session: InterviewSession,
    system_prompt: str,
    participant_message: str,
) -> list[dict[str, Any]]:
    """Construct the OpenAI chat messages. Short transcript history included
    to give the LLM enough context without bloating every call."""
    history_tail = session.transcript[-8:] if session.transcript else []
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    for turn in history_tail:
        role = "assistant" if turn.get("role") == "agent" else "user"
        messages.append({"role": role, "content": turn.get("text", "")})
    messages.append({"role": "user", "content": participant_message})
    return messages


def _parse_decision(raw_arguments: str) -> ModeratorDecision | None:
    raw_arguments = raw_arguments.strip()
    if not raw_arguments:
        return None
    try:
        payload = json.loads(raw_arguments)
        return ModeratorDecision.model_validate(payload)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("moderator.decision.parse_failed", extra={"error": str(exc)})
        return None


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
                # Concept Testing 2.0: enqueue a stimulus_show event when
                # the cursor crosses a concept boundary so the voice /
                # SSE consumer can forward it over the wire.
                from merism.conductor.concept_plan import concept_transition_payload

                payload = concept_transition_payload(
                    state.concept_by_question_id,
                    old_qid,
                    target_id,
                )
                if payload is not None:
                    concept_id = state.concept_by_question_id.get(target_id, {}).get(
                        "concept_id"
                    )
                    if concept_id and concept_id not in state.concepts_shown:
                        state.concepts_shown.append(concept_id)
                    state.pending_stimulus_events.append(payload)
    elif decision.next_action == "close":
        state.phase = "ended"


def _resolve_stimulus_description(
    session: InterviewSession, stimulus_ids: list[str]
) -> str:
    """Return a compact description string for any stimulus shown this turn.

    Intentionally DB-free on the happy path (no stimulus IDs = cheap).
    """
    if not stimulus_ids:
        return ""
    # Lazy import to avoid circular deps.
    from asgiref.sync import sync_to_async

    from merism.models import Stimulus

    @sync_to_async
    def _load() -> str:
        parts: list[str] = []
        for s in Stimulus.objects.filter(id__in=stimulus_ids):
            parts.append(f"{s.kind}: {s.title or ''} — {s.description or ''}")
        return "\n".join(parts).strip()

    # Moderator runs in async context; this is a sync DB call wrapped.
    import asyncio

    return asyncio.get_event_loop().run_until_complete(_load())


async def _asave_session(session: InterviewSession) -> None:
    """Async-aware save — Merism runs on ASGI so we use ``asave()`` when available."""
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
    """Expand any ``per_concept`` sections in the guide using the study's
    ConceptBlocks. Returns ``([], {})`` when the guide has no per_concept
    sections (legacy single-stimulus studies).

    Concept rotation is seeded by the session id so the order is
    reproducible (useful for replay + debugging).
    """
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
        """Atomic increment of ``ConceptRotationCursor.position``.

        Returns the post-increment value (so the first session gets 1,
        not 0). Cyclic Latin-square row i uses offset ``i % N``, so
        concrete positions start from 1 — that's fine; the modulo
        inside ``order_latin_square`` makes the first session see
        offset 1, which is also balanced across participations.
        """
        ConceptRotationCursor.objects.get_or_create(block_id=block_id)
        ConceptRotationCursor.objects.filter(block_id=block_id).update(
            position=F("position") + 1
        )
        return ConceptRotationCursor.objects.get(block_id=block_id).position

    blocks = await _load_blocks()
    # Per-block seed override: latin-square blocks get the persistent
    # cursor value so ordering is balanced across the sample; fixed +
    # random blocks keep the session seed.
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
    """Append three SessionEvent rows atomically for one moderator turn.

    Per-turn events are the **authoritative** record; ``moderator_state``
    and ``decision_log`` on the session are derived caches. This lets any
    worker (voice consumer, text SSE view, test replay) reconstruct
    state from events alone.
    """
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
                    },
                    "validator_overridden": validator_overridden,
                    "validator_reason": validator_reason,
                },
            )
        )

    trace_id = getattr(session, "trace_id", None)
    await sync_to_async(append_events)(
        session, payload_events, trace_id=trace_id
    )


async def _acheck_closure(session: InterviewSession) -> None:
    """Run the 6-signal closure check after each turn. No-op if no signal fires."""
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
