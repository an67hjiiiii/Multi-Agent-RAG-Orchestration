from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models.user import User
from app.models.session import PhienDangNhap as AuthSession
from app.core.config import settings
from app.core.security import bam_ma_phien as token_digest
COOKIE_NAME = settings.ten_cookie_phien
def utc_now():
    return datetime.now(timezone.utc)


def test_registration_hashes_password_and_does_not_start_a_session(
    client: TestClient, db_session: Session
) -> None:
    password = "correct-horse-battery"
    response = client.post(
        "/api/auth/register",
        json={
            "email": "member@example.com",
            "password": password,
            "name": "Member One",
        },
    )

    assert response.status_code == 201
    assert set(response.json()) == {"id", "email", "name", "message"}
    assert response.json()["email"] == "member@example.com"
    assert password not in response.text
    assert "password_hash" not in response.text
    assert client.cookies.get(COOKIE_NAME) is None

    user = db_session.scalar(select(User).where(User.email == "member@example.com"))
    assert user is not None
    assert user.password_hash != password
    assert user.password_hash.startswith("$argon2")
    assert db_session.scalar(select(func.count()).select_from(AuthSession)) == 0

    me = client.get("/api/auth/session")
    assert me.status_code == 200
    assert me.json()["authenticated"] is False
    assert me.json()["user"] is None


def test_registration_normalizes_email_and_rejects_case_insensitive_duplicate(
    client: TestClient, db_session: Session
) -> None:
    first = client.post(
        "/api/auth/register",
        json={
            "email": " Member@Example.com ",
            "password": "correct-horse-battery",
            "name": "First Member",
        },
    )
    duplicate = client.post(
        "/api/auth/register",
        json={
            "email": "MEMBER@example.com",
            "password": "another-correct-password",
            "name": "Second Member",
        },
    )

    assert first.status_code == 201
    assert first.json()["email"] == "member@example.com"
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Email đã được đăng ký"
    assert db_session.scalar(select(func.count()).select_from(User)) == 1


@pytest.mark.parametrize(
    "payload, expected_status, expected_detail",
    [
        pytest.param(
            {"email": "invalid-email", "password": "submitted-secret-123", "name": "Member"},
            422,
            "email",
            id="invalid-email",
        ),
        pytest.param(
            {"email": "member@example.com", "password": "short", "name": "Member"},
            400,
            "Mật khẩu phải có ít nhất 8 ký tự",
            id="short-password",
        ),
        pytest.param(
            {"email": "member@example.com", "password": "submitted-secret-123", "name": "   "},
            400,
            "Họ tên không được để trống",
            id="blank-name",
        ),
        pytest.param(
            {
                "email": "member@example.com",
                "password": "submitted-secret-123",
                "name": "Member",
                "unexpected": "submitted-secret-123",
            },
            422,
            "extra_forbidden",
            id="unexpected-field",
            marks=pytest.mark.xfail(
                strict=True,
                reason="CONTRACT_NEEDS_CONFIRMATION: extra fields currently ignored on dev",
            ),
        ),
    ],
)
def test_registration_validation_is_sanitized(
    client: TestClient,
    payload: dict[str, str],
    expected_status: int,
    expected_detail: str,
) -> None:
    response = client.post("/api/auth/register", json=payload)

    assert response.status_code == expected_status
    detail = response.json()["detail"]

    if expected_status == 400:
        assert detail == expected_detail
    else:
        assert isinstance(detail, list)
        assert any(
            expected_detail in str(item.get("loc", ()))
            if expected_detail == "email"
            else item.get("type") == expected_detail
            for item in detail
        )

    assert "submitted-secret-123" not in response.text
    assert "password_hash" not in response.text






def test_expired_session_is_rejected(client: TestClient, register_user, db_session: Session) -> None:
    user = register_user(client)
    login = client.post(
        "/api/auth/login",
        json={"email": "member@example.com", "password": "correct-horse-battery"},
    )
    assert login.status_code == 200

    stored_session = db_session.scalar(
        select(AuthSession).where(AuthSession.ma_nguoi_dung == user["id"])
    )
    assert stored_session is not None
    stored_session.thoi_gian_het_han = utc_now() - timedelta(seconds=1)
    db_session.commit()

    response = client.get("/api/auth/session")
    assert response.status_code == 200
    assert response.json()["authenticated"] is False
    assert response.json()["user"] is None


def test_logout_revokes_session_and_clears_cookie(
    client: TestClient, register_user, db_session: Session
) -> None:
    user = register_user(client)
    login = client.post(
        "/api/auth/login",
        json={"email": "member@example.com", "password": "correct-horse-battery"},
    )
    assert login.status_code == 200
    raw_token = client.cookies.get(COOKIE_NAME)
    assert raw_token

    response = client.post("/api/auth/logout")

    assert response.status_code == 200
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert COOKIE_NAME not in client.cookies
    stored_session = db_session.scalar(
        select(AuthSession).where(AuthSession.ma_nguoi_dung == user["id"])
    )
    assert stored_session is not None
    assert stored_session.thoi_gian_thu_hoi is not None
    assert stored_session.ma_bam_phien == token_digest(raw_token)
    assert client.get("/api/auth/session").json() == {"authenticated": False, "user": None}















@pytest.fixture
def register_user():
    def register(client, email='member@example.com', password='correct-horse-battery', display_name='Test Member'):
        response = client.post('/api/auth/register', json={'email': email, 'password': password, 'name': display_name})
        assert response.status_code == 201
        return response.json()
    return register
