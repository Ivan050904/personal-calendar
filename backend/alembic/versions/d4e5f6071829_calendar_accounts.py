"""Own calendar accounts: login, password hash, display name (D34, wave 1)."""
import sqlalchemy as sa
from alembic import op

revision = 'd4e5f6071829'
down_revision = 'c3d4e5f60718'
branch_labels = None
depends_on = None


def upgrade():
    # batch mode: plain ALTER on MySQL/MariaDB, copy-and-move on SQLite.
    with op.batch_alter_table('calendar_principals') as batch:
        batch.add_column(sa.Column('login', sa.String(32), nullable=True))
        batch.add_column(sa.Column('password_hash', sa.String(255), nullable=True))
        batch.add_column(sa.Column('display_name', sa.String(255), nullable=True))
        batch.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
        batch.create_unique_constraint('uq_calendar_principals_login', ['login'])


def downgrade():
    with op.batch_alter_table('calendar_principals') as batch:
        batch.drop_constraint('uq_calendar_principals_login', type_='unique')
        for column in ('created_at', 'display_name', 'password_hash', 'login'):
            batch.drop_column(column)
