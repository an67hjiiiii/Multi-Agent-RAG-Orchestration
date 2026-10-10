from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
import pytest
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.auth import (
    YeuCauDangKy,
    YeuCauDangNhap,
    dang_ky_nguoi_dung,
    dang_nhap,
    dang_xuat,
    kiem_tra_phien,
    lay_nguoi_dung_hien_tai,
    router as auth_router,
)
from app.db.database import get_db
from app.core.security import bam_ma_phien, bam_mat_khau, xac_thuc_mat_khau
from app.models.session import PhienDangNhap
from app.models.user import User


def test_dang_ky_thanh_cong(client: TestClient, db_session: Session):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "User@Example.com",
            "name": "Thanh Hai",
            "password": "SecurePassword123",
        },
    )
    assert response.status_code == 201
    du_lieu = response.json()
    assert du_lieu["email"] == "user@example.com"
    assert du_lieu["name"] == "Thanh Hai"
    assert du_lieu["message"] == "Đăng ký thành công"
    assert "id" in du_lieu

    nguoi_dung_trong_db = db_session.scalar(
        select(User).where(User.email == "user@example.com")
    )
    assert nguoi_dung_trong_db is not None
    assert nguoi_dung_trong_db.email == "user@example.com"
    assert nguoi_dung_trong_db.name == "Thanh Hai"
    assert nguoi_dung_trong_db.role == "USER"
    assert nguoi_dung_trong_db.password_hash is not None
    assert nguoi_dung_trong_db.password_hash.startswith("$argon2id$")
    assert xac_thuc_mat_khau("SecurePassword123", nguoi_dung_trong_db.password_hash)
    assert nguoi_dung_trong_db.password_hash != "SecurePassword123"


def test_name_hop_le_va_duoc_luu_dung(client: TestClient, db_session: Session):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "trimmed_name@example.com",
            "name": "   Nguyen Van A   ",
            "password": "Password123",
        },
    )
    assert response.status_code == 201
    du_lieu = response.json()
    assert du_lieu["name"] == "Nguyen Van A"

    nguoi_dung_trong_db = db_session.scalar(
        select(User).where(User.email == "trimmed_name@example.com")
    )
    assert nguoi_dung_trong_db is not None
    assert nguoi_dung_trong_db.name == "Nguyen Van A"


def test_name_de_trong(client: TestClient):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "empty_name@example.com",
            "name": "",
            "password": "Password123",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Họ tên không được để trống"


def test_name_chi_chua_khoang_trang(client: TestClient):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "spaces_name@example.com",
            "name": "   ",
            "password": "Password123",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Họ tên không được để trống"


def test_name_vuot_qua_100_ky_tu(client: TestClient):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "long_name@example.com",
            "name": "a" * 101,
            "password": "Password123",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Họ tên không được vượt quá 100 ký tự"


def test_thieu_name(client: TestClient):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "missing_name@example.com",
            "password": "Password123",
        },
    )
    assert response.status_code == 422


def test_response_khong_chua_password_va_hash(client: TestClient):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "nopass@example.com",
            "name": "No Pass User",
            "password": "SecretPassword123",
        },
    )
    assert response.status_code == 201
    du_lieu = response.json()
    assert "password" not in du_lieu
    assert "password_hash" not in du_lieu
    assert "token" not in du_lieu


def test_duplicate_email_tra_ve_409(client: TestClient):
    client.post(
        "/api/auth/register",
        json={
            "email": "duplicate@example.com",
            "name": "Duplicate User 1",
            "password": "Password123",
        },
    )
    response = client.post(
        "/api/auth/register",
        json={
            "email": "DUPLICATE@example.com",
            "name": "Duplicate User 2",
            "password": "OtherPassword456",
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Email đã được đăng ký"


def test_email_khong_hop_le(client: TestClient):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "abc",
            "name": "Invalid Email User",
            "password": "Password123",
        },
    )
    assert response.status_code == 422


def test_mat_khau_de_trong(client: TestClient):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "empty_pass@example.com",
            "name": "Empty Pass User",
            "password": "",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Mật khẩu không được để trống"


def test_mat_khau_chi_chua_khoang_trang(client: TestClient):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "spaces_pass@example.com",
            "name": "Spaces Pass User",
            "password": "   ",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Mật khẩu không được để trống"


def test_mat_khau_ngan_hon_8_ky_tu(client: TestClient):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "short_pass@example.com",
            "name": "Short Pass User",
            "password": "1234567",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Mật khẩu phải có ít nhất 8 ký tự"


def test_mat_khau_dung_8_ky_tu(client: TestClient):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "exact_8@example.com",
            "name": "Exact Eight User",
            "password": "12345678",
        },
    )
    assert response.status_code == 201


def test_thieu_email(client: TestClient):
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Missing Email User",
            "password": "Password123",
        },
    )
    assert response.status_code == 422


def test_thieu_password(client: TestClient):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "user@example.com",
            "name": "Missing Pass User",
        },
    )
    assert response.status_code == 422


