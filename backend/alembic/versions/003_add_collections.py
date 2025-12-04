"""Add collections and video organization

Revision ID: 003_add_collections
Revises: 002_fix_boolean
Create Date: 2025-12-03 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003_add_collections'
down_revision: Union[str, None] = '002_fix_boolean'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create collections table
    op.create_table(
        'collections',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('is_default', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )

    # Create unique constraint for default collection per user
    op.create_index('idx_collections_user_id', 'collections', ['user_id'])
    op.create_index('idx_collections_metadata', 'collections', ['metadata'], postgresql_using='gin')
    op.execute("""
        CREATE UNIQUE INDEX unique_user_default
        ON collections(user_id, is_default)
        WHERE is_default = TRUE
    """)

    # Create collection_videos join table
    op.create_table(
        'collection_videos',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('collection_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('video_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('added_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('added_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('position', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['collection_id'], ['collections.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['video_id'], ['videos.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['added_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('collection_id', 'video_id', name='unique_collection_video')
    )

    op.create_index('idx_collection_videos_collection', 'collection_videos', ['collection_id'])
    op.create_index('idx_collection_videos_video', 'collection_videos', ['video_id'])

    # Create collection_members table (for sharing - Phase 4)
    op.create_table(
        'collection_members',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('collection_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('added_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('added_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['collection_id'], ['collections.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['added_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('collection_id', 'user_id', name='unique_collection_member'),
        sa.CheckConstraint("role IN ('owner', 'editor', 'viewer')", name='valid_role')
    )

    op.create_index('idx_collection_members_collection', 'collection_members', ['collection_id'])
    op.create_index('idx_collection_members_user', 'collection_members', ['user_id'])

    # Add tags column to videos table
    op.add_column('videos', sa.Column('tags', postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]"), nullable=False))
    op.create_index('idx_videos_tags', 'videos', ['tags'], postgresql_using='gin')

    # Create default "Uncategorized" collection for existing users
    op.execute("""
        INSERT INTO collections (user_id, name, description, is_default, metadata)
        SELECT
            id as user_id,
            'Uncategorized' as name,
            'Default collection for uncategorized videos' as description,
            TRUE as is_default,
            '{}'::jsonb as metadata
        FROM users
    """)

    # Add all existing videos to their user's default collection
    op.execute("""
        INSERT INTO collection_videos (collection_id, video_id, added_by_user_id)
        SELECT
            c.id as collection_id,
            v.id as video_id,
            v.user_id as added_by_user_id
        FROM videos v
        JOIN collections c ON c.user_id = v.user_id AND c.is_default = TRUE
        WHERE v.is_deleted = FALSE
    """)


def downgrade() -> None:
    # Drop indexes and tables in reverse order
    op.drop_index('idx_videos_tags', table_name='videos')
    op.drop_column('videos', 'tags')

    op.drop_index('idx_collection_members_user', table_name='collection_members')
    op.drop_index('idx_collection_members_collection', table_name='collection_members')
    op.drop_table('collection_members')

    op.drop_index('idx_collection_videos_video', table_name='collection_videos')
    op.drop_index('idx_collection_videos_collection', table_name='collection_videos')
    op.drop_table('collection_videos')

    op.execute('DROP INDEX IF EXISTS unique_user_default')
    op.drop_index('idx_collections_metadata', table_name='collections')
    op.drop_index('idx_collections_user_id', table_name='collections')
    op.drop_table('collections')
