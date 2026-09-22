"""Baseline schema placeholder for Wave 1.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-09-18

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "0001_baseline"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Entity tables land in Wave 2.
    pass


def downgrade() -> None:
    pass
