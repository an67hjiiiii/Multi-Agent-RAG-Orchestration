import dataclasses
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.base import Base
from app.models.knowledge import KnowledgeSource
from app.models.user import User
from app.services.ingestion import (
    IngestionError,
    IngestionNotFoundError,
    IngestionSecurityError,
    process_knowledge_source,
)


@pytest.fixture
def test_upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Tạo thư mục uploads an toàn độc lập và thay thế Settings."""
    upload_dir = tmp_path / "uploads_isolated"
    upload_dir.mkdir(parents=True, exist_ok=True)
    new_settings = dataclasses.replace(settings, upload_dir=upload_dir)
    monkeypatch.setattr("app.services.ingestion.settings", new_settings)
    monkeypatch.setattr("app.api.knowledge.settings", new_settings)
    return upload_dir


@pytest.fixture
def sqlite_db_session():
    """Tạo isolated SQLite DB in-memory cho unit/service test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_users(sqlite_db_session):
    """Tạo 2 users để kiểm thử IDOR và cô lập chủ sở hữu."""
    user_a = User(
        email="user_a@example.com",
        name="User A",
        password_hash="fakehashedpasswordA",
    )
    user_b = User(
        email="user_b@example.com",
        name="User B",
        password_hash="fakehashedpasswordB",
    )
    sqlite_db_session.add_all([user_a, user_b])
    sqlite_db_session.commit()
    sqlite_db_session.refresh(user_a)
    sqlite_db_session.refresh(user_b)
    return user_a, user_b


class TestIngestionServiceOwnershipAndSecurity:
    """Kiểm thử bảo mật chủ sở hữu (IDOR) và kiểm soát đường dẫn lưu trữ."""

    def test_user_a_trich_xuat_thanh_cong(
        self, sqlite_db_session, test_users, test_upload_dir: Path
    ):
        user_a, _ = test_users

        # Tạo file thật trên đĩa tuân thủ contract: uploads/<uuid4_hex>.txt
        uuid_hex = "12345678123456781234567812345678"
        file_path = test_upload_dir / f"{uuid_hex}.txt"
        file_path.write_text("Nội dung tài liệu nghiên cứu của User A", encoding="utf-8")

        source = KnowledgeSource(
            owner_id=user_a.id,
            original_filename="nghien_cuu.txt",
            stored_path=f"uploads/{uuid_hex}.txt",
            file_size=len(file_path.read_bytes()),
            mime_type="text/plain",
            status="UPLOADED",
        )
        sqlite_db_session.add(source)
        sqlite_db_session.commit()
        sqlite_db_session.refresh(source)

        result = process_knowledge_source(
            db=sqlite_db_session,
            source_id=source.id,
            trusted_owner_id=user_a.id,
        )

        assert result.source_id == source.id
        assert result.owner_id == user_a.id
        assert result.original_filename == "nghien_cuu.txt"
        assert result.text == "Nội dung tài liệu nghiên cứu của User A"
        assert len(result.segments) == 1
        assert result.segments[0].segment_index == 1

        # Kiểm tra Database State: Phải là EXTRACTED, tuyệt đối KHÔNG ĐƯỢC LÀ READY
        sqlite_db_session.refresh(source)
        assert source.status == "EXTRACTED"
        assert source.status != "READY"

    def test_chong_idor_user_b_khong_the_trich_xuat_tai_lieu_user_a(
        self, sqlite_db_session, test_users, test_upload_dir: Path
    ):
        user_a, user_b = test_users

        uuid_hex = "abcdef12abcdef12abcdef12abcdef12"
        file_path = test_upload_dir / f"{uuid_hex}.txt"
        file_path.write_text("Dữ liệu tuyệt mật của User A", encoding="utf-8")

        source_a = KnowledgeSource(
            owner_id=user_a.id,
            original_filename="tai_lieu_a.txt",
            stored_path=f"uploads/{uuid_hex}.txt",
            file_size=len(file_path.read_bytes()),
            mime_type="text/plain",
            status="UPLOADED",
        )
        sqlite_db_session.add(source_a)
        sqlite_db_session.commit()
        sqlite_db_session.refresh(source_a)

        # User B cố tình gửi yêu cầu trích xuất tài liệu của User A
        with pytest.raises(IngestionNotFoundError, match="Không tìm thấy tài liệu"):
            process_knowledge_source(
                db=sqlite_db_session,
                source_id=source_a.id,
                trusted_owner_id=user_b.id,
            )

        # Trạng thái của User A không hề bị ảnh hưởng hay thay đổi
        sqlite_db_session.refresh(source_a)
        assert source_a.status == "UPLOADED"

    def test_chong_path_traversal_stored_path_bat_thuong(
        self, sqlite_db_session, test_users, test_upload_dir: Path
    ):
        user_a, _ = test_users

        # stored_path chứa directory traversal ../../etc/passwd
        source_malicious = KnowledgeSource(
            owner_id=user_a.id,
            original_filename="evil.txt",
            stored_path="uploads/../../etc/passwd",
            file_size=100,
            mime_type="text/plain",
            status="UPLOADED",
        )
        sqlite_db_session.add(source_malicious)
        sqlite_db_session.commit()
        sqlite_db_session.refresh(source_malicious)

        with pytest.raises(IngestionSecurityError, match="không hợp lệ"):
            process_knowledge_source(
                db=sqlite_db_session,
                source_id=source_malicious.id,
                trusted_owner_id=user_a.id,
            )

        # Source của owner này bị đánh dấu FAILED do đường dẫn không an toàn
        sqlite_db_session.refresh(source_malicious)
        assert source_malicious.status == "FAILED"

    def test_tep_tin_vat_ly_khong_ton_tai_tren_dia(
        self, sqlite_db_session, test_users, test_upload_dir: Path
    ):
        user_a, _ = test_users

        uuid_hex = "99999999999999999999999999999999"
        # Không tạo file trên đĩa
        source_missing = KnowledgeSource(
            owner_id=user_a.id,
            original_filename="missing.txt",
            stored_path=f"uploads/{uuid_hex}.txt",
            file_size=100,
            mime_type="text/plain",
            status="UPLOADED",
        )
        sqlite_db_session.add(source_missing)
        sqlite_db_session.commit()
        sqlite_db_session.refresh(source_missing)

        with pytest.raises(IngestionSecurityError, match="không tồn tại"):
            process_knowledge_source(
                db=sqlite_db_session,
                source_id=source_missing.id,
                trusted_owner_id=user_a.id,
            )

        sqlite_db_session.refresh(source_missing)
        assert source_missing.status == "FAILED"


