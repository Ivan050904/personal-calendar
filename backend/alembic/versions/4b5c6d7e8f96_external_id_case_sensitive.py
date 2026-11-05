"""Case-sensitive external_id on MySQL/MariaDB (D37).

An app's own id is opaque: `Lesson-1` and `lesson-1` are two records. MariaDB's default collation
(utf8mb4_uca1400_ai_ci in mariadb:11) ignores case and accents, so a resend of one would update the
other. SQLite compares bytes already; nothing to do there."""
from alembic import op
from sqlalchemy.dialects import mysql

revision = '4b5c6d7e8f96'
down_revision = '3a4b5c6d7e85'
branch_labels = None
depends_on = None

TABLES = ('events', 'tasks', 'plans')


def _mysql():
    return op.get_bind().dialect.name in ('mysql', 'mariadb')


def upgrade():
    if _mysql():
        for table in TABLES:
            op.alter_column(table, 'external_id', type_=mysql.VARCHAR(255, collation='utf8mb4_bin'),
                            existing_type=mysql.VARCHAR(255), existing_nullable=True)


def downgrade():
    # Fails on the unique key if an app stored ids that differ only in case; that data needs review first.
    if _mysql():
        for table in TABLES:
            op.alter_column(table, 'external_id', type_=mysql.VARCHAR(255),
                            existing_type=mysql.VARCHAR(255, collation='utf8mb4_bin'), existing_nullable=True)
