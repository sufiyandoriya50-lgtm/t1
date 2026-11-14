
"""add Google identity to users

Revision ID: 8285647efa97
Revises: 6537462b7d87
"""

from alembic import op
import sqlalchemy as sa

revision = '8285647efa97'
down_revision = '6537462b7d87'
branch_labels = None
depends_on = None


def upgrade():
    # Add the nullable column directly without rebuilding users.
    op.add_column(
        'users',
        sa.Column('google_sub', sa.String(length=255), nullable=True)
    )

    # Enforce uniqueness for linked Google accounts.
    op.create_index(
        'ix_users_google_sub',
        'users',
        ['google_sub'],
        unique=True
    )


def downgrade():
    op.drop_index('ix_users_google_sub', table_name='users')
    op.drop_column('users', 'google_sub')
