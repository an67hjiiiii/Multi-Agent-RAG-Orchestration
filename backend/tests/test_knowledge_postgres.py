from collections.abc import Generator
import dataclasses
import io
import os
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, or_, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.database import get_db
from app.main import app
from app.models.knowledge import KnowledgeSource
from app.models.user import User


# ============================================================================
# SAFETY GUARD — BẮT BUỘC TRƯỚC KHI TẠO ENGINE POSTGRESQL
# ============================================================================


def lay_url_kiem_thu_an_toan() -> str:
    url_str = os.getenv("TEST_DATABASE_URL")
    if not url_str or not url_str.strip():
        raise RuntimeError("Thieu bien moi truong TEST_DATABASE_URL cho kiem thu PostgreSQL")

    if url_str.startswith("postgresql://"):
        url_str = url_str.replace("postgresql://", "postgresql+psycopg://", 1)

    url_obj = make_url(url_str)
    ten_db = url_obj.database
    host_db = url_obj.host
    backend_name = url_obj.get_backend_name()

    if backend_name != "postgresql":
        raise RuntimeError(f"Backend khong phai PostgreSQL: {backend_name}")

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


# ============================================================================
# FIXTURES — CÁCH LY THƯ MỤC UPLOAD & QUẢN LÝ DỮ LIỆU TEST AN TOÀN
# ============================================================================


@pytest.fixture(autouse=True)
def override_upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    test_upload_dir = tmp_path / "test_uploads_pg"
    test_upload_dir.mkdir(parents=True, exist_ok=True)
    new_settings = dataclasses.replace(settings, upload_dir=test_upload_dir)
    monkeypatch.setattr("app.api.knowledge.settings", new_settings)
    return test_upload_dir


@pytest.fixture
def danh_sach_user_id() -> list[int]:
    return []


@pytest.fixture
def danh_sach_knowledge_id() -> list[int]:
    return []


@pytest.fixture
def session_postgres(
    danh_sach_user_id: list[int],
    danh_sach_knowledge_id: list[int],
) -> Generator[Session, None, None]:
    """Session độc lập dành riêng cho luồng test thực hiện truy vấn và dọn dẹp dữ liệu."""
    session = PostgresTestingSessionLocal()
    assert session.bind.dialect.name == "postgresql", "Session phai ket noi toi PostgreSQL"
    try:
        yield session
    finally:
        try:
            # Rollback bất kỳ transaction thất bại/chưa hoàn tất nào của test
            session.rollback()

            # 1. Xóa KnowledgeSource trước vì foreign key không có ON DELETE CASCADE
            dieu_kien_xoa = []
            if danh_sach_knowledge_id:
                dieu_kien_xoa.append(KnowledgeSource.id.in_(danh_sach_knowledge_id))
            if danh_sach_user_id:
                dieu_kien_xoa.append(KnowledgeSource.owner_id.in_(danh_sach_user_id))

            if dieu_kien_xoa:
                session.execute(delete(KnowledgeSource).where(or_(*dieu_kien_xoa)))
                session.commit()

            # 2. Xóa User (auth_sessions sẽ tự cascade theo User)
            if danh_sach_user_id:
                session.execute(delete(User).where(User.id.in_(danh_sach_user_id)))
                session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


@pytest.fixture
def client_postgres() -> Generator[TestClient, None, None]:
    """TestClient với session PostgreSQL riêng biệt cho từng HTTP request."""
    def override_get_db() -> Generator[Session, None, None]:
        req_session = PostgresTestingSessionLocal()
        try:
            yield req_session
        finally:
            req_session.close()

    original_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        test_client.close()
        if original_override is not None:
            app.dependency_overrides[get_db] = original_override
        else:
            app.dependency_overrides.pop(get_db, None)


# ============================================================================
# HELPER — ĐĂNG KÝ VÀ ĐĂNG NHẬP USER POSTGRESQL
# ============================================================================


