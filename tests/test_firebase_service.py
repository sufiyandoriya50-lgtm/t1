import pytest

from app.services import firebase_service


def test_initialize_firebase_is_optional_without_credentials():
    assert firebase_service.initialize_firebase(None) is None


def test_initialize_firebase_rejects_missing_credentials_file(monkeypatch):
    monkeypatch.setattr(firebase_service.os.path, "isfile", lambda path: False)

    with pytest.raises(FileNotFoundError):
        firebase_service.initialize_firebase("missing-service-account.json")


def test_initialize_firebase_reuses_existing_app(monkeypatch):
    existing_app = object()
    monkeypatch.setattr(firebase_service.os.path, "isfile", lambda path: True)
    monkeypatch.setattr(firebase_service.firebase_admin, "get_app", lambda: existing_app)

    def unexpected_initialization(*args, **kwargs):
        pytest.fail("Firebase should reuse the existing application")

    monkeypatch.setattr(
        firebase_service.firebase_admin,
        "initialize_app",
        unexpected_initialization,
    )

    assert firebase_service.initialize_firebase("test-service-account.json") is existing_app


def test_initialize_firebase_creates_new_app(monkeypatch):
    credentials_object = object()
    firebase_app = object()
    monkeypatch.setattr(firebase_service.os.path, "isfile", lambda path: True)

    def no_existing_app():
        raise ValueError("Firebase app does not exist")

    monkeypatch.setattr(firebase_service.firebase_admin, "get_app", no_existing_app)
    monkeypatch.setattr(
        firebase_service.credentials,
        "Certificate",
        lambda path: credentials_object,
    )

    initialized = []

    def mock_initialize_app(credentials):
        initialized.append(credentials)
        return firebase_app

    monkeypatch.setattr(
        firebase_service.firebase_admin,
        "initialize_app",
        mock_initialize_app,
    )

    assert firebase_service.initialize_firebase("test-service-account.json") is firebase_app
    assert initialized == [credentials_object]
