"""Email adapter tests.

Two layers:

1. **Mocked smtplib** — fast, hermetic, covers 95% of the adapter
   logic (message construction, address validation, headers,
   HTML+plain multi-part, transport_fn override, factory registration).
2. **Real asyncio SMTP server** (aiosmtpd) — one end-to-end test that
   actually hands an envelope over TCP to prove we speak SMTP for real.
   Skipped if the loopback environment refuses the controller's
   self-check connect (some Docker / sandbox setups).
"""

from __future__ import annotations

import asyncio
import threading
from email.message import EmailMessage
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from merism.recruitment.adapters.base import IMMessage
from merism.recruitment.adapters.email_adapter import EmailAdapter, _EmailConfig


# ── Layer 1 : mocked smtplib.SMTP ────────────────────────────


def _adapter(from_address: str = "merism@example.com") -> EmailAdapter:
    return EmailAdapter.from_config(
        {
            "host": "smtp.example.com",
            "port": 587,
            "use_tls": True,
            "username": "merism",
            "password": "secret",
            "from_address": from_address,
        }
    )


def test_send_plain_text_builds_correct_envelope() -> None:
    adapter = _adapter()
    with patch("smtplib.SMTP") as smtp_cls:
        instance = smtp_cls.return_value.__enter__.return_value
        result = adapter.send_message(
            "alice@example.com",
            IMMessage(content="Hi Alice, please join our study.", msg_type="text"),
        )

    assert result.success is True
    assert result.message_id is not None
    # Exactly one send_message call
    call = instance.send_message.call_args
    sent: EmailMessage = call.args[0]
    assert sent["To"] == "alice@example.com"
    assert sent["From"] == "merism@example.com"
    assert sent["Subject"] == "Invitation"
    body = sent.get_content().strip()
    assert "please join our study" in body
    # STARTTLS + login were called (we asked for TLS + gave credentials)
    instance.starttls.assert_called_once()
    instance.login.assert_called_once_with("merism", "secret")


def test_send_html_adds_plain_alt_part() -> None:
    adapter = _adapter()
    html = "<p>Hi <strong>Bob</strong>, <a href='https://x'>join study</a>.</p>"
    with patch("smtplib.SMTP") as smtp_cls:
        instance = smtp_cls.return_value.__enter__.return_value
        result = adapter.send_message(
            "bob@example.com",
            IMMessage(
                content=html,
                msg_type="html",
                extra={"subject": "You're invited"},
            ),
        )

    assert result.success is True
    sent: EmailMessage = instance.send_message.call_args.args[0]
    assert sent["Subject"] == "You're invited"
    assert sent.is_multipart()
    html_part = sent.get_body(("html",))
    plain_part = sent.get_body(("plain",))
    assert html_part is not None and "<strong>Bob</strong>" in html_part.get_content()
    # plain alt part should have stripped tags
    assert plain_part is not None and "join study" in plain_part.get_content()


def test_invalid_address_is_soft_failure() -> None:
    adapter = _adapter()
    with patch("smtplib.SMTP") as smtp_cls:
        result = adapter.send_message("not-an-email", IMMessage(content="x"))
    assert result.success is False
    assert "invalid email" in (result.error or "")
    smtp_cls.assert_not_called()  # never opened a socket


def test_reply_to_header_from_credentials() -> None:
    adapter = EmailAdapter.from_config(
        {
            "host": "smtp.example.com",
            "from_address": "merism@example.com",
            "reply_to": "pm@example.com",
        }
    )
    with patch("smtplib.SMTP") as smtp_cls:
        instance = smtp_cls.return_value.__enter__.return_value
        adapter.send_message("alice@example.com", IMMessage(content="hi"))
    sent: EmailMessage = instance.send_message.call_args.args[0]
    assert sent["Reply-To"] == "pm@example.com"


def test_reply_to_header_from_message_extra_overrides() -> None:
    adapter = EmailAdapter.from_config(
        {
            "host": "smtp.example.com",
            "from_address": "merism@example.com",
            "reply_to": "pm@example.com",
        }
    )
    with patch("smtplib.SMTP") as smtp_cls:
        instance = smtp_cls.return_value.__enter__.return_value
        adapter.send_message(
            "alice@example.com",
            IMMessage(content="hi", extra={"reply_to": "other@example.com"}),
        )
    sent: EmailMessage = instance.send_message.call_args.args[0]
    assert sent["Reply-To"] == "other@example.com"


def test_smtp_error_returns_soft_failure() -> None:
    import smtplib

    adapter = _adapter()
    with patch("smtplib.SMTP") as smtp_cls:
        instance = smtp_cls.return_value.__enter__.return_value
        instance.send_message.side_effect = smtplib.SMTPRecipientsRefused({"a@x": (550, b"rejected")})
        result = adapter.send_message("alice@example.com", IMMessage(content="x"))
    assert result.success is False
    assert "SMTP error" in (result.error or "")