def dang_ky_va_dang_nhap_pg(
    client: TestClient,
    danh_sach_user_id: list[int],
    email: str,
    name: str = "PG Test User",
    password: str = "PasswordPg123",
) -> int:
    reg_res = client.post(
        "/api/auth/register",
        json={"email": email, "name": name, "password": password},
    )
    assert reg_res.status_code == 201, f"Dang ky that bai: {reg_res.text}"
    user_id = reg_res.json()["id"]
    danh_sach_user_id.append(user_id)

    login_res = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200, f"Dang nhap that bai: {login_res.text}"
    assert "capone_session" in client.cookies
    return user_id


# ============================================================================
# PG1 — UPLOAD THẬT VÀO POSTGRESQL (TXT VÀ PDF)
# ============================================================================


def test_pg1_upload_txt_thanh_cong_tren_postgres(
    client_postgres: TestClient,
    session_postgres: Session,
    danh_sach_user_id: list[int],
    danh_sach_knowledge_id: list[int],
    override_upload_dir: Path,
):
    user_id = dang_ky_va_dang_nhap_pg(
        client_postgres,
        danh_sach_user_id,
        f"txt_pg_{uuid4().hex[:8]}@example.com",
    )
    noi_dung = "Nội dung tài liệu PostgreSQL kiểm thử UTF-8 tiếng Việt".encode("utf-8")

    response = client_postgres.post(
        "/api/knowledge/upload",
        files={"file": ("postgres_doc.txt", io.BytesIO(noi_dung), "text/plain")},
    )
    assert response.status_code == 201
    du_lieu = response.json()
    danh_sach_knowledge_id.append(du_lieu["id"])

    # Kiểm tra HTTP response contract
    assert du_lieu["id"] > 0
    assert du_lieu["filename"] == "postgres_doc.txt"
    assert du_lieu["file_size"] == len(noi_dung)
    assert du_lieu["mime_type"] == "text/plain"
    assert du_lieu["status"] == "UPLOADED"
    assert "created_at" in du_lieu

    # Truy vấn trực tiếp từ bảng knowledge_sources trên PostgreSQL bằng session_postgres riêng
    ban_ghi = session_postgres.scalar(
        select(KnowledgeSource).where(KnowledgeSource.id == du_lieu["id"])
    )
    assert ban_ghi is not None
    assert ban_ghi.owner_id == user_id
    assert ban_ghi.original_filename == "postgres_doc.txt"
    assert ban_ghi.file_size == len(noi_dung)
    assert ban_ghi.mime_type == "text/plain"
    assert ban_ghi.status == "UPLOADED"
    assert ban_ghi.created_at is not None
    assert ban_ghi.created_at.tzinfo is not None  # TIMESTAMP WITH TIME ZONE

    # Kiểm tra file vật lý trên đĩa
    file_disk_name = Path(ban_ghi.stored_path).name
    target_file = override_upload_dir / file_disk_name
    assert target_file.exists()
    assert target_file.read_bytes() == noi_dung


def test_pg1_upload_pdf_thanh_cong_tren_postgres(
    client_postgres: TestClient,
    session_postgres: Session,
    danh_sach_user_id: list[int],
    danh_sach_knowledge_id: list[int],
    override_upload_dir: Path,
):
    user_id = dang_ky_va_dang_nhap_pg(
        client_postgres,
        danh_sach_user_id,
        f"pdf_pg_{uuid4().hex[:8]}@example.com",
    )
    noi_dung_pdf = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"

    response = client_postgres.post(
        "/api/knowledge/upload",
        files={"file": ("tech_spec.pdf", io.BytesIO(noi_dung_pdf), "application/pdf")},
    )
    assert response.status_code == 201
    du_lieu = response.json()
    danh_sach_knowledge_id.append(du_lieu["id"])

    assert du_lieu["filename"] == "tech_spec.pdf"
    assert du_lieu["file_size"] == len(noi_dung_pdf)
    assert du_lieu["mime_type"] == "application/pdf"
    assert du_lieu["status"] == "UPLOADED"

    ban_ghi = session_postgres.scalar(
        select(KnowledgeSource).where(KnowledgeSource.id == du_lieu["id"])
    )
    assert ban_ghi is not None
    assert ban_ghi.owner_id == user_id
    assert ban_ghi.mime_type == "application/pdf"
    assert ban_ghi.stored_path.endswith(".pdf")

    file_disk_name = Path(ban_ghi.stored_path).name
    target_file = override_upload_dir / file_disk_name
    assert target_file.exists()
    assert target_file.read_bytes() == noi_dung_pdf


