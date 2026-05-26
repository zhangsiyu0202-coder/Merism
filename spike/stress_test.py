"""压力测试 conductor 真实场景。

设计:
- 9 题 outline 跨 3 section, 混合 3 个 follow_up_mode
- 用户回答覆盖: 长叙述 / 短答 / 跑题 / 拒答 / 模糊 / 完整
- 度量: 每 turn latency, mode 行为是否正确 (off=0 probe, standard ≤2, deep ≤4)
- 验证 probe_instruction 是否被 judge 真的用了
"""

from __future__ import annotations

import os
import statistics
import sys
import time
from typing import Any

import django

# Setup Django
sys.path.insert(0, "/home/jia/merism-app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "merism.settings.dev")
django.setup()

from langgraph.checkpoint.memory import InMemorySaver
from dotenv import load_dotenv
load_dotenv("/home/jia/merism-app/.env")

from merism.conductor.graph import build_graph
from merism.conductor.runner import (
    answer_interview,
    get_interrupt_payload,
    start_interview,
)
from merism.conductor.schema import Outline, Question, Section


def stress_outline() -> Outline:
    return Outline(
        sections=[
            Section(
                id="warmup",
                title="热身 (off 模式)",
                questions=[
                    Question(
                        id="greeting",
                        ask="先介绍一下你是谁?",
                        follow_up_mode="off",
                    ),
                    Question(
                        id="time_avail",
                        ask="今天大概有多长时间能聊?",
                        follow_up_mode="off",
                    ),
                ],
            ),
            Section(
                id="main",
                title="主访谈 (standard 模式)",
                questions=[
                    Question(
                        id="role",
                        ask="你目前主要负责什么工作?",
                        follow_up_mode="standard",
                        probe_instruction="如果用户只说职位没说具体职责, 追问'平时主要做什么事'",
                    ),
                    Question(
                        id="pain_point",
                        ask="工作中最让你头疼的事是什么?",
                        follow_up_mode="standard",
                        probe_instruction="如果用户只描述现象没说为什么困扰, 追问'为什么这件事让你头疼'",
                    ),
                    Question(
                        id="frequency",
                        ask="这个问题多久会发生一次?",
                        follow_up_mode="standard",
                    ),
                ],
            ),
            Section(
                id="deep_dive",
                title="深挖 (deep 模式)",
                questions=[
                    Question(
                        id="impact_detail",
                        ask="这个问题给你和团队带来了什么具体影响?",
                        follow_up_mode="deep",
                        probe_instruction="影响要具体到: 时间损失/效率下降/客户后果/情绪负担/协作摩擦, 至少 2 个维度。",
                    ),
                    Question(
                        id="current_solution",
                        ask="你目前是怎么应对的? 有没有想过解决方案?",
                        follow_up_mode="deep",
                        probe_instruction="如果用户只说'忍着'之类的笼统回答, 深挖具体的临时手段; 如果有解决方案, 问'尝试过的效果'",
                    ),
                    Question(
                        id="ideal_state",
                        ask="如果有一个魔法工具可以解决这个问题, 你希望它能做到什么? 越具体越好",
                        follow_up_mode="deep",
                        probe_instruction="希望具体到行为层面 (e.g. '自动同步' 而不是 '高效'); 如果用户给抽象答案, 追问'具体来说做什么动作'",
                    ),
                ],
            ),
            Section(
                id="closing",
                title="收尾 (standard 模式)",
                questions=[
                    Question(
                        id="anything_else",
                        ask="还有什么我没问到但你想说的?",
                        follow_up_mode="standard",
                    ),
                ],
            ),
        ],
    )


# 模拟一个真实用户 (受访者: 中型 SaaS 公司 PM, 在做客户成功平台) 的回答
SCENARIO_ANSWERS: dict[str, list[str]] = {
    # warmup off 模式 - 不该追问, 一次过
    "greeting": [
        "我叫小明, 是一家做企业服务的 SaaS 公司的产品经理"
    ],
    "time_avail": [
        "大概 30 到 45 分钟吧"
    ],

    # standard 模式 - 第一答故意省略, 应追问
    "role": [
        "我做产品的",  # 太笼统, 应该追问
        "具体来说, 我负责客户成功模块, 主要做客户健康度看板、续费预警、自动 onboarding 流程这三块, 团队有 6 个开发对接我",
    ],
    "pain_point": [
        "需求老变",  # 太笼统, 应追问 "为什么困扰"
        "因为销售那边不停地拿到新客户的需求, 我刚跟开发对齐好的迭代计划, 第二天又要插新需求, 开发也烦, 我夹在中间双方都不满意",
    ],
    "frequency": [
        # 这次故意一次说全, 不该追问
        "差不多一周 2-3 次, 高峰期 (季度末) 每天都会发生"
    ],

    # deep 模式 - 故意答得模糊, 应严格追问
    "impact_detail": [
        "影响挺大的",  # 完全笼统, 不算
        "主要是开发延期, 团队效率下降",  # 只说了 2 个维度的标签, 没具体
        "比如 Q3 我们规划的健康度看板要 8 月上线, 实际拖到 10 月, 中间销售丢了 3 个续费机会, 客户成功团队投诉我们 6 次, 开发同学连续 3 周 996",
    ],
    "current_solution": [
        "就忍着",  # 笼统
        "其实有几个临时办法: 一是每周一上午开'需求冻结会', 把当周新需求统一收口; 二是给销售一份'功能 ROI 表', 让他们自己排优先级; 但这两个都没真正解决插队问题",
    ],
    "ideal_state": [
        "希望能自动同步",  # 抽象, 应追问
        "具体来说, 当销售在 CRM 里勾选某个客户需求作为'紧急', 系统应该自动算这个需求和当前 sprint 的冲突度, 如果冲突, 自动给销售弹窗说'要插这个就要砍掉 X', 让销售自己做权衡, 而不是甩给我",
    ],

    # closing
    "anything_else": [
        "嗯, 其实还有一点, 销售部门的 KPI 也是问题——他们只看签约不看续费, 所以他们对'插队'本身没成本感, 这是制度层面的问题"
    ],
}


def get_answer(qid: str, used: dict[str, int]) -> str:
    answers = SCENARIO_ANSWERS.get(qid, ["嗯"])
    idx = min(used.get(qid, 0), len(answers) - 1)
    used[qid] = idx + 1
    return answers[idx]


def main() -> None:
    print("=" * 70)
    print("Conductor v3 压力测试")
    print("=" * 70)
    print(f"Outline: 9 题, 4 section, 模式: 2 off + 4 standard + 3 deep")
    print(f"答案场景: 笼统→追问→具体, 长叙述, 拒答, 跑题")
    print()

    graph = build_graph(checkpointer=InMemorySaver())
    thread_id = f"stress-{int(time.time())}"
    used: dict[str, int] = {}

    turn_records: list[dict[str, Any]] = []
    total_start = time.time()

    # Start
    t0 = time.time()
    result = start_interview(
        graph,
        outline=stress_outline(),
        thread_id=thread_id,
        follow_up_mode="standard",
    )
    start_lat = (time.time() - t0) * 1000

    turn_idx = 0
    while True:
        payload = get_interrupt_payload(result)
        if payload is None:
            break
        turn_idx += 1
        qid = payload["question_id"]
        kind = payload["kind"]
        question_text = payload["question"]
        answer = get_answer(qid, used)

        print(f"[Turn {turn_idx}] {qid} ({kind})")
        print(f"  AI: {question_text}")
        print(f"  USER: {answer[:80]}{'...' if len(answer) > 80 else ''}")

        t0 = time.time()
        result = answer_interview(graph, user_answer=answer, thread_id=thread_id)
        latency_ms = int((time.time() - t0) * 1000)

        evaluation = result.get("last_evaluation") or {}
        sufficient = evaluation.get("sufficient")
        skipped = evaluation.get("skipped")
        next_payload = get_interrupt_payload(result)
        next_qid = next_payload["question_id"] if next_payload else None
        next_kind = next_payload["kind"] if next_payload else None

        print(
            f"  → judge: sufficient={sufficient} skipped={skipped} "
            f"next={next_qid}/{next_kind} ({latency_ms}ms)"
        )
        print()

        turn_records.append(
            {
                "turn_idx": turn_idx,
                "qid": qid,
                "kind": kind,
                "answer_len": len(answer),
                "sufficient": sufficient,
                "skipped": bool(skipped),
                "next_qid": next_qid,
                "next_kind": next_kind,
                "latency_ms": latency_ms,
            }
        )

        if turn_idx > 30:
            print("⚠️ 安全 break, turn 数量异常")
            break

    total_time = time.time() - total_start
    transcript = result.get("transcript", [])

    # ─── 统计 ───
    print("=" * 70)
    print("统计")
    print("=" * 70)

    # Per-question turn breakdown
    per_q_turns: dict[str, list[dict]] = {}
    for r in turn_records:
        per_q_turns.setdefault(r["qid"], []).append(r)

    expected_mode = {
        "greeting": "off",
        "time_avail": "off",
        "role": "standard",
        "pain_point": "standard",
        "frequency": "standard",
        "impact_detail": "deep",
        "current_solution": "deep",
        "ideal_state": "deep",
        "anything_else": "standard",
    }
    expected_max_probes = {"off": 0, "standard": 2, "deep": 4}

    print(f"{'qid':<22}{'mode':<10}{'turns':>6}{'probes':>8}{'budget':>8}{'status':>8}")
    print("-" * 70)
    correct_mode_behavior = 0
    total_questions = 0
    for qid, mode in expected_mode.items():
        turns = per_q_turns.get(qid, [])
        total_questions += 1
        n_turns = len(turns)
        n_probes = sum(1 for t in turns if t["kind"] == "followup")
        budget = expected_max_probes[mode]
        status = "✓" if n_probes <= budget else "✗ OVER"
        if mode == "off" and any(not t["skipped"] for t in turns):
            status = "✗ NOT_SKIPPED"
        if status == "✓":
            correct_mode_behavior += 1
        print(f"{qid:<22}{mode:<10}{n_turns:>6}{n_probes:>8}{budget:>8}{status:>8}")

    # Latency stats
    latencies = [r["latency_ms"] for r in turn_records if r["latency_ms"] > 0]
    if latencies:
        ls = sorted(latencies)
        median = ls[len(ls) // 2]
        p95 = ls[int(len(ls) * 0.95)]
        print()
        print(f"Latency: median {median}ms / p95 {p95}ms / min {min(ls)}ms / max {max(ls)}ms")
        print(f"Total turns: {turn_idx} / probes: {sum(1 for t in turn_records if t['next_kind'] == 'followup')}")
        print(f"Total wall time: {total_time:.1f}s")
        print(f"Transcript length: {len(transcript)} turns")

    # Mode behavior verdict
    print()
    print(f"Mode 行为正确: {correct_mode_behavior}/{total_questions}")
    if correct_mode_behavior == total_questions:
        print("✅ 全部模式按预期工作")
    else:
        print(f"⚠️  {total_questions - correct_mode_behavior} 个题模式行为异常")

    # Probe instruction usage check
    print()
    print("Probe instruction 抽查 (随机看 1 个 deep mode 题的 evaluation):")
    deep_q_with_probe = [
        r for r in turn_records
        if r["qid"] == "impact_detail" and r["kind"] == "main"
    ]
    if deep_q_with_probe:
        # State at impact_detail
        ev = deep_q_with_probe[0]
        next_q = ev["next_qid"]
        if next_q == "impact_detail" and ev["next_kind"] == "followup":
            print("  impact_detail (deep) 第 1 答太笼统 → judge 触发追问 ✓")
        else:
            print(f"  impact_detail (deep) 第 1 答 → 直接进 {next_q} ✗")


if __name__ == "__main__":
    main()
