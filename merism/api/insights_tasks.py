"""Celery tasks for AI-powered insights and report generation.

Two main tasks:
- :func:`generate_insights_task` — generates StudyInsights from sessions
- :func:`generate_report_task` — generates per-question analysis for a CustomReport
"""

from __future__ import annotations

import json
import logging
from typing import Any

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def generate_insights_task(self, insights_id: str) -> None:
    """Generate AI insights for a study."""
    from merism.memai.llm import get_llm
    from merism.models import (
        InsightFinding,
        InsightHighlight,
        InterviewSession,
        SessionInsight,
        StudyInsights,
    )

    try:
        insights = StudyInsights.objects.select_related("study").get(id=insights_id)
    except StudyInsights.DoesNotExist:
        logger.error("StudyInsights %s not found", insights_id)
        return

    study = insights.study
    try:
        # Gather session data
        sessions = InterviewSession.objects.filter(study=study, status=InterviewSession.Status.COMPLETED)
        session_insights = SessionInsight.objects.filter(session__study=study)

        completed_count = sessions.count()
        if completed_count == 0:
            insights.status = StudyInsights.Status.FAILED
            insights.error_message = "No completed interviews to analyze."
            insights.save(update_fields=["status", "error_message", "updated_at"])
            return

        # Compute avg session time
        from django.db.models import Avg, DurationField, ExpressionWrapper, F

        avg_duration = (
            sessions.filter(started_at__isnull=False, ended_at__isnull=False)
            .annotate(dur=ExpressionWrapper(F("ended_at") - F("started_at"), output_field=DurationField()))
            .aggregate(avg=Avg("dur"))["avg"]
        )
        avg_minutes = (avg_duration.total_seconds() / 60) if avg_duration else 0.0

        # Build context for LLM
        summaries = list(session_insights.values_list("summary", flat=True)[:20])
        highlights_data = list(session_insights.values_list("highlights", flat=True)[:20])

        prompt = _build_insights_prompt(
            research_goal=study.research_goal,
            session_count=completed_count,
            summaries=summaries,
            highlights_data=highlights_data,
        )

        client = get_llm()
        response = client.chat.completions.create(
            model="deepseek-reasoner",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        result = json.loads(response.choices[0].message.content)

        # Update insights
        insights.completed_interviews = completed_count
        insights.avg_session_minutes = round(avg_minutes, 1)
        insights.interview_topics = result.get("topics", [])
        insights.executive_summary = result.get("executive_summary", "")
        insights.status = StudyInsights.Status.READY
        insights.generated_at = timezone.now()
        insights.save()

        # Create highlights
        insights.highlights.all().delete()
        for i, h in enumerate(result.get("highlights", [])[:6]):
            InsightHighlight.objects.create(
                team=insights.team,
                insights=insights,
                headline=h.get("headline", ""),
                summary=h.get("summary", ""),
                icon=h.get("icon", ""),
                display_order=i,
            )

        # Create findings
        insights.findings.all().delete()
        for i, f in enumerate(result.get("findings", [])[:10]):
            InsightFinding.objects.create(
                team=insights.team,
                insights=insights,
                title=f.get("title", ""),
                summary=f.get("summary", ""),
                display_order=i,
                chart_spec=f.get("chart_spec", {}),
                chart_interpretation=f.get("chart_interpretation", ""),
                themes=f.get("themes", []),
                subthemes=f.get("subthemes", []),
                insight_nuggets=f.get("insight_nuggets", []),
                supporting_evidence=f.get("supporting_evidence", []),
            )

    except Exception as exc:
        logger.exception("Insights generation failed for %s", insights_id)
        insights.status = StudyInsights.Status.FAILED
        insights.error_message = str(exc)[:500]
        insights.save(update_fields=["status", "error_message", "updated_at"])
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def generate_report_task(self, report_id: str) -> None:
    """Generate AI analysis for all questions in a custom report."""
    from merism.memai.llm import get_llm
    from merism.models import CustomReport, ReportQuestion

    try:
        report = CustomReport.objects.select_related("study").get(id=report_id)
    except CustomReport.DoesNotExist:
        logger.error("CustomReport %s not found", report_id)
        return

    study = report.study
    questions = report.questions.order_by("question_number")

    if not questions.exists():
        report.status = CustomReport.Status.FAILED
        report.error_message = "No questions to analyze."
        report.save(update_fields=["status", "error_message", "updated_at"])
        return

    try:
        # Gather interview data
        from merism.models import InterviewSession, SessionInsight

        InterviewSession.objects.filter(study=study, status=InterviewSession.Status.COMPLETED)
        session_insights = SessionInsight.objects.filter(session__study=study)
        summaries = list(session_insights.values_list("summary", flat=True)[:20])

        client = get_llm()

        # Generate per-question analysis
        for question in questions:
            question.status = ReportQuestion.Status.GENERATING
            question.save(update_fields=["status", "updated_at"])

            prompt = _build_question_prompt(
                research_goal=study.research_goal,
                question_title=question.title,
                question_type=question.get_question_type_display(),
                summaries=summaries,
            )

            response = client.chat.completions.create(
                model="deepseek-reasoner",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.3,
            )

            result = json.loads(response.choices[0].message.content)

            question.ai_summary = result.get("summary", "")
            question.chart_spec = result.get("chart_spec", {})
            question.themes = result.get("themes", [])
            question.quotes = result.get("quotes", [])
            question.status = ReportQuestion.Status.READY
            question.save()

        # Generate overall synthesis
        synthesis_prompt = _build_synthesis_prompt(
            research_goal=study.research_goal,
            questions=[{"title": q.title, "summary": q.ai_summary} for q in questions],
        )
        synthesis_response = client.chat.completions.create(
            model="deepseek-reasoner",
            messages=[{"role": "user", "content": synthesis_prompt}],
            temperature=0.3,
        )
        report.ai_synthesis = synthesis_response.choices[0].message.content
        report.status = CustomReport.Status.READY
        report.generated_at = timezone.now()
        report.save()

    except Exception as exc:
        logger.exception("Report generation failed for %s", report_id)
        report.status = CustomReport.Status.FAILED
        report.error_message = str(exc)[:500]
        report.save(update_fields=["status", "error_message", "updated_at"])
        raise self.retry(exc=exc) from exc


def _build_insights_prompt(
    research_goal: str,
    session_count: int,
    summaries: list[str],
    highlights_data: list[Any],
) -> str:
    return f"""You are a senior UX researcher analyzing qualitative interview data.

Research Goal: {research_goal}
Completed Interviews: {session_count}

Session Summaries:
{chr(10).join(f"- {s}" for s in summaries if s)}

Session Highlights:
{json.dumps(highlights_data[:10], ensure_ascii=False, indent=2)}

Generate a comprehensive research insights report. Return JSON with:
{{
  "executive_summary": "2-3 paragraph narrative summary",
  "topics": ["topic1", "topic2", ...],
  "highlights": [
    {{"headline": "...", "summary": "...", "icon": "lightbulb|trending-up|users|alert-triangle|heart|zap"}}
  ],
  "findings": [
    {{
      "title": "Finding title",
      "summary": "One-line summary",
      "chart_spec": {{"type": "bar|pie|line", "title": "...", "categories": [...], "series": [{{"name": "...", "data": [...]}}]}},
      "chart_interpretation": "What the chart shows",
      "themes": [{{"name": "...", "count": N, "description": "..."}}],
      "subthemes": [{{"name": "...", "parent": "...", "description": "..."}}],
      "insight_nuggets": [{{"label": "...", "value": "...", "unit": "..."}}],
      "supporting_evidence": [{{"quote": "...", "source": "...", "context": "..."}}]
    }}
  ]
}}

Generate 3-6 highlights and 4-8 findings. Be specific and data-driven."""


def _build_question_prompt(
    research_goal: str,
    question_title: str,
    question_type: str,
    summaries: list[str],
) -> str:
    return f"""You are a senior UX researcher analyzing interview data for a specific question.

Research Goal: {research_goal}
Question: {question_title}
Question Type: {question_type}

Interview Summaries:
{chr(10).join(f"- {s}" for s in summaries if s)}

Analyze the interview data for this question. Return JSON with:
{{
  "summary": "2-3 sentence AI summary of findings for this question",
  "chart_spec": {{"type": "bar|pie|line", "title": "...", "categories": [...], "series": [{{"name": "...", "data": [...]}}]}},
  "themes": [{{"name": "...", "count": N, "description": "...", "sentiment": "positive|negative|neutral"}}],
  "quotes": [{{"text": "...", "source": "Participant X", "theme": "..."}}]
}}

Be specific and evidence-based."""


def _build_synthesis_prompt(
    research_goal: str,
    questions: list[dict[str, str]],
) -> str:
    q_text = "\n".join(f"- {q['title']}: {q['summary']}" for q in questions)
    return f"""You are a senior UX researcher writing an executive synthesis.

Research Goal: {research_goal}

Question-level findings:
{q_text}

Write a 2-3 paragraph synthesis that ties together the findings across all questions.
Focus on actionable insights and key patterns."""
