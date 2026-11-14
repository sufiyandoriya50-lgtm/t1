import hashlib
import hmac
import secrets

from datetime import datetime, timedelta, timezone

from flask import current_app
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.pending_email_change import PendingEmailChange
from app.models.email_verification_token import EmailVerificationToken
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User

OTP_EXPIRY_MINUTES = 10
OTP_RESEND_COOLDOWN_SECONDS = 60
OTP_MAX_ATTEMPTS = 5


def _utc(value):
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _hash_code(user_id, email, code):
    secret = current_app.config.get("SECRET_KEY")
    if not isinstance(secret, str) or not secret:
        raise RuntimeError("Application secret key is not configured")
    message = f"email-change:{user_id}:{email}:{code}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def create_email_change_otp(user, new_email):
    if not isinstance(user, User) or user.role != "citizen":
        raise ValueError("A valid citizen account is required")
    if not isinstance(new_email, str) or not new_email.strip() or len(new_email.strip()) > 120:
        raise ValueError("A valid email address is required")

    new_email = new_email.strip().lower()
    if "@" not in new_email or new_email.startswith("@") or new_email.endswith("@"):
        raise ValueError("A valid email address is required")
    if user.email and user.email.lower() == new_email:
        raise ValueError("This email address is already linked to your account")
    if User.query.filter(User.email == new_email, User.id != user.id).first():
        raise ValueError("This email address is already linked to another account")

    now = datetime.now(timezone.utc)
    latest = (PendingEmailChange.query.filter_by(user_id=user.id)
              .order_by(PendingEmailChange.created_at.desc()).first())
    if latest is not None and latest.consumed_at is None:
        if (now - _utc(latest.created_at)).total_seconds() < OTP_RESEND_COOLDOWN_SECONDS:
            raise ValueError("Please wait before requesting another OTP")

    try:
        PendingEmailChange.query.filter_by(user_id=user.id, consumed_at=None).update(
            {"consumed_at": now}, synchronize_session=False
        )
        code = f"{secrets.randbelow(1_000_000):06d}"
        record = PendingEmailChange(
            user_id=user.id, email=new_email,
            code_hash=_hash_code(user.id, new_email, code),
            expires_at=now + timedelta(minutes=OTP_EXPIRY_MINUTES),
            attempt_count=0, max_attempts=OTP_MAX_ATTEMPTS,
        )
        db.session.add(record)
        db.session.commit()
        return code
    except Exception:
        db.session.rollback()
        raise


def verify_email_change_otp(user, new_email, supplied_code):
    if not isinstance(user, User) or user.role != "citizen":
        return False
    if not isinstance(new_email, str) or not isinstance(supplied_code, str):
        return False
    new_email = new_email.strip().lower()
    if len(supplied_code) != 6 or not supplied_code.isdigit():
        return False

    now = datetime.now(timezone.utc)
    try:
        record = (PendingEmailChange.query.filter_by(
            user_id=user.id, email=new_email, consumed_at=None
        ).order_by(PendingEmailChange.created_at.desc()).with_for_update().first())
        if record is None:
            return False
        if record.attempt_count >= record.max_attempts or _utc(record.expires_at) <= now:
            record.consumed_at = now
            db.session.commit()
            return False

        record.attempt_count += 1
        expected = _hash_code(user.id, new_email, supplied_code)
        if not hmac.compare_digest(record.code_hash, expected):
            if record.attempt_count >= record.max_attempts:
                record.consumed_at = now
            db.session.commit()
            return False

        if User.query.filter(User.email == new_email, User.id != user.id).first():
            record.consumed_at = now
            db.session.commit()
            return False

        record.consumed_at = now
        user.email = new_email
        user.email_verified_at = now

        # Existing OTPs were issued for the previous email identity.
        EmailVerificationToken.query.filter_by(
            user_id=user.id, used_at=None
        ).update({"used_at": now}, synchronize_session=False)
        PasswordResetToken.query.filter_by(
            user_id=user.id, used_at=None
        ).update({"used_at": now}, synchronize_session=False)

        db.session.commit()
        return True
    except IntegrityError:
        db.session.rollback()
        return False
    except Exception:
        db.session.rollback()
        raise
