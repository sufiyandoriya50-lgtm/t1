
from datetime import datetime, timedelta, timezone

import pytest

from app.extensions import db
from app.models.user import User
from app.models.phone_otp_challenge import PhoneOtpChallenge
from app.services import phone_otp_service


def create_citizen():
    user = User(
        name="Phone OTP Test Citizen",
        role="citizen",
    )
    db.session.add(user)
    db.session.commit()
    return user


def mock_sms_delivery(monkeypatch):
    sent_messages = []

    monkeypatch.setattr(
        phone_otp_service,
        "send_phone_otp",
        lambda phone, otp: sent_messages.append((phone, otp)),
    )

    return sent_messages


def test_phone_auth_otp_can_be_requested_and_verified(
    app, monkeypatch
):
    sent_messages = mock_sms_delivery(monkeypatch)

    with app.app_context():
        result = phone_otp_service.request_phone_otp(
            "9876543210"
        )

        assert result is True
        assert len(sent_messages) == 1

        phone, otp = sent_messages[0]

        assert phone == "9876543210"
        assert len(otp) == 6
        assert otp.isdigit()

        challenge = PhoneOtpChallenge.query.filter_by(
            phone_number=phone,
            purpose="phone_auth",
        ).first()

        assert challenge is not None
        assert challenge.user_id is None
        assert challenge.consumed_at is None

        verified = phone_otp_service.verify_phone_otp(
            phone,
            otp,
        )

        assert verified is not None
        assert verified.consumed_at is not None

        # The same OTP must not work a second time.
        second_attempt = phone_otp_service.verify_phone_otp(
            phone,
            otp,
        )

        assert second_attempt is None


def test_phone_link_otp_is_bound_to_requesting_user(
    app, monkeypatch
):
    sent_messages = mock_sms_delivery(monkeypatch)

    with app.app_context():
        first_user = create_citizen()
        second_user = create_citizen()

        phone_otp_service.request_phone_otp(
            "9876543210",
            purpose="phone_link",
            user_id=first_user.id,
        )

        phone, otp = sent_messages[0]

        # Another user must not be able to consume this OTP.
        wrong_user_result = phone_otp_service.verify_phone_otp(
            phone,
            otp,
            purpose="phone_link",
            expected_user_id=second_user.id,
        )

        assert wrong_user_result is None

        challenge = PhoneOtpChallenge.query.filter_by(
            phone_number=phone,
            purpose="phone_link",
        ).first()

        assert challenge.consumed_at is None

        # The original requesting user can still verify it.
        correct_user_result = phone_otp_service.verify_phone_otp(
            phone,
            otp,
            purpose="phone_link",
            expected_user_id=first_user.id,
        )

        assert correct_user_result is not None
        assert correct_user_result.user_id == first_user.id


def test_phone_link_requires_expected_user_id(
    app, monkeypatch
):
    sent_messages = mock_sms_delivery(monkeypatch)

    with app.app_context():
        user = create_citizen()

        phone_otp_service.request_phone_otp(
            "9876543210",
            purpose="phone_link",
            user_id=user.id,
        )

        phone, otp = sent_messages[0]

        with pytest.raises(ValueError):
            phone_otp_service.verify_phone_otp(
                phone,
                otp,
                purpose="phone_link",
            )


def test_phone_otp_resend_cooldown(
    app, monkeypatch
):
    mock_sms_delivery(monkeypatch)

    with app.app_context():
        phone_otp_service.request_phone_otp("9876543210")

        with pytest.raises(ValueError):
            phone_otp_service.request_phone_otp("9876543210")


def test_expired_phone_otp_is_rejected(
    app, monkeypatch
):
    sent_messages = mock_sms_delivery(monkeypatch)

    with app.app_context():
        phone_otp_service.request_phone_otp("9876543210")

        phone, otp = sent_messages[0]

        challenge = PhoneOtpChallenge.query.filter_by(
            phone_number=phone,
            purpose="phone_auth",
        ).first()

        challenge.expires_at = (
            datetime.now(timezone.utc) - timedelta(minutes=1)
        )
        db.session.commit()

        result = phone_otp_service.verify_phone_otp(
            phone,
            otp,
        )

        assert result is None
        assert challenge.consumed_at is not None


def test_phone_otp_is_consumed_after_maximum_wrong_attempts(
    app, monkeypatch
):
    sent_messages = mock_sms_delivery(monkeypatch)

    with app.app_context():
        phone_otp_service.request_phone_otp("9876543210")

        phone, correct_otp = sent_messages[0]

        wrong_otp = (
            "999999" if correct_otp != "999999" else "888888"
        )

        for _ in range(5):
            result = phone_otp_service.verify_phone_otp(
                phone,
                wrong_otp,
            )
            assert result is None

        challenge = PhoneOtpChallenge.query.filter_by(
            phone_number=phone,
            purpose="phone_auth",
        ).first()

        assert challenge.attempt_count == 5
        assert challenge.consumed_at is not None

        # Even the correct OTP must now be rejected.
        result = phone_otp_service.verify_phone_otp(
            phone,
            correct_otp,
        )

        assert result is None
