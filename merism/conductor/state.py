"""Interview conductor state.

Per PRODUCT.md §5.2 and ``merism-platform`` Req 14, the interview moderator
is a **single LLM call** per user turn. State persists between turns; one
call produces both the spoken text and the ``next_action`` function call.

Do NOT introduce macro/meso/micro layers. Do NOT add policies (coverage_steer,
engagement, off_topic). Both are explicitly forbidden by the spec (Req
14.7, Req 21.5) — revisit after 100+ real interviews.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ExecutionState(BaseModel):
    """Per-session conductor state. Persisted on
    ``InterviewSession.moderator_state``.
    """

    model_config = ConfigDict(extra="forbid")

    # ── session identity ──────────────────────────────────
    session_id: UUID = Field(default_factory=uuid4)

    # ── lifecycle ─────────────────────────────────────────
    phase: Literal["warmup", "active", "closing", "ended"] = "warmup"
    turn_count: int = 0
    started_at_epoch: float = 0.0
    # Number of post-guide exchanges still allowed before we hard-close.
    closing_rounds_remaining: int = 0

    # ── progress through the guide ────────────────────────
    current_section_id: str = ""
    current_question_id: str = ""
    # Per-question preset follow-up budget tracking.
    # {question_id: {"asked": int, "budget": int}}
    followups_used: dict[str, dict[str, int]] = Field(default_factory=dict)
    # Per-question dynamic follow-up budget tracking (Typebot-inspired
    # dual-layer probe model — see docs/specs/dual-layer-followup/design.md).
    # Researcher must opt-in per question via ``question.dynamic_probe.enabled``.
    # {question_id: {"asked": int, "budget": int}}
    dynamic_probes_used: dict[str, dict[str, int]] = Field(default_factory=dict)
    # Question IDs already answered (moved past).
    answered_question_ids: list[str] = Field(default_factory=list)

    # ── single-call output fields ─────────────────────────
    # Latest next_action decision returned by the LLM function call.
    # "followup" / "move_on" / "clarify" / "close" per PRODUCT.md §5.2.
    last_action: Literal["followup", "move_on", "clarify", "close", ""] = ""

    # ── Concept Testing 2.0 ───────────────────────────────
    # Expanded guide sections (per_concept sections unrolled once per
    # concept). The moderator uses this when non-empty, falling back
    # to ``session.guide.sections`` for legacy single-stimulus studies.
    expanded_sections: list[dict] = Field(default_factory=list)
    # ``{question_id: {"concept_id", "concept_index", "concept_count",
    # "block_id", "block_title", "stimulus_id", "label", "notes"}}``.
    # Empty for global / comparative / unknown questions.
    concept_by_question_id: dict[str, dict] = Field(default_factory=dict)
    # Concept ids we've already sent a ``stimulus_show`` for in this
    # session. Used to debounce switch messages to exactly one per
    # concept transition.
    concepts_shown: list[str] = Field(default_factory=list)
    # Pending stimulus-show events the voice pipeline / SSE consumer
    # should drain and emit. Each entry matches the shape returned by
    # :func:`merism.conductor.concept_plan.concept_transition_payload`.
    pending_stimulus_events: list[dict] = Field(default_factory=list)

    def remaining_followups(self, question_id: str) -> int:
        info = self.followups_used.get(question_id, {"asked": 0, "budget": 0})
        return max(0, info["budget"] - info["asked"])

    def probes_done_for(self, question_id: str) -> int:
        """Count of probes already asked for this question (0 if unseen).

        Alias for ``followups_used[qid].asked`` — kept semantically
        distinct so the prompt + validator code reads naturally in
        terms of "probes done" instead of "followups used".
        """
        info = self.followups_used.get(question_id, {"asked": 0, "budget": 0})
        return int(info.get("asked", 0))

    def mark_followup_used(self, question_id: str) -> None:
        info = self.followups_used.setdefault(question_id, {"asked": 0, "budget": 0})
        info["asked"] += 1

    def dynamic_probes_done_for(self, question_id: str) -> int:
        """Count of dynamic probes already asked for this question."""
        info = self.dynamic_probes_used.get(question_id, {"asked": 0, "budget": 0})
        return int(info.get("asked", 0))

    def remaining_dynamic_probes(self, question_id: str) -> int:
        """How many more dynamic probes can be fired for this question."""
        info = self.dynamic_probes_used.get(question_id, {"asked": 0, "budget": 0})
        return max(0, info["budget"] - info["asked"])

    def mark_dynamic_probe_used(self, question_id: str) -> None:
        info = self.dynamic_probes_used.setdefault(
            question_id, {"asked": 0, "budget": 0}
        )
        info["asked"] += 1

    def mark_answered(self, question_id: str) -> None:
        if question_id and question_id not in self.answered_question_ids:
            self.answered_question_ids.append(question_id)

    def enter_closing(self, rounds: int = 3) -> None:
        """Switch into closing grace and seed the remaining exchange budget."""
        self.phase = "closing"
        self.closing_rounds_remaining = max(self.closing_rounds_remaining, rounds)

    def consume_closing_round(self) -> None:
        """Consume one closing exchange if grace is active."""
        if self.phase == "closing" and self.closing_rounds_remaining > 0:
            self.closing_rounds_remaining -= 1
