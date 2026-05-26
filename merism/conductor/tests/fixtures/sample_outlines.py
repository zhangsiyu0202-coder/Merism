"""Shared outline fixtures used across node + graph tests."""

from __future__ import annotations

from merism.conductor.schema import Outline, Question, Section


def outline_3q_basic(*, follow_up_mode: str = "standard") -> Outline:
    """3 questions across 2 sections.

    All questions use the same ``follow_up_mode`` (default ``standard``);
    pass ``follow_up_mode="off"`` to drive the judge_off path.
    """
    return Outline(
        sections=[
            Section(
                id="background",
                title="Background",
                questions=[
                    Question(
                        id="role_context",
                        ask="先介绍一下你现在的角色?",
                        follow_up_mode=follow_up_mode,  # type: ignore[arg-type]
                    ),
                    Question(
                        id="current_problem",
                        ask="你最头疼的问题是什么?",
                        follow_up_mode=follow_up_mode,  # type: ignore[arg-type]
                    ),
                ],
            ),
            Section(
                id="workflow",
                title="Workflow",
                questions=[
                    Question(
                        id="current_process",
                        ask="你现在怎么处理这个问题?",
                        follow_up_mode=follow_up_mode,  # type: ignore[arg-type]
                    ),
                ],
            ),
        ],
    )


def outline_with_probe_instruction() -> Outline:
    """1 question with probe_instruction set."""
    return Outline(
        sections=[
            Section(
                id="s1",
                title="Section 1",
                questions=[
                    Question(
                        id="q1",
                        ask="你最头疼什么?",
                        follow_up_mode="standard",
                        probe_instruction="如果用户没说频率, 问'多久一次'; 没说影响, 问'对工作有什么妨碍'",
                    ),
                ],
            ),
        ],
    )


__all__ = ["outline_3q_basic", "outline_with_probe_instruction"]
