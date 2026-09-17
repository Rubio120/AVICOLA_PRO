from __future__ import annotations

from importlib import import_module

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base shared by all persistence modules."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


metadata = Base.metadata


def load_persistence_models() -> None:
    """Register every persisted model on the shared metadata."""

    import_module("avicola_pro.modules.identity.infrastructure.models")
    import_module("avicola_pro.modules.audit.infrastructure.models")
