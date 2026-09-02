"""use clock timestamp on audit tables

Revision ID: 12f424259bd4
Revises: 6ac50fb82673
Create Date: 2026-09-02 01:05:52.290134+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "12f424259bd4"
down_revision: str | None = "6ac50fb82673"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AUDIT_TABLES = ("stage_transitions", "webhook_deliveries")


def upgrade() -> None:
    """Apply the schema changes of this revision."""
    for table_name in AUDIT_TABLES:
        op.alter_column(
            table_name,
            "created_at",
            existing_type=postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            existing_nullable=False,
        )


def downgrade() -> None:
    """Revert the schema changes of this revision."""
    for table_name in reversed(AUDIT_TABLES):
        op.alter_column(
            table_name,
            "created_at",
            existing_type=postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            existing_nullable=False,
        )
