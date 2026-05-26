"""Configuration loading from env + RunnableConfig.configurable."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from merism.conductor.configuration import Configuration


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip Configuration-related env vars before every test."""
    for name in Configuration.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)


class TestDefaults:
    def test_no_env_no_config(self) -> None:
        cfg = Configuration.from_runnable_config(None)
        assert cfg.judge_model == "deepseek-chat"
        assert cfg.judge_temperature == 0.0
        assert cfg.standard_followups == 2
        assert cfg.deep_followups == 4

    def test_empty_runnable_config(self) -> None:
        cfg = Configuration.from_runnable_config({"configurable": {}})
        assert cfg.judge_model == "deepseek-chat"

    def test_runnable_config_without_configurable_key(self) -> None:
        cfg = Configuration.from_runnable_config({})  # type: ignore[arg-type]
        assert cfg.judge_model == "deepseek-chat"


class TestEnvOverride:
    def test_judge_model_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JUDGE_MODEL", "deepseek-reasoner")
        cfg = Configuration.from_runnable_config(None)
        assert cfg.judge_model == "deepseek-reasoner"

    def test_temperature_coerced_from_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JUDGE_TEMPERATURE", "0.7")
        cfg = Configuration.from_runnable_config(None)
        assert cfg.judge_temperature == 0.7

    def test_standard_followups_coerced_from_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("STANDARD_FOLLOWUPS", "3")
        cfg = Configuration.from_runnable_config(None)
        assert cfg.standard_followups == 3

    def test_deep_followups_coerced_from_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DEEP_FOLLOWUPS", "6")
        cfg = Configuration.from_runnable_config(None)
        assert cfg.deep_followups == 6


class TestConfigurableOverride:
    def test_configurable_overrides_default(self) -> None:
        cfg = Configuration.from_runnable_config({"configurable": {"judge_model": "custom-model"}})
        assert cfg.judge_model == "custom-model"

    def test_env_beats_configurable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JUDGE_MODEL", "from-env")
        cfg = Configuration.from_runnable_config({"configurable": {"judge_model": "from-config"}})
        assert cfg.judge_model == "from-env"

    def test_configurable_only_used_when_env_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cfg = Configuration.from_runnable_config({"configurable": {"judge_model": "from-config"}})
        assert cfg.judge_model == "from-config"


class TestValidationBounds:
    def test_temperature_too_high_raises(self) -> None:
        with pytest.raises(ValidationError):
            Configuration(judge_temperature=3.0)

    def test_temperature_negative_raises(self) -> None:
        with pytest.raises(ValidationError):
            Configuration(judge_temperature=-0.1)

    def test_standard_followups_negative_raises(self) -> None:
        with pytest.raises(ValidationError):
            Configuration(standard_followups=-1)

    def test_deep_followups_too_high_raises(self) -> None:
        with pytest.raises(ValidationError):
            Configuration(deep_followups=11)

    def test_extra_field_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            Configuration(unknown_field="oops")  # type: ignore[call-arg]

    def test_env_out_of_bounds_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JUDGE_TEMPERATURE", "99")
        with pytest.raises(ValidationError):
            Configuration.from_runnable_config(None)
