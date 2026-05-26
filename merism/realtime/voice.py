"""WebSocket voice consumer — pipeline-driven orchestration.

Architecture (ADR 0005):

    ┌───── client mic (PCM16) ──────┐
    │  binary frames                 │
    └────────────────────────────────┘
                │
                ▼
    ┌─── VoiceConsumer (WS handler) ───┐
    │   Parse → push frames into       │
    │   ``PipelineTask``               │
    └──────────────────────────────────┘
                │
                ▼
    Pipeline([
        STTProcessor,        # → TranscriptionFrame / InterimTranscriptionFrame
        LLMProcessor,        # → LLMTextFrame (with response_id)
        TTSProcessor,        # → TTSAudioRawFrame
        ConversationState,   # → truncation-aware history (OpenAI-Realtime-style)
        UserIdleDetector,    # → inject synthetic turns on long silence
    ])
                │
                ▼
    Observers fire on every frame push. At end-of-pipe
    (``dst is None``) the ``WebSocketEgressObserver`` serialises
    selected frames to the wire. ``MetricsObserver`` tracks per-turn
    latency. ``TranscriptRecorder`` accumulates the conversation for
    persistence on disconnect.

Barge-in (ADR 0002 + OpenAI Realtime ``conversation.item.truncate``):
    PTT start from the client produces an ``InterruptionFrame``
    carrying ``audio_played_ms`` (client-estimated). TTSProcessor
    converts the played-ms into a ``TruncatedFrame`` which
    ``ConversationState`` uses to trim the stored assistant turn — so
    the LLM's next context reflects what the user actually HEARD.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from pydantic import ValidationError

from merism.models import InterviewSession
from merism.realtime.recording_observer import RecordingObserver
from merism.realtime.voice_egress import WebSocketEgressObserver
from merism.realtime.voice_protocol import (
    ClientMessage,
    ErrorMessage,
    InterruptionMessage,
    PongMessage,
    PttSpeakingStartMessage,
    ServerMessage,
    SessionReadyMessage,
    TextInputMessage,
    parse_client_message,
)
from merism.voice import (
    CompositeObserver,
    EndFrame,
    InputAudioRawFrame,
    InterruptionFrame,
    MetricsObserver,
    TranscriptionFrame,
    TranscriptRecorder,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)

logger = logging.getLogger(__name__)

_DEFAULT_SYSTEM_PROMPT = (
    "You are Merism, a professional qualitative-research interviewer. "
    "Ask one open-ended question at a time, acknowledge answers briefly "
    "before probing, and keep responses under two short sentences."
)


class VoiceConsumer(AsyncWebsocketConsumer):
    """Channels consumer at ``ws://host/ws/sessions/<session_id>/voice``."""

    async def connect(self) -> None:
        session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.session_id = str(session_id)
        self.session = await self._load_session(self.session_id)
        if self.session is None:
            await self.close(code=4404)
            return

        # Barge-in is disabled product-wide (2026-05-25): the AI is
        # never interrupted by an in-flight PTT press. We still
        # accept ``ptt_speaking_start`` to track signal counts for
        # diagnostics, but it never fires an ``InterruptionFrame``.
        # See `_handle_ptt_start` below.

        self._metrics = MetricsObserver()
        self._recorder = TranscriptRecorder()
        self._egress = WebSocketEgressObserver(self)
        self._audio_recorder = RecordingObserver(session_id=self.session_id)
        composite = CompositeObserver(
            self._metrics,
            self._recorder,
            self._egress,
            self._audio_recorder,
        )

        # Pipeline construction is fully owned by ``merism.voice.setup``.
        # This consumer only wires the WebSocket transport — the moderator
        # / engine choice, the processor order, the v3-vs-ad-hoc branch
        # all live in one place. Decouples voice mode from changes to
        # ``conductor`` internals (per the 2026-05-23 refactor).
        from merism.voice.setup import build_voice_pipeline

        self._task, self._conversation_state = build_voice_pipeline(
            session=self.session,
            observer=composite,
        )

        self._ptt_signals = 0
        self._barge_in_fires = 0

        await self.accept()
        await self._send(
            SessionReadyMessage(
                session_id=self.session_id,
            )
        )
        await self._task.start()

        logger.info(
            "voice.session.start",
            extra={
                "session_id": self.session_id,
            },
        )

    async def disconnect(self, code: int) -> None:
        sid = getattr(self, "session_id", "")
        logger.info(
            "voice.session.end",
            extra={
                "session_id": sid,
                "ptt_signals": getattr(self, "_ptt_signals", 0),
                "barge_in_fires": getattr(self, "_barge_in_fires", 0),
                "close_code": code,
            },
        )
        task = getattr(self, "_task", None)
        if task is not None:
            try:
                await task.queue_frame(EndFrame())
                await task.stop()
            except Exception as exc:
                logger.warning("voice.session.stop_failed", extra={"error": str(exc)})

        await self._persist_session_artifacts()

    async def receive(self, text_data: str | None = None, bytes_data: bytes | None = None) -> None:
        if bytes_data is not None:
            await self._task.queue_frame(InputAudioRawFrame(audio=bytes_data, sample_rate=16000))
            return

        if text_data is None:
            return

        try:
            raw = json.loads(text_data)
            message: ClientMessage = parse_client_message(raw)
        except (json.JSONDecodeError, ValidationError) as exc:
            await self._send(ErrorMessage(code="malformed_message", message=str(exc)[:200]))
            return

        await self._dispatch_client_message(message)

    async def _dispatch_client_message(self, message: ClientMessage) -> None:
        msg_type = message.type

        if msg_type == "ping":
            await self._send(PongMessage())
            return

        if msg_type == "ptt_speaking_start":
            await self._handle_ptt_start(message)
            return

        if msg_type == "interrupt":
            await self._handle_explicit_interrupt(message)
            return

        if msg_type == "ptt_speaking_end":
            await self._commit_ptt_turn()
            return

        if msg_type == "text_input":
            await self._handle_text_input(message)
            return

        if msg_type == "attachment_uploaded":
            return

        if msg_type == "session_start":
            return

    async def _handle_ptt_start(self, message: PttSpeakingStartMessage) -> None:
        # Always queue UserStartedSpeakingFrame so STT opens its turn.
        # We never fire an InterruptionFrame from a PTT press — barge-in
        # is disabled product-wide. The frontend disables the PTT
        # button while the bot is speaking, so this branch is mostly
        # for diagnostics. The ``audio_played_ms`` field is kept for
        # parity with the explicit-interrupt path.
        self._ptt_signals += 1
        await self._task.queue_frame(UserStartedSpeakingFrame())
        logger.info(
            "voice.ptt.accepted",
            extra={
                "session_id": self.session_id,
                "audio_played_ms": int(getattr(message, "audio_played_ms", 0) or 0),
                "total_ptt_signals": self._ptt_signals,
            },
        )

    async def _handle_explicit_interrupt(self, message: InterruptionMessage) -> None:
        self._barge_in_fires += 1
        played_ms = int(message.audio_played_ms or 0)
        await self._task.queue_frame(InterruptionFrame(audio_played_ms=played_ms))
        logger.info(
            "voice.barge_in.accepted",
            extra={
                "session_id": self.session_id,
                "trigger": "explicit",
                "audio_played_ms": played_ms,
                "total_barge_ins": self._barge_in_fires,
            },
        )

    async def _handle_text_input(self, message: TextInputMessage) -> None:
        await self._task.queue_frame(TranscriptionFrame(text=message.text))

    async def _commit_ptt_turn(self) -> None:
        await self._task.queue_frame(UserStoppedSpeakingFrame())

    async def _send(self, message: ServerMessage) -> None:
        try:
            await self.send(text_data=message.model_dump_json())
        except Exception as exc:
            logger.warning("voice.send_failed", extra={"error": str(exc)})

    @database_sync_to_async
    def _load_session(self, session_id: str) -> InterviewSession | None:
        try:
            return InterviewSession.objects.select_related("study", "guide", "participation").get(id=session_id)
        except InterviewSession.DoesNotExist:
            return None

    async def _persist_session_artifacts(self) -> None:
        session = getattr(self, "session", None)
        if session is None:
            return

        metrics = getattr(self, "_metrics", None)
        recorder = getattr(self, "_recorder", None)
        convo = getattr(self, "_conversation_state", None)
        audio_recorder = getattr(self, "_audio_recorder", None)

        updates: dict[str, Any] = {}
        if metrics is not None:
            updates["metrics"] = metrics.summary()
        if convo is not None:
            snapshot = convo.snapshot()
            updates["conversation"] = [
                {
                    "id": it.id,
                    "role": it.role,
                    "text": it.text,
                    "truncated": it.truncated,
                }
                for it in snapshot.items
            ]

        transcript_additions = recorder.drain() if recorder is not None else []

        audio_keys: dict[str, str] = {}
        if audio_recorder is not None:
            try:
                audio_keys = await database_sync_to_async(audio_recorder.finalize)()
            except Exception as exc:
                logger.warning(
                    "voice.recording.finalize_failed",
                    extra={"error": str(exc), "session_id": self.session_id},
                )

        try:
            await self._write_session(session.id, updates, transcript_additions, audio_keys)
        except Exception as exc:
            logger.warning(
                "voice.session.persist_failed",
                extra={"error": str(exc), "session_id": self.session_id},
            )

    @database_sync_to_async
    def _write_session(
        self,
        session_id: str,
        moderator_state_updates: dict[str, Any],
        transcript_additions: list[dict[str, str]],
        audio_keys: dict[str, str],
    ) -> None:
        if not moderator_state_updates and not transcript_additions and not audio_keys:
            return
        s = InterviewSession.objects.get(id=session_id)
        state = s.moderator_state or {}
        state.update(moderator_state_updates)
        s.moderator_state = state
        if transcript_additions:
            s.transcript = (s.transcript or []) + transcript_additions
        update_fields = ["moderator_state", "transcript", "updated_at"]
        if audio_keys.get("mic"):
            s.audio_s3_key = audio_keys["mic"]
            update_fields.append("audio_s3_key")
        if audio_keys.get("tts"):
            state["tts_audio_s3_key"] = audio_keys["tts"]
            s.moderator_state = state
        s.save(update_fields=update_fields)
