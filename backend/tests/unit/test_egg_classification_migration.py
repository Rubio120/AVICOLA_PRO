from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any, cast
from uuid import uuid4

import pytest

MIGRATION_PATH = Path(__file__).resolve().parents[2] / "migrations" / "versions" / "0014_egg_classification_reversal.py"


def _load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("egg_classification_reversal", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_downgrade_refuses_to_remove_multiple_classification_history() -> None:
    migration = _load_migration()
    duplicate_event_id = uuid4()
    constraint_creations: list[tuple[object, ...]] = []

    class Result:
        def scalar_one_or_none(self) -> object:
            return duplicate_event_id

    class Connection:
        def execute(self, _: object) -> Result:
            return Result()

    class Operations:
        def get_bind(self) -> Connection:
            return Connection()

        def create_unique_constraint(self, *arguments: object) -> None:
            constraint_creations.append(arguments)

    cast(Any, migration).op = Operations()

    with pytest.raises(RuntimeError, match="classification history exists"):
        migration.downgrade()

    assert constraint_creations == []
