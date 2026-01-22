"""Remove Clerk fields and add NextAuth OAuth fields

Revision ID: 010_remove_clerk_add_nextauth
Revises: 009_add_subscriptions
Create Date: 2026-01-19
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade():
    # Add new OAuth fields
    op.add_column('users', sa.Column('oauth_provider', sa.String(length=50), nullable=True))
    op.add_column('users', sa.Column('oauth_provider_id', sa.String(length=255), nullable=True))
    op.create_index('ix_users_oauth_provider_id', 'users', ['oauth_provider_id'])

    # Remove Clerk field
    op.drop_index('ix_users_clerk_user_id', table_name='users')
    op.drop_column('users', 'clerk_user_id')


def downgrade():
    # Re-add Clerk field
    op.add_column('users', sa.Column('clerk_user_id', sa.String(length=255), nullable=True))
    op.create_index('ix_users_clerk_user_id', 'users', ['clerk_user_id'], unique=True)

    # Remove OAuth fields
    op.drop_index('ix_users_oauth_provider_id', table_name='users')
    op.drop_column('users', 'oauth_provider_id')
    op.drop_column('users', 'oauth_provider')
