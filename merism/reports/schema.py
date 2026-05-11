"""Merism report schemas (Pydantic v2).

Two layers:

1. **Block atoms** — ``TextBlock``, ``QuoteBlock``, ``MetricBlock``,
   ``ChartBlock``. These are the low-level primitives that make up a panel.
2. **Panel / document** — ``StudyReportContent`` (the 4-panel shape per
   PRODUCT.md §4 / ``merism-platform`` Req 17) wraps lists of block atoms
   into ``exec_summary`` / ``quant_panel`` / ``qual_panel`` /
   ``insight_nuggets``.

Also exposes ``ChartSpec`` — the shape used by Custom Report Q&A and the
charts field of StudyReport (independent of the block-union representation).

Usage::

    >>> from merism.reports.schema import StudyReportContent, validate_blocks_list
    >>> blocks = validate_blocks_list([{"type": "text", "body": "Hello"}])
    >>> blocks
    [{'type': 'text', 'body': 'Hello'}]
    >>> content = StudyReportContent(
    ...     exec_summary="47 participants, 3 themes surfaced.",
    ...     quant_panel=[{"type": "metric", "label": "NPS", "value": 42, "unit": None}],
    ...     qual_panel=[{"type": "quote", "body": "Pricing feels steep.", "source": "Alice"}],
    ...     insight_nuggets=[{"type": "metric", "label": "Price concerns", "value": 18, "unit": "mentions"}],
    ... )
    >>> content.exec_summary
    '47 participants, 3 themes surfaced.'
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ── Block atoms ─────────────────────────────────────────────


class TextBlock(BaseModel):
    """Plain text block for narrative sections."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["text"]
    body: str = Field(..., min_length=1, description="Markdown body text.")


class QuoteBlock(BaseModel):
    """Highlighted participant quote with attribution."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["quote"]
    body: str = Field(..., min_length=1, description="Quoted participant text.")
    source: str = Field(..., min_length=1, description="Attribution (e.g. 'Participant A').")
    # Optional timestamp for click-to-jump-in-transcript behaviour.
    session_id: str | None = Field(default=None)
    ts: float | None = Field(
        default=None, description="Seconds into session where this quote starts."
    )


class MetricBlock(BaseModel):
    """KPI or quantitative finding."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["metric"]
    label: str = Field(..., min_length=1, description="Metric label.")
    value: float = Field(..., description="Numeric value.")
    unit: str | None = Field(default=None, description="Optional unit (e.g. 'min', '%').")


class ChartBlock(BaseModel):
    """ECharts-ready chart definition."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["chart"]
    title: str = Field(..., min_length=1, description="Chart title.")
    chart_type: Literal["bar", "line", "pie"] = Field(default="bar")
    categories: list[str] = Field(default_factory=list, description="X-axis category labels.")
    series: list[dict[str, Any]] = Field(
        default_factory=list,
        description="ECharts series objects; each must include ``name`` (str) and ``data`` (list[float|int]).",
    )

    @field_validator("series")
    @classmethod
    def _check_series_shape(cls, v: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for i, s in enumerate(v):
            if not isinstance(s, dict):
                raise ValueError(f"series[{i}] must be a dict")
            if "name" not in s or not isinstance(s["name"], str):
                raise ValueError(f"series[{i}].name must be a non-empty string")
            if "data" not in s:
                raise ValueError(f"series[{i}].data is required")
            if not isinstance(s["data"], list):
                raise ValueError(f"series[{i}].data must be a list")
            for j, val in enumerate(s["data"]):
                if not isinstance(val, (int, float)):
                    raise ValueError(
                        f"series[{i}].data[{j}] must be int or float, got {type(val).__name__}"
                    )
        return v


_BlockUnion = Annotated[
    Union[TextBlock, QuoteBlock, MetricBlock, ChartBlock],
    Field(discriminator="type"),
]


class BlocksDocument(BaseModel):
    """Top-level container for a flat list of typed blocks.

    Kept for backwards-compatibility with code that produces / consumes a
    flat list (e.g., legacy report renderers). New code should build a
    :class:`StudyReportContent` instead.
    """

    model_config = ConfigDict(extra="forbid")

    blocks: list[_BlockUnion] = Field(default_factory=list)


def validate_blocks_list(data: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Validate a flat list of block dicts; return the normalised list."""
    if not data:
        return []
    doc = BlocksDocument(blocks=data)
    return [b.model_dump() for b in doc.blocks]


# ── Study report — 4-panel structure (PRODUCT.md §4 / platform Req 17) ──


class StudyReportContent(BaseModel):
    """Structured 4-panel content for a finalized ``StudyReport``.

    Per PRODUCT.md §3.6 / platform Req 17:
    - ``exec_summary`` — narrative paragraph (grey background, no border, in UI)
    - ``quant_panel``  — quantitative blocks (charts + metrics). Shown 5/12 width.
    - ``qual_panel``   — qualitative blocks (quotes + narrative text). Shown 7/12 width.
    - ``insight_nuggets`` — 3-6 metric cards at the bottom.
    """

    model_config = ConfigDict(extra="forbid")

    exec_summary: str = Field(..., description="Conclusion-first paragraph.")
    quant_panel: list[Annotated[Union[ChartBlock, MetricBlock], Field(discriminator="type")]] = (
        Field(default_factory=list)
    )
    qual_panel: list[Annotated[Union[QuoteBlock, TextBlock], Field(discriminator="type")]] = (
        Field(default_factory=list)
    )
    insight_nuggets: list[MetricBlock] = Field(default_factory=list)


def validate_study_report_content(data: dict[str, Any] | None) -> dict[str, Any]:
    """Validate a ``StudyReport.content`` dict; return the normalised dict."""
    if not data:
        return {
            "exec_summary": "",
            "quant_panel": [],
            "qual_panel": [],
            "insight_nuggets": [],
        }
    return StudyReportContent(**data).model_dump()


# ── Custom Report chart_spec ────────────────────────────────


class ChartSpec(BaseModel):
    """Shape used by Custom Report Q&A answers and the ``StudyReport.charts``
    flat list. Per PRODUCT.md §3.6.
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["bar", "line", "pie"]
    title: str
    x: list[str]
    y: list[float]
    unit: str | None = None


class Citation(BaseModel):
    """A single citation attached to a Custom Report answer."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    ts: float
    quote: str
    speaker: str
    # For cross-study Knowledge Explore citations — filled when the
    # answer scopes across studies (otherwise empty).
    study_id: str | None = None
    study_name: str = ""


class CustomReportAnswer(BaseModel):
    """Shape of an Analysis Agent answer to a Custom Report question.

    Function-calling output shape — see PRODUCT.md §5.3 (B).
    """

    model_config = ConfigDict(extra="forbid")

    answer_markdown: str
    chart: ChartSpec | None = None
    citations: list[Citation] = Field(default_factory=list)


__all__ = [
    # block atoms
    "TextBlock",
    "QuoteBlock",
    "MetricBlock",
    "ChartBlock",
    # flat blocks document
    "BlocksDocument",
    "validate_blocks_list",
    # structured 4-panel content
    "StudyReportContent",
    "validate_study_report_content",
    # chart / citation / custom-report answer shapes
    "ChartSpec",
    "Citation",
    "CustomReportAnswer",
]
