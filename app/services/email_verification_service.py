
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models.user import User
from app.models.email_verification_token import EmailVerificationToken
from app.services.auth_token_service import (
    generate_secure_token,
    hash_auth_token,
)


TOKEN_EXPIRY_HOURS = 24


def _utc_datetime(value):
    """
    Normalize a database datetime to timezone-aware UTC.

    SQLite may return naive datetime objects even when the
    SQLAlchemy column is configured with timezone=True.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def create_email_verification_token(user):
    """
    Create a new email verification token.

    Previous unused verification tokens for this user are
    invalidated. Only the token hash is stored in the database.

    Returns the original token so the caller can email it.
    """
    if not isinstance(user, User):
        raise ValueError("A valid user account is required")

    if user.role != "citizen":
        raise ValueError("Only citizen accounts can use email verification")

    if not user.email:
        raise ValueError("The user account must have an email address")

    if user.email_verified_at is not None:
        raise ValueError("The email address is already verified")

    now = datetime.now(timezone.utc)

    try:
        # Invalidate previous unused verification tokens.
        previous_tokens = EmailVerificationToken.query.filter_by(
            user_id=user.id,
            used_at=None,
        ).all()

        for previous_token in previous_tokens:
            previous_token.used_at = now

        raw_token = generate_secure_token()

        verification_record = EmailVerificationToken(
            user_id=user.id,
            token_hash=hash_auth_token(raw_token),
            expires_at=now + timedelta(hours=TOKEN_EXPIRY_HOURS),
        )

        db.session.add(verification_record)
        db.session.commit()

        return raw_token

    except Exception:
        db.session.rollback()
        raise


def verify_email_verification_token(raw_token):
    """
    Verify and consume a one-time email verification token.

    Returns:
        True  - verification succeeded
        False - token is invalid, expired, already used,
                or does not belong to an available citizen account
    """
    if not isinstance(raw_token, str) or not raw_token.strip():
        return False

    token_hash = hash_auth_token(raw_token)
    now = datetime.now(timezone.utc)

    try:
        verification_record = (
            EmailVerificationToken.query
            .filter_by(token_hash=token_hash)
            .with_for_update()
            .first()
        )

        if verification_record is None:
            return False

        if verification_record.used_at is not None:
            return False

        expires_at = _utc_datetime(verification_record.expires_at)

        if expires_at <= now:
            return False

        user = db.session.get(User, verification_record.user_id)

        if user is None or user.role != "citizen":
            return False

        if user.email_verified_at is not None:
            verification_record.used_at = now
            db.session.commit()
            return True

        verification_record.used_at = now
        user.email_verified_at = now

        db.session.commit()

        return True

    except Exception:
        db.session.rollback()
        raise
