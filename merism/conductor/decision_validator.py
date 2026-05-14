"""Server-side enforcement of ``probe_policy`` / ``max_probes`` rules.

The moderator LLM receives these rules in its prompt, but the spec
requires that researcher intent is honoured *regardless* of what the
model returns. This module is the belt-and-braces validator.

Hard rules:

    Rule 1a  probe_policy == "none"   → action=probe  →  forced move_on
    Rule 1b  probe_policy == "deep"   → action=move_on AND probes_done == 0  →  forced probe
    Rule 2   probes_done >= max_probes AND NOT valid dynamic probe → forced move_on
    Rule 3   probe_kind=="dynamic" but invalid (not enabled / trigger not allowed / budget exhausted)
             → downgrade to preset if budget remains, else forced move_on

Every override is returned along with a reason so the moderator can log
it (enabling post-hoc debugging of "why did the AI jump questions?").
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from merism.conductor.guide_cursor import next_question
from merism.conductor.prompts import ModeratorDecision

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Outcome of :func:`validate_decision`.

    ``overridden=True`` means the LLM's decision was replaced; the
    caller should prefer ``decision`` over the raw LLM output.
    """

    decision: ModeratorDecision
    overridden: bool
    reason: str = ""


def validate_decision(
    decision: ModeratorDecision | None,
    *,
    question: dict[str, Any] | None,
    probes_done: int,
    sections: list[dict[str, Any]],
    dynamic_probes_done: int = 0,
) -> ValidationResult:
    """Enforce the hard probe rules (preset + dynamic).

    Pure function — doesn't touch the DB or ``ExecutionState``. Callers
    apply the returned decision via their usual ``_apply_decision_to_state``
    path. On an override we construct a fresh ``ModeratorDecision`` with
    ``matches_rule`` set to the rule number that fired.
    """
    if decision is None or question is None:
        return ValidationResult(
            decision=decision or ModeratorDecision(next_action="move_on"),
            overridden=False,
        )

    policy = question.get("probe_policy", "light")
    max_probes = int(question.get("max_probes", question.get("followup_depth", 3)))
    q_id = question.get("id", "")

    # Rule 1a — probe_policy == none forbids any follow-up.
    if policy == "none" and decision.next_action == "followup":
        next_qid = _next_qid_after(sections, q_id)
        return _override(
            decision,
            next_action="move_on",
            next_question_id=next_qid,
            probe_kind=None,
            dynamic_trigger=None,
            reason=f"probe_policy=none forbids followup on q={q_id}",
            matches_rule=1,
        )

    # Rule 1b — probe_policy == deep requires at least one probe.
    if (
        policy == "deep"
        and decision.next_action == "move_on"
        and probes_done == 0
    ):
        return _override(
            decision,
            next_action="followup",
            next_question_id=None,
            probe_type="expansion",
            probe_kind="preset",
            dynamic_trigger=None,
            probe_triggered_by="probe_policy=deep requires >=1 probe",
            reason=f"probe_policy=deep enforced on q={q_id}",
            matches_rule=1,
        )

    # Rule 2 — preset budget exhausted → move_on (unless valid dynamic probe).
    if (
        decision.next_action == "followup"
        and getattr(decision, "probe_kind", None) != "dynamic"
        and probes_done >= max_probes
    ):
        next_qid = _next_qid_after(sections, q_id)
        return _override(
            decision,
            next_action="move_on",
            next_question_id=next_qid,
            probe_kind=None,
            dynamic_trigger=None,
            reason=f"max_probes={max_probes} reached on q={q_id}",
            matches_rule=2,
        )

    # Rule 3 — dynamic probe validity check (enabled + trigger allowed + budget).
    if decision.next_action == "followup" and getattr(decision, "probe_kind", None) == "dynamic":
        dp = question.get("dynamic_probe") or {}
        dp_enabled = dp.get("enabled", False)
        dp_max = int(dp.get("max_extra_rounds", 0))
        dp_triggers = dp.get("triggers", [])
        trigger = getattr(decision, "dynamic_trigger", None)

        invalid_reason = None
        if not dp_enabled:
            invalid_reason = "dynamic_probe not enabled"
        elif not trigger:
            invalid_reason = "dynamic_trigger is required"
        elif trigger not in dp_triggers:
            invalid_reason = f"trigger={trigger} not in {dp_triggers}"
        elif dynamic_probes_done >= dp_max:
            invalid_reason = f"dynamic budget={dp_max} exhausted"

        if invalid_reason:
            if probes_done < max_probes:
                return _override(
                    decision,
                    next_action="followup",
                    next_question_id=None,
                    probe_type=decision.probe_type or "expansion",
                    probe_kind="preset",
                    dynamic_trigger=None,
                    probe_triggered_by=decision.probe_triggered_by or "downgraded from dynamic",
                    reason=f"{invalid_reason} on q={q_id}, downgraded to preset",
                    matches_rule=3,
                )
            next_qid = _next_qid_after(sections, q_id)
            return _override(
                decision,
                next_action="move_on",
                next_question_id=next_qid,
                probe_kind=None,
                dynamic_trigger=None,
                reason=f"{invalid_reason} on q={q_id} and preset exhausted",
                matches_rule=3,
            )

    # Model's decision stands.
    return ValidationResult(decision=decision, overridden=False)


def _next_qid_after(
    sections: list[dict[str, Any]], current_qid: str
) -> str | None:
    """Find the next question id after ``current_qid`` (or None at guide end)."""
    _, q = next_question(sections, current_qid)
    if q is None:
        return None
    return q.get("id")


def _override(
    original: ModeratorDecision,
    *,
    next_action: str,
    next_question_id: str | None,
    probe_type: str | None = None,
    probe_kind: str | None = None,
    dynamic_trigger: str | None = None,
    probe_triggered_by: str | None = None,
    reason: str,
    matches_rule: int,
) -> ValidationResult:
    """Construct a forced decision + log the override."""
    new = ModeratorDecision(
        next_action=next_action,  # type: ignore[arg-type]
        next_question_id=next_question_id,
        probe_type=probe_type,  # type: ignore[arg-type]
        probe_kind=probe_kind,  # type: ignore[arg-type]
        dynamic_trigger=dynamic_trigger,  # type: ignore[arg-type]
        probe_triggered_by=probe_triggered_by,
        matches_rule=matches_rule,
    )
    logger.info(
        "moderator.decision.overridden",
        extra={
            "llm_action": original.next_action,
            "forced_action": next_action,
            "reason": reason,
            "rule": matches_rule,
        },
    )
    return ValidationResult(decision=new, overridden=True, reason=reason)
