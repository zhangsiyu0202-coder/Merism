#!/usr/bin/env python
"""Django management entry point."""

from __future__ import annotations

import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "merism.settings.dev")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Run `uv sync --extra dev` and activate `.venv/`."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