def test_race_condition_integrity_error_tra_ve_409_va_rollback():
    mock_db = MagicMock(spec=Session)
    mock_db.scalar.return_value = None
    mock_db.flush.side_effect = IntegrityError(
        "duplicate key value violates unique constraint",
        params={},
        orig=Exception("duplicate key"),
    )

    payload = YeuCauDangKy(
        email="race@example.com",
        name="Race User",
        password="Password123",
    )

    with pytest.raises(HTTPException) as thong_tin_loi:
        dang_ky_nguoi_dung(payload=payload, db=mock_db)

    assert thong_tin_loi.value.status_code == 409
    assert thong_tin_loi.value.detail == "Email đã được đăng ký"
    mock_db.rollback.assert_called_once()


def test_loi_db_o_buoc_query_duplicate_tra_ve_500():
    mock_db = MagicMock(spec=Session)
    mock_db.scalar.side_effect = SQLAlchemyError("Database query connection failed")

    payload = YeuCauDangKy(
        email="query_err@example.com",
        name="Query User",
        password="Password123",
    )

    with pytest.raises(HTTPException) as thong_tin_loi:
        dang_ky_nguoi_dung(payload=payload, db=mock_db)

    assert thong_tin_loi.value.status_code == 500
    assert thong_tin_loi.value.detail == "Lỗi hệ thống khi đăng ký người dùng"
    mock_db.rollback.assert_called_once()


def test_loi_db_o_buoc_ghi_hoac_commit_tra_ve_500_va_rollback():
    mock_db = MagicMock(spec=Session)
    mock_db.scalar.return_value = None
    mock_db.commit.side_effect = SQLAlchemyError("Database commit disk error")

    payload = YeuCauDangKy(
        email="commit_err@example.com",
        name="Commit User",
        password="Password123",
    )

    with pytest.raises(HTTPException) as thong_tin_loi:
        dang_ky_nguoi_dung(payload=payload, db=mock_db)

    assert thong_tin_loi.value.status_code == 500
    assert thong_tin_loi.value.detail == "Lỗi hệ thống khi đăng ký người dùng"
    mock_db.rollback.assert_called_once()


def test_commit_thanh_cong_khong_goi_refresh():
    mock_db = MagicMock(spec=Session)
    mock_db.scalar.return_value = None

    def mo_phong_flush():
        nguoi_dung_moi = mock_db.add.call_args[0][0]
        nguoi_dung_moi.id = 1

    mock_db.flush.side_effect = mo_phong_flush

    payload = YeuCauDangKy(
        email="no_refresh@example.com",
        name="No Refresh",
        password="Password123",
    )
    ket_qua = dang_ky_nguoi_dung(payload=payload, db=mock_db)

    assert ket_qua.id == 1
    assert ket_qua.email == "no_refresh@example.com"
    assert ket_qua.name == "No Refresh"
    assert ket_qua.message == "Đăng ký thành công"
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_not_called()


# =====================================================================
# US2 — Login & Session Verification Tests
# =====================================================================


def test_login_thanh_cong(client: TestClient, db_session: Session):
    mat_khau_chua_bam = "SecurePassword123"
    nguoi_dung = User(
        email="login_user@example.com",
        name="Thanh Hai",
        password_hash=bam_mat_khau(mat_khau_chua_bam),
        role="USER",
    )
    db_session.add(nguoi_dung)
    db_session.commit()

    response = client.post(
        "/api/auth/login",
        json={
            "email": "login_user@example.com",
            "password": mat_khau_chua_bam,
        },
    )
    assert response.status_code == 200
    du_lieu = response.json()
    assert du_lieu["authenticated"] is True
    assert du_lieu["user"]["id"] == nguoi_dung.id
    assert du_lieu["user"]["email"] == "login_user@example.com"
    assert du_lieu["user"]["name"] == "Thanh Hai"
    assert du_lieu["user"]["role"] == "USER"

    # JSON response khong duoc chua raw token, hash token hoac hash password
    assert "token" not in du_lieu
    assert "capone_session" not in du_lieu
    assert "token_hash" not in du_lieu
    assert "password_hash" not in du_lieu
    assert "password" not in du_lieu["user"]


def test_login_cookie_dung_contract(client: TestClient, db_session: Session):
    nguoi_dung = User(
        email="cookie_user@example.com",
        name="Cookie User",
        password_hash=bam_mat_khau("Password123"),
        role="USER",
    )
    db_session.add(nguoi_dung)
    db_session.commit()

    response = client.post(
        "/api/auth/login",
        json={
            "email": "cookie_user@example.com",
            "password": "Password123",
        },
    )
    assert response.status_code == 200

    set_cookie_header = response.headers.get("set-cookie")
    assert set_cookie_header is not None
    header = set_cookie_header.lower()
    assert "capone_session=" in header
    assert "; httponly" in header
    assert "; samesite=lax" in header
    assert "; path=/" in header
    assert "; max-age=3600" in header
    assert "; secure" not in header


