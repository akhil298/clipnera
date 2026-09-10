"""add_subscription_system

Revision ID: 20250905150000
Revises: 20250904140000
Create Date: 2025-09-05 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20250905150000'
down_revision: Union[str, None] = '20250904140000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'plans',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('slug', sa.Enum('free', 'pro', 'pro_plus', name='plan_slug'), nullable=False),
        sa.Column('credit_minutes', sa.Integer(), nullable=False),
        sa.Column('price_monthly', sa.Numeric(10, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('features', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_plans_slug'), 'plans', ['slug'], unique=True)

    op.create_table(
        'user_subscriptions',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('plan_id', sa.String(36), nullable=False),
        sa.Column('status', sa.Enum('active', 'canceled', 'expired', 'pending', name='subscription_status'), nullable=False),
        sa.Column('current_period_start', sa.DateTime(), nullable=False),
        sa.Column('current_period_end', sa.DateTime(), nullable=False),
        sa.Column('canceled_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['plan_id'], ['plans.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_user_subscriptions_user_id'), 'user_subscriptions', ['user_id'], unique=False)

    op.create_table(
        'payment_transactions',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('plan_id', sa.String(36), nullable=False),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('status', sa.Enum('pending', 'success', 'failed', name='payment_status'), nullable=False),
        sa.Column('payment_uuid', sa.String(36), nullable=False),
        sa.Column('payment_method', sa.String(50), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['plan_id'], ['plans.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_payment_transactions_payment_uuid'), 'payment_transactions', ['payment_uuid'], unique=True)
    op.create_index(op.f('ix_payment_transactions_user_id'), 'payment_transactions', ['user_id'], unique=False)

    op.create_table(
        'credit_ledger',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('balance_after', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(255), nullable=False),
        sa.Column('reference_id', sa.String(36), nullable=True),
        sa.Column('reference_type', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_credit_ledger_user_id'), 'credit_ledger', ['user_id'], unique=False)
    op.create_index(op.f('ix_credit_ledger_reference_id'), 'credit_ledger', ['reference_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_credit_ledger_reference_id'), table_name='credit_ledger')
    op.drop_index(op.f('ix_credit_ledger_user_id'), table_name='credit_ledger')
    op.drop_table('credit_ledger')
    op.drop_index(op.f('ix_payment_transactions_user_id'), table_name='payment_transactions')
    op.drop_index(op.f('ix_payment_transactions_payment_uuid'), table_name='payment_transactions')
    op.drop_table('payment_transactions')
    op.drop_index(op.f('ix_user_subscriptions_user_id'), table_name='user_subscriptions')
    op.drop_table('user_subscriptions')
    op.drop_index(op.f('ix_plans_slug'), table_name='plans')
    op.drop_table('plans')
    op.execute('DROP TYPE IF EXISTS plan_slug')
    op.execute('DROP TYPE IF EXISTS subscription_status')
    op.execute('DROP TYPE IF EXISTS payment_status')
