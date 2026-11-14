from app import create_app
from app.config import TestingConfig


def test_security_headers_are_added(client):
    response = client.get("/api/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Permissions-Policy" in response.headers


def test_auth_responses_are_not_cached(client):
    response = client.post("/api/auth/login", json={})

    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Pragma"] == "no-cache"


def test_cors_allows_only_explicitly_configured_origins():
    class CorsTestingConfig(TestingConfig):
        CORS_ORIGINS = ["https://citizen.example"]

    app = create_app(CorsTestingConfig)
    with app.test_client() as client:
        allowed = client.get(
            "/api/health",
            headers={"Origin": "https://citizen.example"},
        )
        denied = client.get(
            "/api/health",
            headers={"Origin": "https://untrusted.example"},
        )

    assert allowed.headers.get("Access-Control-Allow-Origin") == "https://citizen.example"
    assert denied.headers.get("Access-Control-Allow-Origin") is None