def test_login_database_chi_luu_hash(client: TestClient, db_session: Session):
    nguoi_dung = User(
        email="hash_user@example.com",
        name="Hash User",
        password_hash=bam_mat_khau("Password123"),
        role="USER",
    )
    db_session.add(nguoi_dung)
    db_session.commit()

    response = client.post(
        "/api/auth/login",
        json={
            "email": "hash_user@example.com",
            "password": "Password123",
        },
    )
    assert response.status_code == 200

    raw_token = client.cookies.get("capone_session")
    assert raw_token is not None

    phien_trong_db = db_session.scalar(
        select(PhienDangNhap).where(PhienDangNhap.ma_nguoi_dung == nguoi_dung.id)
    )
    assert phien_trong_db is not None
    assert phien_trong_db.ma_bam_phien == bam_ma_phien(raw_token)
    assert phien_trong_db.ma_bam_phien != raw_token
    assert len(phien_trong_db.ma_bam_phien) == 64


def test_login_sai_mat_khau(client: TestClient, db_session: Session):
    nguoi_dung = User(
        email="wrongpass@example.com",
        name="Wrong Pass User",
        password_hash=bam_mat_khau("Password123"),
        role="USER",
    )
    db_session.add(nguoi_dung)
    db_session.commit()

    response = client.post(
        "/api/auth/login",
        json={
            "email": "wrongpass@example.com",
            "password": "WrongPassword999",
        },
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}
    assert "capone_session" not in client.cookies

    cac_phien = db_session.scalars(select(PhienDangNhap)).all()
    assert len(cac_phien) == 0


def test_login_email_khong_ton_tai(client: TestClient, db_session: Session):
    response = client.post(
        "/api/auth/login",
        json={
            "email": "notfound@example.com",
            "password": "AnyPassword123",
        },
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}
    assert "capone_session" not in client.cookies

    cac_phien = db_session.scalars(select(PhienDangNhap)).all()
    assert len(cac_phien) == 0


def test_login_thieu_email(client: TestClient, db_session: Session):
    response = client.post(
        "/api/auth/login",
        json={"password": "Password123"},
    )
    assert response.status_code == 422
    assert "capone_session" not in client.cookies

    cac_phien = db_session.scalars(select(PhienDangNhap)).all()
    assert len(cac_phien) == 0


def test_login_thieu_password(client: TestClient, db_session: Session):
    response = client.post(
        "/api/auth/login",
        json={"email": "some_user@example.com"},
    )
    assert response.status_code == 422
    assert "capone_session" not in client.cookies

    cac_phien = db_session.scalars(select(PhienDangNhap)).all()
    assert len(cac_phien) == 0


def test_login_email_khong_hop_le(client: TestClient, db_session: Session):
    response = client.post(
        "/api/auth/login",
        json={"email": "invalid-email-format", "password": "Password123"},
    )
    assert response.status_code == 422
    assert "capone_session" not in client.cookies

    cac_phien = db_session.scalars(select(PhienDangNhap)).all()
    assert len(cac_phien) == 0


def test_login_email_duoc_chuan_hoa(client: TestClient, db_session: Session):
    nguoi_dung = User(
        email="normalized_login@example.com",
        name="Normalized User",
        password_hash=bam_mat_khau("Password123"),
        role="USER",
    )
    db_session.add(nguoi_dung)
    db_session.commit()

    response = client.post(
        "/api/auth/login",
        json={
            "email": "  NORMALIZED_LOGIN@Example.COM  ",
            "password": "Password123",
        },
    )
    assert response.status_code == 200
    assert response.json()["authenticated"] is True
    assert response.json()["user"]["email"] == "normalized_login@example.com"


def test_get_session_hop_le(client: TestClient, db_session: Session):
    nguoi_dung = User(
        email="session_user@example.com",
        name="Session User",
        password_hash=bam_mat_khau("Password123"),
        role="USER",
    )
    db_session.add(nguoi_dung)
    db_session.commit()

    login_res = client.post(
        "/api/auth/login",
        json={
            "email": "session_user@example.com",
            "password": "Password123",
        },
    )
    assert login_res.status_code == 200

    response = client.get("/api/auth/session")
    assert response.status_code == 200
    du_lieu = response.json()
    assert du_lieu["authenticated"] is True
    assert du_lieu["user"]["id"] == nguoi_dung.id
    assert du_lieu["user"]["email"] == "session_user@example.com"
    assert du_lieu["user"]["name"] == "Session User"
    assert du_lieu["user"]["role"] == "USER"


def test_get_session_khong_co_cookie(client: TestClient):
    response = client.get("/api/auth/session")
    assert response.status_code == 200
    assert response.json() == {"authenticated": False, "user": None}


def test_get_session_cookie_gia_hoac_token_khong_ton_tai(client: TestClient):
    client.cookies.set("capone_session", "fake_random_token_not_in_database")
    response = client.get("/api/auth/session")
    assert response.status_code == 200
    assert response.json() == {"authenticated": False, "user": None}