class TestIngestionLifecycleAndRetry:
    """Kiểm thử vòng đời trạng thái, lỗi và cơ chế retry."""

    def test_trich_xuat_that_bai_chuyen_sang_failed(
        self, sqlite_db_session, test_users, test_upload_dir: Path
    ):
        user_a, _ = test_users

        uuid_hex = "11112222333344445555666677778888"
        corrupt_file = test_upload_dir / f"{uuid_hex}.pdf"
        corrupt_file.write_bytes(b"%PDF-1.4 corrupt content trailer")

        source = KnowledgeSource(
            owner_id=user_a.id,
            original_filename="bad.pdf",
            stored_path=f"uploads/{uuid_hex}.pdf",
            file_size=len(corrupt_file.read_bytes()),
            mime_type="application/pdf",
            status="UPLOADED",
        )
        sqlite_db_session.add(source)
        sqlite_db_session.commit()
        sqlite_db_session.refresh(source)

        with pytest.raises(IngestionError):
            process_knowledge_source(
                db=sqlite_db_session,
                source_id=source.id,
                trusted_owner_id=user_a.id,
            )

        sqlite_db_session.refresh(source)
        assert source.status == "FAILED"

    def test_retry_thanh_cong_sau_khi_sua_tep_nguon(
        self, sqlite_db_session, test_users, test_upload_dir: Path
    ):
        user_a, _ = test_users

        uuid_hex = "22223333444455556666777788889999"
        file_path = test_upload_dir / f"{uuid_hex}.txt"
        file_path.write_bytes(b"")  # Ban đầu file rỗng

        source = KnowledgeSource(
            owner_id=user_a.id,
            original_filename="retry.txt",
            stored_path=f"uploads/{uuid_hex}.txt",
            file_size=0,
            mime_type="text/plain",
            status="UPLOADED",
        )
        sqlite_db_session.add(source)
        sqlite_db_session.commit()

        # Lần 1: Thất bại do file rỗng -> chuyển sang FAILED
        with pytest.raises(IngestionError):
            process_knowledge_source(
                db=sqlite_db_session,
                source_id=source.id,
                trusted_owner_id=user_a.id,
            )
        sqlite_db_session.refresh(source)
        assert source.status == "FAILED"

        # Khắc phục: Ghi nội dung hợp lệ vào file
        file_path.write_text("Nội dung đã được phục hồi thành công.", encoding="utf-8")

        # Lần 2: Retry
        result = process_knowledge_source(
            db=sqlite_db_session,
            source_id=source.id,
            trusted_owner_id=user_a.id,
        )

        assert result.text == "Nội dung đã được phục hồi thành công."
        sqlite_db_session.refresh(source)
        assert source.status == "EXTRACTED"
        assert source.status != "READY"

    def test_tu_choi_symlink_tro_ra_ngoai_storage(
        self, sqlite_db_session, test_users, test_upload_dir: Path, tmp_path: Path
    ):
        user_a, _ = test_users
        outside_file = tmp_path / "secret_outside.txt"
        outside_file.write_text("Dữ liệu nhạy cảm bên ngoài upload dir", encoding="utf-8")

        uuid_hex = "33334444555566667777888899990000"
        symlink_path = test_upload_dir / f"{uuid_hex}.txt"

        try:
            symlink_path.symlink_to(outside_file)
        except (OSError, NotImplementedError):
            pytest.skip("Hệ điều hành hoặc quyền hiện tại không hỗ trợ tạo symlink")

        source = KnowledgeSource(
            owner_id=user_a.id,
            original_filename="symlink.txt",
            stored_path=f"uploads/{uuid_hex}.txt",
            file_size=len(outside_file.read_bytes()),
            mime_type="text/plain",
            status="UPLOADED",
        )
        sqlite_db_session.add(source)
        sqlite_db_session.commit()

        with pytest.raises(IngestionSecurityError, match="symlink"):
            process_knowledge_source(
                db=sqlite_db_session,
                source_id=source.id,
                trusted_owner_id=user_a.id,
            )

        sqlite_db_session.refresh(source)
        assert source.status == "FAILED"

    def test_db_failure_khi_commit_thanh_cong_rollback_an_toan(
        self, sqlite_db_session, test_users, test_upload_dir: Path, monkeypatch
    ):
        user_a, _ = test_users
        uuid_hex = "44445555666677778888999900001111"
        file_path = test_upload_dir / f"{uuid_hex}.txt"
        file_path.write_text("Nội dung tài liệu hợp lệ", encoding="utf-8")

        source = KnowledgeSource(
            owner_id=user_a.id,
            original_filename="doc.txt",
            stored_path=f"uploads/{uuid_hex}.txt",
            file_size=len(file_path.read_bytes()),
            mime_type="text/plain",
            status="UPLOADED",
        )
        sqlite_db_session.add(source)
        sqlite_db_session.commit()

        # Giả lập db.commit() bị lỗi DB bất ngờ khi lưu kết quả EXTRACTED
        original_commit = sqlite_db_session.commit
        commit_calls = 0

        def flaky_commit():
            nonlocal commit_calls
            commit_calls += 1
            if commit_calls == 1:
                from sqlalchemy.exc import OperationalError
                raise OperationalError("database disk error", None, Exception())
            return original_commit()

        monkeypatch.setattr(sqlite_db_session, "commit", flaky_commit)

        # Phải phân biệt rõ ràng: Extraction thành công nhưng DB commit EXTRACTED thất bại
        with pytest.raises(IngestionError) as exc_info:
            process_knowledge_source(
                db=sqlite_db_session,
                source_id=source.id,
                trusted_owner_id=user_a.id,
            )

        assert exc_info.value.code == "EXTRACTION_SUCCESS_DB_FAILED"
        sqlite_db_session.rollback()
        sqlite_db_session.refresh(source)
        # Vì commit lần đầu lỗi, trạng thái không thể là EXTRACTED
        assert source.status != "EXTRACTED"

    def test_tu_choi_trich_xuat_khi_source_dang_ready(
        self, sqlite_db_session, test_users, test_upload_dir: Path
    ):
        """Đảm bảo tài liệu đã READY tuyệt đối không bị hạ trạng thái khi trích xuất lại."""
        user_a, _ = test_users
        uuid_hex = "55556666777788889999000011112222"
        file_path = test_upload_dir / f"{uuid_hex}.txt"
        file_path.write_text("Tài liệu đã index hoàn chỉnh", encoding="utf-8")

        source = KnowledgeSource(
            owner_id=user_a.id,
            original_filename="ready_doc.txt",
            stored_path=f"uploads/{uuid_hex}.txt",
            file_size=len(file_path.read_bytes()),
            mime_type="text/plain",
            status="READY",
        )
        sqlite_db_session.add(source)
        sqlite_db_session.commit()

        with pytest.raises(IngestionError) as exc_info:
            process_knowledge_source(
                db=sqlite_db_session,
                source_id=source.id,
                trusted_owner_id=user_a.id,
            )

        assert exc_info.value.code == "INVALID_STATE"
        sqlite_db_session.refresh(source)
        # Khẳng định trạng thái READY được bảo toàn nguyên vẹn
        assert source.status == "READY"

    def test_trich_xuat_that_bai_va_commit_failed_cung_that_bai(
        self, sqlite_db_session, test_users, test_upload_dir: Path, monkeypatch
    ):
        """Phân biệt an toàn: Extraction failed VÀ việc lưu trạng thái FAILED cũng failed."""
        user_a, _ = test_users
        uuid_hex = "66667777888899990000111122223333"
        corrupt_file = test_upload_dir / f"{uuid_hex}.pdf"
        corrupt_file.write_bytes(b"%PDF-1.4 corrupt content trailer")

        source = KnowledgeSource(
            owner_id=user_a.id,
            original_filename="bad.pdf",
            stored_path=f"uploads/{uuid_hex}.pdf",
            file_size=len(corrupt_file.read_bytes()),
            mime_type="application/pdf",
            status="UPLOADED",
        )
        sqlite_db_session.add(source)
        sqlite_db_session.commit()

        def fail_commit():
            from sqlalchemy.exc import OperationalError
            raise OperationalError("disk full", None, Exception())

        monkeypatch.setattr(sqlite_db_session, "commit", fail_commit)

        with pytest.raises(IngestionError) as exc_info:
            process_knowledge_source(
                db=sqlite_db_session,
                source_id=source.id,
                trusted_owner_id=user_a.id,
            )

        assert exc_info.value.code == "EXTRACTION_FAILED_DB_FAILED"


