"""Microsecond recorded_at on confirmations for MySQL/MariaDB.

Undo of a task completion picks the latest fact by recorded_at; with whole seconds two completions in
one second tie and the undo is refused at random. SQLite already keeps microseconds."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = '3a4b5c6d7e85'
down_revision = '293a4b5c6d74'
branch_labels = None
depends_on = None


def _mysql():
    return op.get_bind().dialect.name in ('mysql', 'mariadb')


def upgrade():
    if _mysql():
        op.alter_column('calendar_confirmations', 'recorded_at', type_=mysql.DATETIME(fsp=6),
                        existing_type=sa.DateTime(), existing_nullable=False)


def downgrade():
    if _mysql():
        op.alter_column('calendar_confirmations', 'recorded_at', type_=sa.DateTime(),
                        existing_type=mysql.DATETIME(fsp=6), existing_nullable=False)
