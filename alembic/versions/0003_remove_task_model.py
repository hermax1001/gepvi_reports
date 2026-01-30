"""remove task model

Revision ID: 0003
Revises: 0002
Create Date: 2026-01-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    # Make task_id nullable first
    op.alter_column('reports', 'task_id', nullable=True, schema='gepvi_reports')

    # Set all task_id to NULL
    op.execute("UPDATE gepvi_reports.reports SET task_id = NULL")

    # Drop FK constraint
    op.drop_constraint('reports_task_id_fkey', 'reports', schema='gepvi_reports', type_='foreignkey')

    # Drop task_id column
    op.drop_column('reports', 'task_id', schema='gepvi_reports')

    # Drop tasks table indexes
    op.drop_index('idx_tasks_user_id', table_name='tasks', schema='gepvi_reports')
    op.drop_index('idx_tasks_next_task_time', table_name='tasks', schema='gepvi_reports')

    # Drop tasks table
    op.drop_table('tasks', schema='gepvi_reports')


def downgrade():
    # Recreate tasks table
    op.create_table(
        'tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('next_task_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('period', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        schema='gepvi_reports'
    )

    # Recreate indexes
    op.create_index('idx_tasks_user_id', 'tasks', ['user_id'], unique=False, schema='gepvi_reports')
    op.create_index('idx_tasks_next_task_time', 'tasks', ['next_task_time'], unique=False, schema='gepvi_reports')

    # Add task_id column back (nullable first)
    op.add_column('reports', sa.Column('task_id', sa.Integer(), nullable=True), schema='gepvi_reports')

    # Add FK constraint
    op.create_foreign_key('reports_task_id_fkey', 'reports', 'tasks', ['task_id'], ['id'], source_schema='gepvi_reports', referent_schema='gepvi_reports')

    # Note: We cannot restore the task_id data as it was deleted
