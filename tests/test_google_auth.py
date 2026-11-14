
from datetime import datetime, timezone

from app.extensions import db
from app.models.user import User


def mock_google_claims():
    return {
        "google_sub": "google-test-sub-123",
        "email": "google_test@example.com",
        "name": "Google Test Citizen",
    }


def test_google_login_creates_new_citizen(
    client, app, monkeypatch
):
    from app.routes import auth

    monkeypatch.setattr(
        auth,
        "verify_google_id_token",
        lambda token: mock_google_claims()
    )

    response = client.post(
        "/api/auth/google",
        json={"id_token": "mock-google-token"}
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["status"] == "success"
    assert data["access_token"]
    assert data["token_type"] == "Bearer"
    assert data["user"]["email"] == "google_test@example.com"
    assert data["user"]["role"] == "citizen"

    with app.app_context():
        user = User.query.filter_by(
            google_sub="google-test-sub-123"
        ).first()

        assert user is not None
        assert user.email_verified_at is not None
        assert user.password_hash is None
        assert user.role == "citizen"


def test_google_login_existing_linked_account(
    client, app, monkeypatch
):
    from app.routes import auth

    monkeypatch.setattr(
        auth,
        "verify_google_id_token",
        lambda token: mock_google_claims()
    )

    with app.app_context():
        user = User(
            name="Existing Google Citizen",
            email="google_test@example.com",
            google_sub="google-test-sub-123",
            role="citizen",
            email_verified_at=datetime.now(timezone.utc),
        )

        db.session.add(user)
        db.session.commit()

        original_user_id = user.id

    response = client.post(
        "/api/auth/google",
        json={"id_token": "mock-google-token"}
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["status"] == "success"
    assert data["user"]["id"] == original_user_id

    with app.app_context():
        assert User.query.count() == 1


def test_google_login_rejects_existing_unlinked_email(
    client, app, monkeypatch
):
    from app.routes import auth

    monkeypatch.setattr(
        auth,
        "verify_google_id_token",
        lambda token: mock_google_claims()
    )

    with app.app_context():
        user = User(
            name="Existing Email Citizen",
            email="google_test@example.com",
            role="citizen",
            email_verified_at=datetime.now(timezone.utc),
        )

        user.set_password("ExistingPassword123")

        db.session.add(user)
        db.session.commit()

    response = client.post(
        "/api/auth/google",
        json={"id_token": "mock-google-token"}
    )

    assert response.status_code == 409

    with app.app_context():
        user = User.query.filter_by(
            email="google_test@example.com"
        ).first()

        assert user.google_sub is None
        assert User.query.count() == 1


def test_google_login_rejects_invalid_token(
    client, monkeypatch
):
    from app.routes import auth

    def reject_token(token):
        raise ValueError("Invalid token")

    monkeypatch.setattr(
        auth,
        "verify_google_id_token",
        reject_token
    )

    response = client.post(
        "/api/auth/google",
        json={"id_token": "invalid-token"}
    )

    assert response.status_code == 401


def test_google_login_rejects_missing_token(client):
    response = client.post(
        "/api/auth/google",
        json={}
    )

    assert response.status_code == 400


def test_google_login_never_authenticates_admin(
    client, app, monkeypatch
):
    from app.routes import auth

    monkeypatch.setattr(
        auth,
        "verify_google_id_token",
        lambda token: mock_google_claims()
    )

    with app.app_context():
        admin = User(
            name="Google Admin",
            email="google_test@example.com",
            google_sub="google-test-sub-123",
            role="admin",
        )

        db.session.add(admin)
        db.session.commit()

    response = client.post(
        "/api/auth/google",
        json={"id_token": "mock-google-token"}
    )

    assert response.status_code == 403
