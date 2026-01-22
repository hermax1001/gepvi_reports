"""init

Revision ID: 0001
Revises:
Create Date: 2025-11-19 13:35:08.996410

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create schema
    op.execute('CREATE SCHEMA IF NOT EXISTS gepvi_users')

    # Create users table
    op.create_table(
        'users',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('telegram_user_id', sa.String(), nullable=True),
        sa.Column('subscription_expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('user_id'),
        schema='gepvi_users'
    )
    op.create_index('idx_users_telegram_user_id', 'users', ['telegram_user_id'], schema='gepvi_users', unique=True)
    op.create_index('idx_users_created_at', 'users', ['created_at'], schema='gepvi_users')
    op.create_index('idx_users_subscription_expires_at', 'users', ['subscription_expires_at'], schema='gepvi_users')

    # Create webhooks table
    op.create_table(
        'webhooks',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('provider_name', sa.String(), nullable=False),
        sa.Column('webhook_payload', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('response_code', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        schema='gepvi_users'
    )
    op.create_index('idx_webhooks_created_at', 'webhooks', ['created_at'], schema='gepvi_users')


def downgrade():
    op.drop_index('idx_webhooks_created_at', table_name='webhooks', schema='gepvi_users')
    op.drop_table('webhooks', schema='gepvi_users')
    op.drop_index('idx_users_subscription_expires_at', table_name='users', schema='gepvi_users')
    op.drop_index('idx_users_created_at', table_name='users', schema='gepvi_users')
    op.drop_index('idx_users_telegram_user_id', table_name='users', schema='gepvi_users')
    op.drop_table('users', schema='gepvi_users')
    op.execute('DROP SCHEMA IF EXISTS gepvi_users CASCADE')
