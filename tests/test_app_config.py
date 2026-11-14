import pytest

from app import create_app
from app.config import DevelopmentConfig, ProductionConfig, TestingConfig


def _set_production_secrets(monkeypatch):
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "a" * 48)
    monkeypatch.setattr(ProductionConfig, "JWT_SECRET_KEY", "b" * 48)


def _set_production_infrastructure(monkeypatch):
    _set_production_secrets(monkeypatch)
    monkeypatch.setattr(
        ProductionConfig,
        "SQLALCHEMY_DATABASE_URI",
        "postgresql://user:password@localhost/floodshield",
    )
    monkeypatch.setattr(
        ProductionConfig,
        "RATELIMIT_STORAGE_URI",
        "redis://localhost:6379/0",
    )


def test_production_requires_firebase_credentials(monkeypatch):
    _set_production_infrastructure(monkeypatch)
    monkeypatch.setattr(ProductionConfig, "FIREBASE_CREDENTIALS_PATH", None)

    with pytest.raises(
        RuntimeError,
        match="FIREBASE_CREDENTIALS_PATH is required in production",
    ):
        create_app(ProductionConfig)


def test_production_initializes_firebase_when_configured(monkeypatch):
    import app as application

    _set_production_infrastructure(monkeypatch)
    monkeypatch.setattr(
        ProductionConfig,
        "FIREBASE_CREDENTIALS_PATH",
        "test-service-account.json",
    )

    initialized_paths = []

    def mock_initialize_firebase(credentials_path):
        initialized_paths.append(credentials_path)

    monkeypatch.setattr(application, "initialize_firebase", mock_initialize_firebase)
    create_app(ProductionConfig)

    assert initialized_paths == ["test-service-account.json"]


def test_testing_configuration_skips_firebase(monkeypatch):
    import app as application

    def unexpected_firebase_initialization(credentials_path):
        pytest.fail("Firebase should not initialize during automated tests")

    monkeypatch.setattr(
        application,
        "initialize_firebase",
        unexpected_firebase_initialization,
    )
    create_app(TestingConfig)


def test_development_allows_missing_firebase_credentials(monkeypatch):
    import app as application

    initialized_paths = []

    def mock_initialize_firebase(credentials_path):
        initialized_paths.append(credentials_path)
        return None

    monkeypatch.setattr(DevelopmentConfig, "FIREBASE_CREDENTIALS_PATH", None)
    monkeypatch.setattr(application, "initialize_firebase", mock_initialize_firebase)
    create_app(DevelopmentConfig)

    assert initialized_paths == [None]


def test_production_rejects_missing_database_url(monkeypatch):
    monkeypatch.setattr(ProductionConfig, "SQLALCHEMY_DATABASE_URI", None)

    with pytest.raises(RuntimeError, match="DATABASE_URL is required"):
        ProductionConfig.validate_database_config()


def test_production_rejects_sqlite_database(monkeypatch):
    monkeypatch.setattr(
        ProductionConfig,
        "SQLALCHEMY_DATABASE_URI",
        "sqlite:///floodshield.db",
    )

    with pytest.raises(RuntimeError, match="Production requires a PostgreSQL"):
        ProductionConfig.validate_database_config()


def test_production_accepts_postgresql_database(monkeypatch):
    monkeypatch.setattr(
        ProductionConfig,
        "SQLALCHEMY_DATABASE_URI",
        "postgresql://user:password@localhost/floodshield",
    )
    ProductionConfig.validate_database_config()


def test_production_rejects_missing_rate_limit_storage(monkeypatch):
    monkeypatch.setattr(ProductionConfig, "RATELIMIT_STORAGE_URI", None)

    with pytest.raises(RuntimeError, match="RATELIMIT_STORAGE_URI is required"):
        ProductionConfig.validate_rate_limit_config()


def test_production_rejects_memory_rate_limit_storage(monkeypatch):
    monkeypatch.setattr(ProductionConfig, "RATELIMIT_STORAGE_URI", "memory://")

    with pytest.raises(RuntimeError, match="shared rate-limit storage"):
        ProductionConfig.validate_rate_limit_config()


def test_production_accepts_redis_rate_limit_storage(monkeypatch):
    monkeypatch.setattr(
        ProductionConfig,
        "RATELIMIT_STORAGE_URI",
        "redis://localhost:6379/0",
    )
    ProductionConfig.validate_rate_limit_config()


def test_production_rejects_weak_or_reused_signing_secrets(monkeypatch):
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "short")
    monkeypatch.setattr(ProductionConfig, "JWT_SECRET_KEY", "another-short")
    with pytest.raises(RuntimeError, match="at least 32 characters"):
        ProductionConfig.validate_security_config()

    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "c" * 48)
    monkeypatch.setattr(ProductionConfig, "JWT_SECRET_KEY", "c" * 48)
    with pytest.raises(RuntimeError, match="must be different"):
        ProductionConfig.validate_security_config()


def test_production_accepts_separate_strong_signing_secrets(monkeypatch):
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "d" * 48)
    monkeypatch.setattr(ProductionConfig, "JWT_SECRET_KEY", "e" * 48)
    ProductionConfig.validate_security_config()
