"""Merism DRF serializers.

One file per domain in the long run; for MVP we co-locate them so imports
stay shallow. Grouped by Merism domain (study / interview / knowledge /
recruitment / report / memory).

Validation rules enforced here:
- ``Study.research_goal`` must be non-empty (PRODUCT.md §1 — the North Star).
- ``StudyReport.content`` is validated against
  :func:`merism.reports.schema.validate_study_report_content`.
- Every tenant model injects ``team`` from the serializer context.
- ``ChannelConfig`` returns masked credentials to non-admins (Req 7.4).
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from merism.models import (
    AgentMemory,
    ChannelConfig,
    Concept,
    ConceptBlock,
    Conversation,
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
    Team,
)
from merism.recruitment.crypto import decrypt_credentials, encrypt_credentials
from merism.reports.schema import validate_blocks_list, validate_study_report_content


# ── Team ───────────────────────────────────────────────────


class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ["id", "name", "organization", "created_at"]
        read_only_fields = ["id", "organization", "created_at"]


# ── Study domain ───────────────────────────────────────────


class StudySerializer(serializers.ModelSerializer):
    class Meta:
        model = Study
        fields = [
            "id",
            "name",
            "research_goal",
            "research_objectives",
            "research_background",
            "hypothesis",
            "success_metrics",
            "status",
            "interview_mode",
            "estimated_minutes",
            "barge_in_enabled",
            "target_audience",
            "target_completed_count",
            "recruitment_quotas",
            "codebook",
            "slug",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]

    def validate_research_goal(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Research goal is required (PRODUCT.md §1).")
        return value

    def validate_research_objectives(self, value: list) -> list:
        if not isinstance(value, list):
            raise serializers.ValidationError("research_objectives must be a list of strings.")
        cleaned: list[str] = []
        for i, item in enumerate(value):
            if not isinstance(item, str):
                raise serializers.ValidationError(
                    f"research_objectives[{i}] must be a string, got {type(item).__name__}."
                )
            stripped = item.strip()
            if stripped:  # drop blanks silently — lets the editor delete rows
                cleaned.append(stripped)
        return cleaned


class StudyLinkSerializer(serializers.ModelSerializer):
    url_path = serializers.ReadOnlyField()

    class Meta:
        model = StudyLink
        fields = ["id", "study", "slug", "is_active", "url_path", "created_at"]
        read_only_fields = ["id", "slug", "url_path", "created_at"]


class StudyTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudyTemplate
        fields = [
            "id",
            "name",
            "description",
            "category",
            "interview_mode",
            "payload",
            "is_system",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class StudyTriggerSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudyTrigger
        fields = [
            "id",
            "study",
            "condition_type",
            "event_name",
            "predicate",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ScreenerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Screener
        fields = ["id", "study", "questions", "pass_logic", "created_at"]
        read_only_fields = ["id", "created_at"]


class StimulusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stimulus
        fields = [
            "id",
            "study",
            "kind",
            "title",
            "description",
            "content",
            "linked_question_ids",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


# ── Interview domain ───────────────────────────────────────


class InterviewGuideSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterviewGuide
        fields = [
            "id",
            "study",
            "version",
            "is_current",
            "language",
            "sections",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_sections(self, value: Any) -> list[dict[str, Any]]:
        from merism.interview_guide import validate_sections

        return validate_sections(value)


class ParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Participant
        fields = ["id", "external_id", "email", "name", "attributes", "created_at"]
        read_only_fields = ["id", "created_at"]


class ParticipationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Participation
        fields = [
            "id",
            "study",
            "participant",
            "source",
            "status",
            "is_preview",
            "delivery_id",
            "created_at",
        ]
        read_only_fields = ["id", "browser_token", "created_at"]


class InterviewSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterviewSession
        fields = [
            "id",
            "study",
            "participation",
            "guide",
            "mode",
            "status",
            "started_at",
            "ended_at",
            "transcript",
            "video_s3_key",
            "vision_frames",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "audio_s3_key",  # voice mode never stores audio (PRODUCT.md Req 12.4)
            "video_s3_key",
            "vision_frames",
            "moderator_state",
            "decision_log",
            "created_at",
            "updated_at",
        ]


class InterviewSessionListSerializer(serializers.ModelSerializer):
    """Lighter ``InterviewSession`` shape for list endpoints.

    Transcripts + vision_frames + decision_log can be very large
    (>1 MB per session for long interviews). The list endpoint omits
    them — callers that need the full payload hit ``retrieve``.
    Derived fields (``turn_count``, ``duration_seconds``) give the
    list UI enough to render per-row chips without paying the cost.
    """

    turn_count = serializers.SerializerMethodField()
    duration_seconds = serializers.SerializerMethodField()

    class Meta:
        model = InterviewSession
        fields = [
            "id",
            "study",
            "participation",
            "guide",
            "mode",
            "status",
            "started_at",
            "ended_at",
            "turn_count",
            "duration_seconds",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_turn_count(self, obj: InterviewSession) -> int:
        transcript = obj.transcript or []
        return len(transcript) if isinstance(transcript, list) else 0

    def get_duration_seconds(self, obj: InterviewSession) -> int | None:
        if obj.started_at and obj.ended_at:
            delta = (obj.ended_at - obj.started_at).total_seconds()
            return int(delta) if delta >= 0 else 0
        return None


# ── Knowledge domain ───────────────────────────────────────


class KnowledgeChunkSerializer(serializers.ModelSerializer):
    document_title = serializers.CharField(source="document.title", read_only=True)
    source_type = serializers.CharField(source="document.source_type", read_only=True)
    source_id = serializers.CharField(source="document.source_id", read_only=True)

    class Meta:
        model = KnowledgeChunk
        fields = [
            "id",
            "document",
            "document_title",
            "source_type",
            "source_id",
            "chunk_index",
            "content",
            "metadata",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class KnowledgeDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeDocument
        fields = [
            "id",
            "title",
            "source_type",
            "source_id",
            "status",
            "study",
            "session",
            "metadata",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


# ── Recruitment domain ─────────────────────────────────────


class ChannelConfigSerializer(serializers.ModelSerializer):
    """Credentials are write-only (plaintext in) and masked on read."""

    credentials = serializers.DictField(write_only=True, required=False)
    credentials_masked = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ChannelConfig
        fields = [
            "id",
            "channel_type",
            "name",
            "status",
            "credentials",
            "credentials_masked",
            "last_healthy_at",
            "last_error",
            "consecutive_failures",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "last_healthy_at",
            "last_error",
            "consecutive_failures",
            "created_at",
            "updated_at",
        ]

    def get_credentials_masked(self, obj: ChannelConfig) -> dict[str, Any]:
        if not obj.credentials_encrypted:
            return {}
        try:
            plain = decrypt_credentials(obj.credentials_encrypted)
        except Exception:
            return {}
        return {k: _mask(v) for k, v in plain.items()}

    def create(self, validated_data: dict[str, Any]) -> ChannelConfig:
        creds = validated_data.pop("credentials", None) or {}
        instance = super().create(validated_data)
        if creds:
            instance.credentials_encrypted = encrypt_credentials(creds)
            instance.save(update_fields=["credentials_encrypted"])
        return instance

    def update(self, instance: ChannelConfig, validated_data: dict[str, Any]) -> ChannelConfig:
        creds = validated_data.pop("credentials", None)
        instance = super().update(instance, validated_data)
        if creds is not None:
            instance.credentials_encrypted = encrypt_credentials(creds)
            instance.save(update_fields=["credentials_encrypted"])
        return instance


def _mask(value: Any) -> str:
    text = str(value)
    if len(text) <= 4:
        return "****"
    return f"****{text[-4:]}"


class MessageTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageTemplate
        fields = ["id", "name", "channel_type", "content", "is_system", "created_at"]
        read_only_fields = ["id", "is_system", "created_at"]

    def validate_content(self, value: str) -> str:
        required = ["{{study_name}}", "{{study_link}}"]
        missing = [p for p in required if p not in value]
        if missing:
            raise serializers.ValidationError(
                f"Template missing required placeholder(s): {', '.join(missing)}"
            )
        return value


class RecruitmentBroadcastSerializer(serializers.ModelSerializer):
    channel_name = serializers.CharField(source="channel.name", read_only=True)

    class Meta:
        model = RecruitmentBroadcast
        fields = [
            "id",
            "study",
            "study_link",
            "channel",
            "channel_name",
            "template",
            "status",
            "approved_snapshot",
            "counters",
            "retry_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "counters",
            "retry_count",
            "created_at",
            "updated_at",
        ]


class DeliveryRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryRecord
        fields = [
            "id",
            "broadcast",
            "recipient_id",
            "recipient_kind",
            "status",
            "message_id",
            "error",
            "sent_at",
            "delivered_at",
            "retry_count",
        ]
        read_only_fields = fields  # deliveries are fully system-managed


# ── Report domain ──────────────────────────────────────────


class SessionInsightSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionInsight
        fields = [
            "id",
            "session",
            "summary",
            "highlights",
            "tags",
            "extracted_tasks",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class StudyReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudyReport
        fields = [
            "id",
            "study",
            "status",
            "content",
            "charts",
            "generated_by",
            "generated_at",
        ]
        read_only_fields = ["id", "generated_at"]

    def validate_content(self, value: dict[str, Any]) -> dict[str, Any]:
        return validate_study_report_content(value)


class CustomReportQuerySerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomReportQuery
        fields = [
            "id",
            "study",
            "question",
            "answer_markdown",
            "chart_spec",
            "citations",
            "pinned",
            "created_at",
        ]
        read_only_fields = ["id", "answer_markdown", "chart_spec", "citations", "created_at"]


# ── MEM AI / memory ────────────────────────────────────────


class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = ["id", "title", "metadata", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class AgentMemorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentMemory
        fields = ["id", "content", "metadata", "created_at"]
        read_only_fields = ["id", "created_at"]


# ── Concept Testing 2.0 ────────────────────────────────────


class ConceptSerializer(serializers.ModelSerializer):
    stimulus_title = serializers.CharField(source="stimulus.title", read_only=True)
    stimulus_kind = serializers.CharField(source="stimulus.kind", read_only=True)

    class Meta:
        model = Concept
        fields = [
            "id",
            "block",
            "stimulus",
            "stimulus_title",
            "stimulus_kind",
            "label",
            "rank",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "stimulus_title", "stimulus_kind", "created_at", "updated_at"]


class ConceptBlockSerializer(serializers.ModelSerializer):
    concepts = ConceptSerializer(many=True, read_only=True)
    concept_count = serializers.IntegerField(source="concepts.count", read_only=True)

    class Meta:
        model = ConceptBlock
        fields = [
            "id",
            "study",
            "title",
            "description",
            "rotation",
            "show_counter_chip",
            "concepts",
            "concept_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "concepts", "concept_count", "created_at", "updated_at"]


class InboxItemSerializer(serializers.ModelSerializer):
    """Read-only list serializer for researcher inbox."""

    class Meta:
        model = __import__("merism.models", fromlist=["InboxItem"]).InboxItem
        fields = ("id", "kind", "ref_kind", "ref_id", "title", "body", "payload", "read_by", "trace_id", "created_at")
        read_only_fields = ("id", "created_at")
