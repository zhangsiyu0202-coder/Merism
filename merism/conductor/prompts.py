"""All v3 prompt templates as module-level f-string templates.

Pattern provenance: design.md §0 / pattern 6. Google's reference keeps
``query_writer_instructions``, ``reflection_instructions``, etc. as
module-level strings; nodes import and ``.format(...)`` at call site.
We follow the same convention so prompt iteration only touches one file.

**DeepSeek json_mode constraint**: every template that drives a
``with_structured_output`` call MUST contain the literal word ``JSON``
(case-insensitive substring check at API edge). Each template ends with
a ``返回 JSON: ...`` line to satisfy this.

v3 has 2 prompt templates only (``judge_standard`` + ``judge_deep``).
"""

from __future__ import annotations

# ---- judge_standard: lenient sufficiency check + probe generation ----
JUDGE_STANDARD_PROMPT = """你是访谈流程控制器, 不是闲聊助手。

判断标准(宽松): 用户回答是否已经回应了主问 — 主要意思到位即视为 sufficient=true。

特殊规则:
- 用户表达拒答意愿("不方便说"/"不想答"/"下一题") → sufficient=true
- 用户明显答不出("不知道"/"没想过") → sufficient=true
- 跑题但顺带回应了主问 → 算回应

当前问题: {ask}
研究员的追问指引 (probe_instruction, 研究员手写, 直接采纳, 不要改写):
{probe_instruction}

最近上下文:
{transcript_tail}

用户刚才的回答:
{answer}

请判断:
1. sufficient: 用户是否回应了主问
2. followup: 不足时按 probe_instruction 给一句自然、简短、具体的追问
3. 用户明显拒答 / 答不出, 直接 sufficient=true, followup=null

返回 JSON: 形如 {{"sufficient": true, "followup": null, "reason": "..."}}
"""


# ---- judge_deep: strict sufficiency check + probe generation ----
JUDGE_DEEP_PROMPT = """你是严格的访谈流程控制器, 追求每一点都被讲透。

判断标准(严格): 用户回答必须用具体例子 / 数字 / 频率 / 影响 / 场景说清楚才算 sufficient=true。
- 提到了具体例子 / 数字 / 频率 / 影响 / 场景 = 具体, 算回应
- 只是说"有", "是", "经常" 而无细节 = 模糊, 不算

特殊规则:
- 用户明确拒答("不方便说"/"不想答") → sufficient=true(尊重意愿, 不再追)
- 用户答不出("不知道"/"没想过") → sufficient=true(避免逼问)

当前问题: {ask}
研究员的追问指引 (probe_instruction, 研究员手写, 直接采纳, 不要改写):
{probe_instruction}

最近上下文:
{transcript_tail}

用户刚才的回答:
{answer}

请判断:
1. sufficient: 严格 - 必须有具体细节
2. followup: 不足时按 probe_instruction 给 1 条精确追问 (要具体, 不要"再说说看")
3. 用户明显拒答 / 答不出, sufficient=true, followup=null

返回 JSON: 形如 {{"sufficient": false, "followup": "...", "reason": "..."}}
"""


__all__ = [
    "JUDGE_DEEP_PROMPT",
    "JUDGE_STANDARD_PROMPT",
]
