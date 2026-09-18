from __future__ import annotations

from avicola_pro.bootstrap.app import create_app
from avicola_pro.shared.infrastructure.config import Settings

DATABASE_URL = "postgresql+psycopg://avicola:local-test-password@127.0.0.1:55432/avicola_pro_test"
SESSION_HMAC_KEY = "jUrUWz89-ZPO0xh7ppVRm50Pt-un53S_NSfNCACPXaM"


class _Database:
    session_factory = object()

    async def check_ready(self) -> None:
        return None

    async def dispose(self) -> None:
        return None


def test_delivery_two_admin_routes_are_registered() -> None:
    app = create_app(
        Settings(_env_file=None, database_url=DATABASE_URL, session_hmac_key=SESSION_HMAC_KEY),
        database=_Database(),
    )
    paths = set(app.openapi()["paths"])

    assert "/api/v1/users" in paths
    assert "/api/v1/roles" in paths
    assert "/api/v1/permissions" in paths
    assert "/api/v1/audit-events" in paths
