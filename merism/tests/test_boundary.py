"""Boundary smoke tests for the Merism test entry.

Unlike the old cutover repo where ``posthog.*`` was physically present and we
had to block its test-harness from loading, merism-app has no ``posthog``
package at all. These tests enforce that state.

If any of these fail, someone has copied PostHog code without noticing.
"""

from __future__ import annotations

import importlib.util
import os
import sys

from django.conf import settings


def test_django_settings_is_merism_test() -> None:
    assert os.environ.get("DJANGO_SETTINGS_MODULE") == "merism.settings.test"


def test_no_posthog_package_installed() -> None:
    # The ``posthog`` package must not be importable at all in merism-app.
    # ``find_spec`` raises ``ModuleNotFoundError`` when the parent package
    # itself is absent, which is the happy path for us.
    for target in ("posthog", "posthog.models", "posthog.test.base"):
        try:
            spec = importlib.util.find_spec(target)
        except ModuleNotFoundError:
            spec = None
        assert spec is None, (
            f"{target} should not be importable in merism-app — "
            "we rebuilt specifically to shed that dep."
        )


def test_no_posthog_modules_loaded() -> None:
    offenders = sorted(
        m
        for m in sys.modules
        if (m == "posthog" or m.startswith("posthog.")) and "posthoganalytics" not in m
    )
    assert not offenders, (
        "Unexpected posthog modules loaded:\n  - " + "\n  - ".join(offenders)
    )


def test_installed_apps_is_merism_only() -> None:
    """Every entry in INSTALLED_APPS must be either Django built-ins,
    DRF, Merism itself, or one of the explicitly approved accelerators
    from ADR 0001.
    """
    allowed_prefixes = (
        "django.",
        "rest_framework",
        "drf_spectacular",
        "merism",
    )
    # ADR 0001 accelerators — approved additions.
    allowed_exact = {
        "unfold",
        "unfold.contrib.filters",
        "unfold.contrib.forms",
        "daphne",
        "channels",
        "allauth",
        "allauth.account",
        "allauth.socialaccount",
        "anymail",
        "corsheaders",
        # Observability — django-prometheus exposes /metrics for scraping.
        "django_prometheus",
    }
    offenders = [
        app
        for app in settings.INSTALLED_APPS
        if app not in allowed_exact
        and not any(app.startswith(p) or app == p for p in allowed_prefixes)
    ]
    assert not offenders, f"Unexpected INSTALLED_APPS entries: {offenders}"


def test_merism_db_table_prefix_is_project_convention() -> None:
    # We're asserting the docstring of the convention, not (yet) the models —
    # model-level enforcement lives in test_model_conventions.py once models
    # are defined. This test just makes the convention discoverable via grep.
    from merism import apps

    assert apps.MerismConfig.label == "merism"
