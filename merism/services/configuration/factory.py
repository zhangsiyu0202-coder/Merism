"""Service Factory — instantiate clients from config."""

from __future__ import annotations

from typing import Any

from merism.services.configuration.registry import (
    EmbeddingConfig,
    LLMConfig,
    STTConfig,
    TTSConfig,
)


def create_llm_service(config: LLMConfig, *, async_: bool = False) -> Any:
    from openai import AsyncOpenAI, OpenAI

    cls = AsyncOpenAI if async_ else OpenAI
    return cls(api_key=config.api_key, base_url=config.base_url)


def create_tts_service(config: TTSConfig) -> Any:
    from merism.tts import CosyVoiceClient

    return CosyVoiceClient(
        api_key=config.api_key,
        model=config.model,
        voice=config.voice,
        language_type=config.language,
        url=config.url,
    )


def create_stt_service(config: STTConfig) -> Any:
    from merism.stt import ParaformerClient

    return ParaformerClient(
        api_key=config.api_key,
        model=config.model,
        language=config.language,
        use_server_vad=config.use_server_vad,
        url=config.url,
    )


def create_embedding_service(config: EmbeddingConfig, *, async_: bool = False) -> Any:
    from openai import AsyncOpenAI, OpenAI

    cls = AsyncOpenAI if async_ else OpenAI
    return cls(api_key=config.api_key, base_url=config.base_url)
