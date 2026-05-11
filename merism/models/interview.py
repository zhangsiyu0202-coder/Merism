"""Interview-domain models.

Per ``merism-platform``:
- Req 4/14: ``InterviewGuide`` versioning + ``Question.followup_depth``.
- Req 11-15: ``InterviewSession`` with ``mode ∈ {voice, video}``; audio-only
  mode keeps transcript only (no S3 audio); video mode writes
  ``video_s3_key`` and ``vision_frames``.
- Req 9/10: ``Participation`` records one attempt by one participant
  (status flow: invited → started → consented → screened → interviewing →
  completed / dropped).
- Req 23: Preview mode uses ``Participation.is_preview=True`` with no real
  data retention / analysis / quota consumption.
"""

from __future__ import annotations

import uuid

from django.db import models

from merism.models.study import Study
from merism.models.team import Team, TimestampedModel


class InterviewGuide(TimestampedModel):
    """Versioned interview guide. Finalizing a study produces ``is_current=True``
    for the latest version; historical versions are preserved."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="interview_guides")
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="guides")
    version = models.CharField(max_length=16, default="1.0.0")
    is_current = models.BooleanField(default=True)
    language = models.CharField(max_length=8, default="en")
    # Sections: [{id, title, questions: [{id, text, followup_depth, required,
    # probe_directions, linked_stimulus_ids}]}]
    sections = models.JSONField(default=list)

    class Meta:
        db_table = "merism_interview_guide"
        indexes = [
            models.Index(fields=["study", "is_current"], name="merism_guide_current_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["study", "version"],
                name="merism_guide_unique_version",
            ),
        ]

    def __str__(self) -> str:
        return f"InterviewGuide(study={self.study_id}, v{self.version})"


class Participant(TimestampedModel):
    """A person who participates in research. One Participant can have many
    Participations across many studies.

    Keep PII minimal: we store only what the researcher actually needs to
    correlate sessions. ``external_id`` is whatever identifier the
    recruitment channel uses (Feishu open_id, WeCom user_id, email).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="participants")
    external_id = models.CharField(max_length=200, blank=True, default="", db_index=True)
    email = models.EmailField(blank=True, default="")
    name = models.CharField(max_length=200, blank=True, default="")
    attributes = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "merism_participant"
        indexes = [
            models.Index(fields=["team", "external_id"], name="merism_part_extid_idx"),
        ]

    def __str__(self) -> str:
        return f"Participant({self.name or self.external_id or self.email or 'anon'})"


class Participation(TimestampedModel):
    """One attempt by one Participant to take one Study."""

    class Source(models.TextChoices):
        DIRECT_LINK = "direct_link"
        COWAGENT = "cowagent"
        EMAIL = "email"
        BEHAVIOR_TRIGGER = "behavior_trigger"

    class Status(models.TextChoices):
        INVITED = "invited"
        STARTED = "started"
        CONSENTED = "consented"
        SCREENED = "screened"
        INTERVIEWING = "interviewing"
        COMPLETED = "completed"
        DROPPED = "dropped"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="participations")
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="participations")
    participant = models.ForeignKey(
        Participant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="participations",
    )
    source = models.CharField(max_length=24, choices=Source.choices, default=Source.DIRECT_LINK)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.INVITED)
    # Preview mode (Req 8): set when a researcher tests their own study.
    # Preview participations do not count toward quotas and do not enqueue
    # session analysis.
    is_preview = models.BooleanField(default=False)
    # Attribution back to the specific delivery that invited this participant.
    delivery_id = models.UUIDField(null=True, blank=True, db_index=True)
    # Opaque browser identity — persists across reloads of the same attempt.
    browser_token = models.UUIDField(default=uuid.uuid4, db_index=True)
    trace_id = models.UUIDField(default=uuid.uuid4, db_index=True, editable=False)
    # Timestamp of the consent POST. NULL until consent given.
    consented_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    # Screener outcome cache. NULL = not screened; 0.0 = failed; 1.0 = passed.
    # Anything in between is a weighted score when screener uses weights.
    screener_score = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = "merism_participation"
        indexes = [
            models.Index(fields=["team", "study", "status"], name="merism_ptn_status_idx"),
            models.Index(fields=["delivery_id"], name="merism_ptn_delivery_idx"),
        ]

    def __str__(self) -> str:
        return f"Participation({self.status}, study={self.study_id})"


class InterviewSession(TimestampedModel):
    """A single interview session (one sitting, one participant).

    Voice mode: ``transcript`` only, ``audio_s3_key`` stays empty (audio is
    streamed through STT and discarded).
    Video mode: ``video_s3_key`` populated; ``vision_frames`` holds
    10-second-interval VL descriptions.
    """

    class Mode(models.TextChoices):
        VOICE = "voice"
        VIDEO = "video"
        TEXT = "text"
        OFFLINE = "offline"

    class Status(models.TextChoices):
        PENDING = "pending"
        ACTIVE = "active"
        COMPLETED = "completed"
        FAILED = "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="interview_sessions")
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="interview_sessions")
    participation = models.ForeignKey(
        Participation,
        on_delete=models.CASCADE,
        related_name="sessions",
    )
    guide = models.ForeignKey(
        InterviewGuide,
        on_delete=models.PROTECT,
        related_name="sessions",
    )
    mode = models.CharField(max_length=16, choices=Mode.choices, default=Mode.VOICE)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)

    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    # Transcripts: list of {ts, role, text, question_id?}
    trace_id = models.UUIDField(null=True, blank=True, db_index=True)
    transcript = models.JSONField(default=list, blank=True)
    # Audio never stored (voice mode). Kept as empty for API stability; in
    # rare cases (debugging) might hold a temporary key that's cleaned up.
    audio_s3_key = models.CharField(max_length=512, blank=True, default="")
    # Video only.
    video_s3_key = models.CharField(max_length=512, blank=True, default="")
    # Video mode: [{ts, vl_description}] 10-second interval
    vision_frames = models.JSONField(default=list, blank=True)
    # Conductor-side state (single-call moderator): current_question_id,
    # remaining_followups per question, etc.
    moderator_state = models.JSONField(default=dict, blank=True)
    # Persisted decision log (used by analysis + debugging).
    decision_log = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "merism_interview_session"
        indexes = [
            models.Index(fields=["team", "study", "status"], name="merism_sess_status_idx"),
            models.Index(fields=["participation"], name="merism_sess_ptn_idx"),
        ]

    def __str__(self) -> str:
        return f"InterviewSession({self.mode}, {self.status}, study={self.study_id})"


class InterviewRecording(TimestampedModel):
    """Per-session video recording metadata (separate table so video can be
    deleted independently of session transcripts)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="interview_recordings")
    session = models.OneToOneField(
        InterviewSession,
        on_delete=models.CASCADE,
        related_name="recording",
    )
    video_s3_key = models.CharField(max_length=512)
    duration_s = models.FloatField(null=True, blank=True)
    size_bytes = models.BigIntegerField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = "merism_interview_recording"

    def __str__(self) -> str:
        return f"InterviewRecording(session={self.session_id})"
