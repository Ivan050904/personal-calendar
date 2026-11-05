"""external_id on tasks and plans (D37, wave 5): v2 now writes them too."""
import sqlalchemy as sa
from alembic import op

revision = '18293a4b5c63'
down_revision = '0718293a4b52'
branch_labels = None
depends_on = None


def upgrade():
    for table in ('tasks', 'plans'):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column('source_client_id', sa.String(64), nullable=True))
            batch.add_column(sa.Column('external_id', sa.String(255), nullable=True))
            batch.create_unique_constraint(f'uq_{table}_external_id', ['calendar_id', 'source_client_id', 'external_id'])


def downgrade():
    for table in ('plans', 'tasks'):
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(f'uq_{table}_external_id', type_='unique')
            batch.drop_column('external_id')
            batch.drop_column('source_client_id')
