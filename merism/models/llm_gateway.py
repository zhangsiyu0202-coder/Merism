"""LLM Gateway data models.

Three tables:
- :class:`LLMProvider` — upstream AI service credentials + config
- :class:`LLMRoute`    — maps logical_name (chat/asr_realtime/…) → provider
- :class:`LLMBudget`   — per-team monthly spend cap
"""

from __future__ import annotations

from decimal import Decimal

from django.db import models

from merism.models.team import Team, UUIDModel


class LLMProvider(UUIDModel):
    """An upstream AI provider's connection config.

    Credentials are Fernet-encrypted at rest (reuses
    ``merism.recruitment.crypto``). The ``protocol`` field determines
    which adapter handles the call:

    - ``http``  → LiteLLM (covers 100+ OpenAI-compatible providers)
    - ``ws``    → Reuse merism/stt.py or merism/tts.py (OpenAI Realtime protocol)
    """

    class Protocol(models.TextChoices):
        HTTP = "http", "HTTP (OpenAI-compatible via LiteLLM)"
        WS = "ws", "WebSocket Realtime (OpenAI Realtime protocol)"

    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="llm_providers",
        null=True,
        blank=True,
        help_text="Null = global default available to all teams.",
    )
    display_name = models.CharField(max_length=128, help_text="Human label, e.g. 'DeepSeek 生产账号'")
    protocol = models.CharField(max_length=8, choices=Protocol.choices)
    base_url = models.URLField(max_length=512, help_text="e.g. https://api.deepseek.com or wss://dashscope...")
    model = models.CharField(max_length=128, help_text="Model identifier sent to the provider.")
    credentials_encrypted = models.BinaryField(
        help_text="Fernet-encrypted API key. Use merism.recruitment.crypto.encrypt/decrypt."
    )
    extra_headers = models.JSONField(
        default=dict,
        blank=True,
        help_text="Optional headers (e.g. OpenAI-Beta for realtime).",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "merism_llm_provider"
        indexes = [
            models.Index(fields=["team", "is_active"], name="llmprov_team_active_idx"),
        ]

    def __str__(self) -> str:
        scope = f"team={self.team_id}" if self.team_id else "global"
        return f"LLMProvider({self.display_name}, {self.protocol}, {scope})"


class LLMRoute(UUIDModel):
    """Maps a logical capability name to a primary (+ optional fallback) provider.

    Logical names:
        chat, reasoner, embedding, vision,
        asr_realtime, tts_realtime, omni_realtime
    """

    class LogicalName(models.TextChoices):
        CHAT = "chat", "Chat"
        REASONER = "reasoner", "Reasoner"
        EMBEDDING = "embedding", "Embedding"
        VISION = "vision", "Vision"
        ASR_REALTIME = "asr_realtime", "ASR Realtime"
        TTS_REALTIME = "tts_realtime", "TTS Realtime"
        OMNI_REALTIME = "omni_realtime", "Omni Realtime"

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="llm_routes")
    logical_name = models.CharField(max_length=32, choices=LogicalName.choices)
    primary = models.ForeignKey(
        LLMProvider,
        on_delete=models.PROTECT,
        related_name="primary_routes",
    )
    fallback = models.ForeignKey(
        LLMProvider,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="fallback_routes",
    )
    # Tuning knobs (HTTP only; WS ignores these)
    temperature = models.FloatField(default=0.7)
    max_output_tokens = models.PositiveIntegerField(null=True, blank=True)
    timeout_seconds = models.PositiveIntegerField(default=30)
    max_retries = models.PositiveIntegerField(default=2)

    class Meta:
        db_table = "merism_llm_route"
        unique_together = [("team", "logical_name")]

    def __str__(self) -> str:
        return f"LLMRoute({self.team_id}/{self.logical_name} → {self.primary.display_name})"


class LLMBudget(UUIDModel):
    """Per-team monthly LLM spend cap.

    ``hard_limit_action`` controls what happens when the cap is hit:
    - alert_only: log + notify, don't block (default for first release)
    - degrade: switch to cheapest model automatically
    - block: reject new LLM requests with BudgetExceededError
    """

    class Action(models.TextChoices):
        ALERT_ONLY = "alert_only", "Alert only (don't block)"
        DEGRADE = "degrade", "Downgrade to cheapest model"
        BLOCK = "block", "Block new requests"

    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="llm_budgets")
    period = models.CharField(max_length=7, help_text="YYYY-MM format, e.g. '2026-05'")
    monthly_cap_usd = models.DecimalField(max_digits=10, decimal_places=2)
    soft_limit_pct = models.PositiveIntegerField(
        default=80,
        help_text="Percentage of cap at which a warning is sent.",
    )
    hard_limit_action = models.CharField(
        max_length=16,
        choices=Action.choices,
        default=Action.ALERT_ONLY,
    )
    current_spent_usd = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=Decimal("0"),
        help_text="Periodically reconciled from Langfuse. Not real-time authoritative.",
    )

    class Meta:
        db_table = "merism_llm_budget"
        unique_together = [("team", "period")]

    def __str__(self) -> str:
        return f"LLMBudget({self.team_id}/{self.period}: ${self.current_spent_usd}/${self.monthly_cap_usd})"

    @property
    def is_over_soft_limit(self) -> bool:
        if self.monthly_cap_usd == 0:
            return False
        return (self.current_spent_usd / self.monthly_cap_usd * 100) >= self.soft_limit_pct

    @property
    def is_over_hard_limit(self) -> bool:
        return self.current_spent_usd >= self.monthly_cap_usd
