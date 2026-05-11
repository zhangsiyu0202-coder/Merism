"""DRF global throttle configuration.

Tests run with throttle disabled (see settings/test.py), so here we
validate the *config* rather than actual rate-limit enforcement:

- The default throttle classes list is non-empty in base.py.
- The rates map includes the scopes views rely on.
- DRF can parse each rate spec (catches typos like "60minute" early).
"""

from __future__ import annotations

import pytest
from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle

from merism.settings.base import REST_FRAMEWORK as BASE_REST_FRAMEWORK


class TestThrottleConfig:
    def test_base_has_anon_and_user_throttles(self) -> None:
        """The production baseline must ship with anon + user caps."""
        classes = BASE_REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"]
        assert any("AnonRateThrottle" in c for c in classes), classes
        assert any("UserRateThrottle" in c for c in classes), classes
        assert any("ScopedRateThrottle" in c for c in classes), classes

    def test_base_rates_include_required_scopes(self) -> None:
        """Named scopes expected by production views."""
        rates = BASE_REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
        for scope in ("anon", "user", "interview_turn", "ask_stream", "auth"):
            assert scope in rates, f"missing scope: {scope} (have {sorted(rates)})"

    @pytest.mark.parametrize(
        "scope",
        ["anon", "user", "interview_turn", "ask_stream", "auth", "recruitment_dispatch"],
    )
    def test_rate_spec_parses(self, scope: str) -> None:
        """DRF's SimpleRateThrottle.parse_rate must accept every base rate."""
        rate = BASE_REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"][scope]
        # SimpleRateThrottle.parse_rate is a static-ish helper on the instance.
        throttle = SimpleRateThrottle.__new__(SimpleRateThrottle)
        num_requests, duration = throttle.parse_rate(rate)
        assert num_requests > 0, f"scope {scope}: {rate}"
        assert duration > 0, f"scope {scope}: {rate}"

    def test_tests_disable_throttle(self) -> None:
        """pytest-time overrides must blank the throttle list so the 210+
        test suite does not thrash the shared LocMem cache."""
        assert settings.REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] == []
        assert settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] == {}
