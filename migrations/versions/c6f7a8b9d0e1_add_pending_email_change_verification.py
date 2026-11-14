"""add pending email change verification"""

from alembic import op
import sqlalchemy as sa

revision = "c6f7a8b9d0e1"
down_revision = "8285647efa97"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pending_email_changes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=120), nullable=False),
        sa.Column("code_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="5", nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(trim(email)) > 0 AND length(email) <= 120", name="check_pending_email_change_email"),
        sa.CheckConstraint("length(trim(code_hash)) > 0", name="check_pending_email_change_code_hash"),
        sa.CheckConstraint("attempt_count >= 0 AND attempt_count <= max_attempts", name="check_pending_email_change_attempts"),
        sa.CheckConstraint("max_attempts > 0", name="check_pending_email_change_max_attempts"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pending_email_changes_user_id", "pending_email_changes", ["user_id"], unique=False)
    op.create_index("ix_pending_email_changes_email", "pending_email_changes", ["email"], unique=False)


def downgrade():
    op.drop_index("ix_pending_email_changes_email", table_name="pending_email_changes")
    op.drop_index("ix_pending_email_changes_user_id", table_name="pending_email_changes")
    op.drop_table("pending_email_changes")
