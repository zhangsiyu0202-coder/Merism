"""Anonymous participant-entry views.

Mounted at ``/i/<slug>/...``. Every view here is:

- unauthenticated-safe (no login required — participants are strangers)
- CSRF-exempt for POSTs (session cookie identifies them, not CSRF token)
- rate-limited per source IP via the existing rate_limit helper

State is carried on two things:

- The **slug** (URL) identifies the StudyLink → Study.
- The **merism_browser_token** cookie (HttpOnly, SameSite=Lax, 30-day)
  identifies the Participation within that study.

See ``merism/participant/design.md`` for the full state machine.
"""

from __future__ import annotations

import uuid
from typing import Any

from django.db import models, transaction
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from merism.models import (
    InterviewGuide,
    InterviewSession,
    Invitation,
    Participant,
    Participation,
    Screener,
    Study,
    StudyLink,
)

COOKIE_NAME = "merism_browser_token"
COOKIE_MAX_AGE = 30 * 24 * 3600  # 30 days


def _resolve_invitation(link: StudyLink, token: str | None) -> tuple[Invitation | None, str | None]:
    """Return (invitation, error_code).

    - link.require_invitation=False + no token → (None, None) — open flow
    - link.require_invitation=True + no token → (None, "invitation_required")
    - token present but invalid → (None, "invitation_invalid")
    - token present, expired → (None, "invitation_expired")
    - token present, valid → (invitation, None)
    """
    if not token:
        if link.require_invitation:
            return None, "invitation_required"
        return None, None
    inv = Invitation.objects.filter(study_link=link, token=token).first()
    if inv is None:
        return None, "invitation_invalid"
    if inv.status == Invitation.Status.REVOKED:
        return None, "invitation_revoked"
    if inv.expires_at and inv.expires_at < timezone.now():
        return None, "invitation_expired"
    return inv, None


# ── Helpers ──────────────────────────────────────────────


def _resolve_link(slug: str, *, is_preview: bool = False) -> tuple[StudyLink | None, str | None]:
    """Return (link, error_code) for the given slug.

    Access control philosophy (per the 2026-05-23 simplification): the
    link is open by default. The researcher controls access via two
    explicit toggles:

    - ``StudyLink.is_active``: the "Accepting responses" switch on the
      Recruit tab. Researcher flips it off to stop new participants.
    - ``StudyLink.expires_at``: optional hard deadline.

    ``Study.status == CLOSED`` is **metadata only** — it doesn't auto-
    block the link. A study can be marked closed for analytics /
    inbox purposes while still accepting walk-ins (e.g. a long-tail
    pilot). If the researcher wants to fully close it, they flip
    ``is_active`` off.

    ``is_preview=True`` bypasses ``link_closed`` so researchers can
    preview a deactivated study.
    """
    try:
        link = StudyLink.objects.select_related("study", "team").get(slug=slug)
    except StudyLink.DoesNotExist:
        return None, "not_found"

    if is_preview:
        return link, None

    if not link.is_active:
        # Disambiguate: if the link was auto-closed by reaching the
        # target count, surface "study_full" (more informative) rather
        # than the generic "link_closed".
        study = link.study
        if study.actual_completed_count >= study.target_completed_count:
            return link, "study_full"
        return link, "link_closed"
    if link.expires_at and link.expires_at < timezone.now():
        return link, "link_expired"

    return link, None


def _get_or_create_participation(
    request: HttpRequest,
    link: StudyLink,
    is_preview: bool,
    invitation: Invitation | None = None,
) -> tuple[Participation, bool]:
    """Return (participation, created). Uses browser_token cookie if
    present, creates a new one otherwise.

    Honours study quota unless ``is_preview`` is True.

    If ``invitation`` is provided and not yet bound, binds it to the
    new/existing participation and stamps ``accepted_at``.
    """
    raw_token = request.COOKIES.get(COOKIE_NAME)
    existing: Participation | None = None
    if raw_token:
        try:
            token = uuid.UUID(raw_token)
            existing = Participation.objects.filter(study=link.study, browser_token=token).first()
        except (ValueError, TypeError):
            pass

    # If an invitation already resolved to a participation, prefer that
    # (the invited person came back from a different browser/device).
    if invitation is not None and invitation.participation_id:
        already = invitation.participation
        if already and (not existing or already.id == existing.id):
            existing = already

    if existing:
        _maybe_bind_invitation(existing, invitation)
        return existing, False

    # Quota check — only for real participants.
    if not is_preview:
        real_completed = Participation.objects.filter(
            study=link.study,
            is_preview=False,
            status=Participation.Status.COMPLETED,
        ).count()
        if real_completed >= link.study.target_completed_count:
            raise _StudyFullError()

    # If invited, reuse the invitation's trace_id so the whole funnel
    # (delivery → consent → session → insight) shares one trace.
    trace_id = invitation.trace_id if invitation else uuid.uuid4()

    new = Participation.objects.create(
        team=link.team,
        study=link.study,
        participant=None,
        source=Participation.Source.DIRECT_LINK,
        status=Participation.Status.INVITED,
        is_preview=is_preview,
        trace_id=trace_id,
    )
    _maybe_bind_invitation(new, invitation)
    return new, True