def test_get_session_het_han(client: TestClient, db_session: Session):
    nguoi_dung = User(
        email="expired_user@example.com",
        name="Expired User",
        password_hash=bam_mat_khau("Password123"),
        role="USER",
    )
    db_session.add(nguoi_dung)
    db_session.commit()

    raw_token = "expired_test_token"
    thoi_diem_qua_khu = datetime.now(timezone.utc) - timedelta(minutes=10)
    phien_het_han = PhienDangNhap(
        ma_nguoi_dung=nguoi_dung.id,
        ma_bam_phien=bam_ma_phien(raw_token),
        thoi_gian_tao=thoi_diem_qua_khu - timedelta(minutes=60),
        thoi_gian_het_han=thoi_diem_qua_khu,
        thoi_gian_thu_hoi=None,
    )
    db_session.add(phien_het_han)
    db_session.commit()

    client.cookies.set("capone_session", raw_token)
    response = client.get("/api/auth/session")
    assert response.status_code == 200
    assert response.json() == {"authenticated": False, "user": None}


def test_get_session_bi_revoke(client: TestClient, db_session: Session):
    nguoi_dung = User(
        email="revoked_user@example.com",
        name="Revoked User",
        password_hash=bam_mat_khau("Password123"),
        role="USER",
    )
    db_session.add(nguoi_dung)
    db_session.commit()

    raw_token = "revoked_test_token"
    thoi_diem_hien_tai = datetime.now(timezone.utc)
    phien_bi_revoke = PhienDangNhap(
        ma_nguoi_dung=nguoi_dung.id,
        ma_bam_phien=bam_ma_phien(raw_token),
        thoi_gian_tao=thoi_diem_hien_tai - timedelta(minutes=5),
        thoi_gian_het_han=thoi_diem_hien_tai + timedelta(minutes=55),
        thoi_gian_thu_hoi=thoi_diem_hien_tai,
    )
    db_session.add(phien_bi_revoke)
    db_session.commit()

    client.cookies.set("capone_session", raw_token)
    response = client.get("/api/auth/session")
    assert response.status_code == 200
    assert response.json() == {"authenticated": False, "user": None}


def test_login_loi_database_khi_tao_session_rollback_va_500():
    mock_db = MagicMock(spec=Session)
    mock_user = User(
        id=1,
        email="db_err@example.com",
        name="Error User",
        password_hash=bam_mat_khau("Password123"),
        role="USER",
    )
    mock_db.scalar.return_value = mock_user
    mock_db.commit.side_effect = SQLAlchemyError("Database disk failure")

    mock_response = MagicMock(spec=Response)
    payload = YeuCauDangNhap(email="db_err@example.com", password="Password123")

    with pytest.raises(HTTPException) as thong_tin_loi:
        dang_nhap(payload=payload, response=mock_response, db=mock_db)

    assert thong_tin_loi.value.status_code == 500
    assert thong_tin_loi.value.detail == "Lỗi hệ thống khi tạo phiên đăng nhập"
    mock_db.rollback.assert_called_once()
    mock_response.set_cookie.assert_not_called()


def test_get_session_loi_database_rollback_va_500():
    mock_db = MagicMock(spec=Session)
    mock_db.scalar.side_effect = SQLAlchemyError("Database connection lost")
    mock_request = MagicMock(spec=Request)
    mock_request.cookies = {"capone_session": "some_token"}

    with pytest.raises(HTTPException) as thong_tin_loi:
        kiem_tra_phien(request=mock_request, db=mock_db)

    assert thong_tin_loi.value.status_code == 500
    assert thong_tin_loi.value.detail == "Lỗi hệ thống khi kiểm tra phiên đăng nhập"
    mock_db.rollback.assert_called_once()


# =====================================================================
# US3 — Logout & Session Invalidation Tests
# =====================================================================


def test_logout_thanh_cong(client: TestClient, db_session: Session):
    nguoi_dung = User(
        email="logout_success@example.com",
        name="Logout User",
        password_hash=bam_mat_khau("Password123"),
        role="USER",
    )
    db_session.add(nguoi_dung)
    db_session.commit()

    res_login = client.post(
        "/api/auth/login",
        json={"email": "logout_success@example.com", "password": "Password123"},
    )
    assert res_login.status_code == 200

    response = client.post("/api/auth/logout")
    assert response.status_code == 200
    assert response.json() == {"ok": True, "authenticated": False}


def test_logout_cookie_duoc_xoa(client: TestClient, db_session: Session):
    nguoi_dung = User(
        email="cookie_clear@example.com",
        name="Clear Cookie User",
        password_hash=bam_mat_khau("Password123"),
        role="USER",
    )
    db_session.add(nguoi_dung)
    db_session.commit()

    client.post(
        "/api/auth/login",
        json={"email": "cookie_clear@example.com", "password": "Password123"},
    )
    assert "capone_session" in client.cookies

    response = client.post("/api/auth/logout")
    assert response.status_code == 200

    set_cookie_header = response.headers.get("set-cookie")
    assert set_cookie_header is not None
    header = set_cookie_header.lower()
    assert "capone_session=" in header
    assert "path=/" in header
    assert "httponly" in header
    assert "samesite=lax" in header
    assert ("max-age=0" in header) or ("expires=" in header)
    assert client.cookies.get("capone_session") is None


