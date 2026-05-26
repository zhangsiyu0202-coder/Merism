"""
Spike: DeepSeek + LangChain `with_structured_output(Evaluation)` 稳定性测试

目标: 50 次活体调用, 看 LangChain 路径下 DeepSeek 结构化输出的:
- 命中率 (返回 well-formed Pydantic Evaluation)
- 内容合理性 (sufficient/missing/followup 三字段语义合理)
- 延迟 (median, p95)

如果 ≥ 47/50 well-formed → LangGraph 4 节点方案可行
如果 40-46 → 边缘, 需要调 prompt
如果 < 40 → 死路, 必须改方案
"""

from __future__ import annotations

import os
import statistics
import time
from typing import Optional

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

load_dotenv("/home/jia/merism-app/.env")

API_KEY = os.environ["MERISM_LLM_API_KEY"]
BASE_URL = os.environ["MERISM_LLM_BASE_URL"]
MODEL = os.environ["MERISM_LLM_MODEL"]


class Evaluation(BaseModel):
    """访谈追问决策模型 (从另一 AI 方案直接抄)."""

    sufficient: bool = Field(description="回答是否已经满足当前问题的目标")
    missing: list[str] = Field(default_factory=list, description="还缺哪些关键信息")
    followup: Optional[str] = Field(
        default=None, description="如果需要追问, 只给一个自然、简短的问题"
    )
    reason: str = Field(default="", description="判断理由, 供调试使用")


# 10 个测试场景: 单题 "你现在主要负责什么工作", 不同回答风格
SCENARIOS = [
    {
        "name": "direct_full",
        "answer": "我是 ToB SaaS 产品经理, 主要负责客户成功模块, 包括 onboarding 流程优化、客户健康度看板、续费预警系统这三大块, 团队 6 个人.",
        "expect_sufficient": True,
        "comment": "完整答 — 角色/职责/场景都齐",
    },
    {
        "name": "role_only",
        "answer": "产品经理.",
        "expect_sufficient": False,
        "comment": "只答了角色, 缺职责和场景",
    },
    {
        "name": "vague",
        "answer": "做产品的, 各种事情都搞.",
        "expect_sufficient": False,
        "comment": "笼统, 必须追问",
    },
    {
        "name": "off_topic",
        "answer": "今天天气真不错, 你们公司在哪儿啊?",
        "expect_sufficient": False,
        "comment": "完全跑题",
    },
    {
        "name": "refused",
        "answer": "这个不太方便说.",
        "expect_sufficient": True,
        "comment": "明确拒答, 不该再追",
    },
    {
        "name": "long_narrative",
        "answer": "其实我做这个岗位也挺有意思的, 我们公司是做企业服务的, "
        "我具体的角色叫产品运营经理, 平时主要工作就是和客户沟通收集需求, "
        "然后跟开发对齐排期, 再跟销售那边同步功能上线时间, "
        "典型一天就是早上看数据看反馈, 下午开会, 晚上写需求文档.",
        "expect_sufficient": True,
        "comment": "长答 — 角色/职责/场景全有",
    },
    {
        "name": "partial_role_no_scene",
        "answer": "我负责设计, UI 那块.",
        "expect_sufficient": False,
        "comment": "有角色和职责, 但缺典型工作场景",
    },
    {
        "name": "evasive",
        "answer": "嗯, 这个呢, 怎么说呢, 反正就是那样.",
        "expect_sufficient": False,
        "comment": "含糊, 应追问",
    },
    {
        "name": "tangent_then_answer",
        "answer": "你这问题挺大的. 简单说我是后端工程师, 主要做支付系统, "
        "对接十几个银行渠道.",
        "expect_sufficient": True,
        "comment": "先吐槽再回答, 内容齐",
    },
    {
        "name": "garbled",
        "answer": "呃啊嗯...那个...就是...",
        "expect_sufficient": False,
        "comment": "支离破碎",
    },
]


def build_prompt(answer: str) -> str:
    return f"""你是访谈流程控制器, 不是闲聊助手.

当前主问题:
先介绍一下你现在的角色, 以及你主要负责什么事情?

这题的目标:
了解受访者当前身份、职责和业务场景.

这题必须拿到的信息:
['当前角色', '主要职责', '典型工作场景']

最近访谈上下文:
无 (这是第一题)

用户刚刚的回答:
{answer}

请判断:
1. 当前回答是否已经足够支撑本题目标;
2. 如果不足, 还缺什么;
3. 如果还可以追问, 请只生成一个自然、简短、具体的追问;
4. 不要重复已经问过的问题;
5. 如果用户已经明显回答不了, 或者追问价值不大, 就判定 sufficient=true.

请以 JSON 格式返回, 包含 sufficient/missing/followup/reason 4 个字段.
"""


