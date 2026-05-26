"""LLM factory — env var validation + json_mode binding."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from merism.conductor.llm import LLMConfigError, build_evaluator, build_llm
from merism.conductor.tools_and_schemas import Evaluation


@pytest.fixture(autouse=True)
def _llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide canonical env for all LLM tests."""
    monkeypatch.setenv("MERISM_LLM_API_KEY", "test-key-not-real")
    monkeypatch.setenv("MERISM_LLM_BASE_URL", "https://api.deepseek.com")


class TestBuildLlm:
    def test_returns_chat_openai_with_args(self) -> None:
        llm = build_llm("deepseek-chat", temperature=0.0)
        assert llm.model_name == "deepseek-chat"
        assert llm.temperature == 0.0

    def test_passes_base_url_from_env(self) -> None:
        llm = build_llm("deepseek-chat")
        # ChatOpenAI exposes base URL via openai_api_base. Stringify it
        # tolerantly (SecretStr / URL-like objects across LangChain versions).
        base_url_str = str(getattr(llm, "openai_api_base", "") or "")
        assert "deepseek" in base_url_str

    def test_default_temperature_is_zero(self) -> None:
        llm = build_llm("deepseek-chat")
        assert llm.temperature == 0.0

    def test_custom_temperature(self) -> None:
        llm = build_llm("deepseek-chat", temperature=0.5)
        assert llm.temperature == 0.5

    def test_missing_api_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MERISM_LLM_API_KEY", raising=False)
        with pytest.raises(LLMConfigError, match="MERISM_LLM_API_KEY"):
            build_llm("deepseek-chat")

    def test_missing_base_url_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MERISM_LLM_BASE_URL", raising=False)
        with pytest.raises(LLMConfigError, match="MERISM_LLM_BASE_URL"):
            build_llm("deepseek-chat")


class TestBuildEvaluator:
    def test_passes_json_mode_method(self) -> None:
        llm = MagicMock()
        result_runnable: Any = MagicMock()
        llm.with_structured_output.return_value = result_runnable

        actual = build_evaluator(llm, Evaluation)

        llm.with_structured_output.assert_called_once_with(Evaluation, method="json_mode")
        assert actual is result_runnable

    def test_real_llm_accepts_evaluator_call(self) -> None:
        # Real ChatOpenAI accepts with_structured_output without making a
        # network call (the binding happens at invoke time). This catches
        # signature regressions if LangChain ever changes the API.
        llm = build_llm("deepseek-chat")
        evaluator = build_evaluator(llm, Evaluation)
        # Just verify it built without raising; we don't invoke()
        # (would require network).
        assert evaluator is not None


class TestModuleNotConstructingLlmAtImportTime:
    """Pattern 4 invariant: no LLM construction at module top.

    Verify that importing the llm module does not consume env vars or
    instantiate ChatOpenAI. This protects against regressions where
    someone moves a `_default_llm = build_llm(...)` call to module level.
    """

    def test_no_chat_openai_at_module_import(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Strip env, then re-import; if module top called build_llm, it
        # would raise LLMConfigError on import.
        monkeypatch.delenv("MERISM_LLM_API_KEY", raising=False)
        monkeypatch.delenv("MERISM_LLM_BASE_URL", raising=False)
        with patch.dict("sys.modules", {}):
            import importlib

            from merism.conductor import llm as llm_module

            # If the import succeeds without env vars, no LLM was
            # constructed at import time. (We had env stripped before
            # the import call.)
            importlib.reload(llm_module)
