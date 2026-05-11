"""Merism MEM AI — agent layer.

Scope: Merism-native tools + three agents per PRODUCT.md §5.

Public surface:
- :class:`~merism.memai.tool.MemTool` — abstract base for all tools
- :func:`~merism.memai.llm.get_llm` — OpenAI-compatible client factory
- :mod:`~merism.memai.agents` — Outline Review + Analysis agents
"""

from __future__ import annotations

from merism.memai.agents import (
    OutlineReviewResponse,
    answer_custom_report_question,
    apply_proposed_changes,
    generate_session_insight,
    review_outline,
)
from merism.memai.llm import default_model, get_llm, reasoner_model
from merism.memai.tool import (
    MemTool,
    MemToolError,
    MemToolFatalError,
    MemToolRetryableError,
)

__all__ = [
    # tool primitives
    "MemTool",
    "MemToolError",
    "MemToolFatalError",
    "MemToolRetryableError",
    # llm
    "get_llm",
    "default_model",
    "reasoner_model",
    # agents
    "review_outline",
    "apply_proposed_changes",
    "OutlineReviewResponse",
    "generate_session_insight",
    "answer_custom_report_question",
]
