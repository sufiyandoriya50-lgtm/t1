import os
from dotenv import load_dotenv
from datetime import timedelta
# Load environment variables from the backend .env file
load_dotenv()


class Config:
    """Base configuration for FloodShield."""

    # Security
    SECRET_KEY = os.getenv("SECRET_KEY")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
        # JWT authentication supports API headers and secure browser cookies.
    JWT_TOKEN_LOCATION = ["headers", "cookies"]

    # Protect cookie-authenticated requests against CSRF.
    JWT_COOKIE_CSRF_PROTECT = True
    JWT_CSRF_IN_COOKIES = True
    JWT_CSRF_METHODS = ["POST", "PUT", "PATCH", "DELETE"]
    JWT_CSRF_HEADER_NAME = "X-CSRF-TOKEN"

    # Browser cookie security.
    JWT_COOKIE_SECURE = False
    JWT_COOKIE_HTTPONLY = True
    JWT_COOKIE_SAMESITE = "Lax"

    # JWT token lifetimes
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///floodshield.db"
    )
    # Google Sign-In
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    # Maximum total HTTP request size, including multipart upload overhead.(17mb with total 3 pics is max )
    MAX_CONTENT_LENGTH = 17 * 1024 * 1024

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Application logging level.
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    # API rate limiting
    RATELIMIT_STORAGE_URI = os.getenv(
        "RATELIMIT_STORAGE_URI",
        "memory://"
    )
    RATELIMIT_HEADERS_ENABLED = True

    # Explicit browser origins allowed to call the API. Empty means same-origin
    # only; never use "*" with credentialed browser requests.
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "").split(",")
        if origin.strip()
    ]
    # Weather API
    WEATHER_API_URL = os.getenv(
        "WEATHER_API_URL",
        "https://api.open-meteo.com/v1/forecast"
    )
    #firebase
    FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH")
    # Whether Firebase credentials are mandatory in this environment.
    # Firebase Admin is optional locally and used only for FCM push delivery.
    REQUIRE_FIREBASE = False

    # Fast2SMS phone OTP delivery
    FAST2SMS_API_KEY = os.getenv("FAST2SMS_API_KEY")
    FAST2SMS_SENDER_ID = os.getenv("FAST2SMS_SENDER_ID")
    FAST2SMS_MESSAGE_ID = os.getenv("FAST2SMS_MESSAGE_ID")
    # Application settings
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"


class DevelopmentConfig(Config):
    """Configuration for local development."""

    DEBUG = True


# Configuration used only during automated tests.
class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_SECRET_KEY = "floodshield-testing-secret-key-2026-secure"
    SECRET_KEY = "floodshield-testing-secret-key-2026"


class ProductionConfig(Config):
    """Configuration for production deployment."""

    # Production requires Firebase Admin credentials for FCM push delivery only.
    REQUIRE_FIREBASE = True
    DEBUG = False
    TESTING = False
    
    # Require an explicitly configured PostgreSQL database in production.
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    # Production must use shared rate-limit storage.
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI")
    # Require HTTPS for administrator authentication cookies.
    JWT_COOKIE_SECURE = True
    @classmethod
    def validate_security_config(cls):
        """Require strong, separate signing secrets in production."""
        for setting in ("SECRET_KEY", "JWT_SECRET_KEY"):
            value = getattr(cls, setting, None)
            if not isinstance(value, str) or len(value.strip()) < 32:
                raise RuntimeError(
                    f"{setting} must contain at least 32 characters in production."
                )

        if cls.SECRET_KEY.strip() == cls.JWT_SECRET_KEY.strip():
            raise RuntimeError(
                "SECRET_KEY and JWT_SECRET_KEY must be different in production."
            )

    @classmethod
    def validate_database_config(cls):
        """Ensure production uses a valid PostgreSQL connection URL."""

        database_url = cls.SQLALCHEMY_DATABASE_URI

        if not database_url:
            raise RuntimeError(
                "DATABASE_URL is required in production."
            )

        if not database_url.startswith(
            ("postgresql://", "postgresql+psycopg://")
        ):
            raise RuntimeError(
                "Production requires a PostgreSQL database."
            )
    @classmethod
    def validate_rate_limit_config(cls):
        """Ensure production uses shared rate-limit storage."""

        storage_uri = cls.RATELIMIT_STORAGE_URI

        if not storage_uri:
            raise RuntimeError(
                "RATELIMIT_STORAGE_URI is required in production."
            )

        if storage_uri.strip().lower().startswith("memory://"):
            raise RuntimeError(
                "Production requires shared rate-limit storage, not memory://."
            )