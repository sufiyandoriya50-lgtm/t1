
import hashlib
import secrets


def generate_secure_token():
    """
    Generate a cryptographically secure random token.

    The original token is sent to the user's email.
    Only its hash should be stored in the database.
    """
    return secrets.token_urlsafe(32)


def hash_auth_token(token):
    """
    Convert an authentication token into a SHA-256 hash.

    This allows the database to verify tokens without
    storing the original usable token.
    """
    if not isinstance(token, str) or not token.strip():
        raise ValueError("A valid authentication token is required")

    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def verify_auth_token(token, stored_hash):
    """
    Verify a supplied token against its stored SHA-256 hash.
    """
    if (
        not isinstance(token, str)
        or not token
        or not isinstance(stored_hash, str)
        or not stored_hash
    ):
        return False

    calculated_hash = hash_auth_token(token)

    return secrets.compare_digest(
        calculated_hash,
        stored_hash
    )
