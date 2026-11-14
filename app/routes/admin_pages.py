
from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    url_for
)
from flask_jwt_extended import (
    get_jwt,
    get_jwt_identity,
    set_access_cookies,
    unset_jwt_cookies,
    verify_jwt_in_request,
)

from app.extensions import db, limiter
from datetime import datetime, timezone

from app.models.user import User
from app.models.refresh_session import RefreshSession
from app.models.revoked_token import RevokedToken
from app.services.token_service import create_token_pair


# Defines browser-facing administrator dashboard and session routes.
admin_pages_bp = Blueprint("admin_pages", __name__)


# Displays the administrator login page.
@admin_pages_bp.route("/admin/login", methods=["GET"])
def admin_login_page():
    return render_template("admin/login.html")


# Authenticates an administrator and establishes a secure browser session.
@admin_pages_bp.route("/admin/session", methods=["POST"])
@limiter.limit("5 per minute")
def create_admin_session():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "status": "error",
            "message": "Request body must contain valid JSON"
        }), 400

    email = data.get("email")
    password = data.get("password")

    if (
        not isinstance(email, str)
        or not email.strip()
        or not isinstance(password, str)
        or not password
    ):
        return jsonify({
            "status": "error",
            "message": "Email and password are required"
        }), 400

    user = User.query.filter_by(email=email.strip()).first()

    if (
        user is None
        or not user.check_password(password)
        or user.role != "admin"
    ):
        return jsonify({
            "status": "error",
            "message": "Invalid email or password"
        }), 401

    # Use the same server-side session family as API logins. The browser
    # receives only the short-lived access cookie; refresh tokens are not
    # exposed to this dashboard flow.
    tokens = create_token_pair(user)
    access_token = tokens["access_token"]

    response = jsonify({
        "status": "success",
        "message": "Administrator login successful",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role
        }
    })

    set_access_cookies(response, access_token)

    return response, 200


# Displays the dashboard only to authenticated administrators.
@admin_pages_bp.route("/admin", methods=["GET"])
def admin_dashboard_page():
    verify_jwt_in_request(
        optional=True,
        locations=["cookies"]
    )

    identity = get_jwt_identity()

    if identity is None:
        return redirect(url_for("admin_pages.admin_login_page"))

    try:
        user_id = int(identity)
    except (TypeError, ValueError):
        return redirect(url_for("admin_pages.admin_login_page"))

    user = db.session.get(User, user_id)

    if user is None or user.role != "admin":
        return redirect(url_for("admin_pages.admin_login_page"))

    return render_template(
        "admin/dashboard.html",
        admin=user
    )


# Ends the authenticated administrator browser session.
@admin_pages_bp.route("/admin/logout", methods=["POST"])
def admin_logout():
    verify_jwt_in_request(locations=["cookies"])

    try:
        user_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return jsonify({
            "status": "error",
            "message": "Invalid administrator session"
        }), 401

    user = db.session.get(User, user_id)

    if user is None or user.role != "admin":
        return jsonify({
            "status": "error",
            "message": "Administrator access required"
        }), 403

    jwt_data = get_jwt()
    jti = jwt_data.get("jti")
    family_id = jwt_data.get("sid")
    expires_at = jwt_data.get("exp")

    if not jti or not family_id or not expires_at:
        return jsonify({
            "status": "error",
            "message": "Invalid administrator session"
        }), 401

    now = datetime.now(timezone.utc)

    try:
        if RevokedToken.query.filter_by(jti=jti).first() is None:
            db.session.add(
                RevokedToken(
                    jti=jti,
                    expires_at=datetime.fromtimestamp(
                        expires_at,
                        tz=timezone.utc,
                    ),
                )
            )

        RefreshSession.query.filter_by(
            family_id=family_id,
            user_id=user.id,
            revoked_at=None,
        ).update(
            {"revoked_at": now},
            synchronize_session=False,
        )

        db.session.commit()

    except Exception:
        db.session.rollback()
        current_app.logger.exception("Administrator logout failed")
        return jsonify({
            "status": "error",
            "message": "Administrator logout is temporarily unavailable"
        }), 500

    response = jsonify({
        "status": "success",
        "message": "Administrator logged out successfully"
    })

    unset_jwt_cookies(response)

    return response, 200
