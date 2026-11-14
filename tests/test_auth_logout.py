
from datetime import datetime, timezone

from flask_jwt_extended import create_access_token, decode_token

from app.extensions import db
from app.models.user import User
from app.models.revoked_token import RevokedToken
from app.models.refresh_session import RefreshSession
from app.services.token_service import create_token_pair


def create_test_citizen():
    user = User(
        name="Logout Test Citizen",
        email="logout_test@example.com",
        role="citizen",
        email_verified_at=datetime.now(timezone.utc),
    )

    user.set_password("CitizenPassword123")

    db.session.add(user)
    db.session.commit()

    return user



def test_logout_revokes_current_access_token(client, app):
    with app.test_request_context():
        user = create_test_citizen()
        tokens = create_token_pair(user)
        access_token = tokens["access_token"]

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    logout_response = client.post(
        "/api/auth/logout",
        headers=headers
    )

    assert logout_response.status_code == 200

    protected_response = client.post(
        "/api/auth/logout",
        headers=headers
    )

    assert protected_response.status_code == 401

    with app.app_context():
        revoked = RevokedToken.query.first()
        assert revoked is not None


def test_logout_rejects_request_without_token(client):
    response = client.post("/api/auth/logout")

    assert response.status_code == 401



def test_new_access_token_works_after_previous_token_is_revoked(
    client,
    app
):
    with app.test_request_context():
        user = create_test_citizen()

        tokens = create_token_pair(user)

        first_token = tokens["access_token"]

        family_id = decode_token(first_token)["sid"]

        second_token = create_access_token(
            identity=str(user.id),
            additional_claims={
                "sid": family_id
            }
        )

    first_headers = {
        "Authorization": f"Bearer {first_token}"
    }

    second_headers = {
        "Authorization": f"Bearer {second_token}"
    }

    logout_response = client.post(
        "/api/auth/logout",
        headers=first_headers
    )

    assert logout_response.status_code == 200

    revoked_response = client.post(
        "/api/auth/logout",
        headers=first_headers
    )

    assert revoked_response.status_code == 401

    second_response = client.post(
        "/api/auth/logout",
        headers=second_headers
    )

    # The second access token belongs to the revoked session family.
    assert second_response.status_code == 401

def test_refresh_token_rotation_succeeds(client, app):
    # Keep user creation and token generation in the same context.
    with app.test_request_context():
        user = create_test_citizen()
        tokens = create_token_pair(user)
        old_refresh_token = tokens["refresh_token"]

    response = client.post(
        "/api/auth/refresh",
        headers={
            "Authorization": f"Bearer {old_refresh_token}"
        }
    )

    assert response.status_code == 200

    new_tokens = response.get_json()

    assert new_tokens["status"] == "success"
    assert new_tokens["access_token"]
    assert new_tokens["refresh_token"]
    assert new_tokens["refresh_token"] != old_refresh_token

    with app.app_context():
        sessions = RefreshSession.query.order_by(
            RefreshSession.id
        ).all()

        assert len(sessions) == 2
        assert sessions[0].revoked_at is not None
        assert sessions[0].replaced_by_session_id == sessions[1].id
        assert sessions[1].revoked_at is None


def test_reusing_rotated_refresh_token_revokes_session_family(
    client,
    app
):
    # Keep user creation and token generation in the same context.
    with app.test_request_context():
        user = create_test_citizen()
        tokens = create_token_pair(user)
        old_refresh_token = tokens["refresh_token"]

    headers = {
        "Authorization": f"Bearer {old_refresh_token}"
    }

    first_response = client.post(
        "/api/auth/refresh",
        headers=headers
    )

    assert first_response.status_code == 200

    replacement_tokens = first_response.get_json()

    replay_response = client.post(
        "/api/auth/refresh",
        headers=headers
    )

    assert replay_response.status_code == 401

    with app.app_context():
        sessions = RefreshSession.query.all()

        assert len(sessions) == 2
        assert all(
            session.revoked_at is not None
            for session in sessions
        )

    protected_response = client.post(
        "/api/auth/logout",
        headers={
            "Authorization": (
                f"Bearer {replacement_tokens['access_token']}"
            )
        }
    )

    assert protected_response.status_code == 401


def test_logout_revokes_all_access_tokens_in_session_family(
    client,
    app
):
    # Keep user creation and token generation in the same context.
    with app.test_request_context():
        user = create_test_citizen()
        tokens = create_token_pair(user)

        family_id = decode_token(
            tokens["access_token"]
        )["sid"]

        second_access_token = create_access_token(
            identity=str(user.id),
            additional_claims={
                "sid": family_id
            }
        )

    first_response = client.post(
        "/api/auth/logout",
        headers={
            "Authorization": f"Bearer {tokens['access_token']}"
        }
    )

    assert first_response.status_code == 200

    second_response = client.post(
        "/api/auth/logout",
        headers={
            "Authorization": f"Bearer {second_access_token}"
        }
    )

    assert second_response.status_code == 401

    refresh_response = client.post(
        "/api/auth/refresh",
        headers={
            "Authorization": f"Bearer {tokens['refresh_token']}"
        }
    )

    assert refresh_response.status_code == 401
