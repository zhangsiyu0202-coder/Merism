"""Preset loader for the LLM Gateway admin quick-fill dropdown.

Presets are a UX convenience — they pre-populate base_url + model when a
user picks a known provider from the dropdown. They are NOT required for
the system to function; a user can always hand-fill the three fields.

Usage::

    from merism.llm_gateway.presets import load_presets

    presets = load_presets()
    # [{"label": "DeepSeek · Chat", "protocol": "http", "base_url": ..., "model": ..., "serves": [...]}, ...]
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

_PRESETS_PATH = Path(__file__).parent / "presets.yaml"


@lru_cache(maxsize=1)
def load_presets() -> list[dict[str, Any]]:
    """Load and validate presets from the YAML file.

    Returns a list of preset dicts. Cached after first call (file is a
    code asset, not user-editable at runtime).
    """
    with _PRESETS_PATH.open() as f:
        data = yaml.safe_load(f)

    if not isinstance(data, list):
        raise ValueError(f"presets.yaml must be a YAML list, got {type(data).__name__}")

    required_keys = {"label", "protocol", "base_url", "model", "serves"}
    for i, entry in enumerate(data):
        missing = required_keys - set(entry.keys())
        if missing:
            raise ValueError(f"Preset #{i} ({entry.get('label', '?')}) missing keys: {missing}")
        if entry["protocol"] not in ("http", "ws"):
            raise ValueError(f"Preset #{i} has invalid protocol: {entry['protocol']}")

    return data


def presets_for_protocol(protocol: str) -> list[dict[str, Any]]:
    """Filter presets by protocol ('http' or 'ws')."""
    return [p for p in load_presets() if p["protocol"] == protocol]


__all__ = ["load_presets", "presets_for_protocol"]
