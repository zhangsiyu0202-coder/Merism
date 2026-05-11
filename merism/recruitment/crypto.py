from __future__ import annotations

import json
import base64
from functools import lru_cache
from typing import Any

from django.conf import settings

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Fixed salt is acceptable here: the key material (SECRET_KEY) is already secret
# and unique per deployment, so the salt only needs to be stable across restarts.
_SALT = b"merism_channel_creds_v1"


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    """Build a Fernet instance from ``MERISM_CHANNEL_ENCRYPTION_KEY`` (preferred)
    or, as a dev fallback, derive one from ``SECRET_KEY``.

    In production, always set ``MERISM_CHANNEL_ENCRYPTION_KEY`` to a fresh
    Fernet key (``Fernet.generate_key()``) so rotating Django's ``SECRET_KEY``
    does not invalidate every stored channel credential.
    """
    explicit = getattr(settings, "MERISM_CHANNEL_ENCRYPTION_KEY", "")
    if explicit:
        # Fernet keys are urlsafe base64 of 32 bytes — validate by constructing.
        return Fernet(explicit.encode("utf-8"))

    # Dev fallback: derive from SECRET_KEY. Not safe for prod because rotating
    # SECRET_KEY invalidates every channel credential in the database.
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        iterations=100_000,
    )
    raw_key = kdf.derive(settings.SECRET_KEY.encode("utf-8"))
    fernet_key = base64.urlsafe_b64encode(raw_key)
    return Fernet(fernet_key)


def encrypt_credentials(credentials: dict[str, Any]) -> bytes:
    """Encrypt a credentials dict to Fernet-encrypted bytes for DB storage."""
    plaintext = json.dumps(credentials).encode("utf-8")
    return _get_fernet().encrypt(plaintext)


def decrypt_credentials(encrypted: bytes | memoryview) -> dict[str, Any]:
    """Decrypt Fernet-encrypted bytes back to a credentials dict.

    Accepts memoryview because Django's BinaryField returns memoryview on read.
    Raises cryptography.fernet.InvalidToken if the data is tampered or invalid.
    """
    if isinstance(encrypted, memoryview):
        encrypted = bytes(encrypted)
    plaintext = _get_fernet().decrypt(encrypted)
    result: dict[str, Any] = json.loads(plaintext.decode("utf-8"))
    return result
