"""Sentry init behaviour.

The integration itself is provided by sentry-sdk; here we only assert our
thin wrapper makes the right decisions: no-op when DSN is blank, actually
initialise when DSN is set, and scrub participant-facing tokens from
breadcrumbs.
"""

from __future__ import annotations

import os
from unittest.mock import patch

from merism.sentry import _before_send, init_sentry


class TestInitSentry:
    def test_noop_when_dsn_empty(self) -> None:
        with patch.dict(os.environ, {"SENTRY_DSN": ""}, clear=False):
            with patch("merism.sentry.sentry_sdk.init") as mock_init:
                assert init_sentry() is False
            mock_init.assert_not_called()

    def test_noop_when_dsn_whitespace(self) -> None:
        with patch.dict(os.environ, {"SENTRY_DSN": "   "}, clear=False):
            with patch("merism.sentry.sentry_sdk.init") as mock_init:
                assert init_sentry() is False
            mock_init.assert_not_called()

    def test_initialises_when_dsn_set(self) -> None:
        fake_dsn = "https://public@o0.ingest.sentry.io/0"
        with patch.dict(
            os.environ,
            {
                "SENTRY_DSN": fake_dsn,
                "SENTRY_ENVIRONMENT": "ci",
                "SENTRY_TRACES_SAMPLE_RATE": "0.25",
            },
            clear=False,
        ):
            with patch("merism.sentry.sentry_sdk.init") as mock_init:
                assert init_sentry() is True
            mock_init.assert_called_once()
            kwargs = mock_init.call_args.kwargs
            assert kwargs["dsn"] == fake_dsn
            assert kwargs["environment"] == "ci"
            assert kwargs["traces_sample_rate"] == 0.25
            assert kwargs["send_default_pii"] is False


class TestBeforeSend:
    def test_scrubs_cookie_and_authorization_headers(self) -> None:
        event = {
            "request": {
                "headers": {
                    "Cookie": "sessionid=secret",
                    "Authorization": "Bearer abcd",
                    "User-Agent": "pytest",
                }
            }
        }
        out = _before_send(event, hint={})
        assert out["request"]["headers"]["Cookie"] == "[Filtered]"
        assert out["request"]["headers"]["Authorization"] == "[Filtered]"
        assert out["request"]["headers"]["User-Agent"] == "pytest"

    def test_scrubs_invitation_token_from_breadcrumb_urls(self) -> None:
        event = {
            "breadcrumbs": {
                "values": [
                    {"data": {"url": "https://example.com/i/abc/?t=REAL_TOKEN"}},
                    {"data": {"url": "https://example.com/api/studies/"}},
                ]
            }
        }
        out = _before_send(event, hint={})
        crumbs = out["breadcrumbs"]["values"]
        assert crumbs[0]["data"]["url"] == "https://example.com/i/abc/?t=[Filtered]"
        assert crumbs[1]["data"]["url"] == "https://example.com/api/studies/"
