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
    VAD speaking-start from the client produces an ``InterruptionFrame``
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
    ServerMessage,
    SessionReadyMessage,
    TextInputMessage,
    VadSpeakingStartMessage,
    parse_client_message,
)
from merism.voice import (
    CompositeObserver,
    EndFrame,
    InputAudioRawFrame,
    InterruptionFrame,
    MetricsObserver,
    Pipeline,
    PipelineTask,
    TranscriptionFrame,
    TranscriptRecorder,
)
from merism.voice.processors import (
    ConversationState,
    LLMProcessor,
    STTProcessor,
    TTSProcessor,
    UserIdleDetector,
)
from merism.voice.processors.moderator import ModeratorLLMProcessor

logger = logging.getLogger(__name__)


# Default moderator system prompt — studies override via study.moderator_state.
_DEFAULT_SYSTEM_PROMPT = (
    "You are Merism, a professional qualitative-research interviewer. "
    "Ask one open-ended question at a time, acknowledge answers briefly "
    "before probing, and keep responses under two short sentences."
)


class VoiceConsumer(AsyncWebsocketConsumer):
    """Channels consumer at ``ws://host/ws/sessions/<session_id>/voice``.

    One consumer instance per participant. Builds + runs a
    :class:`~merism.voice.Pipeline` for the lifetime of the WebSocket.
    """

    # ── lifecycle ─────────────────────────────────────────

    async def connect(self) -> None:
        session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.session_id = str(session_id)
        self.session = await self._load_session(self.session_id)
        if self.session is None:
            await self.close(code=4404)
            return

        self.barge_in_enabled: bool = await database_sync_to_async(
            lambda: self.session.study.barge_in_enabled
        )()

        # Pipeline + observers
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

        self._conversation_state = ConversationState()
        # Pick the LLM processor based on whether the session is
        # attached to an InterviewGuide. Guide-backed sessions run
        # through ``ModeratorLLMProcessor`` which threads each
        # turn through ``merism.conductor.moderator.stream_turn`` and
        # logs SessionEvent rows. Guide-less sessions (rare — smoke
        # tests / legacy) fall back to the plain LLMProcessor.
        llm_processor = (
            ModeratorLLMProcessor(session_id=self.session_id)
            if self.session.guide_id is not None
            else LLMProcessor(system_prompt=_DEFAULT_SYSTEM_PROMPT)
        )
        pipeline = Pipeline(
            [
                STTProcessor(),
                llm_processor,
                TTSProcessor(),
                self._conversation_state,
                UserIdleDetector(idle_seconds=12.0),
            ]
        )
        self._task = PipelineTask(pipeline, observer=composite, sample_rate=16000)

        # Observability counters
        self._vad_signals = 0
        self._barge_in_fires = 0

        await self.accept()
        await self._send(
            SessionReadyMessage(
                session_id=self.session_id,
                barge_in_enabled=self.barge_in_enabled,
            )
        )
        await self._task.start()

        logger.info(
            "voice.session.start",
            extra={"session_id": self.session_id, "barge_in_enabled": self.barge_in_enabled},
        )

    async def disconnect(self, code: int) -> None:
        sid = getattr(self, "session_id", "")
        logger.info(
            "voice.session.end",
            extra={
                "session_id": sid,
                "vad_signals": getattr(self, "_vad_signals", 0),
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

    # ── inbound routing ───────────────────────────────────

    async def receive(
        self, text_data: str | None = None, bytes_data: bytes | None = None
    ) -> None:
        if bytes_data is not None:
            # Participant audio — goes into the pipeline as an input frame.
            await self._task.queue_frame(
                InputAudioRawFrame(audio=bytes_data, sample_rate=16000)
            )
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

        if msg_type == "vad_speaking_start":
            await self._handle_barge_in(message)
            return

        if msg_type == "interrupt":
            await self._handle_explicit_interrupt(message)
            return

        if msg_type == "vad_speaking_end":
            # STTProcessor's own VAD handles endpointing; we keep the
            # client hook for future endpointing strategies.
            return

        if msg_type == "text_input":
            await self._handle_text_input(message)
            return

        if msg_type == "attachment_uploaded":
            # TODO: route to Qwen-VL for a frame description, inject as
            # system message. Out of scope for Phase 2.
            return

        if msg_type == "session_start":
            # Already handled server-side in ``connect``. Idempotent noop
            # so clients can re-send on reconnection without erroring.
            return

    # ── specific handlers ─────────────────────────────────

    async def _handle_barge_in(self, message: VadSpeakingStartMessage) -> None:
        """PTT: ``vad_speaking_start`` is now button-driven (not auto-VAD).

        Every event is a deliberate user action so we always respect it,
        independent of the legacy ``barge_in_enabled`` flag. That flag
        only gated the old continuous / auto-VAD mode and is vestigial
        in PTT UX.
        """
        self._vad_signals += 1
        self._barge_in_fires += 1
        played_ms = int(getattr(message, "audio_played_ms", 0) or 0)
        await self._task.queue_frame(InterruptionFrame(audio_played_ms=played_ms))
        logger.info(
            "voice.barge_in.accepted",
            extra={
                "session_id": self.session_id,
                "trigger": "ptt",
                "audio_played_ms": played_ms,
                "total_vad_signals": self._vad_signals,
                "total_barge_ins": self._barge_in_fires,
            },
        )

    async def _handle_explicit_interrupt(self, message: InterruptionMessage) -> None:
        """User hit a cancel button (or similar) — always respected regardless of flag.

        Unlike VAD-driven barge-in, explicit interrupts bypass the per-study
        ``barge_in_enabled`` flag. The user pressed a button; respect them.
        """
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
        """Participants who opt out of voice send text — feed it to the LLM path.

        A :class:`TranscriptionFrame` pushed at the top of the pipeline
        walks through STTProcessor (no-op — STT only reacts to audio)
        and is picked up by LLMProcessor. Exactly equivalent to a final
        STT emission.
        """
        await self._task.queue_frame(TranscriptionFrame(text=message.text))

    # ── helpers ───────────────────────────────────────────

    async def _send(self, message: ServerMessage) -> None:
        try:
            await self.send(text_data=message.model_dump_json())
        except Exception as exc:
            logger.warning("voice.send_failed", extra={"error": str(exc)})

    @database_sync_to_async
    def _load_session(self, session_id: str) -> InterviewSession | None:
        try:
            return (
                InterviewSession.objects.select_related("study", "guide", "participation")
                .get(id=session_id)
            )
        except InterviewSession.DoesNotExist:
            return None

    async def _persist_session_artifacts(self) -> None:
        """Save metrics summary + transcript + recording keys when the session ends."""
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

        # Upload recorded audio synchronously — these are small blobs relative
        # to typical S3 throughput and we want the keys persisted in the same
        # write as metrics/transcript.
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
            await self._write_session(
                session.id, updates, transcript_additions, audio_keys
            )
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
        # ``audio_s3_key`` holds the mic recording; TTS goes into moderator_state
        # for now (add a dedicated column in a later migration if needed).
        if audio_keys.get("mic"):
            s.audio_s3_key = audio_keys["mic"]
            update_fields.append("audio_s3_key")
        if audio_keys.get("tts"):
            state["tts_audio_s3_key"] = audio_keys["tts"]
            s.moderator_state = state
        s.save(update_fields=update_fields)