def test_connection_error_returns_soft_failure() -> None:
    adapter = _adapter()
    with patch("smtplib.SMTP") as smtp_cls:
        smtp_cls.side_effect = ConnectionRefusedError("nope")
        result = adapter.send_message("alice@example.com", IMMessage(content="x"))
    assert result.success is False
    assert "connection error" in (result.error or "")


def test_transport_fn_override_bypasses_smtp() -> None:
    """MCP-readiness: transport_fn replaces the default SMTP path."""
    calls: list[EmailMessage] = []

    def fake_mcp_transport(msg: EmailMessage) -> str:
        calls.append(msg)
        return "<stub-id@example.com>"

    cfg = _EmailConfig(
        host="unreachable-from-tests",
        port=9999,
        use_tls=False,
        username=None,
        password=None,
        from_address="merism@example.com",
        transport_fn=fake_mcp_transport,
    )
    adapter = EmailAdapter(cfg)

    result = adapter.send_message(
        "charlie@example.com",
        IMMessage(content="via MCP", msg_type="text"),
    )
    assert result.success is True
    assert result.message_id == "<stub-id@example.com>"
    assert len(calls) == 1
    assert calls[0]["To"] == "charlie@example.com"


def test_factory_registration() -> None:
    """get_adapter('email', ...) returns an EmailAdapter."""
    from merism.recruitment.adapters.factory import get_adapter

    adapter = get_adapter(
        "email",
        {"host": "smtp.example.com", "from_address": "a@example.com"},
    )
    assert isinstance(adapter, EmailAdapter)


def test_from_config_validates_required_fields() -> None:
    with pytest.raises(ValueError, match="host"):
        EmailAdapter.from_config({"from_address": "a@example.com"})
    with pytest.raises(ValueError, match="from_address"):
        EmailAdapter.from_config({"host": "smtp.x"})


# ── Layer 2 : real asyncio SMTP server (integration, skippable) ──


@pytest.fixture()
def real_smtp_server():
    """Spin a real aiosmtpd server in a background thread.

    Bypasses ``Controller`` (its self-check TCP trigger is flaky in
    some sandboxed envs — see pytest failures on GitHub Actions
    runners without full loopback). We drive the asyncio loop
    manually on a daemon thread.
    """
    from aiosmtpd.handlers import Message
    from aiosmtpd.smtp import SMTP

    class _H(Message):
        def __init__(self) -> None:
            super().__init__()
            self.captured: list[EmailMessage] = []

        def handle_message(self, msg: EmailMessage) -> None:
            self.captured.append(msg)

    handler = _H()
    loop = asyncio.new_event_loop()
    ready = threading.Event()
    host_port: dict[str, object] = {}

    async def _serve() -> None:
        server = await loop.create_server(
            lambda: SMTP(handler, enable_SMTPUTF8=False),
            host="127.0.0.1",
            port=0,
        )
        socks = server.sockets
        assert socks is not None
        host_port["host"], host_port["port"] = socks[0].getsockname()[:2]
        ready.set()
        try:
            await server.serve_forever()
        except asyncio.CancelledError:
            server.close()
            await server.wait_closed()

    task_ref: dict[str, asyncio.Task[None]] = {}

    def _run_loop() -> None:
        asyncio.set_event_loop(loop)
        task_ref["t"] = loop.create_task(_serve())
        loop.run_forever()

    thread = threading.Thread(target=_run_loop, daemon=True)
    thread.start()
    if not ready.wait(timeout=3.0):
        pytest.skip("could not start local SMTP server in this env")

    try:
        yield handler, host_port
    finally:
        loop.call_soon_threadsafe(task_ref["t"].cancel)
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=2.0)
        loop.close()


def test_end_to_end_real_smtp(real_smtp_server) -> None:
    handler, addr = real_smtp_server
    adapter = EmailAdapter.from_config(
        {
            "host": addr["host"],
            "port": addr["port"],
            "use_tls": False,
            "from_address": "merism@example.com",
        }
    )
    result = adapter.send_message(
        "alice@example.com",
        IMMessage(content="Real SMTP end-to-end test.", msg_type="text"),
    )
    assert result.success is True, result.error
    assert len(handler.captured) == 1
    msg = handler.captured[0]
    assert msg["To"] == "alice@example.com"
    # aiosmtpd's legacy Message has get_payload(); EmailMessage-style
    # helpers are unavailable, so fall back to as_string().
    assert "Real SMTP end-to-end" in msg.as_string()
