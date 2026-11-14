from datetime import datetime, timezone

from app.extensions import db
from app.models.user import User
from app.models.refresh_session import RefreshSession
from app.services.token_service import create_token_pair
from app.services.password_reset_service import (
    generate_password_reset_otp,
    reset_password_with_otp,
)


def test_email_password_reset_revokes_all_active_sessions(app):
    with app.app_context():
        user = User(
            name="Reset Session User",
            email="reset-session@example.com",
            role="citizen",
            email_verified_at=datetime.now(timezone.utc),
        )
        user.set_password("OldPassword123")
        db.session.add(user)
        db.session.commit()

        otp = generate_password_reset_otp(user)
        create_token_pair(user)

        sessions = RefreshSession.query.filter_by(
            user_id=user.id,
            revoked_at=None,
        ).all()
        assert len(sessions) == 1

        assert reset_password_with_otp(
            user,
            otp,
            "NewPassword123",
        ) is True

        db.session.refresh(sessions[0])
        assert sessions[0].revoked_at is not None
