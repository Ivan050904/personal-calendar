"""Sync (D37, wave 4): external ids on events, actor in the changes feed, webhook subscriptions."""
import sqlalchemy as sa
from alembic import op

revision = '0718293a4b52'
down_revision = 'f60718293a41'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('events') as batch:
        batch.add_column(sa.Column('source_client_id', sa.String(64), nullable=True))
        batch.add_column(sa.Column('external_id', sa.String(255), nullable=True))
        batch.create_unique_constraint('uq_events_external_id', ['calendar_id', 'source_client_id', 'external_id'])
    with op.batch_alter_table('calendar_changes') as batch:
        batch.add_column(sa.Column('actor', sa.String(80), nullable=True))
    op.create_table('webhook_subscriptions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('grant_id', sa.String(36), sa.ForeignKey('oauth_grants.id'), nullable=False),
        sa.Column('url', sa.String(2048), nullable=False), sa.Column('secret', sa.String(64), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False), sa.Column('pending', sa.Boolean(), nullable=False),
        sa.Column('next_attempt_at', sa.DateTime()), sa.Column('first_failed_at', sa.DateTime()),
        sa.Column('failures', sa.Integer(), nullable=False), sa.Column('last_error', sa.String(255)),
        sa.Column('last_delivered_at', sa.DateTime()), sa.Column('created_at', sa.DateTime(), nullable=False))
    op.create_index('ix_webhook_subscriptions_grant_id', 'webhook_subscriptions', ['grant_id'])


def downgrade():
    op.drop_index('ix_webhook_subscriptions_grant_id', table_name='webhook_subscriptions')
    op.drop_table('webhook_subscriptions')
    with op.batch_alter_table('calendar_changes') as batch:
        batch.drop_column('actor')
    with op.batch_alter_table('events') as batch:
        batch.drop_constraint('uq_events_external_id', type_='unique')
        batch.drop_column('external_id')
        batch.drop_column('source_client_id')
