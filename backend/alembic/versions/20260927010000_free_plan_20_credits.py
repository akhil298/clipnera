"""Free plan allowance: 20 credits per cycle

Revision ID: 20260927010000
Revises: 20260926090000
Create Date: 2026-09-27 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260927010000"
down_revision: Union[str, None] = "20260926090000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE plans SET credit_minutes = 20 WHERE slug = 'free'")


def downgrade() -> None:
    op.execute("UPDATE plans SET credit_minutes = 60 WHERE slug = 'free'")
