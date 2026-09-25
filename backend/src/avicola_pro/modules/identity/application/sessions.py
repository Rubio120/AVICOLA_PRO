from __future__ import annotations

import hashlib
import hmac
import secrets
from base64 import urlsafe_b64decode
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IssuedSessionTokens:
    """Usable credentials paired with their persistence-safe keyed hashes."""

    session_token: str
    csrf_token: str
    session_hash: bytes
    csrf_hash: bytes


class SessionTokenService:
    """Issue and verify opaque session credentials."""

    def __init__(self, hmac_key: str, *, session_token_bytes: int, csrf_token_bytes: int) -> None:
        self._key = urlsafe_b64decode(hmac_key + "=" * (-len(hmac_key) % 4))
        self._session_token_bytes = session_token_bytes
        self._csrf_token_bytes = csrf_token_bytes

    def _digest(self, domain: bytes, token: str) -> bytes:
        return hmac.digest(self._key, domain + b"\0" + token.encode("utf-8"), hashlib.sha256)

    def hash_session(self, token: str) -> bytes:
        """Derive the database lookup key for an opaque session token."""
        return self._digest(b"session", token)

    def issue(self) -> IssuedSessionTokens:
        """Create independent CSPRNG session and CSRF credentials."""
        session_token = secrets.token_urlsafe(self._session_token_bytes)
        csrf_token = secrets.token_urlsafe(self._csrf_token_bytes)
        return IssuedSessionTokens(
            session_token=session_token,
            csrf_token=csrf_token,
            session_hash=self.hash_session(session_token),
            csrf_hash=self._digest(b"csrf", csrf_token),
        )

    def verify_csrf(self, candidate: str, expected_hash: bytes) -> bool:
        """Compare a presented CSRF credential without data-dependent early exit."""
        return hmac.compare_digest(self._digest(b"csrf", candidate), expected_hash)
