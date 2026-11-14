"""Legacy Firebase Authentication endpoints must remain disabled."""


def test_firebase_login_is_retired(client):
    response = client.post(
        "/api/auth/firebase",
        json={"id_token": "legacy-firebase-token"},
    )

    assert response.status_code == 410
    data = response.get_json()
    assert data["status"] == "error"
    assert data["code"] == "FIREBASE_AUTH_RETIRED"


def test_firebase_link_is_retired_even_with_no_token(client):
    response = client.post(
        "/api/auth/firebase/link",
        json={"id_token": "legacy-firebase-token"},
    )

    assert response.status_code == 410
    data = response.get_json()
    assert data["status"] == "error"
    assert data["code"] == "FIREBASE_AUTH_RETIRED"
