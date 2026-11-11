"""initial sandbox accounts and billing records"""
from alembic import op
import sqlalchemy as sa

revision = '0c0cccb66a31'
down_revision = None
branch_labels = None
depends_on = None
def upgrade():
    op.create_table('billing_accounts',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('issuer', sa.String(length=512), nullable=False),
    sa.Column('subject', sa.String(length=255), nullable=False),
    sa.Column('customer_id', sa.String(length=128), nullable=True),
    sa.Column('disabled', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.BigInteger(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('customer_id'),
    sa.UniqueConstraint('issuer', 'subject')
    )
    op.create_table('billing_rate_limits',
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('window', sa.BigInteger(), nullable=False),
    sa.Column('count', sa.Integer(), nullable=False),
    sa.Column('expires_at', sa.BigInteger(), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    op.create_table('billing_checkouts',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('session_id', sa.String(length=128), nullable=True),
    sa.Column('created_at', sa.BigInteger(), nullable=False),
    sa.Column('expires_at', sa.BigInteger(), nullable=False),
    sa.Column('closed', sa.Boolean(), nullable=False),
    sa.Column('terms_version', sa.String(length=80), nullable=False),
    sa.Column('price_id', sa.String(length=128), nullable=False),
    sa.Column('consent_at', sa.BigInteger(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['billing_accounts.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('session_id')
    )
    op.create_index(op.f('ix_billing_checkouts_user_id'), 'billing_checkouts', ['user_id'], unique=False)
    op.create_index('uq_billing_open_checkout', 'billing_checkouts', ['user_id'], unique=True, postgresql_where=sa.text('closed IS FALSE'), sqlite_where=sa.text('closed IS 0'))
    op.create_table('billing_entitlements',
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('granted', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=48), nullable=False),
    sa.Column('paid_until', sa.BigInteger(), nullable=False),
    sa.Column('checked_at', sa.BigInteger(), nullable=False),
    sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False),
    sa.Column('subscription_id', sa.String(length=128), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['billing_accounts.id'], ),
    sa.PrimaryKeyConstraint('user_id')
    )
    op.create_table('billing_events',
    sa.Column('id', sa.String(length=128), nullable=False),
    sa.Column('payload_hash', sa.String(length=64), nullable=False),
    sa.Column('kind', sa.String(length=80), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=True),
    sa.Column('outcome', sa.String(length=32), nullable=False),
    sa.Column('processed_at', sa.BigInteger(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['billing_accounts.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('billing_subscriptions',
    sa.Column('id', sa.String(length=128), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('customer_id', sa.String(length=128), nullable=False),
    sa.Column('status', sa.String(length=48), nullable=False),
    sa.Column('price_id', sa.String(length=128), nullable=False),
    sa.Column('paid_until', sa.BigInteger(), nullable=False),
    sa.Column('checked_at', sa.BigInteger(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['billing_accounts.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_billing_subscriptions_user_id'), 'billing_subscriptions', ['user_id'], unique=False)
def downgrade():
    op.drop_index(op.f('ix_billing_subscriptions_user_id'), table_name='billing_subscriptions')
    op.drop_table('billing_subscriptions')
    op.drop_table('billing_events')
    op.drop_table('billing_entitlements')
    op.drop_index('uq_billing_open_checkout', table_name='billing_checkouts', postgresql_where=sa.text('closed IS FALSE'), sqlite_where=sa.text('closed IS 0'))
    op.drop_index(op.f('ix_billing_checkouts_user_id'), table_name='billing_checkouts')
    op.drop_table('billing_checkouts')
    op.drop_table('billing_rate_limits')
    op.drop_table('billing_accounts')
