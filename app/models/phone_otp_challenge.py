
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint

from app.extensions import db


class PhoneOtpChallenge(db.Model):
    __tablename__ = "phone_otp_challenges"

    __table_args__ = (
        CheckConstraint(
            "length(trim(phone_number)) > 0 AND length(phone_number) <= 20",
            name="check_phone_otp_phone_number"
        ),
        CheckConstraint(
            "length(trim(code_hash)) > 0",
            name="check_phone_otp_code_hash"
        ),
        CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= max_attempts",
            name="check_phone_otp_attempt_count"
        ),
        CheckConstraint(
            "max_attempts > 0",
            name="check_phone_otp_max_attempts"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    phone_number = db.Column(
        db.String(20),
        nullable=False,
        index=True
    )

    purpose = db.Column(
        db.String(30),
        nullable=False,
        default="phone_auth",
        server_default="phone_auth"
    )

    code_hash = db.Column(
        db.String(128),
        nullable=False
    )

    expires_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False
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

    consumed_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    def __repr__(self):
        return f"<PhoneOtpChallenge id={self.id} phone={self.phone_number}>"
