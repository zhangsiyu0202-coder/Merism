"""Merism Django settings package.

Four stacked settings modules:

- :mod:`merism.settings.base` — shared across every environment
- :mod:`merism.settings.dev`  — local development (Postgres + Redis via docker compose)
- :mod:`merism.settings.test` — pytest boundary (sqlite :memory:, no services)
- :mod:`merism.settings.prod` — production (read secrets from env)

Choose with ``DJANGO_SETTINGS_MODULE=merism.settings.dev`` (etc.).
"""
