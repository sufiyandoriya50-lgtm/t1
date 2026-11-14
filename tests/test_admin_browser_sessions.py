from app.extensions import db
from app.models.user import User
from app.models.refresh_session import RefreshSession


def _create_admin():
    admin = User(
        name="Browser Session Admin",
        email="browser-admin@example.com",
        role="admin",
    )
    admin.set_password("AdminPassword123")
    db.session.add(admin)
    db.session.commit()
    return admin


def test_admin_browser_login_creates_revocable_server_session(app, client):
    with app.app_context():
        _create_admin()

    login = client.post(
        "/admin/session",
        json={
            "email": "browser-admin@example.com",
            "password": "AdminPassword123",
        },
    )
    assert login.status_code == 200
    assert login.headers.getlist("Set-Cookie")
    assert "refresh_token" not in (login.get_json() or {})

    with app.app_context():
        session = RefreshSession.query.filter_by(
            revoked_at=None,
        ).first()
        assert session is not None
        session_id = session.id

    dashboard = client.get("/admin")
    assert dashboard.status_code == 200

    csrf_cookie = client.get_cookie("csrf_access_token")
    assert csrf_cookie is not None

    logout = client.post(
        "/admin/logout",
        headers={"X-CSRF-TOKEN": csrf_cookie.value},
    )
    assert logout.status_code == 200

    with app.app_context():
        saved_session = db.session.get(RefreshSession, session_id)
        assert saved_session is not None
        assert saved_session.revoked_at is not None

    dashboard_after_logout = client.get("/admin")
    assert dashboard_after_logout.status_code == 302
