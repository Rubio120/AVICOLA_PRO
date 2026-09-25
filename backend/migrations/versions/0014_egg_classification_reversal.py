"""Allow immutable history of reversed egg classifications."""

import sqlalchemy as sa
from alembic import op

revision = "0014_egg_classification_reversal"
down_revision = "0013_sales_channel"
branch_labels = None
depends_on = None

_CLASSIFICATION_EVENT_UNIQUE = "uq_egg_production_classifications_production_event_id"


def upgrade() -> None:
    op.drop_constraint(
        _CLASSIFICATION_EVENT_UNIQUE,
        "egg_production_classifications",
        type_="unique",
    )


def downgrade() -> None:
    duplicate_event_id = op.get_bind().execute(
        sa.text(
            "select production_event_id from egg_production_classifications "
            "group by production_event_id having count(*) > 1 limit 1"
        )
    ).scalar_one_or_none()
    if duplicate_event_id is not None:
        raise RuntimeError("cannot restore one-classification-per-event uniqueness while classification history exists")
    op.create_unique_constraint(
        _CLASSIFICATION_EVENT_UNIQUE,
        "egg_production_classifications",
        ["production_event_id"],
    )