# ============================================================================
# PG2 — OWNER ISOLATION & CHỐNG GIẢ MẠO OWNER
# ============================================================================


def test_pg2_owner_isolation_giua_hai_user_tren_postgres(
    client_postgres: TestClient,
    session_postgres: Session,
    danh_sach_user_id: list[int],
    danh_sach_knowledge_id: list[int],
):
    client_a = client_postgres
    client_b = TestClient(app)
    try:
        user_a_id = dang_ky_va_dang_nhap_pg(
            client_a,
            danh_sach_user_id,
            f"owner_a_{uuid4().hex[:8]}@example.com",
        )
        user_b_id = dang_ky_va_dang_nhap_pg(
            client_b,
            danh_sach_user_id,
            f"owner_b_{uuid4().hex[:8]}@example.com",
        )
        assert user_a_id != user_b_id

        # User A tải lên tài liệu A
        res_a = client_a.post(
            "/api/knowledge/upload",
            files={"file": ("doc_a.txt", io.BytesIO(b"Noi dung cua User A"), "text/plain")},
        )
        assert res_a.status_code == 201
        id_a = res_a.json()["id"]
        danh_sach_knowledge_id.append(id_a)

        # User B tải lên tài liệu B
        res_b = client_b.post(
            "/api/knowledge/upload",
            files={"file": ("doc_b.txt", io.BytesIO(b"Noi dung cua User B"), "text/plain")},
        )
        assert res_b.status_code == 201
        id_b = res_b.json()["id"]
        danh_sach_knowledge_id.append(id_b)

        # Kiểm tra cách ly trong PostgreSQL bằng session_postgres riêng
        doc_a_db = session_postgres.scalar(
            select(KnowledgeSource).where(KnowledgeSource.id == id_a)
        )
        doc_b_db = session_postgres.scalar(
            select(KnowledgeSource).where(KnowledgeSource.id == id_b)
        )
        assert doc_a_db is not None
        assert doc_b_db is not None
        assert doc_a_db.owner_id == user_a_id
        assert doc_b_db.owner_id == user_b_id
        assert doc_a_db.owner_id != doc_b_db.owner_id
    finally:
        client_b.close()


def test_pg2_owner_id_gia_mao_bi_bo_qua_tren_postgres(
    client_postgres: TestClient,
    session_postgres: Session,
    danh_sach_user_id: list[int],
    danh_sach_knowledge_id: list[int],
):
    # Tạo User A (nạn nhân) và User B (kẻ tấn công)
    user_a_id = dang_ky_va_dang_nhap_pg(
        client_postgres,
        danh_sach_user_id,
        f"victim_{uuid4().hex[:8]}@example.com",
    )
    user_b_id = dang_ky_va_dang_nhap_pg(
        client_postgres,
        danh_sach_user_id,
        f"attacker_{uuid4().hex[:8]}@example.com",
    )
    assert user_a_id != user_b_id

    # User B đang login, cố tình truyền owner_id=user_a_id trong form data
    noi_dung = b"Attacker payload attempting to set owner_id to victim"
    response = client_postgres.post(
        "/api/knowledge/upload",
        data={"owner_id": str(user_a_id)},
        files={"file": ("spoof_attempt.txt", io.BytesIO(noi_dung), "text/plain")},
    )
    assert response.status_code == 201
    du_lieu = response.json()
    danh_sach_knowledge_id.append(du_lieu["id"])

    # Bản ghi trong PostgreSQL bắt buộc phải thuộc về User B, không bị chiếm quyền sở hữu
    ban_ghi = session_postgres.scalar(
        select(KnowledgeSource).where(KnowledgeSource.id == du_lieu["id"])
    )
    assert ban_ghi is not None
    assert ban_ghi.owner_id == user_b_id
    assert ban_ghi.owner_id != user_a_id


