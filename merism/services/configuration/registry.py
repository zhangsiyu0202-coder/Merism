"""Service configuration schemas.

All LLM/Embedding providers use OpenAI-compatible protocol — one config
class is enough: base_url + api_key + model. TTS/STT have their own
because they use WebSocket (DashScope Realtime protocol).

No per-provider classes. No registry decorators. No discriminated unions.
Just fill in the URL and it works.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    """Any OpenAI-compatible LLM. DeepSeek, Qwen, OpenAI, Moonshot, GLM, etc."""

    base_url: str = "https://api.deepseek.com"
    api_key: str = ""
    model: str = "deepseek-chat"
    temperature: float = 0.7
    max_tokens: int | None = None


class EmbeddingConfig(BaseModel):
    """Any OpenAI-compatible embedding endpoint."""

    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    api_key: str = ""
    model: str = "text-embedding-v3"


class TTSConfig(BaseModel):
    """DashScope Realtime TTS (WebSocket protocol)."""

    url: str = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
    api_key: str = ""
    model: str = "qwen3-tts-instruct-flash-realtime"
    voice: str = "Cherry"
    language: str = "Chinese"


class STTConfig(BaseModel):
    """DashScope Realtime STT (WebSocket protocol)."""

    url: str = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
    api_key: str = ""
    model: str = "qwen3-asr-flash-realtime"
    language: str = "zh"
    use_server_vad: bool = True
