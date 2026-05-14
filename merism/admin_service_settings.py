"""Django Admin for ServiceSettings."""

from __future__ import annotations

from typing import Any

from django import forms
from django.contrib import admin

from merism.models.service_settings import ServiceSettings


class ServiceSettingsForm(forms.ModelForm):
    # LLM
    llm_base_url = forms.URLField(required=False, initial="https://api.deepseek.com", label="Base URL")
    llm_api_key = forms.CharField(required=False, widget=forms.PasswordInput(attrs={"autocomplete": "off"}), label="API Key")
    llm_model = forms.CharField(required=False, initial="deepseek-chat", label="Model")
    llm_temperature = forms.FloatField(required=False, initial=0.7, label="Temperature")

    # TTS
    tts_url = forms.CharField(required=False, initial="wss://dashscope.aliyuncs.com/api-ws/v1/realtime", label="WebSocket URL")
    tts_api_key = forms.CharField(required=False, widget=forms.PasswordInput(attrs={"autocomplete": "off"}), label="API Key")
    tts_model = forms.CharField(required=False, initial="qwen3-tts-instruct-flash-realtime", label="Model")
    tts_voice = forms.CharField(required=False, initial="Cherry", label="Voice")

    # STT
    stt_url = forms.CharField(required=False, initial="wss://dashscope.aliyuncs.com/api-ws/v1/realtime", label="WebSocket URL")
    stt_api_key = forms.CharField(required=False, widget=forms.PasswordInput(attrs={"autocomplete": "off"}), label="API Key")
    stt_model = forms.CharField(required=False, initial="qwen3-asr-flash-realtime", label="Model")
    stt_language = forms.CharField(required=False, initial="zh", label="Language")

    # Embedding
    embedding_base_url = forms.URLField(required=False, initial="https://dashscope.aliyuncs.com/compatible-mode/v1", label="Base URL")
    embedding_api_key = forms.CharField(required=False, widget=forms.PasswordInput(attrs={"autocomplete": "off"}), label="API Key")
    embedding_model = forms.CharField(required=False, initial="text-embedding-v3", label="Model")

    class Meta:
        model = ServiceSettings
        fields = ["team"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self._populate("llm", ["base_url", "model", "temperature"])
            self._populate("tts", ["url", "model", "voice"])
            self._populate("stt", ["url", "model", "language"])
            self._populate("embedding", ["base_url", "model"])

    def _populate(self, prefix: str, fields: list[str]) -> None:
        data = getattr(self.instance, prefix, {})
        for f in fields:
            key = f"{prefix}_{f}"
            if key in self.fields and data.get(f):
                self.initial[key] = data[f]

    def save(self, commit: bool = True) -> ServiceSettings:
        instance = super().save(commit=False)

        for prefix, fields in [
            ("llm", ["base_url", "model", "temperature"]),
            ("tts", ["url", "model", "voice"]),
            ("stt", ["url", "model", "language"]),
            ("embedding", ["base_url", "model"]),
        ]:
            data = {}
            for f in fields:
                val = self.cleaned_data.get(f"{prefix}_{f}")
                if val not in (None, ""):
                    data[f] = val
            api_key = self.cleaned_data.get(f"{prefix}_api_key")
            if api_key:
                data["api_key"] = api_key
            if data:
                instance.set_config(prefix, data)
            elif not api_key:
                # Preserve existing encrypted key if no new key entered
                existing = getattr(instance, prefix, {})
                if not data and existing.get("_encrypted_key"):
                    pass  # keep as-is
                else:
                    setattr(instance, prefix, {})

        if commit:
            instance.save()
        return instance


@admin.register(ServiceSettings)
class ServiceSettingsAdmin(admin.ModelAdmin):
    form = ServiceSettingsForm
    list_display = ("team", "llm_", "tts_", "stt_", "updated_at")
    search_fields = ("team__name",)
    readonly_fields = ("id", "created_at", "updated_at")

    fieldsets = (
        ("Team", {"fields": ("team",)}),
        ("LLM (OpenAI-compatible)", {"fields": ("llm_base_url", "llm_api_key", "llm_model", "llm_temperature")}),
        ("TTS (WebSocket Realtime)", {"fields": ("tts_url", "tts_api_key", "tts_model", "tts_voice")}),
        ("STT (WebSocket Realtime)", {"fields": ("stt_url", "stt_api_key", "stt_model", "stt_language")}),
        ("Embedding (OpenAI-compatible)", {"fields": ("embedding_base_url", "embedding_api_key", "embedding_model")}),
        ("Metadata", {"fields": ("id", "created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="LLM")
    def llm_(self, obj: ServiceSettings) -> str:
        return obj.llm.get("model", "—")

    @admin.display(description="TTS")
    def tts_(self, obj: ServiceSettings) -> str:
        return obj.tts.get("model", "—")

    @admin.display(description="STT")
    def stt_(self, obj: ServiceSettings) -> str:
        return obj.stt.get("model", "—")
