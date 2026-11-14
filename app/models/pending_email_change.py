from datetime import datetime, timezone

from sqlalchemy import CheckConstraint

from app.extensions import db


class PendingEmailChange(db.Model):
    __tablename__ = "pending_email_changes"

    __table_args__ = (
        CheckConstraint("length(trim(email)) > 0 AND length(email) <= 120", name="check_pending_email_change_email"),
        CheckConstraint("length(trim(code_hash)) > 0", name="check_pending_email_change_code_hash"),
        CheckConstraint("attempt_count >= 0 AND attempt_count <= max_attempts", name="check_pending_email_change_attempts"),
        CheckConstraint("max_attempts > 0", name="check_pending_email_change_max_attempts"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    code_hash = db.Column(db.String(128), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    attempt_count = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    max_attempts = db.Column(db.Integer, nullable=False, default=5, server_default="5")
    consumed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
