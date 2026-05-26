"""Test doubles for v3 nodes — replace LLM and evaluator at the boundary."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class FakeEvaluator:
    """Stand-in for the runnable returned by ``llm.with_structured_output``.

    Pops one response per ``.invoke()``. Raises ``IndexError`` when out
    of responses (forces tests to declare exact expected call count).
    """

    def __init__(self, responses: list[BaseModel] | None = None) -> None:
        self._responses: list[BaseModel] = list(responses or [])
        self.invocations: list[str] = []

    def invoke(self, prompt: str) -> BaseModel:
        self.invocations.append(prompt)
        if not self._responses:
            raise IndexError("FakeEvaluator out of responses")
        return self._responses.pop(0)


class FakeLLM:
    """Stand-in for ``ChatOpenAI`` for plain ``.invoke()`` (used by finalize).

    Returns an object with ``.content: str`` to match ``AIMessage``.
    """

    class _Msg:
        def __init__(self, content: str) -> None:
            self.content = content

    def __init__(self, responses: list[str] | None = None) -> None:
        self._responses: list[str] = list(responses or [])
        self.invocations: list[str] = []

    def invoke(self, prompt: str) -> Any:
        self.invocations.append(prompt)
        if not self._responses:
            raise IndexError("FakeLLM out of responses")
        return self._Msg(self._responses.pop(0))


class ExplodingLLM:
    """Always raises on invoke. Use to test failure-path branches."""

    def __init__(self, exc: Exception | None = None) -> None:
        self._exc = exc or RuntimeError("simulated LLM failure")

    def invoke(self, prompt: str) -> Any:
        raise self._exc


__all__ = ["ExplodingLLM", "FakeEvaluator", "FakeLLM"]
