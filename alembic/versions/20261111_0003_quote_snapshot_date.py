"""nullable snapshot_date on quotes with partial unique index

Revision ID: 20261111_0003
Revises: 20261111_0002
Create Date: 2026-11-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261111_0003"
down_revision: Union[str, Sequence[str], None] = "20261111_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "quotes",
        sa.Column("snapshot_date", sa.Date(), nullable=True),
    )
    op.create_index(
        "uq_quotes_ticker_snapshot_date",
        "quotes",
        ["ticker", "snapshot_date"],
        unique=True,
        postgresql_where=sa.text("snapshot_date IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_quotes_ticker_snapshot_date",
        table_name="quotes",
        postgresql_where=sa.text("snapshot_date IS NOT NULL"),
    )
    op.drop_column("quotes", "snapshot_date")
