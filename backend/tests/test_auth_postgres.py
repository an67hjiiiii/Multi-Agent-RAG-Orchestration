from collections.abc import Generator
from datetime import datetime, timedelta, timezone
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.security import bam_ma_phien, bam_mat_khau, xac_thuc_mat_khau
from app.db.database import get_db
from app.main import app
from app.models.session import PhienDangNhap
from app.models.user import User


def lay_url_kiem_thu_an_toan() -> str:
    url_str = os.getenv("TEST_DATABASE_URL")
    if not url_str or not url_str.strip():
        raise RuntimeError("Thieu bien moi truong TEST_DATABASE_URL cho kiem thu PostgreSQL")

    if url_str.startswith("postgresql://"):
        url_str = url_str.replace("postgresql://", "postgresql+psycopg://", 1)

    url_obj = make_url(url_str)
    ten_db = url_obj.database
    host_db = url_obj.host

    if not ten_db or ten_db != "multi_agent_rag_test":
        raise RuntimeError(f"Database khong an toan cho kiem thu: {ten_db}")

    if not host_db or host_db not in ("localhost", "127.0.0.1"):
        raise RuntimeError(f"Host khong hop le cho moi truong kiem thu: {host_db}")

    return url_str


URL_KIEM_THU = lay_url_kiem_thu_an_toan()

postgres_test_engine = create_engine(
    URL_KIEM_THU,
    echo=False,
    pool_pre_ping=True,
)

PostgresTestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=postgres_test_engine,
)


@pytest.fixture
def danh_sach_id() -> list[int]:
    return []


@pytest.fixture
def session_postgres(danh_sach_id: list[int]) -> Generator[Session, None, None]:
    session = PostgresTestingSessionLocal()
    try:
        yield session
    finally:
        try:
            if danh_sach_id:
                session.execute(delete(User).where(User.id.in_(danh_sach_id)))
                session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


