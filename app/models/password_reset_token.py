
from datetime import datetime, timezone

from app.extensions import db


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Stores the HMAC hash of the reset OTP, never the plaintext code.
    token_hash = db.Column(
        db.String(128),
        nullable=False,
        unique=True,
    )

    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    used_at = db.Column(db.DateTime(timezone=True), nullable=True)

    attempt_count = db.Column(
        db.Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    max_attempts = db.Column(
        db.Integer,
        nullable=False,
        default=5,
        server_default="5",
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        db.CheckConstraint(
            "length(token_hash) > 0",
            name="ck_password_reset_token_hash_nonempty",
        ),
        db.CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= max_attempts",
            name="ck_password_reset_attempt_count_valid",
        ),
        db.CheckConstraint(
            "max_attempts > 0",
            name="ck_password_reset_max_attempts_positive",
        ),
    )