def _maybe_bind_invitation(participation: Participation, invitation: Invitation | None) -> None:
    if invitation is None or invitation.participation_id == participation.id:
        return
    invitation.participation = participation
    if invitation.status != Invitation.Status.ACCEPTED:
        invitation.status = Invitation.Status.ACCEPTED
        invitation.accepted_at = timezone.now()
    invitation.save(update_fields=["participation", "status", "accepted_at", "updated_at"])


class _StudyFullError(Exception):
    """Raised when a study has hit its target_completed_count."""


def _ok(
    participation: Participation,
    link: StudyLink,
    next_step: str,
    **extra: Any,
) -> JsonResponse:
    study = link.study
    payload = {
        "ok": True,
        "next_step": next_step,
        "link_mode": link.link_mode,
        "participation": {
            "id": str(participation.id),
            "status": participation.status,
            "is_preview": participation.is_preview,
        },
        "study": {
            "id": str(study.id),
            "name": study.name or "Interview study",
            "research_goal": study.research_goal,
            "interview_mode": study.interview_mode,
            "estimated_minutes": study.estimated_minutes,
        },
        **extra,
    }
    response = JsonResponse(payload)
    response.set_cookie(
        COOKIE_NAME,
        str(participation.browser_token),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="Lax",
        secure=False,  # prod must override with secure=True via nginx
    )
    return response


def _err(code: str, http_status: int = 400, **extra: Any) -> JsonResponse:
    return JsonResponse(
        {"ok": False, "error_code": code, **extra},
        status=http_status,
    )


def _compute_next_step(
    participation: Participation,
    link: StudyLink,
) -> str:
    """Decide which participant scene to show next."""
    if participation.status == Participation.Status.COMPLETED:
        return "thanks"
    if participation.status == Participation.Status.DROPPED:
        return "dropped"

    # Anonymous mode: skip consent/info, go straight to session
    if link.link_mode == StudyLink.LinkMode.ANONYMOUS:
        # Auto-consent
        if participation.consented_at is None:
            participation.consented_at = timezone.now()
            if participation.status == Participation.Status.INVITED:
                participation.status = Participation.Status.CONSENTED
            participation.save(update_fields=["consented_at", "status", "updated_at"])
        return "session"

    # Named mode: need info collection (consent step doubles as info form)
    if participation.consented_at is None:
        return "consent"

    # Has screener on the study?
    has_screener = Screener.objects.filter(study=link.study).exists()
    if has_screener and participation.screener_score is None:
        return "screener"

    return "session"


# ── Endpoints ────────────────────────────────────────────


