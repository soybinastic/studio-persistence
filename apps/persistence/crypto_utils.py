"""Encrypt/decrypt sensitive platform connection fields at rest."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _fernet_key() -> bytes:
    configured = getattr(settings, 'TOKEN_ENCRYPTION_KEY', '')
    source = configured or settings.SECRET_KEY
    if isinstance(source, bytes):
        source = source.decode()

    # Accept a proper Fernet key verbatim; otherwise derive one from the passphrase.
    try:
        Fernet(source.encode())
        return source.encode()
    except (ValueError, TypeError):
        digest = hashlib.sha256(source.encode()).digest()
        return base64.urlsafe_b64encode(digest)


def encrypt_secret(value: str) -> str:
    if not value:
        return ''
    return Fernet(_fernet_key()).encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    if not value:
        return ''
    try:
        return Fernet(_fernet_key()).decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise ValueError('Unable to decrypt stored secret') from exc
