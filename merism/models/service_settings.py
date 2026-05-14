"""Per-team AI service configuration.

One row per team. Stores base_url + model + encrypted api_key for each
service type (LLM, TTS, STT, Embedding).
"""

from __future__ import annotations

from typing import Any

from django.db import models

from merism.models.team import Team, UUIDModel


class ServiceSettings(UUIDModel):
    """Per-team AI service provider selections."""

    team = models.OneToOneField(
        Team,
        on_delete=models.CASCADE,
        related_name="service_settings",
    )
    llm = models.JSONField(default=dict, blank=True)
    tts = models.JSONField(default=dict, blank=True)
    stt = models.JSONField(default=dict, blank=True)
    embedding = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "merism_service_settings"
        verbose_name = "Service Settings"
        verbose_name_plural = "Service Settings"

    def __str__(self) -> str:
        parts = []
        if self.llm.get("model"):
            parts.append(f"LLM={self.llm['model']}")
        if self.tts.get("model"):
            parts.append(f"TTS={self.tts['model']}")
        if self.stt.get("model"):
            parts.append(f"STT={self.stt['model']}")
        return f"ServiceSettings({self.team.name}: {', '.join(parts) or 'unconfigured'})"

    def get_llm_config(self):
        from merism.services.configuration.registry import LLMConfig
        if not self.llm.get("base_url"):
            return None
        return LLMConfig(**{**self.llm, "api_key": self._decrypt_key(self.llm)})

    def get_tts_config(self):
        from merism.services.configuration.registry import TTSConfig
        if not self.tts.get("url"):
            return None
        return TTSConfig(**{**self.tts, "api_key": self._decrypt_key(self.tts)})

    def get_stt_config(self):
        from merism.services.configuration.registry import STTConfig
        if not self.stt.get("url"):
            return None
        return STTConfig(**{**self.stt, "api_key": self._decrypt_key(self.stt)})

    def get_embedding_config(self):
        from merism.services.configuration.registry import EmbeddingConfig
        if not self.embedding.get("base_url"):
            return None
        return EmbeddingConfig(**{**self.embedding, "api_key": self._decrypt_key(self.embedding)})

    def set_config(self, field: str, data: dict[str, Any]) -> None:
        """Encrypt api_key and store."""
        stored = {k: v for k, v in data.items() if k != "api_key"}
        if data.get("api_key"):
            from merism.recruitment.crypto import encrypt_credentials
            stored["_encrypted_key"] = encrypt_credentials({"api_key": data["api_key"]}).decode("latin-1")
        setattr(self, field, stored)

    @staticmethod
    def _decrypt_key(stored: dict[str, Any]) -> str:
        encrypted = stored.get("_encrypted_key")
        if not encrypted:
            return ""
        from merism.recruitment.crypto import decrypt_credentials
        return decrypt_credentials(encrypted.encode("latin-1")).get("api_key", "")