def test_logout_database_da_revoke(client: TestClient, db_session: Session):
    nguoi_dung = User(
        email="db_revoke@example.com",
        name="DB Revoke User",
        password_hash=bam_mat_khau("Password123"),
        role="USER",
    )
    db_session.add(nguoi_dung)
    db_session.commit()

    client.post(
        "/api/auth/login",
        json={"email": "db_revoke@example.com", "password": "Password123"},
    )
    raw_token = client.cookies.get("capone_session")
    assert raw_token is not None
    ma_bam = bam_ma_phien(raw_token)

    response = client.post("/api/auth/logout")
    assert response.status_code == 200

    phien_trong_db = db_session.scalar(
        select(PhienDangNhap).where(PhienDangNhap.ma_bam_phien == ma_bam)
    )
    assert phien_trong_db is not None
    assert phien_trong_db.thoi_gian_thu_hoi is not None
    thoi_gian_thu_hoi = phien_trong_db.thoi_gian_thu_hoi
    if thoi_gian_thu_hoi.tzinfo is None:
        thoi_gian_thu_hoi = thoi_gian_thu_hoi.replace(tzinfo=timezone.utc)
    assert thoi_gian_thu_hoi <= datetime.now(timezone.utc)


def test_sau_logout_token_cu_khong_con_hop_le(client: TestClient, db_session: Session):
    nguoi_dung = User(
        email="reuse_token@example.com",
        name="Reuse Token User",
        password_hash=bam_mat_khau("Password123"),
        role="USER",
    )
    db_session.add(nguoi_dung)
    db_session.commit()

    client.post(
        "/api/auth/login",
        json={"email": "reuse_token@example.com", "password": "Password123"},
    )
    raw_token = client.cookies.get("capone_session")
    assert raw_token is not None

    res_logout = client.post("/api/auth/logout")
    assert res_logout.status_code == 200

    # Co tinh su dung lai token cu da bi logout
    client.cookies.set("capone_session", raw_token)
    res_session = client.get("/api/auth/session")
    assert res_session.status_code == 200
    assert res_session.json() == {"authenticated": False, "user": None}


def test_logout_khong_co_cookie(client: TestClient):
    client.cookies.clear()
    response = client.post("/api/auth/logout")
    assert response.status_code == 200
    assert response.json() == {"ok": True, "authenticated": False}


def test_logout_token_gia(client: TestClient):
    client.cookies.set("capone_session", "fake_nonexistent_token_string_99999")
    response = client.post("/api/auth/logout")
    assert response.status_code == 200
    assert response.json() == {"ok": True, "authenticated": False}


def test_logout_nhieu_lan(client: TestClient, db_session: Session):
    nguoi_dung = User(
        email="multi_logout@example.com",
        name="Multi Logout User",
        password_hash=bam_mat_khau("Password123"),
        role="USER",
    )
    db_session.add(nguoi_dung)
    db_session.commit()

    client.post(
        "/api/auth/login",
        json={"email": "multi_logout@example.com", "password": "Password123"},
    )

    res1 = client.post("/api/auth/logout")
    assert res1.status_code == 200
    assert res1.json() == {"ok": True, "authenticated": False}

    res2 = client.post("/api/auth/logout")
    assert res2.status_code == 200
    assert res2.json() == {"ok": True, "authenticated": False}


def test_logout_phien_da_het_han(client: TestClient, db_session: Session):
    nguoi_dung = User(
        email="expired_logout@example.com",
        name="Expired Logout User",
        password_hash=bam_mat_khau("Password123"),
        role="USER",
    )
    db_session.add(nguoi_dung)
    db_session.commit()

    raw_token = "expired_logout_token_value"
    thoi_diem_qua_khu = datetime.now(timezone.utc) - timedelta(minutes=15)
    phien_het_han = PhienDangNhap(
        ma_nguoi_dung=nguoi_dung.id,
        ma_bam_phien=bam_ma_phien(raw_token),
        thoi_gian_tao=thoi_diem_qua_khu - timedelta(minutes=60),
        thoi_gian_het_han=thoi_diem_qua_khu,
        thoi_gian_thu_hoi=None,
    )
    db_session.add(phien_het_han)
    db_session.commit()

    client.cookies.set("capone_session", raw_token)
    response = client.post("/api/auth/logout")
    assert response.status_code == 200
    assert response.json() == {"ok": True, "authenticated": False}

    db_session.refresh(phien_het_han)
    assert phien_het_han.thoi_gian_thu_hoi is not None


