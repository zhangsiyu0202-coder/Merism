"""Live LLM end-to-end smoke test against DeepSeek.

Auto-skipped when ``MERISM_LLM_API_KEY`` is unset (the
``merism_llm_live`` marker handles this via pytest collection).

Acceptance per requirements.md Req 31:
- Run a 5-question outline in ``standard`` mode end-to-end
- Final report non-empty
- Transcript length 5-15 turns (5 mains + up to 10 probes)
- No exceptions raised
- Each turn's evaluator response was well-formed (json_mode worked)
"""

from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from merism.conductor.graph import build_graph
from merism.conductor.runner import (
    answer_interview,
    get_interrupt_payload,
    start_interview,
)
from merism.conductor.schema import Outline, Question, Section

pytestmark = [
    pytest.mark.merism_llm_live,
    pytest.mark.merism_slow,
]


def _live_outline() -> Outline:
    """5 questions, 2 sections, with probe_instruction on 2 questions."""
    return Outline(
        sections=[
            Section(
                id="background",
                title="Background",
                questions=[
                    Question(
                        id="role",
                        ask="先简单介绍一下你现在的工作角色",
                        follow_up_mode="standard",
                    ),
                    Question(
                        id="problem",
                        ask="你最近在工作中最头疼的问题是什么?",
                        follow_up_mode="standard",
                        probe_instruction="如果用户没说影响, 问'对你工作有什么妨碍'",
                    ),
                ],
            ),
            Section(
                id="workflow",
                title="Workflow",
                questions=[
                    Question(
                        id="process",
                        ask="目前你怎么处理这件事?可以说说步骤",
                        follow_up_mode="standard",
                        probe_instruction="如果步骤模糊, 问具体先做什么再做什么",
                    ),
                    Question(
                        id="tools",
                        ask="你用什么工具?",
                        follow_up_mode="standard",
                    ),
                    Question(
                        id="wishlist",
                        ask="如果有一个魔法按钮可以解决, 你最希望它做什么?",
                        follow_up_mode="standard",
                    ),
                ],
            ),
        ],
    )


# Realistic-ish answers for a fictional product manager
_LIVE_ANSWERS: dict[str, list[str]] = {
    "role": ["我是产品经理"],
    "problem": [
        "需求老变",
        "影响是开发延期, 上线时间一推再推, 客户也很不满",
    ],
    "process": [
        "先开会对齐, 然后写需求文档, 再跟开发评估排期",
        "具体来说先跟销售收集客户反馈, 然后内部讨论优先级, 最后写PRD给开发",
    ],
    "tools": ["Jira 跟 Notion 居多"],
    "wishlist": ["希望能自动同步需求变更到所有协作方"],
}


def _next_answer_for(question_id: str, used_count: dict[str, int]) -> str:
    """Pick the next prepared answer for a question (cycling through probes)."""
    answers = _LIVE_ANSWERS.get(question_id, ["嗯"])
    idx = min(used_count.get(question_id, 0), len(answers) - 1)
    used_count[question_id] = idx + 1
    return answers[idx]


class TestLiveSmoke:
    def test_full_outline_completes_without_exceptions(self) -> None:
        graph = build_graph(checkpointer=InMemorySaver())
        thread_id = "live-smoke-001"
        result = start_interview(
            graph,
            outline=_live_outline(),
            thread_id=thread_id,
            follow_up_mode="standard",
        )

        used: dict[str, int] = {}
        seen_questions: list[tuple[str, str]] = []
        max_turns = 20  # safety bound

        for _ in range(max_turns):
            payload = get_interrupt_payload(result)
            if payload is None:
                break
            seen_questions.append((payload["question_id"], payload["kind"]))
            answer = _next_answer_for(payload["question_id"], used)
            result = answer_interview(graph, user_answer=answer, thread_id=thread_id)

        assert get_interrupt_payload(result) is None, "graph did not complete"

        # All 5 main questions must have been asked
        main_qids = {qid for qid, kind in seen_questions if kind == "main"}
        assert main_qids == {"role", "problem", "process", "tools", "wishlist"}, (
            f"missing main questions in transcript: {seen_questions}"
        )

        # Graph reached END (no finalize node in v3; report is produced
        # asynchronously by post_session pipeline).
        assert result.get("done") is True, "graph did not reach done state"

        # No fatal error recorded
        assert result.get("last_error") is None, f"last_error set: {result.get('last_error')}"

        # Transcript length sanity (between 5 mains and 5 mains + 7 probes)
        transcript = result.get("transcript", [])
        assert 5 <= len(transcript) <= 15, f"transcript out of bounds: {len(transcript)} turns"

        # Print summary so -s captures it
        print("\n=== Live smoke summary ===")
        print(f"Questions asked: {len(seen_questions)}")
        print(f"Main: {sum(1 for _, k in seen_questions if k == 'main')}")
        print(f"Followup: {sum(1 for _, k in seen_questions if k == 'followup')}")
        print(f"Transcript turns: {len(transcript)}")
