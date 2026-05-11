"""Email adapter — sends recruitment invitations over SMTP.

Design notes
============

This adapter treats email as another IM channel so the existing
broadcast pipeline (``dispatch_recruitment_delivery`` → ``get_adapter``
→ ``.send_message(recipient_id, message)``) works unchanged. The only
semantic difference is that ``recipient_id`` is an RFC-5322 email
address instead of an IM user id.

**Transport pluggability (MCP-ready)**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The actual wire transport (how bytes reach the SMTP relay) is a
callable stored on the adapter instance. The default transport is
``_send_via_smtplib`` — stdlib, no extra dependencies, works against
any RFC-5321 server.

This keeps the door open to swap in an MCP-based transport (e.g. the
``@resend/mcp-send-email`` Node server, or any of the
``modelcontextprotocol/servers`` reference Gmail / SendGrid servers)
without changing the adapter contract. An MCP-backed transport simply
spawns the MCP process and speaks JSON-RPC over stdio; the ``message``
object shape is identical.

Referenced projects:
- https://github.com/resend/mcp-send-email (MCP stdio protocol → Resend)
- https://github.com/modelcontextprotocol/servers/tree/main/src/gmail
- https://github.com/aio-libs/aiosmtpd (used by tests)

**Credential shape**
~~~~~~~~~~~~~~~~~~~~

Stored in ``ChannelConfig.credentials_encrypted`` (Fernet-encrypted
JSON). Plaintext shape::

    {
        "transport": "smtp",              # or "mcp" (future)
        "host": "smtp.example.com",
        "port": 587,
        "use_tls": true,                  # STARTTLS
        "username": "merism@example.com",
        "password": "<app-password>",
        "from_address": "Merism Research <merism@example.com>",
        "reply_to": "pm@example.com"      # optional
    }

**Message → email mapping**
~~~~~~~~~~~~~~~~~~~~~~~~~~~

``IMMessage.content`` is treated as:
- **plain text** when ``msg_type`` is ``"text"`` (the default)
- **HTML body** when ``msg_type`` is ``"markdown"`` or ``"html"``
  (we also pass a degraded plain-text alt-part for accessibility)

``IMMessage.extra`` may carry:
- ``subject``   — email Subject header (defaults to study_name)
- ``text_alt``  — plain-text fallback for HTML emails
- ``reply_to``  — overrides credential-level reply_to
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from typing import Any, Callable

from merism.recruitment.adapters.base import IMChannelBase, IMMessage, SendResult

logger = logging.getLogger(__name__)


CHANNEL_EMAIL = "email"


@dataclass
class _EmailConfig:
    """Parsed SMTP credentials. Created from the decrypted JSON blob."""

    host: str
    port: int
    use_tls: bool
    username: str | None
    password: str | None
    from_address: str
    reply_to: str | None = None
    transport: str = "smtp"
    # Extra hook for a non-SMTP transport (e.g. an MCP-based sender).
    # Shape: callable(EmailMessage) -> message_id (str). Keep None for SMTP.
    transport_fn: Callable[[EmailMessage], str] | None = field(default=None, repr=False)


class EmailAdapter(IMChannelBase):
    """SMTP email adapter. Swap ``transport_fn`` to plug in MCP/REST."""

    channel_type = CHANNEL_EMAIL

    def __init__(self, config: _EmailConfig) -> None:
        self._config = config

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "EmailAdapter":
        """Build an adapter from a decrypted credentials dict.

        Unknown or missing keys fall back to safe defaults. ``host`` /
        ``from_address`` are required.
        """
        if not config.get("host"):
            raise ValueError("email adapter: missing 'host' in credentials")
        if not config.get("from_address"):
            raise ValueError("email adapter: missing 'from_address' in credentials")

        return cls(
            _EmailConfig(
                host=str(config["host"]),
                port=int(config.get("port", 587)),
                use_tls=bool(config.get("use_tls", True)),
                username=config.get("username") or None,
                password=config.get("password") or None,
                from_address=str(config["from_address"]),
                reply_to=config.get("reply_to") or None,
                transport=str(config.get("transport", "smtp")),
            )
        )

    # ── Public surface (IMChannelBase contract) ─────────────────

    def send_message(self, recipient_id: str, message: IMMessage) -> SendResult:
        """Send one email to ``recipient_id``.

        ``recipient_id`` must be a valid email address. If validation
        fails here we return a ``SendResult(success=False)`` rather
        than raising — the dispatch task then records it as a failed
        ``DeliveryRecord`` without breaking the rest of the batch.
        """
        if "@" not in recipient_id or recipient_id.strip() != recipient_id:
            return SendResult(
                success=False,
                error=f"invalid email address: {recipient_id!r}",
            )

        try:
            email = self._build_email(recipient_id, message)
        except Exception as exc:
            logger.exception("email.build_failed")
            return SendResult(success=False, error=f"message build failed: {exc}")

        try:
            if self._config.transport_fn is not None:
                msg_id = self._config.transport_fn(email)
            else:
                msg_id = self._send_via_smtplib(email)
            return SendResult(success=True, message_id=msg_id)
        except smtplib.SMTPException as exc:
            logger.warning("email.smtp_error", extra={"err": str(exc)})
            return SendResult(success=False, error=f"SMTP error: {exc}")
        except OSError as exc:
            logger.warning("email.socket_error", extra={"err": str(exc)})
            return SendResult(success=False, error=f"connection error: {exc}")
        except Exception as exc:
            logger.exception("email.unexpected")
            return SendResult(success=False, error=f"unexpected: {exc}")

    def send_to_group(self, group_id: str, message: IMMessage) -> SendResult:
        """Email has no native group concept — treat ``group_id`` as a
        plain recipient (e.g. a mailing-list address). We just forward
        to :meth:`send_message`."""
        return self.send_message(group_id, message)

    # ── Internals ───────────────────────────────────────────────

    def _build_email(self, to: str, message: IMMessage) -> EmailMessage:
        email = EmailMessage()
        extra = dict(message.extra or {})

        subject = str(extra.get("subject") or "Invitation").strip() or "Invitation"
        email["Subject"] = subject
        email["From"] = self._config.from_address
        email["To"] = to
        email["Message-ID"] = make_msgid(domain=_domain_of(self._config.from_address))

        reply_to = extra.get("reply_to") or self._config.reply_to
        if reply_to:
            email["Reply-To"] = reply_to

        # msg_type "markdown"/"html" → HTML body + plain alt
        # msg_type "text" (default) → plain body only
        if message.msg_type in ("markdown", "html"):
            plain_alt = str(extra.get("text_alt") or _strip_html(message.content))
            email.set_content(plain_alt)
            email.add_alternative(message.content, subtype="html")
        else:
            email.set_content(message.content)

        return email

    def _send_via_smtplib(self, email: EmailMessage) -> str:
        """Default transport. Uses ``smtplib.SMTP`` with optional STARTTLS."""
        cfg = self._config
        context = ssl.create_default_context()

        with smtplib.SMTP(cfg.host, cfg.port, timeout=30) as client:
            client.ehlo()
            if cfg.use_tls:
                client.starttls(context=context)
                client.ehlo()
            if cfg.username and cfg.password:
                client.login(cfg.username, cfg.password)
            client.send_message(email)

        # smtplib doesn't return a transport-side ID; return the
        # message's own Message-ID (RFC-5322 unique per message).
        return email["Message-ID"]


# ── helpers ──────────────────────────────────────────────────


def _domain_of(address: str) -> str:
    """Extract domain from an email or ``"Name <email>"`` address."""
    if "<" in address:
        address = address.split("<", 1)[1].rstrip(">")
    return address.rsplit("@", 1)[-1].strip() or "localhost"


def _strip_html(html: str) -> str:
    """Very cheap HTML → text for alt-parts. Not a real HTML parser —
    we only use this to give the receiver a readable text fallback.

    Aims for "good enough" for the kind of HTML a recruitment template
    produces (paragraphs, links, simple formatting). A future iteration
    can swap in ``beautifulsoup4`` if templates get richer.
    """
    import re

    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    # Collapse runs of blank lines.
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text
