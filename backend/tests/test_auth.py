from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.auth import YeuCauDangKy, dang_ky_nguoi_dung
from app.core.security import xac_thuc_mat_khau
from app.models.user import User


def test_dang_ky_thanh_cong(client: TestClient, db_session: Session):
    response = client.post(
        "/register",
        json={
            "email": "User@Example.com",
            "password": "SecurePassword123",
        },
    )
    assert response.status_code == 201
    du_lieu = response.json()
    assert du_lieu["email"] == "user@example.com"
    assert du_lieu["message"] == "Đăng ký thành công"
    assert "id" in du_lieu

    nguoi_dung_trong_db = db_session.scalar(
        select(User).where(User.email == "user@example.com")
    )
    assert nguoi_dung_trong_db is not None
    assert nguoi_dung_trong_db.email == "user@example.com"
    assert nguoi_dung_trong_db.role == "USER"
    assert nguoi_dung_trong_db.password_hash is not None
    assert nguoi_dung_trong_db.password_hash.startswith("$argon2id$")
    assert xac_thuc_mat_khau("SecurePassword123", nguoi_dung_trong_db.password_hash)
    assert nguoi_dung_trong_db.password_hash != "SecurePassword123"


def test_response_khong_chua_password_va_hash(client: TestClient):
    response = client.post(
        "/register",
        json={
            "email": "nopass@example.com",
            "password": "SecretPassword123",
        },
    )
    assert response.status_code == 201
    du_lieu = response.json()
    assert "password" not in du_lieu
    assert "password_hash" not in du_lieu


def test_duplicate_email_tra_ve_409(client: TestClient):
    client.post(
        "/register",
        json={
            "email": "duplicate@example.com",
            "password": "Password123",
        },
    )
    response = client.post(
        "/register",
        json={
            "email": "DUPLICATE@example.com",
            "password": "OtherPassword456",
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Email đã được đăng ký"


def test_email_khong_hop_le(client: TestClient):
    response = client.post(
        "/register",
        json={
            "email": "abc",
            "password": "Password123",
        },
    )
    assert response.status_code == 422


def test_mat_khau_de_trong(client: TestClient):
    response = client.post(
        "/register",
        json={
            "email": "empty_pass@example.com",
            "password": "",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Mật khẩu không được để trống"


def test_mat_khau_chi_chua_khoang_trang(client: TestClient):
    response = client.post(
        "/register",
        json={
            "email": "spaces_pass@example.com",
            "password": "   ",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Mật khẩu không được để trống"


def test_mat_khau_ngan_hon_8_ky_tu(client: TestClient):
    response = client.post(
        "/register",
        json={
            "email": "short_pass@example.com",
            "password": "1234567",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Mật khẩu phải có ít nhất 8 ký tự"


def test_mat_khau_dung_8_ky_tu(client: TestClient):
    response = client.post(
        "/register",
        json={
            "email": "exact_8@example.com",
            "password": "12345678",
        },
    )
    assert response.status_code == 201


def test_thieu_email(client: TestClient):
    response = client.post(
        "/register",
        json={
            "password": "Password123",
        },
    )
    assert response.status_code == 422


def test_thieu_password(client: TestClient):
    response = client.post(
        "/register",
        json={
            "email": "user@example.com",
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

    payload = YeuCauDangKy(email="race@example.com", password="Password123")

    with pytest.raises(HTTPException) as thong_tin_loi:
        dang_ky_nguoi_dung(payload=payload, db=mock_db)

    assert thong_tin_loi.value.status_code == 409
    assert thong_tin_loi.value.detail == "Email đã được đăng ký"
    mock_db.rollback.assert_called_once()


def test_loi_db_o_buoc_query_duplicate_tra_ve_500():
    mock_db = MagicMock(spec=Session)
    mock_db.scalar.side_effect = SQLAlchemyError("Database query connection failed")

    payload = YeuCauDangKy(email="query_err@example.com", password="Password123")

    with pytest.raises(HTTPException) as thong_tin_loi:
        dang_ky_nguoi_dung(payload=payload, db=mock_db)

    assert thong_tin_loi.value.status_code == 500
    assert thong_tin_loi.value.detail == "Lỗi hệ thống khi đăng ký người dùng"
    mock_db.rollback.assert_called_once()


def test_loi_db_o_buoc_ghi_hoac_commit_tra_ve_500_va_rollback():
    mock_db = MagicMock(spec=Session)
    mock_db.scalar.return_value = None
    mock_db.commit.side_effect = SQLAlchemyError("Database commit disk error")

    payload = YeuCauDangKy(email="commit_err@example.com", password="Password123")

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

    payload = YeuCauDangKy(email="no_refresh@example.com", password="Password123")
    ket_qua = dang_ky_nguoi_dung(payload=payload, db=mock_db)

    assert ket_qua.id == 1
    assert ket_qua.email == "no_refresh@example.com"
    assert ket_qua.message == "Đăng ký thành công"
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_not_called()