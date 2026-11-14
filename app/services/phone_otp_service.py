
import hashlib
import hmac
import secrets

from datetime import datetime, timedelta, timezone

from flask import current_app

from app.extensions import db
from app.models.phone_otp_challenge import PhoneOtpChallenge
from app.services.sms_service import (
    normalize_indian_phone_number,
    send_phone_otp,
)


OTP_EXPIRY_MINUTES = 5
OTP_RESEND_COOLDOWN_SECONDS = 60
OTP_MAX_ATTEMPTS = 5

SUPPORTED_PURPOSES = ("phone_auth", "phone_link", "password_recovery")


def _utc_datetime(value):
    """Normalize database datetimes to timezone-aware UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def _hash_phone_otp(phone_number, purpose, otp):
    """Create a keyed hash of the phone OTP."""

    secret = current_app.config.get("SECRET_KEY")

    if not isinstance(secret, str) or not secret:
        raise RuntimeError("Application secret key is not configured")

    message = (
        f"phone-otp:{purpose}:{phone_number}:{otp}"
    ).encode("utf-8")

    return hmac.new(
        secret.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()


def request_phone_otp(phone_number, purpose="phone_auth", user_id=None):
    """Generate, store and deliver a phone OTP."""

    phone_number = normalize_indian_phone_number(phone_number)

    if purpose not in SUPPORTED_PURPOSES:
        raise ValueError("Unsupported phone OTP purpose")

    if purpose in ("phone_link", "password_recovery") and user_id is None:
        raise ValueError("An account is required for this OTP purpose")

    now = datetime.now(timezone.utc)

    try:
        latest_challenge = (
            PhoneOtpChallenge.query
            .filter_by(
                phone_number=phone_number,
                purpose=purpose,
            )
            .order_by(PhoneOtpChallenge.created_at.desc())
            .first()
        )

        if latest_challenge is not None:
            created_at = _utc_datetime(latest_challenge.created_at)

            elapsed = (now - created_at).total_seconds()

            if elapsed < OTP_RESEND_COOLDOWN_SECONDS:
                raise ValueError(
                    "Please wait before requesting another OTP"
                )

        previous_challenges = (
            PhoneOtpChallenge.query
            .filter_by(
                phone_number=phone_number,
                purpose=purpose,
                consumed_at=None,
            )
            .all()
        )

        for challenge in previous_challenges:
            challenge.consumed_at = now

        otp = f"{secrets.randbelow(1_000_000):06d}"

        challenge = PhoneOtpChallenge(
            user_id=user_id,
            phone_number=phone_number,
            purpose=purpose,
            code_hash=_hash_phone_otp(
                phone_number,
                purpose,
                otp,
            ),
            expires_at=now + timedelta(
                minutes=OTP_EXPIRY_MINUTES
            ),
            attempt_count=0,
            max_attempts=OTP_MAX_ATTEMPTS,
        )

        db.session.add(challenge)
        db.session.commit()

        try:
            send_phone_otp(phone_number, otp)
        except Exception:
            challenge.consumed_at = datetime.now(timezone.utc)
            db.session.commit()
            raise

        return True

    except Exception:
        db.session.rollback()
        raise


def verify_phone_otp(
    phone_number,
    supplied_otp,
    purpose="phone_auth",
    expected_user_id=None,
):
    """
    Verify and consume a phone OTP.

    For phone linking, expected_user_id ensures that only the
    account that requested the OTP can consume it.
    """

    phone_number = normalize_indian_phone_number(phone_number)

    if purpose not in SUPPORTED_PURPOSES:
        raise ValueError("Unsupported phone OTP purpose")

    if purpose in ("phone_link", "password_recovery") and expected_user_id is None:
        raise ValueError("Expected account ID is required for this OTP purpose")

    if (
        not isinstance(supplied_otp, str)
        or len(supplied_otp) != 6
        or not supplied_otp.isdigit()
    ):
        return None

    now = datetime.now(timezone.utc)

    try:
        filters = {
            "phone_number": phone_number,
            "purpose": purpose,
            "consumed_at": None,
        }

        if purpose in ("phone_link", "password_recovery"):
            filters["user_id"] = expected_user_id

        challenge = (
            PhoneOtpChallenge.query
            .filter_by(**filters)
            .order_by(PhoneOtpChallenge.created_at.desc())
            .with_for_update()
            .first()
        )

        if challenge is None:
            return None

        if challenge.attempt_count >= challenge.max_attempts:
            challenge.consumed_at = now
            db.session.commit()
            return None

        if _utc_datetime(challenge.expires_at) <= now:
            challenge.consumed_at = now
            db.session.commit()
            return None

        challenge.attempt_count += 1

        expected_hash = _hash_phone_otp(
            phone_number,
            purpose,
            supplied_otp,
        )

        if not hmac.compare_digest(
            challenge.code_hash,
            expected_hash,
        ):
            if challenge.attempt_count >= challenge.max_attempts:
                challenge.consumed_at = now

            db.session.commit()
            return None

        challenge.consumed_at = now
        db.session.commit()

        return challenge

    except Exception:
        db.session.rollback()
        raise
