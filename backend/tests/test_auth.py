from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException, Request, Response
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.auth import (
    YeuCauDangKy,
    YeuCauDangNhap,
    dang_ky_nguoi_dung,
    dang_nhap,
    kiem_tra_phien,
)
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