def test_logout_khong_anh_huong_phien_khac(client: TestClient, db_session: Session):
    nguoi_dung = User(
        email="multi_session@example.com",
        name="Multi Session User",
        password_hash=bam_mat_khau("Password123"),
        role="USER",
    )
    db_session.add(nguoi_dung)
    db_session.commit()

    # Dang nhap phien 1
    client.post(
        "/api/auth/login",
        json={"email": "multi_session@example.com", "password": "Password123"},
    )
    token_1 = client.cookies.get("capone_session")
    assert token_1 is not None

    # Dang nhap phien 2
    client.post(
        "/api/auth/login",
        json={"email": "multi_session@example.com", "password": "Password123"},
    )
    token_2 = client.cookies.get("capone_session")
    assert token_2 is not None
    assert token_1 != token_2

    # Logout phien 2 (token_2 dang co trong client)
    res_logout = client.post("/api/auth/logout")
    assert res_logout.status_code == 200
    assert res_logout.json() == {"ok": True, "authenticated": False}

    # Kiem tra DB: phien 2 da revoke, phien 1 chua revoke
    phien_1 = db_session.scalar(
        select(PhienDangNhap).where(PhienDangNhap.ma_bam_phien == bam_ma_phien(token_1))
    )
    phien_2 = db_session.scalar(
        select(PhienDangNhap).where(PhienDangNhap.ma_bam_phien == bam_ma_phien(token_2))
    )
    assert phien_1 is not None
    assert phien_1.thoi_gian_thu_hoi is None
    assert phien_2 is not None
    assert phien_2.thoi_gian_thu_hoi is not None

    # Kiem tra phien 1 van truy cap duoc API session
    client.cookies.set("capone_session", token_1)
    res_session = client.get("/api/auth/session")
    assert res_session.status_code == 200
    du_lieu_session = res_session.json()
    assert du_lieu_session["authenticated"] is True
    assert du_lieu_session["user"]["email"] == "multi_session@example.com"


def test_logout_khong_anh_huong_nguoi_dung_khac(client: TestClient, db_session: Session):
    nguoi_dung_a = User(
        email="user_a@example.com",
        name="User A",
        password_hash=bam_mat_khau("PasswordA123"),
        role="USER",
    )
    nguoi_dung_b = User(
        email="user_b@example.com",
        name="User B",
        password_hash=bam_mat_khau("PasswordB123"),
        role="USER",
    )
    db_session.add_all([nguoi_dung_a, nguoi_dung_b])
    db_session.commit()

    # Dang nhap User A
    client.post(
        "/api/auth/login",
        json={"email": "user_a@example.com", "password": "PasswordA123"},
    )
    token_a = client.cookies.get("capone_session")
    assert token_a is not None

    # Dang nhap User B
    client.post(
        "/api/auth/login",
        json={"email": "user_b@example.com", "password": "PasswordB123"},
    )
    token_b = client.cookies.get("capone_session")
    assert token_b is not None
    assert token_a != token_b

    # Logout User A
    client.cookies.set("capone_session", token_a)
    res_logout_a = client.post("/api/auth/logout")
    assert res_logout_a.status_code == 200
    assert res_logout_a.json() == {"ok": True, "authenticated": False}

    # Kiem tra trong DB: session cua User A bi revoke, session cua User B van hoat dong
    phien_a = db_session.scalar(
        select(PhienDangNhap).where(PhienDangNhap.ma_bam_phien == bam_ma_phien(token_a))
    )
    phien_b = db_session.scalar(
        select(PhienDangNhap).where(PhienDangNhap.ma_bam_phien == bam_ma_phien(token_b))
    )
    assert phien_a is not None
    assert phien_a.thoi_gian_thu_hoi is not None
    assert phien_b is not None
    assert phien_b.thoi_gian_thu_hoi is None

    # Thu dung lai token_a goi /session -> phai bi tu choi
    client.cookies.set("capone_session", token_a)
    res_session_a = client.get("/api/auth/session")
    assert res_session_a.status_code == 200
    assert res_session_a.json() == {"authenticated": False, "user": None}

    # Dung token_b goi /session -> van hop le, tra ve dung thong tin User B
    client.cookies.set("capone_session", token_b)
    res_session_b = client.get("/api/auth/session")
    assert res_session_b.status_code == 200
    du_lieu_b = res_session_b.json()
    assert du_lieu_b["authenticated"] is True
    assert du_lieu_b["user"]["id"] == nguoi_dung_b.id
    assert du_lieu_b["user"]["email"] == "user_b@example.com"


