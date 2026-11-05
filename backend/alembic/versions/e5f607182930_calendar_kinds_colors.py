"""Several calendars per account: kind, app source, colour, visibility, order (D36, wave 2)."""
import sqlalchemy as sa
from alembic import op

revision = 'e5f607182930'
down_revision = 'd4e5f6071829'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('calendars') as batch:
        batch.add_column(sa.Column('kind', sa.String(16), nullable=False, server_default='user'))
        batch.add_column(sa.Column('source_client_id', sa.String(64), nullable=True))
        batch.add_column(sa.Column('color', sa.String(16), nullable=False, server_default='#0f766e'))
        batch.add_column(sa.Column('visible', sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.add_column(sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'))
        batch.create_index('ix_calendars_source_client_id', ['source_client_id'])
    # The existing default calendar of each owner is its «Личное».
    op.execute("UPDATE calendars SET kind = 'personal' WHERE default_owner IS NOT NULL")


def downgrade():
    with op.batch_alter_table('calendars') as batch:
        batch.drop_index('ix_calendars_source_client_id')
        for column in ('sort_order', 'visible', 'color', 'source_client_id', 'kind'):
            batch.drop_column(column)
