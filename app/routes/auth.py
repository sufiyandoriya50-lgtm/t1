from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    jwt_required,
    get_jwt_identity
)
from flask import current_app
from flask_jwt_extended import decode_token
import hashlib
from app.models.refresh_session import RefreshSession
from app.services.token_service import create_token_pair
from app.services.google_auth_service import verify_google_id_token
from app.services.sms_service import normalize_indian_phone_number
from app.services.phone_otp_service import request_phone_otp
from app.services.phone_otp_service import verify_phone_otp
from app.services.email_change_service import create_email_change_otp, verify_email_change_otp
from flask_jwt_extended import unset_jwt_cookies,get_jwt
from app.models.user import User
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone
from app.models.password_reset_token import PasswordResetToken
from app.extensions import db , limiter
auth_bp = Blueprint("auth", __name__)


def _json_object():
    """Return a JSON object payload, or an empty object for invalid shapes."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


from app.services.registration_service import register_citizen
from app.services.email_otp_service import (
    generate_email_otp,
    verify_email_otp,
)
from app.services.email_service import send_email
from app.services.password_reset_service import (
    generate_password_reset_otp,
    reset_password_with_otp,
)
from app.models.revoked_token import RevokedToken
# POST /api/auth/login
# Verifies a FloodShield citizen's email and password, then returns a JWT access token.
@auth_bp.route("/api/auth/login", methods=["POST"])
@limiter.limit("5 per minute")
def login():
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

    user = User.query.filter_by(
        email=email.strip().lower()
    ).first()

    if (
        user is None
        or not user.check_password(password)
        or user.role != "citizen"
    ):
        return jsonify({
            "status": "error",
            "message": "Invalid email or password"
        }), 401

    if user.email_verified_at is None:
        return jsonify({
            "status": "error",
            "message": "Please verify your email address before logging in.",
            "email_verified": False
        }), 403

    tokens = create_token_pair(user)

    return jsonify({
        "status": "success",
        "message": "Login successful",
        **tokens,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email
        }
    }), 200
@auth_bp.route("/api/auth/admin/login", methods=["POST"])
@limiter.limit("5 per minute")
def admin_login():
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

    user = User.query.filter_by(
        email=email.strip().lower()
    ).first()

    if (
        user is None
        or not user.check_password(password)
        or user.role != "admin"
    ):
        return jsonify({
            "status": "error",
            "message": "Invalid email or password"
        }), 401

    tokens = create_token_pair(user)

    return jsonify({
        "status": "success",
        "message": "Administrator login successful",
        **tokens,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role
        }
    }), 200

# POST /api/auth/google
# Registers or authenticates a citizen using a verified Google ID token.
@auth_bp.route("/api/auth/google", methods=["POST"])
@limiter.limit("5 per minute")
def google_login():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "status": "error",
            "message": "Request body must contain valid JSON."
        }), 400

    id_token = data.get("id_token")

    if not isinstance(id_token, str) or not id_token.strip():
        return jsonify({
            "status": "error",
            "message": "A Google ID token is required."
        }), 400

    try:
        claims = verify_google_id_token(id_token)

        google_sub = claims["google_sub"]
        email = claims["email"]
        name = claims["name"]

        user = User.query.filter_by(
            google_sub=google_sub
        ).first()

        if user is not None:
            if user.role != "citizen":
                return jsonify({
                    "status": "error",
                    "message": "Google Sign-In is unavailable for this account."
                }), 403

        else:
            existing_email_user = User.query.filter_by(
                email=email
            ).first()

            if existing_email_user is not None:
                return jsonify({
                    "status": "error",
                    "message": (
                        "An account with this email already exists. "
                        "Sign in using your existing method before linking Google."
                    )
                }), 409

            if not name:
                return jsonify({
                    "status": "error",
                    "message": "Your Google profile must provide a name."
                }), 400

            user = User(
                name=name[:100],
                email=email,
                google_sub=google_sub,
                role="citizen",
                email_verified_at=datetime.now(timezone.utc)
            )

            db.session.add(user)
            db.session.commit()

        tokens = create_token_pair(user)

        return jsonify({
            "status": "success",
            "message": "Google Sign-In successful.",
            **tokens,
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "role": user.role
            }
        }), 200

    except ValueError:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "The Google ID token is invalid or expired."
        }), 401

    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "This Google account or email is already registered."
        }), 409

    except Exception:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Google Sign-In is temporarily unavailable."
        }), 503
    
# POST /api/auth/firebase
# Authenticates a citizen using a verified Firebase phone-authentication token.
@auth_bp.route("/api/auth/firebase", methods=["POST"])
@limiter.limit("5 per minute")
def firebase_login():
    """Retired endpoint: Firebase Authentication is not used by FloodShield."""
    return jsonify({
        "status": "error",
        "message": (
            "Firebase Authentication is no longer supported. "
            "Use backend-managed email, phone OTP, or Google Sign-In."
        ),
        "code": "FIREBASE_AUTH_RETIRED",
    }), 410


@auth_bp.route("/api/auth/firebase/link", methods=["POST"])
@limiter.limit("5 per minute")
def link_firebase_account():
    """Retired endpoint: Firebase Authentication is not used by FloodShield."""
    return jsonify({
        "status": "error",
        "message": (
            "Firebase Authentication linking is no longer supported. "
            "Use the backend-managed identity linking endpoints."
        ),
        "code": "FIREBASE_AUTH_RETIRED",
    }), 410


@auth_bp.route("/api/auth/register", methods=["POST"])
@limiter.limit("5 per minute")
def register():

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "status": "error",
            "message": "Request body must contain valid JSON"
        }), 400

    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    try:
        user = register_citizen(name, email, password)

    except ValueError as error:
        return jsonify({
            "status": "error",
            "message": str(error)
        }), 400

    except RuntimeError:
        return jsonify({
            "status": "error",
            "message": (
                "Your account could not receive its verification email. "
                "Please try requesting another OTP."
            )
        }), 503

    except Exception:
        return jsonify({
            "status": "error",
            "message": "Unable to complete registration"
        }), 500

    return jsonify({
        "status": "success",
        "message": "Registration successful. Check your email for the verification OTP.",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "email_verified": False
        }
    }), 201


# POST /api/auth/verify-email
# Verifies a citizen's email using a six-digit OTP.
@auth_bp.route("/api/auth/verify-email", methods=["POST"])
@limiter.limit("10 per minute")
def verify_email():

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "status": "error",
            "message": "Request body must contain valid JSON"
        }), 400

    email = data.get("email")
    otp = data.get("otp")

    if (
        not isinstance(email, str)
        or not email.strip()
        or not isinstance(otp, str)
        or len(otp) != 6
        or not otp.isdigit()
    ):
        return jsonify({
            "status": "error",
            "message": "A valid email address and six-digit OTP are required"
        }), 400

    user = User.query.filter_by(
        email=email.strip().lower()
    ).first()

    if user is None or user.role != "citizen":
        return jsonify({
            "status": "error",
            "message": "Invalid or expired verification code"
        }), 400

    try:
        verified = verify_email_otp(user, otp)

    except Exception:
        return jsonify({
            "status": "error",
            "message": "Email verification is temporarily unavailable"
        }), 500

    if not verified:
        return jsonify({
            "status": "error",
            "message": "Invalid or expired verification code"
        }), 400

    return jsonify({
        "status": "success",
        "message": "Email address verified successfully",
        "email_verified": True
    }), 200


# POST /api/auth/resend-email-otp
# Sends another OTP to an unverified citizen account.
@auth_bp.route("/api/auth/resend-email-otp", methods=["POST"])
@limiter.limit("3 per minute")
def resend_email_otp():

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "status": "error",
            "message": "Request body must contain valid JSON"
        }), 400

    email = data.get("email")

    if not isinstance(email, str) or not email.strip():
        return jsonify({
            "status": "error",
            "message": "A valid email address is required"
        }), 400

    user = User.query.filter_by(
        email=email.strip().lower()
    ).first()

    # Use the same response for unknown, verified and unavailable accounts
    # to reduce account-enumeration information.
    generic_response = {
        "status": "success",
        "message": (
            "If an eligible unverified account exists, "
            "a verification code will be sent."
        )
    }

    if user is None or user.role != "citizen":
        return jsonify(generic_response), 200

    if user.email_verified_at is not None:
        return jsonify(generic_response), 200

    try:
        otp = generate_email_otp(user)

        send_email(
            recipient=user.email,
            subject="Your FloodShield email verification code",
            body=(
                f"Hello {user.name},\n\n"
                f"Your FloodShield email verification OTP is: {otp}\n\n"
                "This code expires in 5 minutes and can only be used once.\n"
                "You have a maximum of 5 verification attempts.\n\n"
                "FloodShield Team"
            )
        )

    except ValueError as error:
        if "wait before requesting" in str(error).lower():
            return jsonify({
                "status": "error",
                "message": "Please wait before requesting another OTP"
            }), 429

        return jsonify(generic_response), 200

    except Exception:
        return jsonify({
            "status": "error",
            "message": "Unable to send verification email right now"
        }), 503

    return jsonify(generic_response), 200

# POST /api/auth/forgot-password
# Sends a password-reset OTP to a verified citizen's email.
@auth_bp.route("/api/auth/forgot-password", methods=["POST"])
@limiter.limit("3 per minute")
def forgot_password():

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "status": "error",
            "message": "Request body must contain valid JSON"
        }), 400

    email = data.get("email")

    if not isinstance(email, str) or not email.strip():
        return jsonify({
            "status": "error",
            "message": "A valid email address is required"
        }), 400

    generic_response = {
        "status": "success",
        "message": (
            "If an eligible account exists, "
            "a password-reset code will be sent."
        )
    }

    user = User.query.filter_by(
        email=email.strip().lower()
    ).first()

    if (
        user is None
        or user.role != "citizen"
        or user.email_verified_at is None
    ):
        return jsonify(generic_response), 200

    try:
        otp = generate_password_reset_otp(user)

        send_email(
            recipient=user.email,
            subject="Your FloodShield password reset code",
            body=(
                f"Hello {user.name},\n\n"
                f"Your password-reset OTP is: {otp}\n\n"
                "This code expires in 10 minutes.\n"
                "You have a maximum of 5 verification attempts.\n\n"
                "If you did not request a password reset, "
                "please ignore this email.\n\n"
                "FloodShield Team"
            )
        )

    except Exception:
        # Keep the response generic to avoid revealing account existence.
        return jsonify(generic_response), 200

    return jsonify(generic_response), 200


# POST /api/auth/reset-password
# Verifies the reset OTP and changes the citizen's password.
@auth_bp.route("/api/auth/reset-password", methods=["POST"])
@limiter.limit("5 per minute")
def reset_password():

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "status": "error",
            "message": "Request body must contain valid JSON"
        }), 400

    email = data.get("email")
    otp = data.get("otp")
    new_password = data.get("new_password")

    if (
        not isinstance(email, str)
        or not email.strip()
        or not isinstance(otp, str)
        or len(otp) != 6
        or not otp.isdigit()
        or not isinstance(new_password, str)
        or not new_password
    ):
        return jsonify({
            "status": "error",
            "message": "Email, six-digit OTP and new password are required"
        }), 400

    user = User.query.filter_by(
        email=email.strip().lower()
    ).first()

    if user is None or user.role != "citizen":
        return jsonify({
            "status": "error",
            "message": "Invalid or expired password-reset code"
        }), 400

    try:
        success = reset_password_with_otp(
            user,
            otp,
            new_password
        )

    except ValueError as error:
        return jsonify({
            "status": "error",
            "message": str(error)
        }), 400

    except Exception:
        return jsonify({
            "status": "error",
            "message": "Password reset is temporarily unavailable"
        }), 500

    if not success:
        return jsonify({
            "status": "error",
            "message": "Invalid or expired password-reset code"
        }), 400

    return jsonify({
        "status": "success",
        "message": "Password reset successfully"
    }), 200
@auth_bp.route("/api/auth/change-password", methods=["POST"])
@jwt_required()
@limiter.limit("5 per minute")
def change_password():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "status": "error",
            "message": "Request body must contain valid JSON"
        }), 400

    current_password = data.get("current_password")
    new_password = data.get("new_password")

    if not isinstance(current_password, str) or not current_password:
        return jsonify({
            "status": "error",
            "message": "Current password is required"
        }), 400

    if (
        not isinstance(new_password, str)
        or not 8 <= len(new_password) <= 128
    ):
        return jsonify({
            "status": "error",
            "message": "New password must be between 8 and 128 characters"
        }), 400

    user_id = get_jwt_identity()
    user = User.query.filter_by(id=user_id).first()

    if user is None or user.role != "citizen":
        return jsonify({
            "status": "error",
            "message": "Account not found"
        }), 404

    if not user.check_password(current_password):
        return jsonify({
            "status": "error",
            "message": "Current password is incorrect"
        }), 401

    if current_password == new_password:
        return jsonify({
            "status": "error",
            "message": "New password must be different from the current password"
        }), 400

    try:
        now = datetime.now(timezone.utc)

        user.set_password(new_password)

        # Invalidate all unused password-reset codes.
        PasswordResetToken.query.filter_by(
            user_id=user.id,
            used_at=None
        ).update(
            {"used_at": now},
            synchronize_session=False
        )

        # Revoke every active session on all devices. The current access token
        # is also invalidated by the session-family blocklist check.
        RefreshSession.query.filter_by(
            user_id=user.id,
            revoked_at=None
        ).update(
            {"revoked_at": now},
            synchronize_session=False
        )

        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Password changed successfully. Please sign in again."
        }), 200

    except Exception:
        db.session.rollback()

        return jsonify({
            "status": "error",
            "message": "Password change is temporarily unavailable"
        }), 500



def _hash_refresh_jti(jti):
    """Hash a refresh token JTI for database lookup."""
    return hashlib.sha256(jti.encode("utf-8")).hexdigest()



@auth_bp.route("/api/auth/refresh", methods=["POST"])
@jwt_required(refresh=True)
@limiter.limit("10 per minute")
def refresh_access_token():
    """Rotate a refresh token safely and detect token reuse."""

    jwt_data = get_jwt()
    jti = jwt_data.get("jti")
    family_id = jwt_data.get("sid")
    user_id = get_jwt_identity()

    if not jti or not family_id or not user_id:
        return jsonify({
            "status": "error",
            "message": "Invalid refresh token."
        }), 401

    try:
        session = RefreshSession.query.filter_by(
            token_hash=_hash_refresh_jti(jti)
        ).first()

        if session is None:
            return jsonify({
                "status": "error",
                "message": "Refresh session not found."
            }), 401

        if (
            session.family_id != family_id
            or str(session.user_id) != str(user_id)
        ):
            return jsonify({
                "status": "error",
                "message": "Invalid refresh session."
            }), 401

        now = datetime.now(timezone.utc)

        # Detect reuse of an already rotated refresh token.
        if session.revoked_at is not None:
            if session.replaced_by_session_id is not None:
                RefreshSession.query.filter_by(
                    family_id=family_id
                ).filter(
                    RefreshSession.revoked_at.is_(None)
                ).update(
                    {"revoked_at": now},
                    synchronize_session=False
                )

                db.session.commit()

                return jsonify({
                    "status": "error",
                    "message": (
                        "Refresh token reuse detected. "
                        "This session has been revoked. Please log in again."
                    )
                }), 401

            return jsonify({
                "status": "error",
                "message": "This refresh session has been revoked."
            }), 401

        # Check refresh-session expiry.
        session_expiry = session.expires_at

        if session_expiry.tzinfo is None:
            session_expiry = session_expiry.replace(
                tzinfo=timezone.utc
            )

        if session_expiry <= now:
            return jsonify({
                "status": "error",
                "message": (
                    "Refresh session has expired. Please log in again."
                )
            }), 401

        user = User.query.filter_by(id=int(user_id)).first()

        if user is None:
            return jsonify({
                "status": "error",
                "message": "Account not found."
            }), 401

        old_session_id = session.id

        # Create a replacement pair without committing yet.
        tokens = create_token_pair(
            user,
            family_id=family_id,
            commit=False
        )

        replacement_claims = decode_token(
            tokens["refresh_token"]
        )

        replacement_jti = replacement_claims.get("jti")

        if not replacement_jti:
            raise RuntimeError(
                "Replacement refresh token has no JTI."
            )

        replacement_session = RefreshSession.query.filter_by(
            token_hash=_hash_refresh_jti(replacement_jti)
        ).first()

        if replacement_session is None:
            raise RuntimeError(
                "Replacement refresh session was not created."
            )

        # Atomically claim the old session.
        # Only one request can update a session that is still active.
        updated_count = RefreshSession.query.filter_by(
            id=old_session_id
        ).filter(
            RefreshSession.revoked_at.is_(None)
        ).update(
            {
                "revoked_at": now,
                "replaced_by_session_id": replacement_session.id,
                "last_used_at": now
            },
            synchronize_session=False
        )

        if updated_count != 1:
            # Discard the replacement tokens and session.
            db.session.rollback()

            # Check whether another request already rotated this token.
            previous_session = RefreshSession.query.filter_by(
                id=old_session_id
            ).first()

            if (
                previous_session is not None
                and previous_session.revoked_at is not None
                and previous_session.replaced_by_session_id is not None
            ):
                RefreshSession.query.filter_by(
                    family_id=family_id
                ).filter(
                    RefreshSession.revoked_at.is_(None)
                ).update(
                    {"revoked_at": datetime.now(timezone.utc)},
                    synchronize_session=False
                )

                db.session.commit()

                return jsonify({
                    "status": "error",
                    "message": (
                        "Refresh token reuse detected. "
                        "This session has been revoked. Please log in again."
                    )
                }), 401

            return jsonify({
                "status": "error",
                "message": "Refresh token is no longer active."
            }), 401

        # Commit the replacement session and old-session revocation together.
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Token refreshed successfully.",
            **tokens
        }), 200

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Refresh token rotation failed."
        )

        return jsonify({
            "status": "error",
            "message": "Token refresh is temporarily unavailable."
        }), 500



@auth_bp.route("/api/auth/logout", methods=["POST"])
@jwt_required()
@limiter.limit("10 per minute")
def logout():
    """Revoke the current access token and its refresh session family."""

    jwt_data = get_jwt()

    jti = jwt_data.get("jti")
    family_id = jwt_data.get("sid")
    expires_at_timestamp = jwt_data.get("exp")

    if not jti or not family_id or not expires_at_timestamp:
        return jsonify({
            "status": "error",
            "message": "Invalid authentication token."
        }), 401

    try:
        now = datetime.now(timezone.utc)

        existing_token = RevokedToken.query.filter_by(
            jti=jti
        ).first()

        if existing_token is None:
            db.session.add(
                RevokedToken(
                    jti=jti,
                    expires_at=datetime.fromtimestamp(
                        expires_at_timestamp,
                        tz=timezone.utc
                    )
                )
            )

        # Revoke every active refresh session in this login family.
        RefreshSession.query.filter_by(
            family_id=family_id
        ).filter(
            RefreshSession.revoked_at.is_(None)
        ).update(
            {"revoked_at": now},
            synchronize_session=False
        )

        db.session.commit()

        response = jsonify({
            "status": "success",
            "message": "Logged out successfully."
        })

        unset_jwt_cookies(response)

        return response, 200

    except Exception:
        db.session.rollback()

        current_app.logger.exception(
            "Logout operation failed."
        )

        return jsonify({
            "status": "error",
            "message": "Logout is temporarily unavailable."
        }), 500


@auth_bp.route("/api/auth/phone/request-otp", methods=["POST"])
@limiter.limit("3 per minute")
def request_phone_otp_route():
    """Request a phone login OTP for a verified citizen."""

    data = _json_object()
    phone_number = data.get("phone_number")

    if not isinstance(phone_number, str) or not phone_number.strip():
        return jsonify({
            "status": "error",
            "message": "A phone number is required."
        }), 400

    try:
        phone_number = normalize_indian_phone_number(phone_number)

        existing_user = User.query.filter_by(
            phone_number="+91" + phone_number
        ).first()

        if (
            existing_user is None
            or existing_user.role != "citizen"
            or existing_user.phone_verified_at is None
        ):
            return jsonify({
                "status": "success",
                "message": "If the phone number is registered, an OTP will be sent."
            }), 200

        request_phone_otp(phone_number)

        return jsonify({
            "status": "success",
            "message": "If the phone number is registered, an OTP will be sent."
        }), 200

    except ValueError as error:
        return jsonify({
            "status": "error",
            "message": str(error)
        }), 400

    except Exception:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Unable to send OTP right now. Please try again later."
        }), 503


@auth_bp.route("/api/auth/phone/link/verify-otp", methods=["POST"])
@jwt_required()
@limiter.limit("5 per minute")
def verify_phone_link_otp_route():
    """Verify ownership of a phone number and link it to the current citizen."""

    data = _json_object()

    phone_number = data.get("phone_number")
    otp = data.get("otp")

    if not isinstance(phone_number, str) or not phone_number.strip():
        return jsonify({
            "status": "error",
            "message": "A phone number is required."
        }), 400

    if not isinstance(otp, str) or not otp.strip():
        return jsonify({
            "status": "error",
            "message": "The OTP is required."
        }), 400

    try:
        normalized_phone = normalize_indian_phone_number(phone_number)

        user_id = int(get_jwt_identity())
        user = db.session.get(User, user_id)

        if user is None or user.role != "citizen":
            return jsonify({
                "status": "error",
                "message": "Citizen account not found."
            }), 403

        if user.phone_number is not None:
            return jsonify({
                "status": "error",
                "message": "A phone number is already linked to this account."
            }), 409

        existing_user = User.query.filter_by(
            phone_number="+91" + normalized_phone
        ).first()

        if existing_user is not None:
            return jsonify({
                "status": "error",
                "message": "This phone number is already linked to an account."
            }), 409

        challenge = verify_phone_otp(
            normalized_phone,
            otp,
            purpose="phone_link",
            expected_user_id=user.id
        )

        if challenge is None:
            return jsonify({
                "status": "error",
                "message": "Invalid or expired OTP."
            }), 400

        user.phone_number = "+91" + normalized_phone
        user.phone_verified_at = datetime.now(timezone.utc)
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Phone number linked successfully.",
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "role": user.role,
                "phone_number": user.phone_number
            }
        }), 200

    except ValueError as error:
        return jsonify({
            "status": "error",
            "message": str(error)
        }), 400

    except Exception:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Phone linking is temporarily unavailable."
        }), 500

@auth_bp.route("/api/auth/phone/link/request-otp", methods=["POST"])
@jwt_required()
@limiter.limit("3 per minute")
def request_phone_link_otp_route():
    """Request an OTP to link a phone number to the current citizen account."""

    data = _json_object()
    phone_number = data.get("phone_number")

    if not isinstance(phone_number, str) or not phone_number.strip():
        return jsonify({
            "status": "error",
            "message": "A phone number is required."
        }), 400

    try:
        phone_number = normalize_indian_phone_number(phone_number)

        user_id = int(get_jwt_identity())
        user = db.session.get(User, user_id)

        if user is None or user.role != "citizen":
            return jsonify({
                "status": "error",
                "message": "Citizen account not found."
            }), 403

        if user.phone_number is not None:
            return jsonify({
                "status": "error",
                "message": "A phone number is already linked to this account."
            }), 409

        existing_user = User.query.filter_by(
           phone_number="+91" + phone_number
           ).first()
        if existing_user is not None:
            return jsonify({
                "status": "error",
                "message": "This phone number is already linked to an account."
            }), 409

        request_phone_otp(
            phone_number,
            purpose="phone_link",
            user_id=user.id
        )

        return jsonify({
            "status": "success",
            "message": "If the number is valid, a verification OTP has been sent."
        }), 200

    except ValueError as error:
        return jsonify({
            "status": "error",
            "message": str(error)
        }), 400

    except Exception:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Unable to send verification OTP right now."
        }), 503

@auth_bp.route("/api/auth/phone/verify-otp", methods=["POST"])
@limiter.limit("5 per minute")
def verify_phone_otp_route():
    data = _json_object()

    phone_number = data.get("phone_number")
    otp = data.get("otp")

    if not isinstance(phone_number, str) or not phone_number.strip():
        return jsonify({
            "status": "error",
            "message": "A phone number is required."
        }), 400

    if not isinstance(otp, str) or not otp.strip():
        return jsonify({
            "status": "error",
            "message": "The OTP is required."
        }), 400

    try:
        challenge = verify_phone_otp(phone_number, otp)

        if challenge is None:
            return jsonify({
                "status": "error",
                "message": "Invalid or expired OTP."
            }), 400

        user = User.query.filter_by(
            phone_number="+91" + challenge.phone_number
        ).first()

        if user is None or user.role != "citizen":
            return jsonify({
                "status": "error",
                "message": "Unable to sign in with this phone number."
            }), 401

        if user.phone_verified_at is None:
            user.phone_verified_at = datetime.now(timezone.utc)
            db.session.commit()

        tokens = create_token_pair(user)

        return jsonify({
            "status": "success",
            "message": "Phone verification successful.",
            **tokens,
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "role": user.role,
                "phone_number": user.phone_number
            }
        }), 200

    except ValueError as error:
        return jsonify({
            "status": "error",
            "message": str(error)
        }), 400

    except Exception:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": "Phone verification is temporarily unavailable."
        }), 500

# ---------------------------------------------------------------------------
# Phase 7: verified identity linking and unlinking
# ---------------------------------------------------------------------------

def _current_citizen_from_jwt():
    try:
        account_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return None
    account = db.session.get(User, account_id)
    if account is None or account.role != "citizen":
        return None
    return account


def _verify_linking_proof(user, data):
    """Require fresh proof using an already-linked sign-in method."""
    password = data.get("current_password")
    if (
        user.password_hash
        and isinstance(password, str)
        and user.check_password(password)
    ):
        return True

    google_token = data.get("current_google_id_token")
    if user.google_sub and isinstance(google_token, str) and google_token.strip():
        try:
            claims = verify_google_id_token(google_token)
            if claims.get("google_sub") == user.google_sub:
                return True
        except (ValueError, RuntimeError):
            pass

    phone_otp = data.get("current_phone_otp")
    if user.phone_number and user.phone_verified_at and isinstance(phone_otp, str):
        try:
            normalized = normalize_indian_phone_number(data.get("current_phone_number", ""))
            if "+91" + normalized != user.phone_number:
                return False
            challenge = verify_phone_otp(normalized, phone_otp, purpose="phone_auth")
            return challenge is not None and challenge.phone_number == normalized
        except (ValueError, TypeError):
            return False

    return False


@auth_bp.route("/api/auth/email/link/request-otp", methods=["POST"])
@jwt_required()
@limiter.limit("3 per minute")
def request_email_link_otp_route():
    data = _json_object()
    user = _current_citizen_from_jwt()
    if user is None:
        return jsonify({"status": "error", "message": "Citizen account not found."}), 403
    if not _verify_linking_proof(user, data):
        return jsonify({"status": "error", "message": "Fresh account verification is required."}), 403

    email = data.get("email")
    try:
        code = create_email_change_otp(user, email)
        send_email(
            email.strip().lower(),
            "Verify your FloodShield email address",
            f"Your FloodShield email verification code is {code}. It expires in 10 minutes. If you did not request this change, ignore this message.",
        )
        return jsonify({"status": "success", "message": "A verification code has been sent to the new email address."}), 200
    except ValueError as error:
        return jsonify({"status": "error", "message": str(error)}), 400
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Email-link OTP delivery failed")
        return jsonify({"status": "error", "message": "Unable to send the verification code right now."}), 503


@auth_bp.route("/api/auth/email/link/verify-otp", methods=["POST"])
@jwt_required()
@limiter.limit("5 per minute")
def verify_email_link_otp_route():
    data = _json_object()
    user = _current_citizen_from_jwt()
    if user is None:
        return jsonify({"status": "error", "message": "Citizen account not found."}), 403
    email = data.get("email")
    code = data.get("otp")
    if not isinstance(email, str) or not isinstance(code, str):
        return jsonify({"status": "error", "message": "Email and OTP are required."}), 400
    try:
        if not verify_email_change_otp(user, email, code):
            return jsonify({"status": "error", "message": "Invalid or expired verification code."}), 400
        return jsonify({"status": "success", "message": "Email address linked and verified successfully.", "user": {"id": user.id, "name": user.name, "email": user.email, "email_verified": True}}), 200
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Email-link verification failed")
        return jsonify({"status": "error", "message": "Email linking is temporarily unavailable."}), 500


@auth_bp.route("/api/auth/google/link", methods=["POST"])
@jwt_required()
@limiter.limit("5 per minute")
def link_google_identity_route():
    data = _json_object()
    user = _current_citizen_from_jwt()
    if user is None:
        return jsonify({"status": "error", "message": "Citizen account not found."}), 403
    if not _verify_linking_proof(user, data):
        return jsonify({"status": "error", "message": "Fresh verification of your existing account is required."}), 403
    token = data.get("id_token")
    if not isinstance(token, str) or not token.strip():
        return jsonify({"status": "error", "message": "A Google ID token is required."}), 400
    try:
        claims = verify_google_id_token(token)
        if user.google_sub:
            return jsonify({"status": "error", "message": "A Google account is already linked."}), 409
        existing = User.query.filter_by(google_sub=claims["google_sub"]).first()
        if existing is not None and existing.id != user.id:
            return jsonify({"status": "error", "message": "This Google account is already linked to another account."}), 409
        user.google_sub = claims["google_sub"]
        db.session.commit()
        return jsonify({"status": "success", "message": "Google account linked successfully."}), 200
    except ValueError:
        db.session.rollback()
        return jsonify({"status": "error", "message": "The Google ID token is invalid or expired."}), 401
    except IntegrityError:
        db.session.rollback()
        return jsonify({"status": "error", "message": "This Google account is already linked."}), 409
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Google identity linking failed")
        return jsonify({"status": "error", "message": "Google linking is temporarily unavailable."}), 500


@auth_bp.route("/api/auth/identities/unlink", methods=["POST"])
@jwt_required()
@limiter.limit("5 per minute")
def unlink_identity_route():
    data = _json_object()
    user = _current_citizen_from_jwt()
    if user is None:
        return jsonify({"status": "error", "message": "Citizen account not found."}), 403
    identity = data.get("identity")
    if identity not in ("email", "phone", "google"):
        return jsonify({"status": "error", "message": "Identity must be email, phone, or google."}), 400
    if not _verify_linking_proof(user, data):
        return jsonify({"status": "error", "message": "Fresh account verification is required."}), 403

    has_email_login = bool(user.email and user.email_verified_at and user.password_hash)
    has_phone_login = bool(user.phone_number and user.phone_verified_at)
    has_google_login = bool(user.google_sub)
    available = {"email": has_email_login, "phone": has_phone_login, "google": has_google_login}
    if not available[identity]:
        return jsonify({"status": "error", "message": "That sign-in method is not linked."}), 404
    remaining = sum(1 for key, value in available.items() if value and key != identity)
    if remaining < 1:
        return jsonify({"status": "error", "message": "You must keep at least one usable sign-in method linked."}), 409

    try:
        if identity == "email":
            user.email = None
            user.email_verified_at = None
            user.password_hash = None
        elif identity == "phone":
            user.phone_number = None
            user.phone_verified_at = None
        else:
            user.google_sub = None
        db.session.commit()
        return jsonify({"status": "success", "message": f"{identity.capitalize()} sign-in method unlinked successfully."}), 200
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Identity unlinking failed")
        return jsonify({"status": "error", "message": "Identity unlinking is temporarily unavailable."}), 500


# ---------------------------------------------------------------------------
# Phase 7: password recovery through an already verified phone identity
# ---------------------------------------------------------------------------

@auth_bp.route("/api/auth/phone/recover-password/request-otp", methods=["POST"])
@limiter.limit("3 per minute")
def request_phone_password_recovery_otp_route():
    data = _json_object()
    phone_number = data.get("phone_number")
    if not isinstance(phone_number, str) or not phone_number.strip():
        return jsonify({"status": "error", "message": "A phone number is required."}), 400

    generic = {
        "status": "success",
        "message": "If the number belongs to an eligible verified account, a recovery code will be sent.",
    }
    try:
        normalized = normalize_indian_phone_number(phone_number)
        user = User.query.filter_by(phone_number="+91" + normalized).first()
        if user is None or user.role != "citizen" or user.phone_verified_at is None:
            return jsonify(generic), 200
        request_phone_otp(
            normalized, purpose="password_recovery", user_id=user.id
        )
        return jsonify(generic), 200
    except ValueError:
        # Keep the response generic for invalid or unregistered numbers.
        return jsonify(generic), 200
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Phone password-recovery OTP request failed")
        return jsonify({"status": "error", "message": "Unable to send a recovery code right now."}), 503


@auth_bp.route("/api/auth/phone/recover-password/verify-otp", methods=["POST"])
@limiter.limit("5 per minute")
def verify_phone_password_recovery_otp_route():
    data = _json_object()
    phone_number = data.get("phone_number")
    otp = data.get("otp")
    new_password = data.get("new_password")

    if not isinstance(phone_number, str) or not phone_number.strip():
        return jsonify({"status": "error", "message": "A phone number is required."}), 400
    if not isinstance(otp, str) or len(otp) != 6 or not otp.isdigit():
        return jsonify({"status": "error", "message": "A valid six-digit OTP is required."}), 400
    if not isinstance(new_password, str) or not 8 <= len(new_password) <= 128:
        return jsonify({"status": "error", "message": "New password must be between 8 and 128 characters."}), 400

    try:
        normalized = normalize_indian_phone_number(phone_number)
        user = User.query.filter_by(phone_number="+91" + normalized).first()
        if user is None or user.role != "citizen" or user.phone_verified_at is None:
            return jsonify({"status": "error", "message": "Invalid or expired recovery code."}), 400

        challenge = verify_phone_otp(
            normalized, otp, purpose="password_recovery", expected_user_id=user.id
        )
        if challenge is None:
            return jsonify({"status": "error", "message": "Invalid or expired recovery code."}), 400

        now = datetime.now(timezone.utc)
        user.set_password(new_password)
        PasswordResetToken.query.filter_by(
            user_id=user.id, used_at=None
        ).update({"used_at": now}, synchronize_session=False)
        RefreshSession.query.filter_by(
            user_id=user.id, revoked_at=None
        ).update({"revoked_at": now}, synchronize_session=False)
        db.session.commit()

        return jsonify({
            "status": "success",
            "message": "Password reset successfully. Please sign in again.",
        }), 200
    except ValueError as error:
        return jsonify({"status": "error", "message": str(error)}), 400
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Phone password recovery failed")
        return jsonify({"status": "error", "message": "Password recovery is temporarily unavailable."}), 500
