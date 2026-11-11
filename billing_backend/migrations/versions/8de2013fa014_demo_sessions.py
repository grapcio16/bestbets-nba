"""Server-side sessions for the isolated account demo.

Revision ID: 8de2013fa014
Revises: 0c0cccb66a31
"""
from alembic import op
import sqlalchemy as sa
revision = '8de2013fa014'
down_revision = '0c0cccb66a31'
branch_labels = depends_on = None


def upgrade():
    op.create_table('demo_web_sessions',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('billing_accounts.id'), nullable=True),
        sa.Column('csrf', sa.String(64), nullable=False),
        sa.Column('expires_at', sa.BigInteger(), nullable=False))
    op.create_index('ix_demo_web_sessions_user_id', 'demo_web_sessions', ['user_id'])
    op.create_index('ix_demo_web_sessions_expires_at', 'demo_web_sessions', ['expires_at'])
    op.create_table('demo_login_flows',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('session_id', sa.String(64), sa.ForeignKey('demo_web_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('encrypted', sa.Text(), nullable=False),
        sa.Column('expires_at', sa.BigInteger(), nullable=False))
    op.create_index('ix_demo_login_flows_expires_at', 'demo_login_flows', ['expires_at'])


def downgrade():
    op.drop_table('demo_login_flows')
    op.drop_table('demo_web_sessions')
