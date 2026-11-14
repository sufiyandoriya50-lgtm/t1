
from flask import current_app
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token


def verify_google_id_token(token):
    """
    Verify a Google ID token and return its trusted claims.

    Google verifies the token signature and standard claims,
    including issuer, audience and expiration.
    """

    if not isinstance(token, str) or not token.strip():
        raise ValueError("A valid Google ID token is required.")

    client_id = current_app.config.get("GOOGLE_CLIENT_ID")

    if not isinstance(client_id, str) or not client_id.strip():
        raise RuntimeError("Google Sign-In is not configured.")

    try:
        claims = id_token.verify_oauth2_token(
            token.strip(),
            google_requests.Request(),
            audience=client_id
        )
    except ValueError as error:
        raise ValueError("Invalid Google ID token.") from error
    except Exception as error:
        raise RuntimeError("Google token verification is unavailable.") from error

    issuer = claims.get("iss")
    if issuer not in (
        "accounts.google.com",
        "https://accounts.google.com"
    ):
        raise ValueError("Invalid Google token issuer.")

    google_sub = claims.get("sub")
    email = claims.get("email")
    email_verified = claims.get("email_verified")
    name = claims.get("name")

    if not isinstance(google_sub, str) or not google_sub.strip():
        raise ValueError("Google account identifier is missing.")

    if not isinstance(email, str) or not email.strip():
        raise ValueError("Google account email is missing.")

    if email_verified is not True:
        raise ValueError("Google email address is not verified.")

    return {
        "google_sub": google_sub,
        "email": email.strip().lower(),
        "name": name.strip() if isinstance(name, str) and name.strip() else None
    }