@csrf_exempt
@require_http_methods(["GET"])
def resolve_link(request: HttpRequest, slug: str) -> JsonResponse:
    """``GET /i/<slug>/`` — the entry point.

    Identifies (or creates) the Participation and returns the study
    context + next_step the frontend should render.

    If ``link.require_invitation`` is set, ``?t=<token>`` must match a
    pending Invitation. Otherwise the link is open (default, backward
    compatible with existing studies).
    """
    is_preview = request.GET.get("preview") == "1"

    link, err = _resolve_link(slug, is_preview=is_preview)
    if err:
        if err == "not_found":
            return _err(err, http_status=404)
        if err == "study_full":
            return _err(err, http_status=409)
        return _err(err, http_status=410)
    assert link is not None

    token = request.GET.get("t")

    invitation, inv_err = _resolve_invitation(link, token)
    if inv_err:
        return _err(inv_err, http_status=403)

    try:
        participation, _created = _get_or_create_participation(
            request, link, is_preview=is_preview, invitation=invitation
        )
    except _StudyFullError:
        return _err("study_full", http_status=409)

    # Record click event (deduped, bot-filtered)
    if not is_preview:
        from merism.participant.link_tracking import record_click

        # Resolve upstream referrer: if ?ref=<participation_id> is present,
        # it means someone shared this link from their session.
        referrer_participation = None
        ref_id = request.GET.get("ref")
        if ref_id:
            referrer_participation = Participation.objects.filter(id=ref_id).first()

        record_click(
            request,
            link,
            participation=participation,
            referrer_participation=referrer_participation,
        )

    return _ok(participation, link, _compute_next_step(participation, link))


@csrf_exempt
@require_http_methods(["POST"])
def post_consent(request: HttpRequest, slug: str) -> JsonResponse:
    """``POST /i/<slug>/consent/`` — record consent + optional participant info.

    Body (for named links): {"name": "...", "contact": "..."}
    """
    link, err = _resolve_link(slug)
    if err:
        if err == "not_found":
            return _err(err, http_status=404)
        if err == "study_full":
            return _err(err, http_status=409)
        return _err(err, http_status=410)
    assert link is not None

    participation = _participation_from_cookie(request, link)
    if participation is None:
        return _err("no_session", http_status=403)

    if participation.consented_at is None:
        participation.consented_at = timezone.now()
        if participation.status == Participation.Status.INVITED:
            participation.status = Participation.Status.CONSENTED
        participation.save(update_fields=["consented_at", "status", "updated_at"])

    # For named links, save participant info
    if link.link_mode == StudyLink.LinkMode.NAMED:
        import json

        try:
            body = json.loads(request.body or b"{}")
        except Exception:
            body = {}
        name = body.get("name", "").strip()
        contact = body.get("contact", "").strip()
        if name or contact:
            participant = Participant.objects.create(
                team=link.team,
                name=name,
                email=contact,
            )
            participation.participant = participant
            participation.save(update_fields=["participant", "updated_at"])

    return _ok(participation, link, _compute_next_step(participation, link))


@csrf_exempt
@require_http_methods(["GET", "POST"])
def screener(request: HttpRequest, slug: str) -> JsonResponse:
    """``GET /i/<slug>/screener/`` → questions.
    ``POST /i/<slug>/screener/`` → submit answers.
    """
    link, err = _resolve_link(slug)
    if err:
        if err == "not_found":
            return _err(err, http_status=404)
        if err == "study_full":
            return _err(err, http_status=409)
        return _err(err, http_status=410)
    assert link is not None

    participation = _participation_from_cookie(request, link)
    if participation is None:
        return _err("no_session", http_status=403)

    screener_obj = Screener.objects.filter(study=link.study).first()
    if screener_obj is None:
        return _err("no_screener", http_status=404)

    if request.method == "GET":
        return JsonResponse(
            {
                "ok": True,
                "questions": screener_obj.questions or [],
            }
        )

    # POST — grade answers.
    try:
        import json

        body = json.loads(request.body or b"{}")
        answers = body.get("answers") or {}
    except Exception:
        return _err("bad_body", http_status=400)

    score, passed = _grade_screener(screener_obj, answers)
    participation.screener_score = score
    participation.status = Participation.Status.SCREENED if passed else Participation.Status.DROPPED
    participation.save(update_fields=["screener_score", "status", "updated_at"])

    return _ok(
        participation,
        link,
        _compute_next_step(participation, link),
        passed=passed,
        score=score,
    )


@csrf_exempt
@require_http_methods(["POST"])
def share_link(request: HttpRequest, slug: str) -> JsonResponse:
    """``POST /i/<slug>/share/`` — record a link copy/share event.

    Body: {"action": "copy" | "share_api" | "forward"}
    """
    link, err = _resolve_link(slug)
    if err:
        if err == "not_found":
            return _err(err, http_status=404)
        return _err(err, http_status=410)
    assert link is not None

    participation = _participation_from_cookie(request, link)

    import json

    try:
        body = json.loads(request.body or b"{}")
    except Exception:
        body = {}
    action = body.get("action", "copy")

    from merism.participant.link_tracking import record_share

    record_share(request, link, action=action, participation=participation)
    return JsonResponse({"ok": True})


