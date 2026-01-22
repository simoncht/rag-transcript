"""add subscriptions table

Revision ID: 009
Revises: 008
Create Date: 2026-01-18

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '009'
down_revision = '008_add_admin_audit_logs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create subscriptions table
    op.create_table(
        'subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('stripe_subscription_id', sa.String(length=255), nullable=True),
        sa.Column('stripe_customer_id', sa.String(length=255), nullable=False),
        sa.Column('stripe_price_id', sa.String(length=255), nullable=False),
        sa.Column('tier', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('current_period_start', sa.DateTime(), nullable=True),
        sa.Column('current_period_end', sa.DateTime(), nullable=True),
        sa.Column('cancel_at_period_end', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('canceled_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )

    # Create indexes
    op.create_index(op.f('ix_subscriptions_user_id'), 'subscriptions', ['user_id'], unique=False)
    op.create_index(op.f('ix_subscriptions_stripe_subscription_id'), 'subscriptions', ['stripe_subscription_id'], unique=True)
    op.create_index(op.f('ix_subscriptions_stripe_customer_id'), 'subscriptions', ['stripe_customer_id'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f('ix_subscriptions_stripe_customer_id'), table_name='subscriptions')
    op.drop_index(op.f('ix_subscriptions_stripe_subscription_id'), table_name='subscriptions')
    op.drop_index(op.f('ix_subscriptions_user_id'), table_name='subscriptions')

    # Drop table
    op.drop_table('subscriptions')
