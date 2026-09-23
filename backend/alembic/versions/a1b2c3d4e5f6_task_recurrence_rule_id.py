"""task_recurrence_rule_id

Revision ID: a1b2c3d4e5f6
Revises: 3c6a18423f34
Create Date: 2026-09-23 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '3c6a18423f34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tasks', sa.Column('recurrence_rule_id', sa.String(length=64), nullable=True))
    op.create_index(op.f('ix_tasks_recurrence_rule_id'), 'tasks', ['recurrence_rule_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_tasks_recurrence_rule_id'), table_name='tasks')
    op.drop_column('tasks', 'recurrence_rule_id')