class TestEndToEndUploadAndExtractionIntegration:
    """
    Kiểm thử tích hợp End-to-End:
    Upload API Sprint 1 -> persisted KnowledgeSource -> file trong test upload dir ->
    internal extraction -> output DTO -> trạng thái EXTRACTED.
    """

    def test_e2e_upload_api_toi_internal_extraction(
        self, client, db_session, test_upload_dir: Path
    ):
        import io
        # Đăng ký và đăng nhập user qua API
        email = "e2e_user@example.com"
        reg_res = client.post(
            "/api/auth/register",
            json={"email": email, "name": "E2E User", "password": "Password123"},
        )
        assert reg_res.status_code == 201
        user_id = reg_res.json()["id"]

        login_res = client.post(
            "/api/auth/login",
            json={"email": email, "password": "Password123"},
        )
        assert login_res.status_code == 200

        # Upload tài liệu qua POST /api/knowledge/upload
        noi_dung = "# Báo cáo Kiến trúc RAG Đa tác tử\n\nNội dung Markdown kỹ thuật.".encode("utf-8")
        upload_res = client.post(
            "/api/knowledge/upload",
            files={"file": ("bao_cao.md", io.BytesIO(noi_dung), "text/markdown")},
        )
        assert upload_res.status_code == 201
        source_id = upload_res.json()["id"]

        # Kiểm tra bản ghi trong DB sau upload
        source_db = db_session.query(KnowledgeSource).filter(KnowledgeSource.id == source_id).first()
        assert source_db is not None
        assert source_db.status == "UPLOADED"
        assert source_db.owner_id == user_id

        # Gọi internal extraction service với trusted owner
        extraction_result = process_knowledge_source(
            db=db_session,
            source_id=source_id,
            trusted_owner_id=user_id,
        )

        # Xác minh kết quả Output DTO
        assert extraction_result.source_id == source_id
        assert extraction_result.owner_id == user_id
        assert extraction_result.original_filename == "bao_cao.md"
        assert "# Báo cáo Kiến trúc RAG Đa tác tử" in extraction_result.text
        assert len(extraction_result.segments) == 1
        assert extraction_result.metadata["has_headings"] is True

        # Xác minh trạng thái DB đã cập nhật thành EXTRACTED (và KHÔNG PHẢI READY)
        db_session.refresh(source_db)
        assert source_db.status == "EXTRACTED"
        assert source_db.status != "READY"

    def test_logging_khong_ro_ri_duong_dan_tuyet_doi_va_noi_dung(
        self, sqlite_db_session, test_users, test_upload_dir: Path, caplog
    ):
        """Xác minh log hệ thống tuyệt đối không chứa raw filepath tuyệt đối hay nội dung tài liệu."""
        import logging
        user_a, _ = test_users
        uuid_hex = "77778888999900001111222233334444"
        sensitive_text = "MAT_KHAU_BAM_CHUOI_BI_MAT_123456"
        file_path = test_upload_dir / f"{uuid_hex}.txt"
        file_path.write_text(sensitive_text, encoding="utf-8")

        source = KnowledgeSource(
            owner_id=user_a.id,
            original_filename="secret.txt",
            stored_path=f"uploads/{uuid_hex}.txt",
            file_size=len(file_path.read_bytes()),
            mime_type="text/plain",
            status="UPLOADED",
        )
        sqlite_db_session.add(source)
        sqlite_db_session.commit()

        with caplog.at_level(logging.WARNING):
            result = process_knowledge_source(
                db=sqlite_db_session,
                source_id=source.id,
                trusted_owner_id=user_a.id,
            )

        log_text = caplog.text
        # Khẳng định nội dung nhạy cảm của tài liệu KHÔNG xuất hiện trong log
        assert sensitive_text not in log_text
        # Khẳng định đường dẫn đĩa vật lý tuyệt đối KHÔNG xuất hiện trong log
        assert str(test_upload_dir) not in log_text