def main() -> None:
    method = os.environ.get("SPIKE_METHOD", "function_calling")
    print(f"=== Spike: DeepSeek + LangChain with_structured_output ===")
    print(f"Model: {MODEL}")
    print(f"Base URL: {BASE_URL}")
    print(f"Method: {method}")
    print(f"Scenarios: {len(SCENARIOS)} × 5 reps = {len(SCENARIOS) * 5} total")
    print()

    llm = ChatOpenAI(
        model=MODEL,
        api_key=API_KEY,
        base_url=BASE_URL,
        temperature=0,
    )
    evaluator = llm.with_structured_output(Evaluation, method=method)

    results = {
        "well_formed": 0,
        "malformed": 0,
        "exceptions": 0,
        "sufficient_correct": 0,
        "sufficient_wrong": 0,
        "latencies_ms": [],
        "per_scenario": {},
    }

    for scenario in SCENARIOS:
        name = scenario["name"]
        results["per_scenario"][name] = {
            "well_formed": 0,
            "sufficient_correct": 0,
            "samples": [],
        }
        print(f"--- scenario: {name} ({scenario['comment']}) ---")

        for rep in range(5):
            t0 = time.time()
            try:
                ev: Evaluation = evaluator.invoke(build_prompt(scenario["answer"]))
                latency_ms = int((time.time() - t0) * 1000)
                results["latencies_ms"].append(latency_ms)

                if not isinstance(ev, Evaluation):
                    results["malformed"] += 1
                    print(f"  rep {rep + 1}: MALFORMED type={type(ev).__name__}")
                    continue

                results["well_formed"] += 1
                results["per_scenario"][name]["well_formed"] += 1

                correct = ev.sufficient == scenario["expect_sufficient"]
                if correct:
                    results["sufficient_correct"] += 1
                    results["per_scenario"][name]["sufficient_correct"] += 1
                else:
                    results["sufficient_wrong"] += 1

                results["per_scenario"][name]["samples"].append(
                    {
                        "sufficient": ev.sufficient,
                        "followup": ev.followup,
                        "missing": ev.missing,
                        "latency_ms": latency_ms,
                    }
                )

                marker = "✓" if correct else "✗"
                followup_preview = (ev.followup or "")[:30]
                print(
                    f"  rep {rep + 1}: {marker} sufficient={ev.sufficient} "
                    f"missing={ev.missing} followup={followup_preview!r} "
                    f"({latency_ms}ms)"
                )
            except Exception as e:
                results["exceptions"] += 1
                latency_ms = int((time.time() - t0) * 1000)
                print(f"  rep {rep + 1}: EXCEPTION {type(e).__name__}: {e} ({latency_ms}ms)")
        print()

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    total = len(SCENARIOS) * 5
    print(f"Total calls:           {total}")
    print(f"Well-formed:           {results['well_formed']}/{total}")
    print(f"Malformed (wrong type):{results['malformed']}/{total}")
    print(f"Exceptions:            {results['exceptions']}/{total}")
    print(
        f"Sufficient correct:    {results['sufficient_correct']}/{results['well_formed']} "
        f"(of well-formed)"
    )

    if results["latencies_ms"]:
        ls = sorted(results["latencies_ms"])
        median = ls[len(ls) // 2]
        p95 = ls[int(len(ls) * 0.95)]
        print(f"Latency median:        {median}ms")
        print(f"Latency p95:           {p95}ms")
        print(f"Latency min/max:       {min(ls)}/{max(ls)}ms")

    print()
    print("--- Per-scenario sufficient.correct ---")
    for name, ps in results["per_scenario"].items():
        print(f"  {name:25} {ps['sufficient_correct']}/5  (well-formed {ps['well_formed']}/5)")

    print()
    print("--- VERDICT ---")
    if results["well_formed"] >= 47:
        print(f"✅ PASS: well-formed {results['well_formed']}/50 ≥ 47, LangGraph 路径可行")
    elif results["well_formed"] >= 40:
        print(
            f"⚠️  EDGE: well-formed {results['well_formed']}/50, "
            "需要 prompt 调优或重试机制"
        )
    else:
        print(f"❌ FAIL: well-formed {results['well_formed']}/50 < 40, LangGraph 路径死路")


if __name__ == "__main__":
    main()
