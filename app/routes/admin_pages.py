
from flask import (
    Blueprint,
    jsonify,
    redirect,
    render_template,
    request,
    url_for
)
from flask_jwt_extended import (
    create_access_token,
    get_jwt_identity,
    set_access_cookies,
    unset_jwt_cookies,
    verify_jwt_in_request
)

from app.extensions import db, limiter
from app.models.user import User


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

    access_token = create_access_token(identity=str(user.id))

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

    response = jsonify({
        "status": "success",
        "message": "Administrator logged out successfully"
    })

    unset_jwt_cookies(response)

    return response, 200
