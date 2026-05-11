"""Frame-based voice pipeline — pipecat-inspired surgical port.

Public surface kept tight. Everything interesting imports from here::

    from merism.voice import (
        Pipeline, PipelineTask, PipelineRunner,
        FrameProcessor, FrameDirection,
        TranscriptionFrame, LLMTextFrame, TTSAudioRawFrame,
        MetricsObserver, TranscriptRecorder,
    )
"""

from __future__ import annotations

from .frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    CancelFrame,
    ControlFrame,
    DataFrame,
    EndFrame,
    ErrorFrame,
    Frame,
    FunctionCallFrame,
    FunctionCallResultFrame,
    InputAudioRawFrame,
    InterimTranscriptionFrame,
    InterruptionFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    MetricsFrame,
    OutputAudioRawFrame,
    StartFrame,
    StimulusShowFrame,
    SystemFrame,
    TTSAudioRawFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
    TTSTextFrame,
    TranscriptionFrame,
    TruncatedFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from .observer import (
    CompositeObserver,
    MetricsObserver,
    Observer,
    StructlogObserver,
    TranscriptRecorder,
)
from .pipeline import (
    FrameDirection,
    FrameProcessor,
    Pipeline,
    PipelineRunner,
    PipelineTask,
)

__all__ = [
    # frames
    "BotStartedSpeakingFrame",
    "BotStoppedSpeakingFrame",
    "CancelFrame",
    "ControlFrame",
    "DataFrame",
    "EndFrame",
    "ErrorFrame",
    "Frame",
    "FunctionCallFrame",
    "FunctionCallResultFrame",
    "InputAudioRawFrame",
    "InterimTranscriptionFrame",
    "InterruptionFrame",
    "LLMFullResponseEndFrame",
    "LLMFullResponseStartFrame",
    "LLMTextFrame",
    "MetricsFrame",
    "OutputAudioRawFrame",
    "StartFrame",
    "StimulusShowFrame",
    "SystemFrame",
    "TTSAudioRawFrame",
    "TTSStartedFrame",
    "TTSStoppedFrame",
    "TTSTextFrame",
    "TranscriptionFrame",
    "TruncatedFrame",
    "UserStartedSpeakingFrame",
    "UserStoppedSpeakingFrame",
    # observers
    "CompositeObserver",
    "MetricsObserver",
    "Observer",
    "StructlogObserver",
    "TranscriptRecorder",
    # pipeline
    "FrameDirection",
    "FrameProcessor",
    "Pipeline",
    "PipelineRunner",
    "PipelineTask",
]
