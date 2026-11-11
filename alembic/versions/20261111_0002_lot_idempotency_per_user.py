"""per-user unique idempotency keys on lots

Revision ID: 20261111_0002
Revises: 20261017_0001
Create Date: 2026-11-11

"""

from typing import Sequence, Union

from alembic import op

revision: str = "20261111_0002"
down_revision: Union[str, Sequence[str], None] = "20261017_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("lots_idempotency_key_key", "lots", type_="unique")
    op.create_unique_constraint(
        "uq_lots_user_idempotency_key",
        "lots",
        ["user_id", "idempotency_key"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_lots_user_idempotency_key", "lots", type_="unique")
    op.create_unique_constraint(
        "lots_idempotency_key_key",
        "lots",
        ["idempotency_key"],
    )
