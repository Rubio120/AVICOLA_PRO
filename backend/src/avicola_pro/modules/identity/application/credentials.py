from __future__ import annotations

import secrets
import string
from dataclasses import dataclass

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError

_COMMON_PASSWORDS = frozenset(
    {
        "12345678",
        "administrator",
        "admin123",
        "letmein",
        "password",
        "password123",
        "qwerty",
        "welcome",
    }
)
_TEMPORARY_SPECIAL_CHARACTERS = "!#$%&*+-=?@_"
_TARGET_TEMPORARY_PASSWORD_LENGTH = 24


class PasswordPolicyError(ValueError):
    """Raised when a new password does not meet the configured policy."""


@dataclass(frozen=True, slots=True)
class PasswordPolicy:
    """Length and basic common-password policy for new credentials."""

    min_length: int
    max_length: int

    def __post_init__(self) -> None:
        if self.min_length < 1 or self.max_length < self.min_length:
            raise ValueError("invalid password length policy")

    def validate(self, password: str) -> None:
        """Reject passwords outside the length bounds or on the basic denylist."""
        if not self.min_length <= len(password) <= self.max_length:
            raise PasswordPolicyError("password does not meet policy")
        if password.strip().casefold() in _COMMON_PASSWORDS:
            raise PasswordPolicyError("password does not meet policy")


@dataclass(frozen=True, slots=True)
class PasswordVerification:
    """Generic verification outcome with an optional replacement hash."""

    is_valid: bool
    updated_hash: str | None = None


class Argon2PasswordService:
    """Hash and verify credentials exclusively with Argon2id."""

    def __init__(
        self,
        policy: PasswordPolicy,
        *,
        time_cost: int = 3,
        memory_cost_kib: int = 65_536,
        parallelism: int = 4,
    ) -> None:
        self._policy = policy
        self._hasher = PasswordHasher(
            time_cost=time_cost,
            memory_cost=memory_cost_kib,
            parallelism=parallelism,
            hash_len=32,
            salt_len=16,
            type=Type.ID,
        )

    def hash(self, password: str) -> str:
        """Validate and encode a new password using Argon2id."""
        self._policy.validate(password)
        return self._hasher.hash(password)

    def verify(self, password: str, encoded_hash: str) -> PasswordVerification:
        """Return a generic result for mismatches/malformed hashes and rehash valid old encodings."""
        try:
            if not self._hasher.verify(encoded_hash, password):
                return PasswordVerification(is_valid=False)
            updated_hash = self._hasher.hash(password) if self._hasher.check_needs_rehash(encoded_hash) else None
        except (InvalidHashError, UnicodeError, VerificationError):
            return PasswordVerification(is_valid=False)
        return PasswordVerification(is_valid=True, updated_hash=updated_hash)


def generate_temporary_password(policy: PasswordPolicy, *, length: int | None = None) -> str:
    """Generate a policy-compliant temporary password with the operating-system CSPRNG."""
    if length is None:
        length = min(max(_TARGET_TEMPORARY_PASSWORD_LENGTH, policy.min_length), policy.max_length)
    if length < max(policy.min_length, 4) or length > policy.max_length:
        raise ValueError("temporary password length is outside policy")

    groups = (string.ascii_lowercase, string.ascii_uppercase, string.digits, _TEMPORARY_SPECIAL_CHARACTERS)
    characters = [secrets.choice(group) for group in groups]
    alphabet = "".join(groups)
    characters.extend(secrets.choice(alphabet) for _ in range(length - len(characters)))
    for index in range(len(characters) - 1, 0, -1):
        swap_index = secrets.randbelow(index + 1)
        characters[index], characters[swap_index] = characters[swap_index], characters[index]
    password = "".join(characters)
    policy.validate(password)
    return password
