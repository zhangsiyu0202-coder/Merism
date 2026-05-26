"""Tests for service configuration."""

from __future__ import annotations

from unittest.mock import patch

from merism.services.configuration.registry import EmbeddingConfig, LLMConfig, STTConfig, TTSConfig


class TestConfigs:
    def test_llm_config_defaults(self):
        c = LLMConfig()
        assert c.base_url == "https://api.deepseek.com"
        assert c.model == "deepseek-chat"

    def test_tts_config_defaults(self):
        c = TTSConfig()
        assert "realtime" in c.url
        assert c.voice == "Cherry"

    def test_stt_config_defaults(self):
        c = STTConfig()
        assert c.language == "zh"
        assert c.use_server_vad is True

    def test_embedding_config_defaults(self):
        c = EmbeddingConfig()
        assert "dashscope" in c.base_url


class TestFactory:
    def test_create_llm(self):
        from merism.services.configuration.factory import create_llm_service

        client = create_llm_service(LLMConfig(api_key="sk-test"))
        assert "deepseek" in str(client.base_url)

    def test_create_embedding(self):
        from merism.services.configuration.factory import create_embedding_service

        client = create_embedding_service(EmbeddingConfig(api_key="sk-test"))
        assert "dashscope" in str(client.base_url)

    def test_create_tts(self):
        from merism.services.configuration.factory import create_tts_service

        with patch("merism.tts.CosyVoiceClient") as m:
            create_tts_service(TTSConfig(api_key="sk-test"))
            m.assert_called_once()

    def test_create_stt(self):
        from merism.services.configuration.factory import create_stt_service

        with patch("merism.stt.ParaformerClient") as m:
            create_stt_service(STTConfig(api_key="sk-test"))
            m.assert_called_once()