def test_phone_otp_is_invalidated_when_sms_delivery_fails(
    app, monkeypatch
):
    def failed_delivery(phone, otp):
        raise RuntimeError("SMS delivery failed")

    monkeypatch.setattr(
        phone_otp_service,
        "send_phone_otp",
        failed_delivery,
    )

    with app.app_context():
        with pytest.raises(RuntimeError):
            phone_otp_service.request_phone_otp(
                "9876543210"
            )

        challenge = PhoneOtpChallenge.query.filter_by(
            phone_number="9876543210",
            purpose="phone_auth",
        ).first()

        assert challenge is not None
        assert challenge.consumed_at is not None
def test_phone_login_does_not_send_otp_to_unregistered_number(
    app, client, monkeypatch
):
    from app.routes import auth as auth_routes

    calls = []

    def fake_send(phone_number, *args, **kwargs):
        calls.append(phone_number)

    monkeypatch.setattr(
        auth_routes,
        "request_phone_otp",
        fake_send,
    )

    response = client.post(
        "/api/auth/phone/request-otp",
        json={"phone_number": "9876543210"},
    )

    assert response.status_code == 200
    assert calls == []        
def test_phone_login_sends_otp_only_to_verified_citizen(
    app, client, monkeypatch
):
    from datetime import datetime, timezone
    from app.extensions import db
    from app.models.user import User
    from app.routes import auth as auth_routes

    calls = []

    def fake_send(phone_number, *args, **kwargs):
        calls.append(phone_number)

    monkeypatch.setattr(
        auth_routes,
        "request_phone_otp",
        fake_send,
    )

    with app.app_context():
        user = User(
            name="Phone Test Citizen",
            role="citizen",
            phone_number="+919876543210",
            phone_verified_at=datetime.now(timezone.utc),
        )
        db.session.add(user)
        db.session.commit()

    response = client.post(
        "/api/auth/phone/request-otp",
        json={"phone_number": "9876543210"},
    )

    assert response.status_code == 200
    assert calls == ["9876543210"]    


def test_password_recovery_otp_is_bound_to_account(app, monkeypatch):
    sent_messages = mock_sms_delivery(monkeypatch)
    with app.app_context():
        user = User(
            name="Recovery Citizen", role="citizen",
            phone_number="+919876543210",
            phone_verified_at=datetime.now(timezone.utc),
        )
        user.set_password("OldPassword123")
        db.session.add(user)
        db.session.commit()

        phone_otp_service.request_phone_otp(
            "9876543210", purpose="password_recovery", user_id=user.id
        )
        phone, otp = sent_messages[0]
        assert phone == "9876543210"

        wrong_account = phone_otp_service.verify_phone_otp(
            phone, otp, purpose="password_recovery", expected_user_id=user.id + 999
        )
        assert wrong_account is None

        verified = phone_otp_service.verify_phone_otp(
            phone, otp, purpose="password_recovery", expected_user_id=user.id
        )
        assert verified is not None
        assert verified.consumed_at is not None



def test_phone_link_request_uses_expected_service_argument(
    app, client, monkeypatch
):
    from app.routes import auth as auth_routes
    from flask_jwt_extended import create_access_token

    captured = {}

    def fake_request(phone_number, purpose="phone_auth", user_id=None):
        captured.update(
            phone_number=phone_number,
            purpose=purpose,
            user_id=user_id,
        )
        return True

    monkeypatch.setattr(auth_routes, "request_phone_otp", fake_request)

    with app.app_context():
        user = User(
            name="Phone Link Route User",
            email="phone-link-route@example.com",
            role="citizen",
        )
        user.set_password("CurrentPassword123")
        db.session.add(user)
        db.session.commit()
        user_id = user.id
        token = create_access_token(identity=str(user_id))

    response = client.post(
        "/api/auth/phone/link/request-otp",
        json={
            "phone_number": "9876543210",
            "current_password": "CurrentPassword123",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert captured == {
        "phone_number": "9876543210",
        "purpose": "phone_link",
        "user_id": user_id,
    }


def test_phone_link_request_handles_non_object_json_safely(app, client):
    from flask_jwt_extended import create_access_token

    with app.app_context():
        user = User(
            name="Malformed Payload User",
            email="malformed-payload@example.com",
            role="citizen",
        )
        user.set_password("CurrentPassword123")
        db.session.add(user)
        db.session.commit()
        token = create_access_token(identity=str(user.id))

    response = client.post(
        "/api/auth/phone/link/request-otp",
        json=["not", "an", "object"],
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert response.get_json()["status"] == "error"
