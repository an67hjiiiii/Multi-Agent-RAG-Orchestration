from fastapi.testclient import TestClient


def test_login_rejects_unknown_email_and_wrong_password_generically(
    client: TestClient,
) -> None:
    registration = client.post(
        "/api/auth/register",
        json={
            "email": "member@example.com",
            "password": "correct-horse-battery",
            "name": "Test Member",
        },
    )
    assert registration.status_code == 201

    wrong_password = client.post(
        "/api/auth/login",
        json={
            "email": "member@example.com",
            "password": "incorrect-password",
        },
    )
    unknown_email = client.post(
        "/api/auth/login",
        json={
            "email": "unknown@example.com",
            "password": "incorrect-password",
        },
    )

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()
    assert wrong_password.json()["detail"] == "Invalid credentials"
    assert "password_hash" not in wrong_password.text + unknown_email.text