@pytest.fixture
def client_postgres(session_postgres: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield session_postgres

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_dang_ky_thanh_cong_tren_postgres(
    client_postgres: TestClient,
    session_postgres: Session,
    danh_sach_id: list[int],
):
    response = client_postgres.post(
        "/api/auth/register",
        json={
            "email": "user_pg@example.com",
            "name": "Nguyen Van PG",
            "password": "Password123",
        },
    )
    assert response.status_code == 201
    du_lieu = response.json()
    danh_sach_id.append(du_lieu["id"])

    assert du_lieu["email"] == "user_pg@example.com"
    assert du_lieu["name"] == "Nguyen Van PG"
    assert du_lieu["message"] == "Đăng ký thành công"
    assert "id" in du_lieu

    nguoi_dung = session_postgres.scalar(
        select(User).where(User.email == "user_pg@example.com")
    )
    assert nguoi_dung is not None
    assert nguoi_dung.id == du_lieu["id"]
    assert nguoi_dung.email == "user_pg@example.com"
    assert nguoi_dung.name == "Nguyen Van PG"
    assert nguoi_dung.role == "USER"


def test_chuan_hoa_email_va_ten_tren_postgres(
    client_postgres: TestClient,
    session_postgres: Session,
    danh_sach_id: list[int],
):
    response = client_postgres.post(
        "/api/auth/register",
        json={
            "email": "  ChUaNhOa@ExAmPlE.CoM  ",
            "name": "   Tran Van Chuan Hoa   ",
            "password": "Password123",
        },
    )
    assert response.status_code == 201
    du_lieu = response.json()
    danh_sach_id.append(du_lieu["id"])

    assert du_lieu["email"] == "chuanhoa@example.com"
    assert du_lieu["name"] == "Tran Van Chuan Hoa"

    nguoi_dung = session_postgres.scalar(
        select(User).where(User.email == "chuanhoa@example.com")
    )
    assert nguoi_dung is not None
    assert nguoi_dung.email == "chuanhoa@example.com"
    assert nguoi_dung.name == "Tran Van Chuan Hoa"


def test_argon2id_va_khong_luu_mat_khau_goc_tren_postgres(
    client_postgres: TestClient,
    session_postgres: Session,
    danh_sach_id: list[int],
):
    mat_khau_goc = "MatKhauBaoMat789"
    response = client_postgres.post(
        "/api/auth/register",
        json={
            "email": "argon2id_pg@example.com",
            "name": "Argon Test User",
            "password": mat_khau_goc,
        },
    )
    assert response.status_code == 201
    du_lieu = response.json()
    danh_sach_id.append(du_lieu["id"])

    nguoi_dung = session_postgres.scalar(
        select(User).where(User.email == "argon2id_pg@example.com")
    )
    assert nguoi_dung is not None
    assert nguoi_dung.password_hash.startswith("$argon2id$")
    assert nguoi_dung.password_hash != mat_khau_goc
    assert xac_thuc_mat_khau(mat_khau_goc, nguoi_dung.password_hash)


def test_duplicate_email_tra_ve_409_tren_postgres(
    client_postgres: TestClient,
    session_postgres: Session,
    danh_sach_id: list[int],
):
    res_dau = client_postgres.post(
        "/api/auth/register",
        json={
            "email": "trung_email@example.com",
            "name": "User Thu Nhat",
            "password": "Password123",
        },
    )
    assert res_dau.status_code == 201
    danh_sach_id.append(res_dau.json()["id"])

    response = client_postgres.post(
        "/api/auth/register",
        json={
            "email": "TRUNG_EMAIL@example.com",
            "name": "User Thu Hai",
            "password": "Password456",
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Email đã được đăng ký"


def test_response_khong_chua_thong_tin_nhay_cam_tren_postgres(
    client_postgres: TestClient,
    session_postgres: Session,
    danh_sach_id: list[int],
):
    response = client_postgres.post(
        "/api/auth/register",
        json={
            "email": "an_toan_pg@example.com",
            "name": "Safe User",
            "password": "Password123",
        },
    )
    assert response.status_code == 201
    du_lieu = response.json()
    danh_sach_id.append(du_lieu["id"])

    assert "password" not in du_lieu
    assert "password_hash" not in du_lieu
    assert "token" not in du_lieu


def test_luu_va_doc_chinh_xac_tren_postgres(
    client_postgres: TestClient,
    session_postgres: Session,
    danh_sach_id: list[int],
):
    danh_sach = [
        {"email": "user1_pg@example.com", "name": "User Mot", "password": "Password123"},
        {"email": "user2_pg@example.com", "name": "User Hai", "password": "Password456"},
    ]
    for item in danh_sach:
        res = client_postgres.post("/api/auth/register", json=item)
        assert res.status_code == 201
        danh_sach_id.append(res.json()["id"])

    danh_sach_db = session_postgres.scalars(
        select(User)
        .where(User.id.in_(danh_sach_id))
        .order_by(User.id)
    ).all()
    assert len(danh_sach_db) == 2
    assert danh_sach_db[0].email == "user1_pg@example.com"
    assert danh_sach_db[0].name == "User Mot"
    assert danh_sach_db[1].email == "user2_pg@example.com"
    assert danh_sach_db[1].name == "User Hai"


# =====================================================================
# US2 — PostgreSQL Integration Tests for Login & Session
# =====================================================================


def test_login_thanh_cong_tren_postgres(
    client_postgres: TestClient,
    session_postgres: Session,
    danh_sach_id: list[int],
):
    mat_khau = "PasswordPg123"
    res_reg = client_postgres.post(
        "/api/auth/register",
        json={
            "email": "login_pg@example.com",
            "name": "Login PG User",
            "password": mat_khau,
        },
    )
    assert res_reg.status_code == 201
    user_id = res_reg.json()["id"]
    danh_sach_id.append(user_id)

    response = client_postgres.post(
        "/api/auth/login",
        json={
            "email": "login_pg@example.com",
            "password": mat_khau,
        },
    )
    assert response.status_code == 200
    du_lieu = response.json()
    assert du_lieu["authenticated"] is True
    assert du_lieu["user"]["id"] == user_id
    assert du_lieu["user"]["email"] == "login_pg@example.com"
    assert "capone_session" in client_postgres.cookies

    # JSON response khong duoc chua raw token, hash token hoac hash password
    assert "token" not in du_lieu
    assert "capone_session" not in du_lieu
    assert "token_hash" not in du_lieu
    assert "password_hash" not in du_lieu
    assert "password" not in du_lieu["user"]


def test_sau_login_postgres_luu_token_hash_va_khong_luu_token_goc(
    client_postgres: TestClient,
    session_postgres: Session,
    danh_sach_id: list[int],
):
    mat_khau = "PasswordPgHash123"
    res_reg = client_postgres.post(
        "/api/auth/register",
        json={
            "email": "hash_pg@example.com",
            "name": "Hash PG User",
            "password": mat_khau,
        },
    )
    assert res_reg.status_code == 201
    user_id = res_reg.json()["id"]
    danh_sach_id.append(user_id)

    response = client_postgres.post(
        "/api/auth/login",
        json={
            "email": "hash_pg@example.com",
            "password": mat_khau,
        },
    )
    assert response.status_code == 200

    raw_token = client_postgres.cookies.get("capone_session")
    assert raw_token is not None

    phien_trong_db = session_postgres.scalar(
        select(PhienDangNhap).where(PhienDangNhap.ma_nguoi_dung == user_id)
    )
    assert phien_trong_db is not None
    assert phien_trong_db.ma_bam_phien == bam_ma_phien(raw_token)
    assert phien_trong_db.ma_bam_phien != raw_token
    assert len(phien_trong_db.ma_bam_phien) == 64


def test_get_session_hop_le_tren_postgres(
    client_postgres: TestClient,
    session_postgres: Session,
    danh_sach_id: list[int],
):
    mat_khau = "PasswordPgSession123"
    res_reg = client_postgres.post(
        "/api/auth/register",
        json={
            "email": "session_valid_pg@example.com",
            "name": "Session Valid PG",
            "password": mat_khau,
        },
    )
    assert res_reg.status_code == 201
    user_id = res_reg.json()["id"]
    danh_sach_id.append(user_id)

    res_login = client_postgres.post(
        "/api/auth/login",
        json={
            "email": "session_valid_pg@example.com",
            "password": mat_khau,
        },
    )
    assert res_login.status_code == 200

    response = client_postgres.get("/api/auth/session")
    assert response.status_code == 200
    du_lieu = response.json()
    assert du_lieu["authenticated"] is True
    assert du_lieu["user"]["id"] == user_id
    assert du_lieu["user"]["email"] == "session_valid_pg@example.com"
    assert du_lieu["user"]["name"] == "Session Valid PG"
    assert du_lieu["user"]["role"] == "USER"


def test_login_sai_password_tren_postgres(
    client_postgres: TestClient,
    session_postgres: Session,
    danh_sach_id: list[int],
):
    mat_khau = "PasswordPgCorrect123"
    res_reg = client_postgres.post(
        "/api/auth/register",
        json={
            "email": "wrong_pass_pg@example.com",
            "name": "Wrong Pass PG",
            "password": mat_khau,
        },
    )
    assert res_reg.status_code == 201
    user_id = res_reg.json()["id"]
    danh_sach_id.append(user_id)

    response = client_postgres.post(
        "/api/auth/login",
        json={
            "email": "wrong_pass_pg@example.com",
            "password": "WrongPassword999",
        },
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}
    assert "capone_session" not in client_postgres.cookies

    phien_trong_db = session_postgres.scalar(
        select(PhienDangNhap).where(PhienDangNhap.ma_nguoi_dung == user_id)
    )
    assert phien_trong_db is None


def test_get_session_het_han_tren_postgres(
    client_postgres: TestClient,
    session_postgres: Session,
    danh_sach_id: list[int],
):
    nguoi_dung = User(
        email="expired_pg@example.com",
        name="Expired PG User",
        password_hash=bam_mat_khau("Password123"),
        role="USER",
    )
    session_postgres.add(nguoi_dung)
    session_postgres.commit()
    danh_sach_id.append(nguoi_dung.id)

    raw_token = "pg_expired_token_test_123"
    thoi_diem_qua_khu = datetime.now(timezone.utc) - timedelta(minutes=10)
    phien_het_han = PhienDangNhap(
        ma_nguoi_dung=nguoi_dung.id,
        ma_bam_phien=bam_ma_phien(raw_token),
        thoi_gian_tao=thoi_diem_qua_khu - timedelta(minutes=60),
        thoi_gian_het_han=thoi_diem_qua_khu,
        thoi_gian_thu_hoi=None,
    )
    session_postgres.add(phien_het_han)
    session_postgres.commit()

    client_postgres.cookies.set("capone_session", raw_token)
    response = client_postgres.get("/api/auth/session")
    assert response.status_code == 200
    assert response.json() == {"authenticated": False, "user": None}


def test_get_session_bi_revoke_tren_postgres(
    client_postgres: TestClient,
    session_postgres: Session,
    danh_sach_id: list[int],
):
    nguoi_dung = User(
        email="revoked_pg@example.com",
        name="Revoked PG User",
        password_hash=bam_mat_khau("Password123"),
        role="USER",
    )
    session_postgres.add(nguoi_dung)
    session_postgres.commit()
    danh_sach_id.append(nguoi_dung.id)

    raw_token = "pg_revoked_token_test_123"
    thoi_diem_hien_tai = datetime.now(timezone.utc)
    phien_bi_revoke = PhienDangNhap(
        ma_nguoi_dung=nguoi_dung.id,
        ma_bam_phien=bam_ma_phien(raw_token),
        thoi_gian_tao=thoi_diem_hien_tai - timedelta(minutes=5),
        thoi_gian_het_han=thoi_diem_hien_tai + timedelta(minutes=55),
        thoi_gian_thu_hoi=thoi_diem_hien_tai,
    )
    session_postgres.add(phien_bi_revoke)
    session_postgres.commit()

    client_postgres.cookies.set("capone_session", raw_token)
    response = client_postgres.get("/api/auth/session")
    assert response.status_code == 200
    assert response.json() == {"authenticated": False, "user": None}