# ============================================================================
# PG3 — FOREIGN KEY CONSTRAINT (RÀNG BUỘC KHÓA NGOẠI)
# ============================================================================


def test_pg3_foreign_key_owner_id_khong_ton_tai_bi_tu_choi_tren_postgres(
    session_postgres: Session,
):
    # Xác định một ID chắc chắn không tồn tại trong bảng users mà không sửa dữ liệu hiện có
    max_user_id = session_postgres.scalar(select(User.id).order_by(User.id.desc()).limit(1))
    owner_id_khong_ton_tai = (max_user_id or 0) + 1_000_000

    # Chứng minh rõ ràng ID này không tồn tại trong database trước khi kiểm tra
    user_ton_tai = session_postgres.scalar(
        select(User).where(User.id == owner_id_khong_ton_tai)
    )
    assert user_ton_tai is None, f"ID {owner_id_khong_ton_tai} khong duoc phep ton tai truoc khi test"

    # Thử chèn trực tiếp vào PostgreSQL một bản ghi với owner_id không tồn tại
    ban_ghi_sai = KnowledgeSource(
        owner_id=owner_id_khong_ton_tai,
        original_filename="orphan.txt",
        stored_path="uploads/orphan.txt",
        file_size=100,
        mime_type="text/plain",
        status="UPLOADED",
    )

    session_postgres.add(ban_ghi_sai)
    with pytest.raises(IntegrityError) as exc_info:
        session_postgres.commit()

    # Rollback ngay để không để lại giao dịch lỗi trên session
    session_postgres.rollback()

    # Ràng buộc khóa ngoại fk_knowledge_sources_owner_id phải được kích hoạt
    assert "fk_knowledge_sources_owner_id" in str(exc_info.value).lower() or "foreign key" in str(exc_info.value).lower()


# ============================================================================
# PG4 — DATABASE FAILURE & CLEANUP TRÊN POSTGRESQL
# ============================================================================


def test_pg4_loi_db_flush_rollback_va_xoa_file_tren_postgres(
    client_postgres: TestClient,
    session_postgres: Session,
    danh_sach_user_id: list[int],
    override_upload_dir: Path,
):
    dang_ky_va_dang_nhap_pg(
        client_postgres,
        danh_sach_user_id,
        f"db_fail_{uuid4().hex[:8]}@example.com",
    )
    noi_dung = b"Sample text for postgres flush error simulation"

    with patch.object(Session, "flush", side_effect=SQLAlchemyError("PostgreSQL connection error")):
        response = client_postgres.post(
            "/api/knowledge/upload",
            files={"file": ("flush_fail.txt", io.BytesIO(noi_dung), "text/plain")},
        )

    assert response.status_code == 500
    assert "lưu thông tin tài liệu" in response.json()["detail"].lower()

    # File vật lý được dọn dẹp sạch
    assert list(override_upload_dir.iterdir()) == []

    # Database không có bản ghi nào lưu lại
    ban_ghi = session_postgres.scalar(
        select(KnowledgeSource).where(KnowledgeSource.original_filename == "flush_fail.txt")
    )
    assert ban_ghi is None


