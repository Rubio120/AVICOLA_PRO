"""Establish an empty schema baseline for the technical foundation.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-09-16
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create no business tables in Delivery 1."""


def downgrade() -> None:
    """Remove no business tables from Delivery 1."""
