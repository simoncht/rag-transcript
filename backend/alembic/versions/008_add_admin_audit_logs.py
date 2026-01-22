"""add admin audit logs for chat monitoring

Revision ID: 008_add_admin_audit_logs
Revises: 007_add_conversation_facts
Create Date: 2026-01-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "008_add_admin_audit_logs"
down_revision: Union[str, None] = "007_add_conversation_facts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admin_audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("role", sa.String(length=20), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("flags", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("message_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ip_hash", sa.String(length=128), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_audit_logs_event_type", "admin_audit_logs", ["event_type"], unique=False)
    op.create_index("ix_admin_audit_logs_user_id", "admin_audit_logs", ["user_id"], unique=False)
    op.create_index("ix_admin_audit_logs_conversation_id", "admin_audit_logs", ["conversation_id"], unique=False)
    op.create_index("ix_admin_audit_logs_message_id", "admin_audit_logs", ["message_id"], unique=False)
    op.create_index("ix_admin_audit_logs_created_at", "admin_audit_logs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_admin_audit_logs_created_at", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_message_id", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_conversation_id", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_user_id", table_name="admin_audit_logs")
    op.drop_index("ix_admin_audit_logs_event_type", table_name="admin_audit_logs")
    op.drop_table("admin_audit_logs")
