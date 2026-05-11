"""Merism AI tool base class.

Every Merism MEM AI tool subclasses :class:`MemTool`. Subclasses declare:

- ``name``                 — unique slug (kebab-case)
- ``description``          — shown to the LLM
- ``args_schema``          — pydantic BaseModel describing call args
- ``_arun_impl(...)``       — async implementation

This is a deliberately thin base compared to the old repo's ``MemTool``.
We dropped LangChain ``BaseTool`` inheritance, ``RunnableConfig`` plumbing,
artifact management, and LangGraph context — they belong to the runner,
not the tool. Merism tools are async functions with a schema.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from pydantic import BaseModel

from merism.models import Team

try:
    from django.contrib.auth.models import AbstractBaseUser
except Exception:  # pragma: no cover
    AbstractBaseUser = None  # type: ignore[assignment,misc]


class MemToolError(Exception):
    """Base class for MEM AI tool errors."""


class MemToolRetryableError(MemToolError):
    """Error the LLM may retry with adjusted inputs."""


class MemToolFatalError(MemToolError):
    """Error that cannot be recovered from within this invocation."""


class MemTool(ABC):
    """Abstract base class for Merism AI tools.

    Usage::

        class SearchResearchTool(MemTool):
            name = "search_research"
            description = "Semantic search over this team's research studies."
            args_schema = SearchResearchArgs

            async def _arun_impl(self, *, query: str, limit: int = 10) -> SearchResearchResult:
                ...
    """

    # Subclass must set these three class-level attributes.
    name: ClassVar[str]
    description: ClassVar[str]
    args_schema: ClassVar[type[BaseModel]]

    def __init__(self, *, team: Team, user: Any) -> None:
        self._team = team
        self._user = user

    # ── override this ───────────────────────────────────────

    @abstractmethod
    async def _arun_impl(self, **kwargs: Any) -> Any:
        """Tool logic. Args validated against ``args_schema`` by the runner."""

    # ── public entry point (called by the agent runner) ─────

    async def arun(self, **kwargs: Any) -> Any:
        """Validate args, then dispatch to ``_arun_impl``."""
        validated = self.args_schema(**kwargs)
        # Pydantic v2 returns a model; pass dict so _arun_impl uses kwargs.
        return await self._arun_impl(**validated.model_dump())

    # ── metadata for LLM function calling ───────────────────

    @classmethod
    def openai_function_spec(cls) -> dict[str, Any]:
        """Return the ``tools`` entry shape for OpenAI chat.completions."""
        return {
            "type": "function",
            "function": {
                "name": cls.name,
                "description": cls.description,
                "parameters": cls.args_schema.model_json_schema(),
            },
        }

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Allow the abstract base + explicit passthrough subclasses to skip
        # the check. Real tools must populate the three class attrs.
        if cls.__name__ == "MemTool" or getattr(cls, "_is_abstract_tool", False):
            return
        for attr in ("name", "description", "args_schema"):
            if not hasattr(cls, attr):
                raise TypeError(
                    f"MemTool subclass {cls.__name__} is missing class attr {attr!r}"
                )
