"""Merism test base classes.

These are thin wrappers on top of ``django.test`` / ``rest_framework.test`` that
give every Merism test:

- ``self.user``    — a real Django ``User`` (from ``django.contrib.auth``)
- ``self.team``    — a Merism team (stub today, real ``merism.Team`` in Phase C1)

Why four variants:

- ``MerismSmokeTest``        — no DB, no transaction wrapping. Fastest. Use for
  pure-logic unit tests (schema validation, pure functions, fakes-only).
- ``MerismTestCase``         — wraps each test in an atomic transaction. Use for
  ORM-backed unit tests that don't need to cross transaction boundaries.
- ``MerismTransactionTestCase`` — no atomic wrapping. Use for tests that touch
  Redis streams, Celery eager mode, external IM adapters, or anything that
  spans transactions.
- ``MerismAPITestCase``      — DRF ``APITestCase`` auto-logged-in as
  ``self.user``. Use for viewset / endpoint tests.

NOTE: Until Phase C1 lands ``merism.Team``, ``self.team`` is a ``SimpleNamespace``
placeholder with ``id=1``. ORM-backed factories that need a real team will
raise ``NotImplementedError`` with a clear "Phase C1 required" message.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, ClassVar

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, TransactionTestCase


_USER_EMAIL = "test@merism.test"
_USER_PASSWORD = "merism-test-password-not-for-production"  # noqa: S105 - test credential


def _make_stub_team(team_id: int = 1, name: str = "Test Team") -> SimpleNamespace:
    """Return a placeholder team. Replaced with real merism.Team in Phase C1."""
    return SimpleNamespace(
        id=team_id,
        pk=team_id,
        name=name,
        # Common attrs Merism code reads. Extend as needed.
        organization_id=1,
        organization=SimpleNamespace(id=1, pk=1, name="Test Org"),
    )


def _build_user(*, email: str = _USER_EMAIL, password: str = _USER_PASSWORD) -> Any:
    User = get_user_model()
    # ``User`` may be a proxy to auth.User or a custom model. The minimum contract
    # Merism tests need is ``email`` / ``pk`` / auth. ``create_user`` exists on
    # both the default ``User`` manager and any reasonable custom one.
    try:
        return User.objects.create_user(username=email, email=email, password=password)
    except TypeError:
        return User.objects.create_user(email=email, password=password)


class _MerismSetupMixin:
    """Shared setUpTestData that creates ``cls.user`` and ``cls.team``."""

    team: ClassVar[Any]
    user: ClassVar[Any]

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()  # type: ignore[misc]
        cls.user = _build_user()
        cls.team = _make_stub_team()


class MerismSmokeTest(SimpleTestCase):
    """No-DB, no-transaction test case. Fastest path.

    Subclasses must NOT touch Django ORM. Use only for pure-function logic,
    schema validation, or fakes-only integration. If you need the ORM, switch
    to :class:`MerismTestCase`.
    """

    # SimpleTestCase disallows DB access by default — good guard rail.
    databases: ClassVar = set()


class MerismTestCase(_MerismSetupMixin, TestCase):
    """Standard Merism unit test case. Atomic transaction rollback per test.

    ``cls.user`` and ``cls.team`` are set up once per TestCase subclass via
    ``setUpTestData``.

    Phase C1 will replace the ``cls.team`` placeholder with a real
    ``merism.Team`` instance — your test code shouldn't need to change.
    """

    pass


class MerismTransactionTestCase(_MerismSetupMixin, TransactionTestCase):
    """For tests that need to cross transaction boundaries.

    Use when your test uses Redis streams, Celery eager-mode chains, or
    anything else that commits mid-test. Slower than :class:`MerismTestCase`
    (truncates tables between tests instead of rolling back), so prefer the
    atomic variant when possible.
    """

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # TransactionTestCase doesn't call setUpTestData automatically.
        cls.setUpTestData()


def _build_merism_api_test_case() -> type:
    """Build :class:`MerismAPITestCase` lazily.

    DRF's ``rest_framework.test`` module reads Django settings at import time
    via ``api_settings.TEST_REQUEST_RENDERER_CLASSES``. Deferring the import
    means ``merism.testing`` can itself be imported before Django is configured
    (e.g., during collection of a smoke test file).
    """
    from rest_framework.test import APITestCase  # local import on first use

    class MerismAPITestCase(_MerismSetupMixin, APITestCase):
        """DRF API test case auto-logged-in as ``self.user``.

        ``self.client`` is a DRF ``APIClient`` with ``force_authenticate`` already
        applied. Use for viewset / endpoint tests.
        """

        def setUp(self) -> None:
            super().setUp()
            self.client.force_authenticate(user=self.user)  # type: ignore[attr-defined]

    return MerismAPITestCase


def __getattr__(name: str) -> Any:
    """Module-level lazy attribute resolution.

    Keeps the DRF import off the happy path for pure-smoke tests that don't
    need ``MerismAPITestCase``. Once resolved, the class is cached on the module.
    """
    if name == "MerismAPITestCase":
        cls = _build_merism_api_test_case()
        globals()["MerismAPITestCase"] = cls
        return cls
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
