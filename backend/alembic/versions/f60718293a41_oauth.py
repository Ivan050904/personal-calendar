"""OAuth 2.0 clients, grants, codes and tokens for connected apps (D35, wave 3)."""
import sqlalchemy as sa
from alembic import op

revision = 'f60718293a41'
down_revision = 'e5f607182930'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('oauth_clients',
        sa.Column('id', sa.String(64), primary_key=True), sa.Column('name', sa.String(255), nullable=False),
        sa.Column('secret_hash', sa.String(64)), sa.Column('client_type', sa.String(16), nullable=False),
        sa.Column('redirect_uris', sa.JSON(), nullable=False), sa.Column('allowed_scopes', sa.JSON(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False), sa.Column('created_at', sa.DateTime(), nullable=False))
    op.create_table('oauth_grants',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('principal_id', sa.String(64), sa.ForeignKey('calendar_principals.id'), nullable=False),
        sa.Column('client_id', sa.String(64), sa.ForeignKey('oauth_clients.id'), nullable=False),
        sa.Column('scopes', sa.JSON(), nullable=False), sa.Column('readable_calendar_ids', sa.JSON(), nullable=False),
        sa.Column('app_calendar_id', sa.String(64), sa.ForeignKey('calendars.id')),
        sa.Column('created_at', sa.DateTime(), nullable=False), sa.Column('last_used_at', sa.DateTime()),
        sa.Column('revoked_at', sa.DateTime()))
    op.create_index('ix_oauth_grants_principal_id', 'oauth_grants', ['principal_id'])
    op.create_index('ix_oauth_grants_client_id', 'oauth_grants', ['client_id'])
    op.create_table('oauth_authorization_codes',
        sa.Column('code_hash', sa.String(64), primary_key=True),
        sa.Column('grant_id', sa.String(36), sa.ForeignKey('oauth_grants.id'), nullable=False),
        sa.Column('client_id', sa.String(64), nullable=False), sa.Column('redirect_uri', sa.String(2048), nullable=False),
        sa.Column('code_challenge', sa.String(128), nullable=False), sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used_at', sa.DateTime()))
    op.create_index('ix_oauth_authorization_codes_grant_id', 'oauth_authorization_codes', ['grant_id'])
    op.create_table('oauth_tokens',
        sa.Column('token_hash', sa.String(64), primary_key=True),
        sa.Column('grant_id', sa.String(36), sa.ForeignKey('oauth_grants.id'), nullable=False),
        sa.Column('kind', sa.String(8), nullable=False), sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('revoked_at', sa.DateTime()), sa.Column('replaced_by', sa.String(64)),
        sa.Column('created_at', sa.DateTime(), nullable=False))
    op.create_index('ix_oauth_tokens_grant_id', 'oauth_tokens', ['grant_id'])


def downgrade():
    for table in ('oauth_tokens', 'oauth_authorization_codes', 'oauth_grants', 'oauth_clients'):
        op.drop_table(table)
