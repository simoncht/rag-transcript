"""add conversation sources and collection link

Revision ID: 004_add_conversation_sources
Revises: 003_add_collections
Create Date: 2025-12-06
"""
from datetime import datetime
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "004_add_conversation_sources"
down_revision = "003_add_collections"
branch_labels = None
depends_on = None


def upgrade():
    # Add collection_id to conversations to track collection-synced conversations
    op.add_column(
        "conversations",
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_conversations_collection_id",
        "conversations",
        ["collection_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_conversations_collection_id",
        "conversations",
        "collections",
        ["collection_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Conversation sources table
    op.create_table(
        "conversation_sources",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "video_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("videos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "is_selected",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "added_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("added_via", sa.String(length=50), nullable=True),
        sa.UniqueConstraint(
            "conversation_id",
            "video_id",
            name="uq_conversation_sources_conversation_video",
        ),
    )
    op.create_index(
        "ix_conversation_sources_conversation_id",
        "conversation_sources",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        "ix_conversation_sources_video_id",
        "conversation_sources",
        ["video_id"],
        unique=False,
    )

    # Backfill existing conversations into conversation_sources
    conn = op.get_bind()
    conversations = conn.execute(
        sa.text("SELECT id, selected_video_ids FROM conversations")
    ).fetchall()

    insert_stmt = sa.text(
        """
        INSERT INTO conversation_sources
        (id, conversation_id, video_id, is_selected, added_at, added_via)
        VALUES (:id, :conversation_id, :video_id, :is_selected, :added_at, :added_via)
        ON CONFLICT ON CONSTRAINT uq_conversation_sources_conversation_video DO NOTHING
        """
    )

    for conversation in conversations:
        conv_id = conversation.id
        video_ids = conversation.selected_video_ids or []
        for video_id in video_ids:
            conn.execute(
                insert_stmt,
                {
                    "id": uuid.uuid4(),
                    "conversation_id": conv_id,
                    "video_id": video_id,
                    "is_selected": True,
                    "added_at": datetime.utcnow(),
                    "added_via": "manual",
                },
            )


def downgrade():
    op.drop_index(
        "ix_conversation_sources_video_id",
        table_name="conversation_sources",
    )
    op.drop_index(
        "ix_conversation_sources_conversation_id",
        table_name="conversation_sources",
    )
    op.drop_table("conversation_sources")
    op.drop_constraint(
        "fk_conversations_collection_id",
        "conversations",
        type_="foreignkey",
    )
    op.drop_index("ix_conversations_collection_id", table_name="conversations")
    op.drop_column("conversations", "collection_id")
