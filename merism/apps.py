"""Merism Django AppConfig.

Single-app project: all Merism models live under ``merism.models.*``. This is
by design — we explicitly chose not to fracture into per-product Django apps.
Rationale is in ``docs/ROADMAP.md``.
"""

from __future__ import annotations

from django.apps import AppConfig


class MerismConfig(AppConfig):
    name = "merism"
    label = "merism"
    verbose_name = "Merism 研究平台"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        # Wire up signal handlers. Each domain that adds signals registers
        # its handlers here so Django picks them up at startup.
        from merism.conductor import signals as _conductor_signals  # noqa: F401
        from merism.conductor import study_closure_signal as _study_closure  # noqa: F401
        from merism.conductor import inbox_signals as _inbox_signals  # noqa: F401
        from merism.signals import user_signup as _user_signup  # noqa: F401
        from merism.signals import transcript_index as _transcript_index  # noqa: F401
        from merism.signals import study_primary_link as _study_primary_link  # noqa: F401

        # Chinese verbose_name for Django Admin
        from merism.verbose_names import apply_verbose_names
        apply_verbose_names()