def test_pg4_loi_db_commit_rollback_va_xoa_file_tren_postgres(
    client_postgres: TestClient,
    session_postgres: Session,
    danh_sach_user_id: list[int],
    override_upload_dir: Path,
):
    dang_ky_va_dang_nhap_pg(
        client_postgres,
        danh_sach_user_id,
        f"commit_fail_{uuid4().hex[:8]}@example.com",
    )
    noi_dung = b"Sample text for postgres commit failure simulation"

    with patch.object(Session, "commit", side_effect=SQLAlchemyError("PostgreSQL commit conflict")):
        response = client_postgres.post(
            "/api/knowledge/upload",
            files={"file": ("commit_fail.txt", io.BytesIO(noi_dung), "text/plain")},
        )

    assert response.status_code == 500
    assert "lưu thông tin tài liệu" in response.json()["detail"].lower()

    # File vật lý được dọn dẹp sạch
    assert list(override_upload_dir.iterdir()) == []

    # Bản ghi bị rollback
    ban_ghi = session_postgres.scalar(
        select(KnowledgeSource).where(KnowledgeSource.original_filename == "commit_fail.txt")
    )
    assert ban_ghi is None


# ============================================================================
# PG5 — ĐỊNH DẠNG MARKDOWN & NGOẠI LỆ BẤT THƯỜNG SAU FLUSH TRÊN POSTGRESQL
# ============================================================================


def test_pg5_upload_markdown_utf8_tren_postgres(
    client_postgres: TestClient,
    session_postgres: Session,
    danh_sach_user_id: list[int],
    danh_sach_knowledge_id: list[int],
    override_upload_dir: Path,
):
    user_id = dang_ky_va_dang_nhap_pg(
        client_postgres,
        danh_sach_user_id,
        f"md_pg_{uuid4().hex[:8]}@example.com",
    )
    noi_dung_md = "# Hướng Dẫn Kỹ Thuật\n\nNội dung Markdown UTF-8 tiếng Việt hợp lệ.".encode("utf-8")

    response = client_postgres.post(
        "/api/knowledge/upload",
        files={"file": ("guide.md", io.BytesIO(noi_dung_md), "text/markdown")},
    )
    assert response.status_code == 201
    du_lieu = response.json()
    danh_sach_knowledge_id.append(du_lieu["id"])

    assert du_lieu["filename"] == "guide.md"
    assert du_lieu["mime_type"] == "text/markdown"
    assert du_lieu["status"] == "UPLOADED"

    ban_ghi = session_postgres.scalar(
        select(KnowledgeSource).where(KnowledgeSource.id == du_lieu["id"])
    )
    assert ban_ghi is not None
    assert ban_ghi.owner_id == user_id
    assert ban_ghi.mime_type == "text/markdown"

    file_disk_name = Path(ban_ghi.stored_path).name
    target_file = override_upload_dir / file_disk_name
    assert target_file.exists()
    assert target_file.read_bytes() == noi_dung_md


def test_pg5_loi_bat_thuong_sau_flush_rollback_va_xoa_file_tren_postgres(
    client_postgres: TestClient,
    session_postgres: Session,
    danh_sach_user_id: list[int],
    override_upload_dir: Path,
):
    dang_ky_va_dang_nhap_pg(
        client_postgres,
        danh_sach_user_id,
        f"abnormal_pg_{uuid4().hex[:8]}@example.com",
    )
    noi_dung = b"Sample text for abnormal exception after flush on postgres"

    with patch("app.api.knowledge.PhanHoiUpload", side_effect=RuntimeError("Response instantiation error")):
        response = client_postgres.post(
            "/api/knowledge/upload",
            files={"file": ("abnormal_pg.txt", io.BytesIO(noi_dung), "text/plain")},
        )

    assert response.status_code == 500
    assert "bất ngờ" in response.json()["detail"].lower()

    # File được dọn dẹp sạch
    assert list(override_upload_dir.iterdir()) == []

    # Database PostgreSQL không lưu lại bản ghi
    ban_ghi = session_postgres.scalar(
        select(KnowledgeSource).where(KnowledgeSource.original_filename == "abnormal_pg.txt")
    )
    assert ban_ghi is None
