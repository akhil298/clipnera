"""Pro price: ₹699 a month

Revision ID: 20260927020000
Revises: 20260927010000
Create Date: 2026-09-27 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260927020000"
down_revision: Union[str, None] = "20260927010000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE plans SET price_inr = 699 WHERE slug = 'pro'")


def downgrade() -> None:
    op.execute("UPDATE plans SET price_inr = 499 WHERE slug = 'pro'")
