"""add password reset OTP attempt limits

Revision ID: 0a2108a0b1cd
Revises: e30e0f01adda
Create Date: 2026-11-14 14:19:25.964083

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0a2108a0b1cd'
down_revision = 'e30e0f01adda'
branch_labels = None
depends_on = None



def upgrade():
    with op.batch_alter_table('password_reset_tokens', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('attempt_count', sa.Integer(), server_default='0', nullable=False)
        )
        batch_op.add_column(
            sa.Column('max_attempts', sa.Integer(), server_default='5', nullable=False)
        )

        batch_op.create_check_constraint(
            'ck_password_reset_token_hash_nonempty',
            'length(token_hash) > 0'
        )
        batch_op.create_check_constraint(
            'ck_password_reset_attempt_count_valid',
            'attempt_count >= 0 AND attempt_count <= max_attempts'
        )
        batch_op.create_check_constraint(
            'ck_password_reset_max_attempts_positive',
            'max_attempts > 0'
        )


def downgrade():
    with op.batch_alter_table('password_reset_tokens', schema=None) as batch_op:
        batch_op.drop_constraint(
            'ck_password_reset_max_attempts_positive',
            type_='check'
        )
        batch_op.drop_constraint(
            'ck_password_reset_attempt_count_valid',
            type_='check'
        )
        batch_op.drop_constraint(
            'ck_password_reset_token_hash_nonempty',
            type_='check'
        )
        batch_op.drop_column('max_attempts')
        batch_op.drop_column('attempt_count')
