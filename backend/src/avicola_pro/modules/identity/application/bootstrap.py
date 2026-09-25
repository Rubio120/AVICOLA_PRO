from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from uuid import UUID

_USERNAME_PATTERN = re.compile(r"^[a-z][a-z0-9._-]{2,63}$")
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _contains_unicode_control(value: str) -> bool:
    return any(unicodedata.category(character) in {"Cc", "Cf"} for character in value)


class BootstrapError(RuntimeError):
    """Base class for safe initial-administrator bootstrap failures."""


class BootstrapAlreadyCompletedError(BootstrapError):
    """Raised when an administrator assignment or conflicting identity already exists."""


class BootstrapConfigurationError(BootstrapError):
    """Raised when the seeded administrator role is unavailable."""


@dataclass(frozen=True, slots=True)
class BootstrapIdentity:
    """Validated and normalized identity for the initial administrator."""

    username: str
    email: str
    display_name: str

    @classmethod
    def from_input(cls, *, username: str, email: str, display_name: str) -> BootstrapIdentity:
        """Normalize operator input and reject values outside persistence constraints."""
        if any(_contains_unicode_control(value) for value in (username, email, display_name)):
            raise ValueError("input contains Unicode control characters")
        normalized_username = unicodedata.normalize("NFKC", username).strip().casefold()
        normalized_email = unicodedata.normalize("NFKC", email).strip().casefold()
        normalized_display_name = " ".join(unicodedata.normalize("NFC", display_name).split())
        if not _USERNAME_PATTERN.fullmatch(normalized_username):
            raise ValueError("invalid username")
        if len(normalized_email) > 320 or not _EMAIL_PATTERN.fullmatch(normalized_email):
            raise ValueError("invalid email")
        if not normalized_display_name or len(normalized_display_name) > 160:
            raise ValueError("invalid display name")
        return cls(
            username=normalized_username,
            email=normalized_email,
            display_name=normalized_display_name,
        )


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    """One-time bootstrap output; callers must not persist or log the temporary password."""

    user_id: UUID
    temporary_password: str
