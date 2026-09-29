from __future__ import annotations

from avicola_pro.modules.production.infrastructure import models as production_models
from avicola_pro.shared.infrastructure.models import Base


def test_egg_production_event_model_is_registered_with_safe_count_and_idempotency() -> None:
    _ = production_models
    table = Base.metadata.tables.get("egg_production_events")
    assert table is not None
    assert "idempotency_key" in table.c
    checks = [constraint for constraint in table.constraints if hasattr(constraint, "sqltext")]
    assert any("egg_count >= 0" in str(constraint.sqltext) for constraint in checks)
