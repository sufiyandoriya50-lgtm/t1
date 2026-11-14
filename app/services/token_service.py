
import hashlib
import uuid

from datetime import datetime, timezone

from flask import has_request_context, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    decode_token,
)

from app.extensions import db
from app.models.refresh_session import RefreshSession


def _hash_jti(jti):
    """Hash a JWT ID before storing it in the database."""
    return hashlib.sha256(jti.encode("utf-8")).hexdigest()


def create_token_pair(user, family_id=None, commit=True):
    """
    Create an access and refresh token pair.

    New logins receive a new session family.
    Refresh operations reuse the existing family_id.

    Set commit=False when the caller manages the transaction.
    """

    if family_id is None:
        family_id = str(uuid.uuid4())

    additional_claims = {
        "sid": family_id
    }

    access_token = create_access_token(
        identity=str(user.id),
        additional_claims=additional_claims
    )

    refresh_token = create_refresh_token(
        identity=str(user.id),
        additional_claims=additional_claims
    )

    refresh_claims = decode_token(refresh_token)

    jti = refresh_claims.get("jti")
    expires_at = refresh_claims.get("exp")

    if not jti or not expires_at:
        raise RuntimeError(
            "Unable to create a valid refresh token."
        )

    device_info = None
    user_agent = None

    if has_request_context():
        device_info = (
            request.headers.get("X-Device-Info", "")[:255] or None
        )

        user_agent = (
            request.headers.get("User-Agent", "")[:512] or None
        )

    session = RefreshSession(
        user_id=user.id,
        token_hash=_hash_jti(jti),
        family_id=family_id,
        expires_at=datetime.fromtimestamp(
            expires_at,
            tz=timezone.utc
        ),
        device_info=device_info,
        user_agent=user_agent,
    )

    try:
        db.session.add(session)
        db.session.flush()

        if commit:
            db.session.commit()

    except Exception:
        db.session.rollback()
        raise

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
    }
