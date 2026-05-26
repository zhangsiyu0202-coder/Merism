"""Merism DRF viewsets.

Thin wrappers over :class:`~merism.api.base.TeamScopedModelViewSet`. Domain
logic (launch a study, finalize an outline, generate a report) calls out
to the domain packages (``merism.conductor``, ``merism.knowledge``,
``merism.memai``, ``merism.recruitment``) via ``@action`` endpoints.
"""

from __future__ import annotations

from django.http import StreamingHttpResponse
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from merism.api.base import TeamScopedModelViewSet, _team_from_request
from merism.api.serializers import (
    AgentMemorySerializer,
    ChannelConfigSerializer,
    ConceptBlockSerializer,
    ConceptSerializer,
    CustomReportQuerySerializer,
    DeliveryRecordSerializer,
    InterviewGuideSerializer,
    InterviewSessionSerializer,
    KnowledgeChunkSerializer,
    KnowledgeDocumentSerializer,
    MessageTemplateSerializer,
    ParticipantSerializer,
    ParticipationSerializer,
    RecruitmentBroadcastSerializer,
    ScreenerSerializer,
    SessionInsightSerializer,
    StimulusSerializer,
    StudyLinkSerializer,
    StudyReportSerializer,
    StudySerializer,
    StudyTemplateSerializer,
    StudyTriggerSerializer,
)
from merism.models import (
    AgentMemory,
    ChannelConfig,
    Concept,
    ConceptBlock,
    CustomReportQuery,
    DeliveryRecord,
    InterviewGuide,
    InterviewSession,
    KnowledgeChunk,
    KnowledgeDocument,
    MessageTemplate,
    Participant,
    Participation,
    RecruitmentBroadcast,
    Screener,
    SessionInsight,
    Stimulus,
    Study,
    StudyLink,
    StudyReport,
    StudyTemplate,
    StudyTrigger,
)

# ── Study ──────────────────────────────────────────────────


