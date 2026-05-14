from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError

from merism.conductor.moderator_eval import (
    ChatClientProtocol,
    load_eval_cases,
    load_manual_scores,
    render_manual_scorecard,
    render_markdown_report,
    run_eval_report,
)
from merism.llm_gateway.client import get_client
from merism.models import Team


DEFAULT_FIXTURE_PATH = "docs/specs/dual-layer-followup/moderator_eval_cases.json"
DEFAULT_MARKDOWN_PATH = "tmp/moderator_eval_report.md"
DEFAULT_SCORECARD_PATH = "tmp/moderator_eval_manual_scorecard.csv"


class Command(BaseCommand):
    help = "Run single-call vs two-call moderator evaluation on the same turn fixtures."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--team-id", required=True, help="Team id with an active chat route.")
        parser.add_argument(
            "--fixture-path",
            default=DEFAULT_FIXTURE_PATH,
            help=f"Path to eval fixtures JSON. Default: {DEFAULT_FIXTURE_PATH}",
        )
        parser.add_argument(
            "--variants",
            default="single_call,two_call",
            help="Comma-separated variants to run. Supported: single_call,two_call",
        )
        parser.add_argument(
            "--manual-scores-path",
            default="",
            help="Optional CSV with manual ratings to merge into the report.",
        )
        parser.add_argument(
            "--output-markdown",
            default=DEFAULT_MARKDOWN_PATH,
            help=f"Where to write the markdown report. Default: {DEFAULT_MARKDOWN_PATH}",
        )
        parser.add_argument(
            "--output-scorecard",
            default=DEFAULT_SCORECARD_PATH,
            help=f"Where to write the manual scoring CSV template. Default: {DEFAULT_SCORECARD_PATH}",
        )

    def handle(self, *args: object, **options: object) -> None:
        team_id = str(options["team_id"])
        variants = [item.strip() for item in str(options["variants"]).split(",") if item.strip()]
        supported = {"single_call", "two_call"}
        unknown = [item for item in variants if item not in supported]
        if unknown:
            raise CommandError(f"Unsupported variants: {', '.join(unknown)}")

        fixture_path = Path(str(options["fixture_path"]))
        if not fixture_path.exists():
            raise CommandError(f"Fixture path not found: {fixture_path}")

        try:
            team = Team.objects.get(id=team_id)
        except Team.DoesNotExist as exc:
            raise CommandError(f"Team not found: {team_id}") from exc

        cases = load_eval_cases(fixture_path)
        manual_scores_path = str(options["manual_scores_path"]).strip()
        manual_scores = load_manual_scores(manual_scores_path) if manual_scores_path else None

        report = asyncio.run(
            run_eval_report(
                cases=cases,
                variants=variants,
                client_factories={
                    variant: _build_live_client_factory(team) for variant in variants
                },
                manual_scores=manual_scores,
            )
        )

        markdown_path = Path(str(options["output_markdown"]))
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown_report(report))

        scorecard_path = Path(str(options["output_scorecard"]))
        scorecard_path.parent.mkdir(parents=True, exist_ok=True)
        scorecard_path.write_text(render_manual_scorecard(report.results))

        self.stdout.write(self.style.SUCCESS(f"Wrote markdown report to {markdown_path}"))
        self.stdout.write(self.style.SUCCESS(f"Wrote manual scorecard to {scorecard_path}"))
        for summary in report.summaries:
            self.stdout.write(
                f"{summary.variant}: rule={summary.rule_adherence_rate:.1%}, "
                f"move_on={summary.move_on_accuracy:.1%}, "
                f"ttfb={_fmt(summary.avg_first_token_latency_ms)} ms, "
                f"latency={summary.avg_total_latency_ms:.1f} ms, "
                f"tokens={summary.avg_total_tokens:.1f}"
            )


def _build_live_client_factory(team: Team):
    async def _factory(trace_id: UUID) -> ChatClientProtocol:
        return await get_client("chat", team=team, trace_id=trace_id)

    return _factory


def _fmt(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.1f}"

