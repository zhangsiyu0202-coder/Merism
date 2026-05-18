"""Interview voice pipeline factory — assembles pipecat components.

Usage (from the WebSocket consumer):

    pipeline_task = await create_interview_pipeline(session, websocket)
    await pipeline_task.run()
"""

from __future__ import annotations

import logging

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineParams, PipelineTask

from merism.models import InterviewSession
from merism.voice.services.moderator_processor import ModeratorProcessor
from merism.voice.services.qwen_stt import QwenSTTService
from merism.voice.services.qwen_tts import QwenTTSService
from merism.voice.transport import WebSocketTransport

logger = logging.getLogger(__name__)


async def create_interview_pipeline(
    session: InterviewSession,
    websocket,
    *,
    stt_sample_rate: int = 16000,
    tts_sample_rate: int = 24000,
    voice: str = "Cherry",
) -> PipelineTask:
    """Create and return a ready-to-run pipeline task.

    Pipeline:
        WebSocket Input → STT → Moderator → TTS → WebSocket Output
    """
    transport = WebSocketTransport(websocket, sample_rate=stt_sample_rate)

    stt = QwenSTTService(sample_rate=stt_sample_rate, language="zh")
    moderator = ModeratorProcessor(session=session)
    tts = QwenTTSService(voice=voice, sample_rate=tts_sample_rate)

    pipeline = Pipeline(
        [
            transport.input(),   # AudioRawFrame from client
            stt,                 # AudioRawFrame → TranscriptionFrame
            moderator,           # TranscriptionFrame → TextFrame
            tts,                 # TextFrame → TTSAudioRawFrame
            transport.output(),  # TTSAudioRawFrame → WebSocket
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=stt_sample_rate,
            audio_out_sample_rate=tts_sample_rate,
        ),
    )

    return task
