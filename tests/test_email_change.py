from datetime import datetime, timezone

from app.extensions import db
from app.models.user import User
from app.models.pending_email_change import PendingEmailChange
from app.services import email_change_service


def _citizen(email="old@example.com"):
    user = User(name="Email Change Citizen", email=email, role="citizen",
                email_verified_at=datetime.now(timezone.utc))
    user.set_password("CurrentPassword123")
    db.session.add(user)
    db.session.commit()
    return user


def test_email_change_otp_updates_only_after_verification(app):
    with app.app_context():
        user = _citizen()
        code = email_change_service.create_email_change_otp(user, "new@example.com")
        assert user.email == "old@example.com"
        wrong_code = "000000" if code != "000000" else "000001"
        assert email_change_service.verify_email_change_otp(user, "new@example.com", wrong_code) is False
        record = PendingEmailChange.query.filter_by(user_id=user.id).first()
        assert record is not None
        assert record.attempt_count == 1
        assert email_change_service.verify_email_change_otp(user, "new@example.com", code) is True
        assert user.email == "new@example.com"
        assert user.email_verified_at is not None
        assert record.consumed_at is not None


def test_email_change_rejects_email_owned_by_another_account(app):
    with app.app_context():
        _citizen("first@example.com")
        second = _citizen("second@example.com")
        try:
            email_change_service.create_email_change_otp(second, "first@example.com")
            assert False, "Expected duplicate email to be rejected"
        except ValueError:
            pass


def test_email_change_otp_cannot_be_used_by_another_user(app):
    with app.app_context():
        first = _citizen("first@example.com")
        second = _citizen("second@example.com")
        code = email_change_service.create_email_change_otp(first, "new@example.com")
        assert email_change_service.verify_email_change_otp(second, "new@example.com", code) is False
        assert first.email == "first@example.com"
        assert second.email == "second@example.com"
