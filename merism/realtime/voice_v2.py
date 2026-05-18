"""VoiceConsumer v2 — pipecat-ai 1.2 based.

Drop-in replacement for voice.py. Uses pipecat's Pipeline/PipelineTask
instead of the hand-rolled version. Same WebSocket protocol, same
moderator logic, just a cleaner pipeline backbone.

Route: ws://host/ws/sessions/<session_id>/voice/v2
"""

from __future__ import annotations

import asyncio
import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.pipeline.base_task import PipelineTaskParams

from merism.models import InterviewSession
from merism.voice.services.moderator_processor import ModeratorProcessor
from merism.voice.services.qwen_stt import QwenSTTService
from merism.voice.services.qwen_tts import QwenTTSService
from merism.voice.transport import WebSocketInputTransport, WebSocketOutputTransport

logger = logging.getLogger(__name__)


class VoiceConsumerV2(AsyncWebsocketConsumer):
    """Pipecat-powered voice consumer.

    Pipeline:
        WSInput → QwenSTT → Moderator → QwenTTS → WSOutput
    """

    async def connect(self) -> None:
        session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.session_id = str(session_id)
        self.session = await self._load_session(self.session_id)
        if self.session is None:
            await self.close(code=4404)
            return

        await self.accept()

        # Build pipecat pipeline
        ws_input = WebSocketInputTransport(self, sample_rate=16000)
        self._ws_input = ws_input
        stt = QwenSTTService(sample_rate=16000, language="zh")
        moderator = ModeratorProcessor(session=self.session)
        tts = QwenTTSService(voice="Cherry", sample_rate=24000)
        ws_output = WebSocketOutputTransport(self)

        pipeline = Pipeline([ws_input, stt, moderator, tts, ws_output])

        self._task = PipelineTask(
            pipeline,
            params=PipelineParams(
                audio_in_sample_rate=16000,
                audio_out_sample_rate=24000,
            ),
        )
        asyncio.create_task(self._task.run(PipelineTaskParams(asyncio.get_running_loop())))

        # Send ready message
        await self.send(text_data=json.dumps({
            "type": "session.ready",
            "session_id": self.session_id,
        }))

        logger.info("voice_v2.session.start", extra={"session_id": self.session_id})

    async def disconnect(self, code: int) -> None:
        task = getattr(self, "_task", None)
        if task:
            await task.cancel()
        # Persist final session state
        session = getattr(self, "session", None)
        if session:
            await database_sync_to_async(session.save)()
        logger.info("voice_v2.session.end", extra={"session_id": self.session_id, "code": code})

    async def receive(self, text_data: str | None = None, bytes_data: bytes | None = None) -> None:
        """Handle incoming WebSocket messages."""
        if bytes_data:
            # Feed audio to the input transport's queue
            if hasattr(self, "_ws_input"):
                self._ws_input.push_audio(bytes_data)
        elif text_data:
            try:
                msg = json.loads(text_data)
                msg_type = msg.get("type", "")
                if msg_type == "ping":
                    await self.send(text_data=json.dumps({"type": "pong"}))
            except json.JSONDecodeError:
                pass

    @database_sync_to_async
    def _load_session(self, session_id: str) -> InterviewSession | None:
        try:
            return InterviewSession.objects.select_related("study", "guide").get(id=session_id)
        except InterviewSession.DoesNotExist:
            return None