class StudyViewSet(TeamScopedModelViewSet):
    queryset = Study.objects.all()
    serializer_class = StudySerializer

    @action(detail=True, methods=["post"])
    def launch(self, request: Request, pk: str | None = None) -> Response:
        """Flip draft → recruiting after the outline is finalized."""
        study = self.get_object()
        if study.status != Study.Status.DRAFT:
            return Response(
                {"detail": f"Cannot launch a study in status '{study.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        study.status = Study.Status.LIVE
        study.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(study).data)

    @action(detail=True, methods=["post"])
    def close(self, request: Request, pk: str | None = None) -> Response:
        study = self.get_object()
        study.status = Study.Status.CLOSED
        study.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(study).data)

    @action(detail=True, methods=["post"], url_path="launch-recruitment")
    def launch_recruitment(self, request: Request, pk: str | None = None) -> Response:
        from merism.recruitment.orchestrator import (
            RecruitmentLaunchError,
            launch_study_recruitment,
        )

        study = self.get_object()
        try:
            result = launch_study_recruitment(study=study)
        except RecruitmentLaunchError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        payload = result.as_dict()
        if not payload["queued_broadcast_ids"]:
            payload["detail"] = "No recruitment broadcasts were queued."
            return Response(payload, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload)

    @action(detail=True, methods=["get"])
    def analysis(self, request: Request, pk: str | None = None) -> Response:
        """Aggregate analytics for the AnalysisTab — pure DB rollup."""
        from merism.reports.analysis_service import compute_study_aggregate

        study = self.get_object()
        return Response(compute_study_aggregate(study))

    @action(detail=True, methods=["post"])
    def narrative(self, request: Request, pk: str | None = None) -> Response:
        """LLM-generated narrative summary for the ExecutiveSummary block."""
        import asyncio

        from merism.memai.agents.study_narrative_summary import summarize_study

        study = self.get_object()
        payload = asyncio.run(summarize_study(study))
        if payload is None:
            return Response(
                {"detail": "Not enough data for a narrative yet."},
                status=status.HTTP_204_NO_CONTENT,
            )
        return Response(payload)

    @action(detail=True, methods=["post"], url_path="review-outline")
    def review_outline_action(self, request: Request, pk: str | None = None) -> Response:
        """Run one Outline Review Agent turn for this study.

        Payload:
            {
                "message": "<researcher message>",
                "sections": [ ... ],
                "chat_history": [ {role, content}, ... ]
            }

        Returns the agent's :class:`~merism.memai.agents.outline_review.OutlineReviewResponse`
        verbatim as JSON.
        """
        from merism.memai.agents import review_outline

        study = self.get_object()
        message = (request.data.get("message") or "").strip()
        sections = request.data.get("sections") or []
        chat_history = request.data.get("chat_history") or []
        if not message:
            return Response(
                {"detail": "'message' is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        response = review_outline(
            research_goal=study.research_goal,
            guide_sections=sections,
            chat_history=chat_history,
            researcher_message=message,
            team=self.get_team(),
        )
        return Response(response.model_dump())

    @action(detail=True, methods=["get", "put"], url_path="outline")
    def outline_action(self, request: Request, pk: str | None = None) -> Response:
        """Read or write the v3 outline for a study.

        ``GET``: returns the current outline (v3 dict shape) or empty
        default when the study has no current guide. v1 list-shape guides
        (legacy) return ``{"outline": null, "legacy_sections": [...]}``.

        ``PUT``: receives ``{"outline": {...}}``, validates via Pydantic
        :class:`~merism.conductor.schema.Outline` + ``validate_outline``,
        persists as a new :class:`InterviewGuide` row with
        ``sections.version == "v3"``. Returns the persisted guide. On
        validation failure: 422 with ``{"outline_errors": [str, ...]}``.
        """
        from pydantic import ValidationError as PydanticValidationError

        from merism.conductor.schema import Outline, OutlineError, validate_outline

        study = self.get_object()
        team = self.get_team()

        if request.method == "GET":
            current = InterviewGuide.objects.filter(study=study, is_current=True).first()
            if current is None:
                return Response({"outline": Outline().model_dump(mode="json")})
            sections = current.sections
            if isinstance(sections, dict) and sections.get("version") == "v3":
                return Response({"outline": sections})
            # Legacy v1 list-shape — surface so the editor can render
            return Response({"outline": None, "legacy_sections": sections})

        # PUT
        body = request.data
        if not isinstance(body, dict):
            return Response(
                {"outline_errors": ["request body must be a JSON object"]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        outline_payload = body.get("outline")
        if not isinstance(outline_payload, dict):
            return Response(
                {"outline_errors": ["request body must contain an 'outline' object"]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            outline = Outline.model_validate(outline_payload)
            validate_outline(outline)
        except PydanticValidationError as exc:
            return Response(
                {"outline_errors": [str(e) for e in exc.errors()]},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except OutlineError as exc:
            return Response(
                {"outline_errors": [str(exc)]},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # Atomic flip: previous current → not current, new row inserted as current.
        from django.db import transaction

        with transaction.atomic():
            InterviewGuide.objects.filter(study=study, is_current=True).update(is_current=False)
            previous = InterviewGuide.objects.filter(study=study).order_by("-created_at").first()
            new_version = _bump_semver(previous.version if previous else "0.0.0")
            guide = InterviewGuide.objects.create(
                team=team,
                study=study,
                version=new_version,
                is_current=True,
                sections=outline.model_dump(mode="json"),
            )
        return Response(InterviewGuideSerializer(guide).data, status=status.HTTP_200_OK)


def _bump_semver(version: str) -> str:
    """Bump the patch component of a semver string (``"1.0.0"`` → ``"1.0.1"``)."""
    parts = version.split(".")
    if len(parts) != 3:
        return "1.0.0"
    try:
        major, minor, patch = (int(p) for p in parts)
    except ValueError:
        return "1.0.0"
    return f"{major}.{minor}.{patch + 1}"


class StudyLinkViewSet(TeamScopedModelViewSet):
    queryset = StudyLink.objects.all()
    serializer_class = StudyLinkSerializer


class StudyTemplateViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Read-only: templates are seeded as system rows or created via admin."""

    queryset = StudyTemplate.objects.all()
    serializer_class = StudyTemplateSerializer


class StudyTriggerViewSet(TeamScopedModelViewSet):
    queryset = StudyTrigger.objects.all()
    serializer_class = StudyTriggerSerializer


class ScreenerViewSet(TeamScopedModelViewSet):
    queryset = Screener.objects.all()
    serializer_class = ScreenerSerializer


class StimulusViewSet(TeamScopedModelViewSet):
    queryset = Stimulus.objects.all()
    serializer_class = StimulusSerializer

    @action(detail=False, methods=["post"], url_path="upload")
    def upload(self, request: Request) -> Response:
        """Upload a file and create a Stimulus record.

        Accepts multipart/form-data with:
          - file: the uploaded file
          - study: study UUID
          - title: optional title
          - kind: auto-detected from content_type if omitted
        """
        from merism.storage import upload_stimulus_file

        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)

        study_id = request.data.get("study")
        if not study_id:
            return Response({"detail": "study is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Auto-detect kind from content type
        content_type = file.content_type or "application/octet-stream"
        kind = request.data.get("kind")
        if not kind:
            if content_type.startswith("image/"):
                kind = "image"
            elif content_type.startswith("video/"):
                kind = "video"
            elif content_type == "application/pdf":
                kind = "pdf"
            else:
                kind = "link"

        url = upload_stimulus_file(
            file,
            study_id=str(study_id),
            filename=file.name,
            content_type=content_type,
        )

        stimulus = Stimulus.objects.create(
            team=request.user.team,
            study_id=study_id,
            kind=kind,
            title=request.data.get("title", file.name),
            content={"url": url, "content_type": content_type, "size": file.size},
        )

        return Response(StimulusSerializer(stimulus).data, status=status.HTTP_201_CREATED)


# ── Concept Testing 2.0 ────────────────────────────────────


class ConceptBlockViewSet(TeamScopedModelViewSet):
    queryset = ConceptBlock.objects.prefetch_related("concepts__stimulus").all()
    serializer_class = ConceptBlockSerializer

    @action(detail=True, methods=["get"])
    def report(self, request: Request, pk: str | None = None) -> Response:
        """Per-concept aggregate report for this block.

        MVP heuristic:
        - ``sessions_seen`` = # completed sessions whose
          :attr:`InterviewSession.moderator_state.concepts_shown`
          contains the concept id.
        - ``dimensions`` = 4-dim score vector (sentiment /
          purchase_intent / appeal / comprehension) computed by
          :mod:`merism.concept.dimensions` over the concatenated
          participant turns for that concept across all sessions.
        - ``winner_concept_id`` = highest ``purchase_intent``, ties
          broken by ``appeal`` then ``sentiment``. Falls back to
          ``sessions_seen`` when no dimension scores exist.
        """
        from merism.concept.dimensions import aggregate_concept_dimensions

        block = self.get_object()
        sessions = list(InterviewSession.objects.filter(study=block.study, status="completed"))
        transcripts = [s.transcript or [] for s in sessions]

        rows: list[dict] = []
        for concept in block.concepts.all():
            concept_id = str(concept.id)
            seen = 0
            for s in sessions:
                shown = (s.moderator_state or {}).get("concepts_shown") or []
                if concept_id in shown:
                    seen += 1
            dimensions = aggregate_concept_dimensions(transcripts, concept_id)
            rows.append(
                {
                    "concept_id": concept_id,
                    "label": concept.label,
                    "rank": concept.rank,
                    "stimulus_id": str(concept.stimulus_id),
                    "sessions_seen": seen,
                    "dimensions": dimensions,
                }
            )

        winner_id = _choose_winner(rows)

        return Response(
            {
                "block_id": str(block.id),
                "block_title": block.title,
                "rotation": block.rotation,
                "concepts": rows,
                "winner_concept_id": winner_id,
                "total_sessions": len(sessions),
            }
        )


class ConceptViewSet(TeamScopedModelViewSet):
    queryset = Concept.objects.select_related("stimulus", "block").all()
    serializer_class = ConceptSerializer


# ── Interview ──────────────────────────────────────────────


class InterviewGuideViewSet(TeamScopedModelViewSet):
    queryset = InterviewGuide.objects.all()
    serializer_class = InterviewGuideSerializer

    @action(detail=True, methods=["post"])
    def finalize(self, request: Request, pk: str | None = None) -> Response:
        """Mark this guide as current; flip the study to ready."""
        guide = self.get_object()
        InterviewGuide.objects.filter(study=guide.study).update(is_current=False)
        guide.is_current = True
        guide.save(update_fields=["is_current", "updated_at"])
        return Response(self.get_serializer(guide).data)


class ParticipantViewSet(TeamScopedModelViewSet):
    queryset = Participant.objects.all()
    serializer_class = ParticipantSerializer


class ParticipationViewSet(TeamScopedModelViewSet):
    queryset = Participation.objects.all()
    serializer_class = ParticipationSerializer


class InterviewSessionViewSet(TeamScopedModelViewSet):
    queryset = InterviewSession.objects.all()
    serializer_class = InterviewSessionSerializer

    def get_serializer_class(self):  # type: ignore[override]
        # Exclude heavy JSON fields (transcript / vision_frames) from list
        # responses. ``retrieve`` continues to return the full payload.
        if self.action == "list":
            from merism.api.serializers import InterviewSessionListSerializer

            return InterviewSessionListSerializer
        return super().get_serializer_class()

    @action(detail=True, methods=["get"])
    def stream(self, request: Request, pk: str | None = None) -> StreamingHttpResponse:
        """SSE stream of session events — mounts onto merism.realtime.sse_interview."""
        from merism.realtime.sse_interview import iter_session_sse

        session = self.get_object()
        response = StreamingHttpResponse(iter_session_sse(session), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"  # Nginx: do not buffer
        return response

    @action(detail=True, methods=["get"])
    def export(self, request: Request, pk: str | None = None) -> Response:
        """Export the session transcript.

        ``?as=clean``   (default) — intelligent-verbatim text
        ``?as=raw``              — original ASR text
        ``?as=srt``              — timed subtitles (auto-generated
                                   from transcript timestamps)

        Tenant-scoped via the base queryset; no extra auth layer needed.
        Note: the query param is ``as`` (not ``format``) to avoid DRF's
        content-negotiation machinery hijacking the suffix.
        """
        from django.http import HttpResponse

        from merism.conductor.transcript_helpers import (
            get_transcript_text,
        )

        session = self.get_object()
        fmt = request.query_params.get("as", "clean").lower()

        transcript = session.transcript or []

        if fmt == "srt":
            body = _transcript_to_srt(transcript)
            return HttpResponse(body, content_type="text/plain; charset=utf-8")

        mode = "raw" if fmt == "raw" else "clean"
        text = get_transcript_text(transcript, mode=mode)

        return HttpResponse(
            text,
            content_type="text/plain; charset=utf-8",
            headers={
                "Content-Disposition": (f'attachment; filename="session-{session.id}-{mode}.txt"'),
            },
        )


def _transcript_to_srt(transcript: list[dict]) -> str:
    """Render a transcript into SRT subtitle format.

    Uses each turn's ``ts`` (start, epoch seconds) and a simple +5s
    duration when a next turn isn't available.
    """
    from merism.conductor.transcript_helpers import get_turn_text

    def _fmt(seconds: float) -> str:
        ms = int(round((seconds - int(seconds)) * 1000))
        total = int(seconds)
        h, rem = divmod(total, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    lines: list[str] = []
    for i, turn in enumerate(transcript):
        if turn.get("role") not in {"agent", "participant"}:
            continue
        start = float(turn.get("ts") or 0)
        nxt = next(
            (float(t.get("ts") or 0) for t in transcript[i + 1 :] if t.get("role") in {"agent", "participant"}),
            start + 5.0,
        )
        text = get_turn_text(turn, "clean")
        if not text:
            continue
        lines.append(str(len(lines) // 4 + 1))
        lines.append(f"{_fmt(start)} --> {_fmt(max(nxt, start + 0.5))}")
        lines.append(f"[{turn.get('role')}] {text}")
        lines.append("")
    return "\n".join(lines)


# ── Knowledge ──────────────────────────────────────────────


class KnowledgeChunkViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = KnowledgeChunk.objects.select_related("document").all()
    serializer_class = KnowledgeChunkSerializer

    @action(detail=False, methods=["post"])
    def search(self, request: Request) -> Response:
        """Hybrid BM25 + cosine search over the team's chunks."""
        from merism.knowledge.search import chunk_search_team

        team = _team_from_request(request)
        if team is None:
            return Response({"results": []})
        query = request.data.get("query", "").strip()
        limit = int(request.data.get("limit", 7))
        chunks = chunk_search_team(team_id=team.id, query=query, limit=limit)
        return Response({"results": [self.get_serializer(c).data for c in chunks]})


class KnowledgeDocumentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = KnowledgeDocument.objects.all()
    serializer_class = KnowledgeDocumentSerializer


# ── Recruitment ────────────────────────────────────────────


class ChannelConfigViewSet(TeamScopedModelViewSet):
    queryset = ChannelConfig.objects.all()
    serializer_class = ChannelConfigSerializer

    @action(detail=True, methods=["post"])
    def test(self, request: Request, pk: str | None = None) -> Response:
        """Ping the channel and flip status to active/error based on result."""
        from merism.recruitment import decrypt_credentials, get_adapter

        config = self.get_object()
        try:
            creds = decrypt_credentials(config.credentials_encrypted)
            adapter = get_adapter(config.channel_type, creds)
            ok, err = adapter.health_check()
        except Exception as exc:  # pragma: no cover - exercised via unit tests
            ok, err = False, str(exc)

        if ok:
            config.status = ChannelConfig.Status.ACTIVE
            config.consecutive_failures = 0
            config.last_error = ""
        else:
            config.status = ChannelConfig.Status.ERROR
            config.consecutive_failures = (config.consecutive_failures or 0) + 1
            config.last_error = err or "health check failed"
        config.save()
        return Response({"ok": ok, "error": err})


class MessageTemplateViewSet(TeamScopedModelViewSet):
    queryset = MessageTemplate.objects.all()
    serializer_class = MessageTemplateSerializer


class RecruitmentBroadcastViewSet(TeamScopedModelViewSet):
    queryset = RecruitmentBroadcast.objects.all()
    serializer_class = RecruitmentBroadcastSerializer

    @action(detail=True, methods=["post"])
    def send(self, request: Request, pk: str | None = None) -> Response:
        """Kick off the broadcast Celery task."""
        from merism.recruitment.tasks import dispatch_recruitment_delivery

        broadcast = self.get_object()
        if broadcast.status != RecruitmentBroadcast.Status.APPROVED:
            return Response(
                {"detail": f"Broadcast must be approved before sending, got '{broadcast.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        dispatch_recruitment_delivery.delay(str(broadcast.id))
        broadcast.status = RecruitmentBroadcast.Status.SENDING
        broadcast.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(broadcast).data)

    @action(detail=True, methods=["post"])
    def retry(self, request: Request, pk: str | None = None) -> Response:
        from merism.recruitment.tasks import retry_failed_deliveries

        broadcast = self.get_object()
        retry_failed_deliveries.delay(str(broadcast.id))
        return Response({"queued": True})


class DeliveryRecordViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = DeliveryRecord.objects.all()
    serializer_class = DeliveryRecordSerializer

    def get_queryset(self):  # type: ignore[override]
        team = _team_from_request(self.request)
        if team is None:
            return DeliveryRecord.objects.none()
        return DeliveryRecord.objects.filter(team=team).order_by("-created_at")


# ── Report ─────────────────────────────────────────────────


class SessionInsightViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = SessionInsight.objects.all()
    serializer_class = SessionInsightSerializer


class StudyReportViewSet(TeamScopedModelViewSet):
    queryset = StudyReport.objects.all()
    serializer_class = StudyReportSerializer

    @action(detail=True, methods=["post"])
    def regenerate(self, request: Request, pk: str | None = None) -> Response:
        """Enqueue re-generation of a study report."""
        # TODO: wire to merism.memai.agents.analysis.generate_study_report
        report = self.get_object()
        report.status = StudyReport.Status.GENERATING
        report.save(update_fields=["status", "updated_at"])
        return Response(self.get_serializer(report).data)


class CustomReportQueryViewSet(TeamScopedModelViewSet):
    queryset = CustomReportQuery.objects.all()
    serializer_class = CustomReportQuerySerializer

    def perform_create(self, serializer) -> None:  # type: ignore[override]
        """Create the query row then run the Analysis Agent synchronously.

        The agent populates ``answer_markdown`` / ``chart_spec`` /
        ``citations`` on the same row. For longer queries this should
        move to a Celery task + SSE stream; keeping sync for now so the
        frontend round-trip stays a single POST.
        """
        from merism.memai.agents import answer_custom_report_question

        team = self.get_team()
        instance = serializer.save(team=team, created_by=self.request.user)

        try:
            answer = answer_custom_report_question(
                study=instance.study,
                question=instance.question,
            )
        except Exception as exc:  # pragma: no cover - live LLM
            instance.answer_markdown = f"Sorry, I couldn't answer that: {exc}"
            instance.save(update_fields=["answer_markdown", "updated_at"])
            return

        instance.answer_markdown = answer.answer_markdown
        instance.chart_spec = answer.chart.model_dump() if answer.chart else {}
        instance.citations = [c.model_dump() for c in answer.citations]
        instance.save(update_fields=["answer_markdown", "chart_spec", "citations", "updated_at"])


class AgentMemoryViewSet(TeamScopedModelViewSet):
    queryset = AgentMemory.objects.filter(is_deleted=False)
    serializer_class = AgentMemorySerializer

    def perform_destroy(self, instance: AgentMemory) -> None:  # type: ignore[override]
        # Soft-delete — the agent's audit trail stays intact.
        instance.is_deleted = True
        instance.save(update_fields=["is_deleted", "updated_at"])


def _choose_winner(rows: list[dict]) -> str | None:
    """Pick the winning concept for a report.

    Priority, all computed across sessions:
    1. Highest ``purchase_intent`` (from dimensions, 0..10).
    2. Tie-break by highest ``appeal``.
    3. Tie-break by highest ``sentiment``.
    4. Fallback to ``sessions_seen`` when no dimensions computed.

    Returns ``None`` when no concept has any signal (e.g. no completed
    sessions yet).
    """

    def dim(row: dict, name: str) -> float:
        for d in row.get("dimensions", []):
            if d.get("name") == name:
                return float(d.get("value", 0) or 0)
        return 0.0

    scored = [
        (
            dim(r, "purchase_intent"),
            dim(r, "appeal"),
            dim(r, "sentiment"),
            r.get("sessions_seen", 0),
            r,
        )
        for r in rows
    ]
    if not scored:
        return None

    # Sort desc by tuple; strongest signal first.
    scored.sort(key=lambda t: (t[0], t[1], t[2], t[3]), reverse=True)
    best = scored[0]
    # No signal at all → no winner.
    if best[0] == 0 and best[1] == 0 and best[2] == 0 and best[3] == 0:
        return None
    return str(best[4]["concept_id"])


class InboxItemViewSet(TeamScopedModelViewSet):
    """Researcher inbox — read + mark-read only. No create (written by signals)."""

    http_method_names = ["get", "post", "head", "options"]
    queryset = None  # set below

    def get_queryset(self):
        from merism.models import InboxItem

        team = _team_from_request(self.request)
        return InboxItem.objects.filter(team=team).order_by("-created_at")

    def get_serializer_class(self):
        from merism.api.serializers import InboxItemSerializer

        return InboxItemSerializer

    def perform_create(self, serializer):
        raise RuntimeError("InboxItem is write-only via signals")

    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request, pk=None):
        item = self.get_object()
        user_id = str(request.user.id) if request.user.is_authenticated else None
        if user_id and user_id not in item.read_by:
            item.read_by = [*item.read_by, user_id]
            item.save(update_fields=["read_by", "updated_at"])
        return Response(self.get_serializer(item).data)