def test_logout_loi_database():
    # Truong hop 1: Loi database o buoc query
    mock_db_query_err = MagicMock(spec=Session)
    mock_db_query_err.scalar.side_effect = SQLAlchemyError("Database query failed")
    mock_request = MagicMock(spec=Request)
    mock_request.cookies = {"capone_session": "any_valid_looking_token"}
    mock_response = MagicMock(spec=Response)

    with pytest.raises(HTTPException) as thong_tin_loi:
        dang_xuat(request=mock_request, response=mock_response, db=mock_db_query_err)

    assert thong_tin_loi.value.status_code == 500
    assert thong_tin_loi.value.detail == "Lỗi hệ thống khi đăng xuất"
    mock_db_query_err.rollback.assert_called_once()
    mock_response.delete_cookie.assert_not_called()

    # Truong hop 2: Loi database o buoc commit
    mock_db_commit_err = MagicMock(spec=Session)
    phien_ton_tai = PhienDangNhap(
        ma_nguoi_dung=1,
        ma_bam_phien=bam_ma_phien("any_valid_looking_token"),
        thoi_gian_tao=datetime.now(timezone.utc),
        thoi_gian_het_han=datetime.now(timezone.utc) + timedelta(minutes=60),
        thoi_gian_thu_hoi=None,
    )
    mock_db_commit_err.scalar.return_value = phien_ton_tai
    mock_db_commit_err.commit.side_effect = SQLAlchemyError("Database commit failure")

    with pytest.raises(HTTPException) as thong_tin_loi_commit:
        dang_xuat(request=mock_request, response=mock_response, db=mock_db_commit_err)

    assert thong_tin_loi_commit.value.status_code == 500
    assert thong_tin_loi_commit.value.detail == "Lỗi hệ thống khi đăng xuất"
    mock_db_commit_err.rollback.assert_called_once()


# =====================================================================
# US4 — Account / Current Session & Protected Dependency Tests
# =====================================================================


def _tao_client_protected(db_session: Session) -> TestClient:
    app_test = FastAPI()
    app_test.include_router(auth_router)

    @app_test.get("/api/test/protected")
    def endpoint_bao_ve(user: User = Depends(lay_nguoi_dung_hien_tai)):
        return {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
        }

    app_test.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app_test)


def test_protected_endpoint_session_hop_le(db_session: Session):
    nguoi_dung = User(
        email="protected_valid@example.com",
        name="Valid User",
        password_hash=bam_mat_khau("Password123"),
        role="USER",
    )
    db_session.add(nguoi_dung)
    db_session.commit()

    client_test = _tao_client_protected(db_session)
    res_login = client_test.post(
        "/api/auth/login",
        json={"email": "protected_valid@example.com", "password": "Password123"},
    )
    assert res_login.status_code == 200

    response = client_test.get("/api/test/protected")
    assert response.status_code == 200
    du_lieu = response.json()
    assert du_lieu["id"] == nguoi_dung.id
    assert du_lieu["email"] == "protected_valid@example.com"
    assert du_lieu["name"] == "Valid User"
    assert du_lieu["role"] == "USER"


def test_protected_endpoint_khong_co_cookie(db_session: Session):
    client_test = _tao_client_protected(db_session)
    response = client_test.get("/api/test/protected")
    assert response.status_code == 401
    assert response.json() == {"detail": "Chưa xác thực hoặc phiên không hợp lệ"}


def test_protected_endpoint_token_gia(db_session: Session):
    client_test = _tao_client_protected(db_session)
    client_test.cookies.set("capone_session", "fake_nonexistent_token_12345")
    response = client_test.get("/api/test/protected")
    assert response.status_code == 401
    assert response.json() == {"detail": "Chưa xác thực hoặc phiên không hợp lệ"}


def test_protected_endpoint_session_het_han(db_session: Session):
    nguoi_dung = User(
        email="protected_expired@example.com",
        name="Expired User",
        password_hash=bam_mat_khau("Password123"),
        role="USER",
    )
    db_session.add(nguoi_dung)
    db_session.commit()

    raw_token = "token_expired_for_protected"
    thoi_diem_qua_khu = datetime.now(timezone.utc) - timedelta(minutes=10)
    phien_het_han = PhienDangNhap(
        ma_nguoi_dung=nguoi_dung.id,
        ma_bam_phien=bam_ma_phien(raw_token),
        thoi_gian_tao=thoi_diem_qua_khu - timedelta(minutes=60),
        thoi_gian_het_han=thoi_diem_qua_khu,
        thoi_gian_thu_hoi=None,
    )
    db_session.add(phien_het_han)
    db_session.commit()

    client_test = _tao_client_protected(db_session)
    client_test.cookies.set("capone_session", raw_token)
    response = client_test.get("/api/test/protected")
    assert response.status_code == 401
    assert response.json() == {"detail": "Chưa xác thực hoặc phiên không hợp lệ"}


def test_protected_endpoint_session_da_revoke(db_session: Session):
    nguoi_dung = User(
        email="protected_revoked@example.com",
        name="Revoked User",
        password_hash=bam_mat_khau("Password123"),
        role="USER",
    )
    db_session.add(nguoi_dung)
    db_session.commit()

    client_test = _tao_client_protected(db_session)
    res_login = client_test.post(
        "/api/auth/login",
        json={"email": "protected_revoked@example.com", "password": "Password123"},
    )
    assert res_login.status_code == 200
    raw_token = client_test.cookies.get("capone_session")
    assert raw_token is not None

    # Logout phien
    res_logout = client_test.post("/api/auth/logout")
    assert res_logout.status_code == 200

    # Co tinh gui lai raw token cu da bi revoke
    client_test.cookies.set("capone_session", raw_token)
    response = client_test.get("/api/test/protected")
    assert response.status_code == 401
    assert response.json() == {"detail": "Chưa xác thực hoặc phiên không hợp lệ"}


