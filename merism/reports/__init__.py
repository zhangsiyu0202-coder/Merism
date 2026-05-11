"""Merism reports — Pydantic schemas for structured study reports.

See :mod:`merism.reports.schema` for the atom + panel + doc model hierarchy.
"""

from __future__ import annotations

from merism.reports.schema import (
    BlocksDocument,
    ChartBlock,
    ChartSpec,
    Citation,
    CustomReportAnswer,
    MetricBlock,
    QuoteBlock,
    StudyReportContent,
    TextBlock,
    validate_blocks_list,
    validate_study_report_content,
)

__all__ = [
    "BlocksDocument",
    "ChartBlock",
    "ChartSpec",
    "Citation",
    "CustomReportAnswer",
    "MetricBlock",
    "QuoteBlock",
    "StudyReportContent",
    "TextBlock",
    "validate_blocks_list",
    "validate_study_report_content",
]
