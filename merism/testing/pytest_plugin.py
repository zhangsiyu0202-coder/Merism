"""Pytest plugin — Merism test markers.

Registers three ``pytest.mark`` markers and skips the tests automatically when
the environment isn't configured for them:

- ``@pytest.mark.merism_llm_live`` — needs a real LLM API key
  (``MERISM_LLM_API_KEY`` env var). Skipped otherwise.
- ``@pytest.mark.merism_im_live`` — needs real IM channel credentials
  (``MERISM_IM_LIVE=1`` env var). Skipped otherwise.
- ``@pytest.mark.merism_slow`` — runs > 1 second. Included by default; opt out
  with ``-m "not merism_slow"``.

To activate the plugin, add this line to your ``pytest.ini``::

    addopts = -p merism.testing.pytest_plugin

The Merism lightweight entry (``merism/pytest.ini``) registers it automatically.
"""

from __future__ import annotations

import os
from typing import Any

import pytest


_MARKERS = {
    "merism_llm_live": (
        "Test requires a live LLM API key. Skipped unless MERISM_LLM_API_KEY is set."
    ),
    "merism_im_live": (
        "Test requires a live IM channel (Feishu/WeCom/QQ). "
        "Skipped unless MERISM_IM_LIVE=1 is set."
    ),
    "merism_storage_live": (
        "Test hits real object storage (MinIO or S3). "
        "Skipped unless MERISM_STORAGE_LIVE=1 is set."
    ),
    "merism_slow": "Test runs for more than ~1 second. Opt out with -m 'not merism_slow'.",
}


def pytest_configure(config: Any) -> None:
    for name, description in _MARKERS.items():
        config.addinivalue_line("markers", f"{name}: {description}")


def pytest_collection_modifyitems(config: Any, items: list[Any]) -> None:
    llm_live = bool(os.environ.get("MERISM_LLM_API_KEY"))
    im_live = os.environ.get("MERISM_IM_LIVE") == "1"
    storage_live = os.environ.get("MERISM_STORAGE_LIVE") == "1"

    skip_llm = pytest.mark.skip(reason="merism_llm_live: MERISM_LLM_API_KEY not set")
    skip_im = pytest.mark.skip(reason="merism_im_live: MERISM_IM_LIVE != 1")
    skip_storage = pytest.mark.skip(reason="merism_storage_live: MERISM_STORAGE_LIVE != 1")

    for item in items:
        if "merism_llm_live" in item.keywords and not llm_live:
            item.add_marker(skip_llm)
        if "merism_im_live" in item.keywords and not im_live:
            item.add_marker(skip_im)
        if "merism_storage_live" in item.keywords and not storage_live:
            item.add_marker(skip_storage)
