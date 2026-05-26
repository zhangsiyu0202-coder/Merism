"""Runtime configuration for the v3 conductor.

Pattern reference: Google's
``gemini-fullstack-langgraph-quickstart/configuration.py``. A Pydantic
``BaseModel`` enumerates every knob the engine has, with sane defaults.
``from_runnable_config()`` resolves overrides in precedence order:

1. **Environment variable** — name is the field uppercased
   (e.g. ``JUDGE_MODEL``). Always wins when set.
2. **RunnableConfig.configurable** — per-invocation override passed by the
   caller (e.g. a per-team admin override stored on the ``Team`` model).
3. **Field default** — the ``Field(default=...)`` value below.

Every node looks up its config at the top of the function:

    cfg = Configuration.from_runnable_config(config)
    llm = build_llm(cfg.judge_model, temperature=cfg.judge_temperature)

Constructing the LLM inside the node (rather than at module top) is
deliberate — it lets us swap models per call without process restarts and
makes node tests trivial to mock.
"""

from __future__ import annotations

import os
from typing import Any

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field


class Configuration(BaseModel):
    """Per-invocation v3 engine configuration.

    All fields have defaults — ``Configuration()`` is always constructible.
    Field-level constraints (``ge`` / ``le``) trip Pydantic validation when
    overrides arrive out of range.
    """

    model_config = ConfigDict(extra="forbid")

    judge_model: str = Field(
        default="deepseek-chat",
        description="Model used by judge_standard / judge_deep nodes.",
    )
    judge_temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        description="Sampling temperature for judge nodes (deterministic by default).",
    )
    standard_followups: int = Field(
        default=2,
        ge=0,
        le=10,
        description="Max follow-up probes per question in 'standard' mode.",
    )
    deep_followups: int = Field(
        default=4,
        ge=0,
        le=10,
        description="Max follow-up probes per question in 'deep' mode.",
    )

    @classmethod
    def from_runnable_config(cls, config: RunnableConfig | None) -> Configuration:
        """Build a :class:`Configuration` from env vars and (optional)
        ``RunnableConfig.configurable``. Env wins over configurable.

        Raises :class:`pydantic.ValidationError` if any override is out of
        bounds (e.g. ``JUDGE_TEMPERATURE=99``).
        """
        configurable: dict[str, Any] = {}
        if config and "configurable" in config:
            configurable = dict(config["configurable"])

        raw: dict[str, Any] = {}
        for name in cls.model_fields:
            env_value = os.environ.get(name.upper())
            if env_value is not None:
                raw[name] = env_value
                continue
            if name in configurable:
                raw[name] = configurable[name]
        return cls(**raw)


__all__ = ["Configuration"]
