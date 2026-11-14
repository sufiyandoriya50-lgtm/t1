
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint

from app.extensions import db


class RefreshSession(db.Model):
    __tablename__ = "refresh_sessions"

    __table_args__ = (
        CheckConstraint(
            "length(trim(token_hash)) > 0",
            name="check_refresh_session_token_hash"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    token_hash = db.Column(
        db.String(128),
        nullable=False,
        unique=True
    )

    family_id = db.Column(
        db.String(36),
        nullable=False,
        index=True
    )

    replaced_by_session_id = db.Column(
        db.Integer,
        db.ForeignKey("refresh_sessions.id"),
        nullable=True
    )

    expires_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False
    )

    revoked_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True
    )

    last_used_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True
    )

    device_info = db.Column(
        db.String(255),
        nullable=True
    )

    user_agent = db.Column(
        db.String(512),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    def __repr__(self):
        return f"<RefreshSession id={self.id} user={self.user_id}>"
