"""Qwen-VL-Max vision client.

Describes a single video frame (JPEG bytes) using the DashScope multimodal
API. Called every 10 seconds during a video-mode interview session to
populate ``InterviewSession.vision_frames``.

Uses the OpenAI-compatible endpoint — delegates to
:func:`merism.memai.llm.get_llm` with a Qwen-VL model override.

Production reads ``DASHSCOPE_VISION_MODEL`` from settings. For tests,
substitute :class:`merism.testing.fakes.FakeVisionClient`.
"""

from __future__ import annotations

import base64
from typing import Any

from django.conf import settings


class VisionClient:
    """Frame-description client. See stt.py docstring re: status."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._api_key = api_key or getattr(settings, "DASHSCOPE_API_KEY", "")
        self._model = model or getattr(settings, "DASHSCOPE_VISION_MODEL", "qwen-vl-max")
        self._base_url = base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"

    def describe_frame(self, *, frame_bytes: bytes, prompt: str = "", **extra: Any) -> str:
        """Return a short description of the frame.

        TODO (R8): implement the real multimodal call.
        """
        if not self._api_key:
            raise RuntimeError(
                "VisionClient requires DASHSCOPE_API_KEY. "
                "For tests, use merism.testing.fakes.FakeVisionClient instead."
            )
        # Placeholder to show how the real call would encode the frame:
        _b64 = base64.b64encode(frame_bytes or b"").decode("ascii")
        _ = _b64, prompt, extra
        return ""
