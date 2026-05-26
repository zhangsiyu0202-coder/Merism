"""Pydantic models for LLM structured output.

Pattern provenance: design.md §0 / pattern 7. Used by the v3 judge nodes
(``judge_standard`` / ``judge_deep``) via
``llm.with_structured_output(Evaluation, method="json_mode")``.

Why json_mode and not the LangChain default ``json_schema``: the spike
(see git tag ``pre-v3-removal-2026-05-23``, ``spike/spike_deepseek_structured.py``)
showed DeepSeek rejects OpenAI-strict ``response_format=json_schema``
with HTTP 400 in 50/50 calls, while ``json_mode`` succeeds 50/50 with
median latency 1.47s and p95 1.78s. The prompt must contain the literal
word ``JSON`` for DeepSeek's safety check; ``prompts.py`` enforces this.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Evaluation(BaseModel):
    """Judge node's structured verdict on a participant reply.

    Returned by both :func:`judge_standard` and :func:`judge_deep`. Fields:

    - ``sufficient``: whether the reply already responds to the question
      adequately. ``standard`` mode treats clear-enough replies as
      sufficient; ``deep`` mode demands concrete detail (different prompt;
      same schema).
    - ``followup``: a short natural-language probe to ask next, or
      ``None`` when ``sufficient=True``.
    - ``reason``: judge's explanation (debug only; not shown to participants).
    """

    model_config = ConfigDict(extra="forbid")

    sufficient: bool = Field(description="回答是否已经回应了主问")
    followup: str | None = Field(
        default=None,
        description="如果需要追问, 一个自然、简短、具体的追问问题",
    )
    reason: str = Field(default="", description="判断理由(debug 用, 不展示给受访者)")


__all__ = ["Evaluation"]