def test_protected_endpoint_ngan_chan_cross_user(db_session: Session):
    nguoi_dung_a = User(
        email="user_a_prot@example.com",
        name="User A Prot",
        password_hash=bam_mat_khau("PasswordA123"),
        role="USER",
    )
    nguoi_dung_b = User(
        email="user_b_prot@example.com",
        name="User B Prot",
        password_hash=bam_mat_khau("PasswordB123"),
        role="USER",
    )
    db_session.add_all([nguoi_dung_a, nguoi_dung_b])
    db_session.commit()

    client_a = _tao_client_protected(db_session)
    client_b = _tao_client_protected(db_session)

    # Login User A tren client_a
    res_a = client_a.post(
        "/api/auth/login",
        json={"email": "user_a_prot@example.com", "password": "PasswordA123"},
    )
    assert res_a.status_code == 200
    token_a = client_a.cookies.get("capone_session")

    # Login User B tren client_b
    res_b = client_b.post(
        "/api/auth/login",
        json={"email": "user_b_prot@example.com", "password": "PasswordB123"},
    )
    assert res_b.status_code == 200
    token_b = client_b.cookies.get("capone_session")
    assert token_a != token_b

    # Goi protected endpoint tu client_a -> chi nhan du lieu User A
    prot_res_a = client_a.get("/api/test/protected")
    assert prot_res_a.status_code == 200
    assert prot_res_a.json()["id"] == nguoi_dung_a.id
    assert prot_res_a.json()["email"] == "user_a_prot@example.com"

    # Goi protected endpoint tu client_b -> chi nhan du lieu User B
    prot_res_b = client_b.get("/api/test/protected")
    assert prot_res_b.status_code == 200
    assert prot_res_b.json()["id"] == nguoi_dung_b.id
    assert prot_res_b.json()["email"] == "user_b_prot@example.com"


def test_protected_endpoint_loi_database_rollback_va_500():
    # Kiem tra truc tiep dependency voi mock database
    mock_db = MagicMock(spec=Session)
    mock_db.scalar.side_effect = SQLAlchemyError("Database query failed")
    mock_request = MagicMock(spec=Request)
    mock_request.cookies = {"capone_session": "valid_looking_token"}

    with pytest.raises(HTTPException) as thong_tin_loi:
        lay_nguoi_dung_hien_tai(request=mock_request, db=mock_db)

    assert thong_tin_loi.value.status_code == 500
    assert thong_tin_loi.value.detail == "Lỗi hệ thống khi xác thực phiên"
    mock_db.rollback.assert_called_once()

    # Kiem tra qua HTTP TestClient tren protected endpoint
    mock_db_http = MagicMock(spec=Session)
    mock_db_http.scalar.side_effect = SQLAlchemyError("Database query failed")
    app_test = FastAPI()
    app_test.dependency_overrides[get_db] = lambda: mock_db_http

    @app_test.get("/api/test/protected")
    def endpoint_bao_ve(user: User = Depends(lay_nguoi_dung_hien_tai)):
        return {"id": user.id}

    client_err = TestClient(app_test, raise_server_exceptions=False)
    client_err.cookies.set("capone_session", "some_token")
    res = client_err.get("/api/test/protected")
    assert res.status_code == 500
    assert res.json() == {"detail": "Lỗi hệ thống khi xác thực phiên"}
    mock_db_http.rollback.assert_called_once()


def test_protected_endpoint_khong_anh_huong_api_session_cu(db_session: Session):
    client_test = _tao_client_protected(db_session)

    # API /api/auth/session cu van giu nguyen HTTP 200 va authenticated=false
    res_session = client_test.get("/api/auth/session")
    assert res_session.status_code == 200
    assert res_session.json() == {"authenticated": False, "user": None}

    # Trong khi protected endpoint phai tu choi bang HTTP 401
    res_protected = client_test.get("/api/test/protected")
    assert res_protected.status_code == 401
    assert res_protected.json() == {"detail": "Chưa xác thực hoặc phiên không hợp lệ"}


def test_protected_endpoint_user_khong_ton_tai(db_session: Session):
    raw_token = "token_for_missing_user"
    thoi_diem_hien_tai = datetime.now(timezone.utc)
    phien_orphaned = PhienDangNhap(
        ma_nguoi_dung=99999,
        ma_bam_phien=bam_ma_phien(raw_token),
        thoi_gian_tao=thoi_diem_hien_tai,
        thoi_gian_het_han=thoi_diem_hien_tai + timedelta(minutes=60),
        thoi_gian_thu_hoi=None,
    )
    db_session.add(phien_orphaned)
    db_session.commit()

    client_test = _tao_client_protected(db_session)
    client_test.cookies.set("capone_session", raw_token)
    response = client_test.get("/api/test/protected")
    assert response.status_code == 401
    assert response.json() == {"detail": "Chưa xác thực hoặc phiên không hợp lệ"}
