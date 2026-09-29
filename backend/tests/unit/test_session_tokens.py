from __future__ import annotations

import base64

from avicola_pro.modules.identity.application.sessions import SessionTokenService

HMAC_KEY = "jUrUWz89-ZPO0xh7ppVRm50Pt-un53S_NSfNCACPXaM"


def test_session_tokens_are_high_entropy_and_only_keyed_hashes_are_persistable() -> None:
    service = SessionTokenService(HMAC_KEY, session_token_bytes=32, csrf_token_bytes=32)

    first = service.issue()
    second = service.issue()

    assert first.session_token != second.session_token
    assert first.csrf_token != second.csrf_token
    assert len(base64.urlsafe_b64decode(first.session_token + "==")) == 32
    assert len(base64.urlsafe_b64decode(first.csrf_token + "==")) == 32
    assert len(first.session_hash) == 32
    assert len(first.csrf_hash) == 32
    assert first.session_token.encode() not in first.session_hash
    assert first.csrf_token.encode() not in first.csrf_hash


def test_session_and_csrf_tokens_use_separate_domains_and_constant_verification() -> None:
    service = SessionTokenService(HMAC_KEY, session_token_bytes=32, csrf_token_bytes=32)
    issued = service.issue()

    assert service.hash_session(issued.session_token) == issued.session_hash
    assert service.verify_csrf(issued.csrf_token, issued.csrf_hash) is True
    assert service.verify_csrf(issued.session_token, issued.csrf_hash) is False
    assert service.verify_csrf("invalid", issued.csrf_hash) is False
