
import hashlib
import hmac
import secrets

from datetime import datetime, timedelta, timezone

from flask import current_app

from app.extensions import db
from app.models.user import User
from app.models.email_verification_token import EmailVerificationToken


OTP_EXPIRY_MINUTES = 5
OTP_RESEND_COOLDOWN_SECONDS = 60
OTP_MAX_ATTEMPTS = 5


def _utc_datetime(value):
    """Normalize database datetimes to timezone-aware UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def _hash_otp(user_id, otp):
    """
    Hash the OTP using HMAC-SHA256 and the application's secret key.

    Unlike a plain SHA-256 hash, this prevents someone with database
    access from cheaply testing all one million possible OTP values.
    """
    secret = current_app.config.get("SECRET_KEY")

    if not isinstance(secret, str) or not secret:
        raise RuntimeError("Application secret key is not configured")

    message = f"email-verification:{user_id}:{otp}".encode("utf-8")

    return hmac.new(
        secret.encode("utf-8"),
        message,
        hashlib.sha256
    ).hexdigest()


def generate_email_otp(user):
    """
    Generate and store a six-digit email OTP.

    Returns the plaintext OTP for the caller to send by email.
    Only its HMAC hash is stored in the database.
    """

    if not isinstance(user, User) or user.role != "citizen":
        raise ValueError("A valid citizen account is required")

    if not user.email:
        raise ValueError("The account must have an email address")

    if user.email_verified_at is not None:
        raise ValueError("Email address is already verified")

    now = datetime.now(timezone.utc)

    try:
        latest_token = (
            EmailVerificationToken.query
            .filter_by(user_id=user.id)
            .order_by(EmailVerificationToken.created_at.desc())
            .first()
        )

        if latest_token is not None and latest_token.used_at is None:
            created_at = _utc_datetime(latest_token.created_at)

            elapsed = (now - created_at).total_seconds()

            if elapsed < OTP_RESEND_COOLDOWN_SECONDS:
                raise ValueError(
                    "Please wait before requesting another OTP"
                )

        # Invalidate every previous unused OTP.
        previous_tokens = (
            EmailVerificationToken.query
            .filter_by(user_id=user.id, used_at=None)
            .all()
        )

        for previous_token in previous_tokens:
            previous_token.used_at = now

        otp = f"{secrets.randbelow(1_000_000):06d}"

        token = EmailVerificationToken(
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


def verify_email_otp(user, supplied_otp):
    """
    Verify and consume an email OTP.

    Returns True when verification succeeds, otherwise False.
    """

    if not isinstance(user, User) or user.role != "citizen":
        return False

    if user.email_verified_at is not None:
        return True

    if (
        not isinstance(supplied_otp, str)
        or len(supplied_otp) != 6
        or not supplied_otp.isdigit()
    ):
        return False

    now = datetime.now(timezone.utc)

    try:
        token = (
            EmailVerificationToken.query
            .filter_by(user_id=user.id, used_at=None)
            .order_by(EmailVerificationToken.created_at.desc())
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
        user.email_verified_at = now

        db.session.commit()
        return True

    except Exception:
        db.session.rollback()
        raise
