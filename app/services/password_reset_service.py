
import hashlib
import hmac
import secrets

from datetime import datetime, timedelta, timezone

from flask import current_app

from app.extensions import db
from app.models.user import User
from app.models.password_reset_token import PasswordResetToken
from app.models.refresh_session import RefreshSession


OTP_EXPIRY_MINUTES = 10
OTP_RESEND_COOLDOWN_SECONDS = 60
OTP_MAX_ATTEMPTS = 5

PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128


def _utc_datetime(value):
    """Normalize database datetimes to timezone-aware UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def _hash_otp(user_id, otp):
    """Store an HMAC hash instead of the plaintext OTP."""
    secret = current_app.config.get("SECRET_KEY")

    if not isinstance(secret, str) or not secret:
        raise RuntimeError("Application secret key is not configured")

    message = f"password-reset:{user_id}:{otp}".encode("utf-8")

    return hmac.new(
        secret.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()


def generate_password_reset_otp(user):
    """Generate and store a password-reset OTP for a verified citizen."""

    if (
        not isinstance(user, User)
        or user.role != "citizen"
        or not user.email
        or user.email_verified_at is None
    ):
        raise ValueError("A verified citizen account is required")

    now = datetime.now(timezone.utc)

    try:
        latest_token = (
            PasswordResetToken.query
            .filter_by(user_id=user.id)
            .order_by(PasswordResetToken.created_at.desc())
            .first()
        )

        if latest_token is not None and latest_token.used_at is None:
            elapsed = (
                now - _utc_datetime(latest_token.created_at)
            ).total_seconds()

            if elapsed < OTP_RESEND_COOLDOWN_SECONDS:
                raise ValueError(
                    "Please wait before requesting another OTP"
                )

        previous_tokens = (
            PasswordResetToken.query
            .filter_by(user_id=user.id, used_at=None)
            .all()
        )

        for token in previous_tokens:
            token.used_at = now

        otp = f"{secrets.randbelow(1_000_000):06d}"

        token = PasswordResetToken(
            user_id=user.id,
            token_hash=_hash_otp(user.id, otp),
            expires_at=now + timedelta(minutes=OTP_EXPIRY_MINUTES),
            attempt_count=0,
            max_attempts=OTP_MAX_ATTEMPTS,
        )

        db.session.add(token)
        db.session.commit()

        return otp

    except Exception:
        db.session.rollback()
        raise


def reset_password_with_otp(user, supplied_otp, new_password):
    """
    Verify a reset OTP and change the password.

    Returns True only when the OTP is valid and the password is changed.
    """

    if (
        not isinstance(user, User)
        or user.role != "citizen"
        or not user.email
        or user.email_verified_at is None
    ):
        return False

    if (
        not isinstance(supplied_otp, str)
        or len(supplied_otp) != 6
        or not supplied_otp.isdigit()
    ):
        return False

    if (
        not isinstance(new_password, str)
        or not PASSWORD_MIN_LENGTH <= len(new_password) <= PASSWORD_MAX_LENGTH
    ):
        raise ValueError(
            f"Password must be between {PASSWORD_MIN_LENGTH} "
            f"and {PASSWORD_MAX_LENGTH} characters"
        )

    now = datetime.now(timezone.utc)

    try:
        token = (
            PasswordResetToken.query
            .filter_by(user_id=user.id, used_at=None)
            .order_by(PasswordResetToken.created_at.desc())
            .with_for_update()
            .first()
        )

        if token is None:
            return False

        if token.attempt_count >= token.max_attempts:
            token.used_at = now
            db.session.commit()
            return False

        if _utc_datetime(token.expires_at) <= now:
            token.used_at = now
            db.session.commit()
            return False

        token.attempt_count += 1

        expected_hash = _hash_otp(user.id, supplied_otp)

        if not hmac.compare_digest(token.token_hash, expected_hash):
            if token.attempt_count >= token.max_attempts:
                token.used_at = now

            db.session.commit()
            return False

        token.used_at = now
        user.set_password(new_password)

        # Invalidate all other outstanding reset codes for this user.
        other_tokens = (
            PasswordResetToken.query
            .filter(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.id != token.id,
            )
            .all()
        )

        for other_token in other_tokens:
            other_token.used_at = now

        # Password recovery invalidates every existing device session.
        RefreshSession.query.filter_by(
            user_id=user.id,
            revoked_at=None,
        ).update(
            {"revoked_at": now},
            synchronize_session=False,
        )

        db.session.commit()
        return True

    except Exception:
        db.session.rollback()
        raise