@csrf_exempt
@require_http_methods(["POST"])
def start_session(request: HttpRequest, slug: str) -> JsonResponse:
    """``POST /i/<slug>/start/`` — create the InterviewSession.

    Uses the study's current InterviewGuide (is_current=True). The
    frontend then navigates to ``/interview/<session_id>``.
    """
    link, err = _resolve_link(slug)
    if err:
        if err == "not_found":
            return _err(err, http_status=404)
        if err == "study_full":
            return _err(err, http_status=409)
        return _err(err, http_status=410)
    assert link is not None

    participation = _participation_from_cookie(request, link)
    if participation is None:
        return _err("no_session", http_status=403)

    if participation.consented_at is None:
        return _err("consent_required", http_status=412)

    guide = InterviewGuide.objects.filter(study=link.study, is_current=True).order_by("-created_at").first()
    if guide is None:
        guide = InterviewGuide.objects.create(
            team=link.team,
            study=link.study,
            version=f"auto-{uuid.uuid4().hex[:8]}",
            is_current=True,
            language="en",
            sections=[],
        )

    # Reuse existing session if already interviewing.
    existing = (
        InterviewSession.objects.filter(
            participation=participation,
            status__in=[InterviewSession.Status.PENDING, InterviewSession.Status.ACTIVE],
        )
        .order_by("-created_at")
        .first()
    )

    if existing is not None:
        return _ok(
            participation,
            link,
            "session",
            session_id=str(existing.id),
        )

    with transaction.atomic():
        # Allocate the next per-Study interview_number atomically.
        # Lock the Study row so concurrent /start/ calls serialise here.
        study = Study.objects.select_for_update().get(id=link.study_id)
        next_number = (
            InterviewSession.objects.filter(study=study).aggregate(max_n=models.Max("interview_number")).get("max_n")
            or 0
        ) + 1

        session = InterviewSession.objects.create(
            team=link.team,
            study=study,
            participation=participation,
            guide=guide,
            guide_snapshot=guide.sections,
            mode=study.interview_mode,
            status=InterviewSession.Status.PENDING,
            trace_id=participation.trace_id,
            interview_number=next_number,
        )
        participation.status = Participation.Status.INTERVIEWING
        participation.save(update_fields=["status", "updated_at"])

    return _ok(
        participation,
        link,
        "session",
        session_id=str(session.id),
    )


# ── Helpers ──────────────────────────────────────────────


def _participation_from_cookie(request: HttpRequest, link: StudyLink) -> Participation | None:
    raw_token = request.COOKIES.get(COOKIE_NAME)
    if not raw_token:
        return None
    try:
        token = uuid.UUID(raw_token)
    except (ValueError, TypeError):
        return None
    return Participation.objects.filter(study=link.study, browser_token=token).first()


def _grade_screener(screener_obj: Screener, answers: dict[str, Any]) -> tuple[float, bool]:
    """Grade screener answers against the pass_logic.

    Shape of ``screener_obj.pass_logic`` (minimal for now)::

        {
            "pass_threshold": 0.7,          # 0..1
            "question_weights": {
                "q1": 0.5,
                "q2": 0.5
            },
            "correct_answers": {
                "q1": "yes",
                "q2": ["a", "b"]
            }
        }

    If ``pass_logic`` is empty we default to: every question must have
    a non-empty answer; all-answered = pass.
    """
    pass_logic = screener_obj.pass_logic or {}
    questions = screener_obj.questions or []

    if not pass_logic:
        passed = bool(questions) and all(
            answers.get(q.get("id") or str(i)) not in (None, "", []) for i, q in enumerate(questions)
        )
        return (1.0 if passed else 0.0), passed

    correct = pass_logic.get("correct_answers", {})
    weights = pass_logic.get("question_weights", {})
    threshold = float(pass_logic.get("pass_threshold", 0.7))

    total_weight = sum(weights.values()) or 1.0
    score = 0.0
    for qid, expected in correct.items():
        given = answers.get(qid)
        hit = given == expected if not isinstance(expected, list) else given in expected
        if hit:
            score += weights.get(qid, 1.0)
    normalised = score / total_weight
    return normalised, normalised >= threshold
