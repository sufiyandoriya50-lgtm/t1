
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.user import User
from app.services.email_service import send_email
from app.services.email_otp_service import generate_email_otp


PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128


def validate_registration_data(name, email, password):
    """Validate citizen registration fields."""

    if not isinstance(name, str) or not name.strip():
        raise ValueError("A valid name is required")

    name = name.strip()

    if len(name) > 100:
        raise ValueError("Name cannot exceed 100 characters")

    if not isinstance(email, str):
        raise ValueError("A valid email address is required")

    email = email.strip().lower()

    if len(email) > 120:
        raise ValueError("Email address cannot exceed 120 characters")

    if (
        not email
        or "@" not in email
        or any(character.isspace() for character in email)
        or email.startswith("@")
        or email.endswith("@")
        or "." not in email.rsplit("@", 1)[-1]
    ):
        raise ValueError("A valid email address is required")

    if not isinstance(password, str):
        raise ValueError("A valid password is required")

    if not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
        raise ValueError(
            f"Password must be between {PASSWORD_MIN_LENGTH} "
            f"and {PASSWORD_MAX_LENGTH} characters"
        )

    return name, email, password


def register_citizen(name, email, password):
    """
    Create an unverified citizen account and email a six-digit OTP.

    Public registration always creates a citizen account.
    It cannot create an administrator account.
    """

    name, email, password = validate_registration_data(
        name,
        email,
        password,
    )

    if User.query.filter_by(email=email).first():
        raise ValueError("An account with this email already exists")

    user = User(
        name=name,
        email=email,
        role="citizen",
        email_verified_at=None,
    )

    user.set_password(password)

    try:
        db.session.add(user)
        db.session.flush()

        otp = generate_email_otp(user)

    except IntegrityError:
        db.session.rollback()
        raise ValueError(
            "An account with this email already exists"
        )

    except Exception:
        db.session.rollback()
        raise

    email_body = (
        f"Hello {name},\n\n"
        "Welcome to FloodShield.\n\n"
        f"Your email verification OTP is: {otp}\n\n"
        "This code expires in 5 minutes and can only be used once.\n"
        "You have a maximum of 5 verification attempts.\n\n"
        "If you did not create this account, please ignore this email.\n\n"
        "FloodShield Team"
    )

    try:
        send_email(
            recipient=email,
            subject="Your FloodShield email verification code",
            body=email_body,
        )
    except Exception:
        # The account remains unverified. The user can request
        # another OTP after the resend cooldown.
        raise RuntimeError(
            "Your account was created, but the verification email "
            "could not be delivered. Please request another OTP."
        )

    return user
