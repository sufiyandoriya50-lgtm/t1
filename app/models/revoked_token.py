
from datetime import datetime, timezone

from app.extensions import db


class RevokedToken(db.Model):
    """Store revoked JWT identifiers to prevent token reuse."""

    __tablename__ = "revoked_tokens"

    id = db.Column(db.Integer, primary_key=True)

    jti = db.Column(
        db.String(64),
        nullable=False,
        unique=True,
        index=True
    )

    expires_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        db.CheckConstraint(
            "length(jti) > 0",
            name="ck_revoked_token_jti_nonempty"
        ),
    )

    def __repr__(self):
        return f"<RevokedToken jti={self.jti!r}>"
