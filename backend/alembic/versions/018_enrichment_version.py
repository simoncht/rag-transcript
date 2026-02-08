"""Add enrichment_version column to chunks for tracking re-enrichment

Revision ID: 018
Revises: 017
Create Date: 2026-02-07

Adds enrichment_version to chunks table so we can track which enrichment
strategy was used (v1 = original, v2 = full contextual enrichment).
New chunks default to v2; existing chunks remain at v1 for lazy re-enrichment.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chunks",
        sa.Column(
            "enrichment_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )


def downgrade() -> None:
    op.drop_column("chunks", "enrichment_version")
