
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint

from app.extensions import db


class EmailVerificationToken(db.Model):
    __tablename__ = "email_verification_tokens"

    __table_args__ = (
        CheckConstraint(
            "length(trim(token_hash)) > 0",
            name="check_email_verification_token_hash"
        ),
        CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= max_attempts",
            name="check_email_verification_attempt_count"
        ),
        CheckConstraint(
            "max_attempts > 0",
            name="check_email_verification_max_attempts"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Stores the secure hash of the six-digit OTP, never the OTP itself.
    token_hash = db.Column(
        db.String(128),
        nullable=False,
        unique=True
    )

    expires_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False
    )

    used_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True
    )

    attempt_count = db.Column(
        db.Integer,
        nullable=False,
        default=0,
        server_default="0"
    )

    max_attempts = db.Column(
        db.Integer,
        nullable=False,
        default=5,
        server_default="5"
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    def __repr__(self):
        return f"<EmailVerificationToken id={self.id} user={self.user_id}>"
