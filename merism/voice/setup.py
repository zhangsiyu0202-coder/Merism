"""Voice-mode pipecat pipeline construction.

Centralizes the wiring decisions that previously lived inline in
``merism.realtime.voice.VoiceConsumer.connect``. Voice mode now has a
single entry point — :func:`build_voice_pipeline` — that owns:

- STT / TTS client construction
- v3 vs ad-hoc moderator selection
- Pipeline assembly with the right processor order

Decoupling rationale (per the 2026-05-23 voice refactor):

- ``VoiceConsumer.connect`` used to grow a v1/v3 routing branch and a
  guide_id branch. Every conductor change risked breaking voice.
- The compiled v3 graph used to come from ``conductor.text_adapter``,
  which tied voice mode to HTTP-mode wiring. Now the graph is fetched
  from :func:`merism.conductor.factory.get_graph` (HTTP-neutral) and
  passed explicitly to ``ModeratorProcessor``.
- Tests can swap STT / TTS / graph independently by passing kwargs.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from merism.stt import ParaformerClient
from merism.voice import Pipeline, PipelineTask
from merism.voice.processors import (
    ConversationState,
    LLMProcessor,
    STTProcessor,
    TTSProcessor,
    UserIdleDetector,
)

if TYPE_CHECKING:
    from merism.models import InterviewSession
    from merism.voice.observer import Observer

logger = logging.getLogger(__name__)


_DEFAULT_AD_HOC_SYSTEM_PROMPT = (
    "You are Merism, a professional qualitative-research interviewer. "
    "Ask one open-ended question at a time, acknowledge answers briefly "
    "before probing, and keep responses under two short sentences."
)


def build_voice_pipeline(
    *,
    session: InterviewSession,
    conversation_state: ConversationState | None = None,
    stt_client: ParaformerClient | None = None,
    graph: Any | None = None,
    observer: Observer | None = None,
    sample_rate: int = 16000,
) -> tuple[PipelineTask, ConversationState]:
    """Assemble a voice pipeline for one interview session.

    Returns ``(task, conversation_state)``. ``conversation_state`` is
    surfaced because the consumer needs to read it for state-bearing
    frames (PTT, barge-in, etc.).

    Parameters:
      ``session``: the InterviewSession ORM row, already loaded.
      ``conversation_state``: optional — pass an existing state to share
        across reconnects; default a fresh one.
      ``stt_client``: optional — pass a fake for tests.
      ``graph``: optional — pass a private graph for tests; production
        defaults to the factory-built shared instance via
        ``ModeratorProcessor``'s lazy resolution.
      ``observer``: optional pipecat observer (metrics + transcript).

    Branch selection:
      - Session has ``guide_id`` → v3 ``ModeratorProcessor`` (LangGraph)
      - Session has no guide → ``LLMProcessor`` (ad-hoc chat with the
        default interviewer system prompt; used for preview / smoke)
    """
    conversation_state = conversation_state or ConversationState()
    stt_client = stt_client or ParaformerClient(language="zh", use_server_vad=False)

    if session.guide_id is not None:
        # Local import to keep the heavy conductor graph construction
        # out of the import path for tests that don't exercise it.
        from merism.voice.processors.moderator import ModeratorProcessor

        moderator = ModeratorProcessor(
            session_id=str(session.id),
            graph=graph,  # None → processor's lazy factory call
        )
        # No idle timer on the v3 path. The moderator simply waits for
        # the user. Premature idle fires (auto-submitting empty text)
        # were polluting the transcript and triggering "imaginary"
        # probes from the judge LLM. Long-running stuck sessions are
        # cleaned up by the session-level abandon_stuck_sessions Celery
        # task (2-hour idle).
        pipeline = Pipeline(
            [
                STTProcessor(client=stt_client),
                moderator,
                TTSProcessor(),
                conversation_state,
            ]
        )
    else:
        pipeline = Pipeline(
            [
                STTProcessor(client=stt_client),
                LLMProcessor(system_prompt=_DEFAULT_AD_HOC_SYSTEM_PROMPT),
                TTSProcessor(),
                conversation_state,
                UserIdleDetector(idle_seconds=12.0),
            ]
        )

    task = PipelineTask(pipeline, observer=observer, sample_rate=sample_rate)
    return task, conversation_state


__all__ = ["build_voice_pipeline"]
