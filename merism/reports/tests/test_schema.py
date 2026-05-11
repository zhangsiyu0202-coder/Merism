"""Tests for :mod:`merism.reports.schema`."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

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


# ── Block atoms ─────────────────────────────────────────────


def test_text_block_requires_non_empty_body() -> None:
    with pytest.raises(ValidationError):
        TextBlock(type="text", body="")


def test_quote_block_requires_source() -> None:
    q = QuoteBlock(type="quote", body="Pricing hurts", source="Alice")
    assert q.source == "Alice"
    with pytest.raises(ValidationError):
        QuoteBlock(type="quote", body="x", source="")


def test_quote_block_accepts_optional_timestamp() -> None:
    q = QuoteBlock(type="quote", body="x", source="A", session_id="s1", ts=342.5)
    assert q.ts == 342.5


def test_metric_block_value_is_numeric() -> None:
    m = MetricBlock(type="metric", label="NPS", value=42)
    assert m.value == 42
    with pytest.raises(ValidationError):
        MetricBlock(type="metric", label="x", value="not a number")  # type: ignore[arg-type]


def test_chart_block_series_shape_enforced() -> None:
    ChartBlock(
        type="chart",
        title="x",
        categories=["a", "b"],
        series=[{"name": "n", "data": [1, 2]}],
    )
    with pytest.raises(ValidationError):
        ChartBlock(type="chart", title="x", series=[{"no_name": 1}])  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        ChartBlock(
            type="chart",
            title="x",
            series=[{"name": "n", "data": [1, "two"]}],
        )


# ── Flat blocks document ────────────────────────────────────


def test_blocks_document_discriminator_routes_correctly() -> None:
    doc = BlocksDocument(
        blocks=[
            {"type": "text", "body": "hello"},
            {"type": "quote", "body": "q", "source": "a"},
        ]
    )
    assert isinstance(doc.blocks[0], TextBlock)
    assert isinstance(doc.blocks[1], QuoteBlock)


def test_blocks_document_rejects_unknown_type() -> None:
    with pytest.raises(ValidationError):
        BlocksDocument(blocks=[{"type": "xyz"}])  # type: ignore[list-item]


def test_validate_blocks_list_empty_inputs() -> None:
    assert validate_blocks_list(None) == []
    assert validate_blocks_list([]) == []


def test_validate_blocks_list_roundtrip() -> None:
    result = validate_blocks_list([{"type": "text", "body": "hi"}])
    assert result == [{"type": "text", "body": "hi"}]


# ── StudyReportContent (4-panel) ────────────────────────────


def test_study_report_content_shape() -> None:
    content = StudyReportContent(
        exec_summary="47 participants; 3 themes.",
        quant_panel=[
            {
                "type": "chart",
                "title": "Pain points",
                "categories": ["a", "b"],
                "series": [{"name": "count", "data": [10, 5]}],
            },
            {"type": "metric", "label": "NPS", "value": 42},
        ],
        qual_panel=[
            {"type": "quote", "body": "Too pricey", "source": "Alice"},
            {"type": "text", "body": "Users grouped concerns into pricing and clarity."},
        ],
        insight_nuggets=[
            {"type": "metric", "label": "Price concerns", "value": 18, "unit": "mentions"}
        ],
    )
    assert content.exec_summary.startswith("47 participants")
    assert len(content.quant_panel) == 2
    assert len(content.qual_panel) == 2
    assert len(content.insight_nuggets) == 1


def test_study_report_content_quant_panel_rejects_quote() -> None:
    # quant_panel only accepts chart or metric blocks
    with pytest.raises(ValidationError):
        StudyReportContent(
            exec_summary="x",
            quant_panel=[{"type": "quote", "body": "x", "source": "a"}],  # type: ignore[list-item]
        )


def test_study_report_content_qual_panel_rejects_metric() -> None:
    with pytest.raises(ValidationError):
        StudyReportContent(
            exec_summary="x",
            qual_panel=[{"type": "metric", "label": "x", "value": 1}],  # type: ignore[list-item]
        )


def test_validate_study_report_content_empty_default() -> None:
    result = validate_study_report_content(None)
    assert result == {
        "exec_summary": "",
        "quant_panel": [],
        "qual_panel": [],
        "insight_nuggets": [],
    }


# ── ChartSpec / Citation / CustomReportAnswer ──────────────


def test_chart_spec_basic() -> None:
    spec = ChartSpec(
        type="bar",
        title="Reasons",
        x=["price", "taste", "packaging"],
        y=[18, 14, 9],
        unit="mentions",
    )
    assert spec.type == "bar"


def test_custom_report_answer_with_chart_and_citations() -> None:
    ans = CustomReportAnswer(
        answer_markdown="Three drivers...",
        chart=ChartSpec(type="bar", title="x", x=["a"], y=[1]),
        citations=[Citation(session_id="s1", ts=342.5, quote="Too pricey", speaker="Alice")],
    )
    assert ans.chart is not None
    assert ans.citations[0].session_id == "s1"


def test_custom_report_answer_minimal() -> None:
    ans = CustomReportAnswer(answer_markdown="No chart needed.")
    assert ans.chart is None
    assert ans.citations == []
