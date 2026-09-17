from __future__ import annotations

import pytest

from avicola_pro.modules.identity.application.credentials import (
    Argon2PasswordService,
    PasswordPolicy,
    PasswordPolicyError,
    generate_temporary_password,
)


def test_password_policy_rejects_short_and_common_passwords() -> None:
    policy = PasswordPolicy(min_length=12, max_length=128)

    with pytest.raises(PasswordPolicyError):
        policy.validate("Short1!")
    with pytest.raises(PasswordPolicyError):
        policy.validate("  PASSWORD123  ")


def test_password_hash_is_argon2id_and_verifies_without_exposing_plaintext() -> None:
    service = Argon2PasswordService(PasswordPolicy(min_length=12, max_length=128))
    password = "Correct-Horse-Avicola-47!"  # noqa: S105 - deliberately fictitious test input

    encoded_hash = service.hash(password)
    verification = service.verify(password, encoded_hash)

    assert encoded_hash.startswith("$argon2id$")
    assert password not in encoded_hash
    assert verification.is_valid is True
    assert verification.updated_hash is None


def test_password_verification_returns_generic_failure_for_mismatch_and_malformed_hash() -> None:
    service = Argon2PasswordService(PasswordPolicy(min_length=12, max_length=128))
    encoded_hash = service.hash("Correct-Horse-Avicola-47!")

    mismatch = service.verify("Different-Valid-Password-82!", encoded_hash)
    malformed = service.verify("Different-Valid-Password-82!", "not-an-argon2-hash")
    non_ascii = service.verify("Different-Valid-Password-82!", "hash-inválido")

    assert mismatch.is_valid is False
    assert mismatch.updated_hash is None
    assert malformed.is_valid is False
    assert malformed.updated_hash is None
    assert non_ascii.is_valid is False
    assert non_ascii.updated_hash is None


def test_password_verification_returns_argon2id_rehash_when_parameters_change() -> None:
    policy = PasswordPolicy(min_length=12, max_length=128)
    old_service = Argon2PasswordService(policy, time_cost=1, memory_cost_kib=8_192, parallelism=1)
    current_service = Argon2PasswordService(policy, time_cost=2, memory_cost_kib=16_384, parallelism=2)
    password = "Correct-Horse-Avicola-47!"  # noqa: S105 - deliberately fictitious test input
    old_hash = old_service.hash(password)

    verification = current_service.verify(password, old_hash)

    assert verification.is_valid is True
    assert verification.updated_hash is not None
    assert verification.updated_hash.startswith("$argon2id$")
    assert current_service.verify(password, verification.updated_hash).updated_hash is None


def test_temporary_passwords_are_unique_and_satisfy_policy() -> None:
    policy = PasswordPolicy(min_length=20, max_length=128)

    generated = {generate_temporary_password(policy, length=24) for _ in range(32)}

    assert len(generated) == 32
    for password in generated:
        policy.validate(password)
        assert len(password) == 24
        assert any(character.islower() for character in password)
        assert any(character.isupper() for character in password)
        assert any(character.isdigit() for character in password)
        assert any(not character.isalnum() for character in password)
