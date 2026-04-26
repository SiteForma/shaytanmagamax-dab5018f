from __future__ import annotations

from fastapi.testclient import TestClient


def test_current_user_profile_updates_name_and_password(client: TestClient) -> None:
    response = client.patch(
        "/api/auth/me",
        json={
            "first_name": "Сергей",
            "last_name": "Селюк",
            "current_password": "magamax-admin",
            "new_password": "new-secure-password",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["first_name"] == "Сергей"
    assert payload["last_name"] == "Селюк"
    assert payload["full_name"] == "Сергей Селюк"
    assert payload["roles"] == ["admin"]

    login_response = client.post(
        "/api/auth/login",
        json={"email": "admin@magamax.local", "password": "new-secure-password"},
    )
    assert login_response.status_code == 200


def test_current_user_profile_rejects_wrong_current_password(client: TestClient) -> None:
    response = client.patch(
        "/api/auth/me",
        json={
            "first_name": "Администратор",
            "last_name": "MAGAMAX",
            "current_password": "wrong-password",
            "new_password": "new-secure-password",
        },
    )

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_current_password"
