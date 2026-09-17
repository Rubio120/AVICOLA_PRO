from __future__ import annotations

import pytest

from avicola_pro.modules.identity.application.bootstrap import BootstrapIdentity


def test_bootstrap_identity_normalizes_valid_operator_input() -> None:
    identity = BootstrapIdentity.from_input(
        username="  INITIAL.Admin  ",
        email="  Initial.Admin@Example.TEST  ",
        display_name="  Ana   María  ",
    )

    assert identity.username == "initial.admin"
    assert identity.email == "initial.admin@example.test"
    assert identity.display_name == "Ana María"


@pytest.mark.parametrize(
    ("username", "email", "display_name"),
    [
        ("ab", "admin@example.test", "Administrator"),
        ("admin space", "admin@example.test", "Administrator"),
        ("administrator", "not-an-email", "Administrator"),
        ("administrator", "admin@example.test", "   "),
    ],
)
def test_bootstrap_identity_rejects_invalid_operator_input(
    username: str,
    email: str,
    display_name: str,
) -> None:
    with pytest.raises(ValueError):
        BootstrapIdentity.from_input(username=username, email=email, display_name=display_name)
