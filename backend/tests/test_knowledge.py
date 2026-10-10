import codecs
import dataclasses
import io
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.knowledge import KnowledgeSource
from app.models.user import User


@pytest.fixture(autouse=True)
def override_upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    test_upload_dir = tmp_path / "test_uploads"
    test_upload_dir.mkdir(parents=True, exist_ok=True)
    new_settings = dataclasses.replace(settings, upload_dir=test_upload_dir)
    monkeypatch.setattr("app.api.knowledge.settings", new_settings)
    return test_upload_dir


def dang_ky_va_dang_nhap(
    client: TestClient,
    email: str = "user@example.com",
    name: str = "Test User",
    password: str = "Password123",
) -> int:
    reg_res = client.post(
        "/api/auth/register",
        json={"email": email, "name": name, "password": password},
    )
    assert reg_res.status_code == 201
    user_id = reg_res.json()["id"]

    login_res = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200
    assert "capone_session" in client.cookies
    return user_id


# ============================================================================
# NHÓM A — UPLOAD THÀNH CÔNG
# ============================================================================


def test_a1_upload_txt_utf8_thanh_cong(
    client: TestClient, db_session: Session, override_upload_dir: Path
):
    user_id = dang_ky_va_dang_nhap(client, "txt_user@example.com")
    noi_dung = "Nội dung tài liệu kỹ thuật kiểm thử tiếng Việt UTF-8".encode("utf-8")

    response = client.post(
        "/api/knowledge/upload",
        files={"file": ("tailieu.txt", io.BytesIO(noi_dung), "text/plain")},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "tailieu.txt"
    assert data["file_size"] == len(noi_dung)
    assert data["mime_type"] == "text/plain"
    assert data["status"] == "UPLOADED"
    assert "created_at" in data
    assert "id" in data

    # Database kiểm tra
    ban_ghi = db_session.scalar(
        select(KnowledgeSource).where(KnowledgeSource.id == data["id"])
    )
    assert ban_ghi is not None
    assert ban_ghi.owner_id == user_id
    assert ban_ghi.original_filename == "tailieu.txt"
    assert ban_ghi.file_size == len(noi_dung)
    assert ban_ghi.mime_type == "text/plain"
    assert ban_ghi.status == "UPLOADED"

    # Kiểm tra file vật lý trên đĩa
    file_tren_dia = override_upload_dir / Path(ban_ghi.stored_path).name
    assert file_tren_dia.exists()
    assert file_tren_dia.read_bytes() == noi_dung


def test_a2_upload_md_thanh_cong(client: TestClient, db_session: Session):
    user_id = dang_ky_va_dang_nhap(client, "md_user@example.com")
    noi_dung = b"# Tieu De Markdown\n\nNoi dung mo ta chi tiet."

    response = client.post(
        "/api/knowledge/upload",
        files={"file": ("huong_dan.md", io.BytesIO(noi_dung), "text/markdown")},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "huong_dan.md"
    assert data["mime_type"] == "text/markdown"
    assert data["file_size"] == len(noi_dung)

    ban_ghi = db_session.scalar(
        select(KnowledgeSource).where(KnowledgeSource.id == data["id"])
    )
    assert ban_ghi is not None
    assert ban_ghi.owner_id == user_id
    assert ban_ghi.mime_type == "text/markdown"


def test_a3_upload_pdf_thanh_cong(client: TestClient, db_session: Session):
    user_id = dang_ky_va_dang_nhap(client, "pdf_user@example.com")
    noi_dung = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"

    response = client.post(
        "/api/knowledge/upload",
        files={"file": ("sample.pdf", io.BytesIO(noi_dung), "application/pdf")},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "sample.pdf"
    assert data["mime_type"] == "application/pdf"
    assert data["file_size"] == len(noi_dung)

    ban_ghi = db_session.scalar(
        select(KnowledgeSource).where(KnowledgeSource.id == data["id"])
    )
    assert ban_ghi is not None
    assert ban_ghi.owner_id == user_id
    assert ban_ghi.mime_type == "application/pdf"


def test_a4_response_khong_lam_lo_thong_tin_nhay_cam(client: TestClient):
    dang_ky_va_dang_nhap(client, "leak_user@example.com")
    noi_dung = b"Safe content without path leaks"

    response = client.post(
        "/api/knowledge/upload",
        files={"file": ("safe.txt", io.BytesIO(noi_dung), "text/plain")},
    )

    assert response.status_code == 201
    data = response.json()
    assert set(data.keys()) == {
        "id",
        "filename",
        "file_size",
        "mime_type",
        "status",
        "created_at",
    }
    assert "stored_path" not in data
    assert "file_path" not in data
    assert "password" not in data
    assert "token" not in data
    assert "capone_session" not in data


# ============================================================================
# NHÓM B — AUTHENTICATION VÀ OWNERSHIP
# ============================================================================


def test_b1_upload_chua_dang_nhap_bi_tu_choi_401(
    client: TestClient, db_session: Session, override_upload_dir: Path
):
    client.cookies.clear()
    noi_dung = b"Sample unauthenticated text"

    response = client.post(
        "/api/knowledge/upload",
        files={"file": ("unauth.txt", io.BytesIO(noi_dung), "text/plain")},
    )

    assert response.status_code == 401
    assert db_session.scalar(select(KnowledgeSource)) is None
    assert list(override_upload_dir.iterdir()) == []


def test_b2_upload_session_khong_hop_le_hoac_da_logout_401(client: TestClient):
    # Cookie giả không tồn tại trong DB
    client.cookies.set("capone_session", "fake_non_existent_token_string")
    response = client.post(
        "/api/knowledge/upload",
        files={"file": ("fake.txt", io.BytesIO(b"data"), "text/plain")},
    )
    assert response.status_code == 401

    # Xóa cookie giả trước khi đăng nhập hợp lệ
    client.cookies.clear()

    # Đăng nhập hợp lệ rồi đăng xuất
    dang_ky_va_dang_nhap(client, "logout_user@example.com")
    logout_res = client.post("/api/auth/logout")
    assert logout_res.status_code == 200

    response_after_logout = client.post(
        "/api/knowledge/upload",
        files={"file": ("after_logout.txt", io.BytesIO(b"data"), "text/plain")},
    )
    assert response_after_logout.status_code == 401


def test_b3_ownership_cach_ly_giua_hai_user_va_khong_cho_gia_mao(
    client: TestClient, db_session: Session
):
    client_a = client
    user_a_id = dang_ky_va_dang_nhap(client_a, "user_a@example.com")

    res_a = client_a.post(
        "/api/knowledge/upload",
        files={"file": ("doc_a.txt", io.BytesIO(b"User A doc"), "text/plain")},
    )
    assert res_a.status_code == 201
    doc_a_id = res_a.json()["id"]

    # Đăng ký và đăng nhập User B (dùng lại client sau khi xóa cookie)
    client.cookies.clear()
    user_b_id = dang_ky_va_dang_nhap(client, "user_b@example.com")

    # User B cố tình gửi form field owner_id giả mạo
    res_b = client.post(
        "/api/knowledge/upload",
        files={"file": ("doc_b.txt", io.BytesIO(b"User B doc"), "text/plain")},
        data={"owner_id": str(user_a_id)},
    )
    assert res_b.status_code == 201
    doc_b_id = res_b.json()["id"]

    ban_ghi_a = db_session.scalar(
        select(KnowledgeSource).where(KnowledgeSource.id == doc_a_id)
    )
    ban_ghi_b = db_session.scalar(
        select(KnowledgeSource).where(KnowledgeSource.id == doc_b_id)
    )

    assert ban_ghi_a is not None and ban_ghi_b is not None
    assert ban_ghi_a.owner_id == user_a_id
    assert ban_ghi_b.owner_id == user_b_id
    assert ban_ghi_b.owner_id != user_a_id


# ============================================================================
# NHÓM C — FILE VALIDATION
# ============================================================================


def test_c1_file_rong_bi_tu_choi_400(client: TestClient):
    dang_ky_va_dang_nhap(client, "empty_file@example.com")

    response = client.post(
        "/api/knowledge/upload",
        files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
    )
    assert response.status_code == 400
    assert "rỗng" in response.json()["detail"].lower()


def test_c2_extension_khong_ho_tro_bi_tu_choi_400(client: TestClient):
    dang_ky_va_dang_nhap(client, "bad_ext@example.com")

    for bad_name in ["script.py", "program.exe", "data.json", "archive.zip"]:
        response = client.post(
            "/api/knowledge/upload",
            files={"file": (bad_name, io.BytesIO(b"content"), "application/octet-stream")},
        )
        assert response.status_code == 400
        assert "không được hỗ trợ" in response.json()["detail"].lower()


def test_c3_pdf_gia_mao_khong_co_signature_400(client: TestClient):
    dang_ky_va_dang_nhap(client, "fake_pdf@example.com")

    response = client.post(
        "/api/knowledge/upload",
        files={"file": ("fake.pdf", io.BytesIO(b"This is just plain text not pdf"), "application/pdf")},
    )
    assert response.status_code == 400
    assert "pdf không hợp lệ" in response.json()["detail"].lower()


def test_c4_txt_md_chua_byte_nul_bi_tu_choi_400(client: TestClient):
    dang_ky_va_dang_nhap(client, "nul_byte@example.com")

    # TXT chứa NUL
    response_txt = client.post(
        "/api/knowledge/upload",
        files={"file": ("test.txt", io.BytesIO(b"Hello\x00World"), "text/plain")},
    )
    assert response_txt.status_code == 400
    assert "không hợp lệ" in response_txt.json()["detail"].lower()

    # MD chứa NUL
    response_md = client.post(
        "/api/knowledge/upload",
        files={"file": ("test.md", io.BytesIO(b"# Doc\x00ument"), "text/markdown")},
    )
    assert response_md.status_code == 400


def test_c5_utf8_khong_hop_le_bi_tu_choi_400(client: TestClient):
    dang_ky_va_dang_nhap(client, "invalid_utf8@example.com")

    # Byte không hợp lệ trong UTF-8 (không chứa byte NUL \x00 để kiểm tra đúng nhánh UTF-8 decoder)
    invalid_utf8_bytes = b"\xff\xfe\x80\x81"
    response = client.post(
        "/api/knowledge/upload",
        files={"file": ("invalid.txt", io.BytesIO(invalid_utf8_bytes), "text/plain")},
    )
    assert response.status_code == 400
    assert "utf-8" in response.json()["detail"].lower()


def test_c6_thieu_multipart_field_file_bi_tu_choi_422(client: TestClient):
    dang_ky_va_dang_nhap(client, "missing_field@example.com")

    response = client.post(
        "/api/knowledge/upload",
        data={"wrong_field": "some data"},
    )
    assert response.status_code == 422


def test_c7_filename_rong_hoac_khong_hop_le_bi_tu_choi_400(client: TestClient):
    dang_ky_va_dang_nhap(client, "empty_fname@example.com")

    # Tên rỗng: client transport TestClient có thể coi "" là thiếu file (422) hoặc endpoint từ chối (400)
    res_empty = client.post(
        "/api/knowledge/upload",
        files={"file": ("", io.BytesIO(b"content"), "text/plain")},
    )
    assert res_empty.status_code in (400, 422)

    # Tên chỉ có khoảng trắng -> _chuan_hoa_ten_file từ chối 400
    res_spaces = client.post(
        "/api/knowledge/upload",
        files={"file": ("   ", io.BytesIO(b"content"), "text/plain")},
    )
    assert res_spaces.status_code == 400
    assert "không hợp lệ" in res_spaces.json()["detail"].lower()

    # Tên quá dài (> 255 ký tự) -> _chuan_hoa_ten_file từ chối 400
    too_long_name = ("a" * 255) + ".txt"
    res_long = client.post(
        "/api/knowledge/upload",
        files={"file": (too_long_name, io.BytesIO(b"content"), "text/plain")},
    )
    assert res_long.status_code == 400
    assert "255" in res_long.json()["detail"]

    # Kiểm tra trực tiếp hàm chuẩn hóa từ chối ký tự điều khiển
    from app.api.knowledge import _chuan_hoa_ten_file
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        _chuan_hoa_ten_file("test\x01file.txt")
    assert exc_info.value.status_code == 400
    assert "ký tự điều khiển" in exc_info.value.detail.lower()


def test_c8_filename_path_traversal_duoc_xu_ly_an_toan(
    client: TestClient, db_session: Session, override_upload_dir: Path
):
    dang_ky_va_dang_nhap(client, "traversal@example.com")
    noi_dung = b"Content inside safe isolated path"

    # Gửi đường dẫn traversal nguy hiểm
    response = client.post(
        "/api/knowledge/upload",
        files={"file": ("../../../../etc/passwd.txt", io.BytesIO(noi_dung), "text/plain")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "passwd.txt"

    ban_ghi = db_session.scalar(
        select(KnowledgeSource).where(KnowledgeSource.id == data["id"])
    )
    assert ban_ghi is not None
    assert ban_ghi.original_filename == "passwd.txt"

    # File nằm hoàn toàn trong thư mục override_upload_dir
    stored_file = override_upload_dir / Path(ban_ghi.stored_path).name
    assert stored_file.exists()
    assert stored_file.parent == override_upload_dir


def test_c9_extension_uppercase_duoc_xu_ly_nhat_quan(client: TestClient):
    dang_ky_va_dang_nhap(client, "upper_ext@example.com")

    # PDF chữ hoa
    res_pdf = client.post(
        "/api/knowledge/upload",
        files={"file": ("REPORT.PDF", io.BytesIO(b"%PDF-1.4\ncontent"), "application/pdf")},
    )
    assert res_pdf.status_code == 201
    assert res_pdf.json()["mime_type"] == "application/pdf"

    # TXT chữ hoa
    res_txt = client.post(
        "/api/knowledge/upload",
        files={"file": ("NOTES.TXT", io.BytesIO(b"plain notes"), "text/plain")},
    )
    assert res_txt.status_code == 201
    assert res_txt.json()["mime_type"] == "text/plain"


# ============================================================================
# NHÓM D — SIZE LIMIT VÀ STREAMING
# ============================================================================


def test_d1_file_dung_10_mib_thanh_cong(client: TestClient):
    dang_ky_va_dang_nhap(client, "exact_10mb@example.com")
    size_10mib = 10 * 1024 * 1024
    header = b"%PDF-"
    noi_dung = header + (b"A" * (size_10mib - len(header)))
    assert len(noi_dung) == size_10mib

    response = client.post(
        "/api/knowledge/upload",
        files={"file": ("large_10mb.pdf", io.BytesIO(noi_dung), "application/pdf")},
    )
    assert response.status_code == 201
    assert response.json()["file_size"] == size_10mib


def test_d2_file_10_mib_cong_1_byte_bi_tu_choi_413(client: TestClient):
    dang_ky_va_dang_nhap(client, "exceed_1byte@example.com")
    size_exceeded = (10 * 1024 * 1024) + 1
    header = b"%PDF-"
    noi_dung = header + (b"A" * (size_exceeded - len(header)))

    response = client.post(
        "/api/knowledge/upload",
        files={"file": ("large_10mb_plus_1.pdf", io.BytesIO(noi_dung), "application/pdf")},
    )
    assert response.status_code == 413
    assert "vượt quá giới hạn 10mb" in response.json()["detail"].lower()


def test_d3_file_vuot_gioi_han_khong_de_lai_file_mo_coi(
    client: TestClient, override_upload_dir: Path
):
    dang_ky_va_dang_nhap(client, "cleanup_exceed@example.com")
    noi_dung = b"%PDF-" + (b"X" * (11 * 1024 * 1024))  # 11 MiB

    response = client.post(
        "/api/knowledge/upload",
        files={"file": ("too_large.pdf", io.BytesIO(noi_dung), "application/pdf")},
    )
    assert response.status_code == 413
    # Thư mục lưu không còn bất kỳ file ghi dở nào
    assert list(override_upload_dir.iterdir()) == []


def test_d4_utf8_multibyte_cat_tai_ranh_gioi_chunk_decode_chinh_xac(
    client: TestClient,
):
    dang_ky_va_dang_nhap(client, "multibyte@example.com")
    # Chunk size là 64 KiB = 65536 bytes.
    # Ký tự emoji 4 bytes '🌟' (b'\xf0\x9f\x8c\x9f') đặt bắt đầu tại byte 65535,
    # ranh giới chunk sẽ cắt giữa byte đầu và 3 byte còn lại.
    emoji_bytes = "🌟".encode("utf-8")
    assert len(emoji_bytes) == 4

    padding = b"A" * 65535
    noi_dung = padding + emoji_bytes + b"Tail content"

    response = client.post(
        "/api/knowledge/upload",
        files={"file": ("split_multibyte.txt", io.BytesIO(noi_dung), "text/plain")},
    )
    assert response.status_code == 201
    assert response.json()["file_size"] == len(noi_dung)


# ============================================================================
# NHÓM E — ERROR HANDLING / CLEANUP
# ============================================================================


def test_e1_db_flush_loi_rollback_va_cleanup_file(
    client: TestClient, db_session: Session, override_upload_dir: Path
):
    dang_ky_va_dang_nhap(client, "flush_error@example.com")
    noi_dung = b"Sample text for flush error test"

    with patch.object(Session, "flush", side_effect=SQLAlchemyError("Simulated flush error")):
        response = client.post(
            "/api/knowledge/upload",
            files={"file": ("flush_fail.txt", io.BytesIO(noi_dung), "text/plain")},
        )

    assert response.status_code == 500
    assert "lưu thông tin tài liệu" in response.json()["detail"].lower()
    # File vật lý được dọn sạch
    assert list(override_upload_dir.iterdir()) == []
    # DB không có bản ghi
    assert db_session.scalar(
        select(KnowledgeSource).where(KnowledgeSource.original_filename == "flush_fail.txt")
    ) is None


def test_e2_db_commit_loi_rollback_va_cleanup_file(
    client: TestClient, db_session: Session, override_upload_dir: Path
):
    dang_ky_va_dang_nhap(client, "commit_error@example.com")
    noi_dung = b"Sample text for commit error test"

    with patch.object(Session, "commit", side_effect=SQLAlchemyError("Simulated commit error")):
        response = client.post(
            "/api/knowledge/upload",
            files={"file": ("commit_fail.txt", io.BytesIO(noi_dung), "text/plain")},
        )

    assert response.status_code == 500
    assert "lưu thông tin tài liệu" in response.json()["detail"].lower()
    # File vật lý được dọn sạch
    assert list(override_upload_dir.iterdir()) == []
    # DB không có bản ghi
    assert db_session.scalar(
        select(KnowledgeSource).where(KnowledgeSource.original_filename == "commit_fail.txt")
    ) is None


def test_e3_loi_ghi_file_tra_ve_500_va_khong_de_lai_file(
    client: TestClient, db_session: Session, override_upload_dir: Path
):
    dang_ky_va_dang_nhap(client, "disk_error@example.com")
    noi_dung = b"Sample text for disk error test"

    # Giả lập lỗi ghi đĩa OSError
    with patch("builtins.open", side_effect=OSError("Disk full or permission denied")):
        response = client.post(
            "/api/knowledge/upload",
            files={"file": ("disk_fail.txt", io.BytesIO(noi_dung), "text/plain")},
        )

    assert response.status_code == 500
    assert "lưu trữ tập tin" in response.json()["detail"].lower()
    assert list(override_upload_dir.iterdir()) == []
    assert db_session.scalar(
        select(KnowledgeSource).where(KnowledgeSource.original_filename == "disk_fail.txt")
    ) is None


def test_e4_mode_xb_khong_ghi_de_file_da_ton_tai(
    client: TestClient, override_upload_dir: Path
):
    dang_ky_va_dang_nhap(client, "collision@example.com")
    fixed_uuid = UUID("12345678-1234-5678-1234-567812345678")
    noi_dung_1 = b"Original content in first upload"
    noi_dung_2 = b"Attempted overwrite in second upload"

    with patch("app.api.knowledge.uuid4", return_value=fixed_uuid):
        # Lần 1: Thành công
        res1 = client.post(
            "/api/knowledge/upload",
            files={"file": ("original.txt", io.BytesIO(noi_dung_1), "text/plain")},
        )
        assert res1.status_code == 201

        target_file = override_upload_dir / f"{fixed_uuid.hex}.txt"
        assert target_file.exists()
        assert target_file.read_bytes() == noi_dung_1

        # Lần 2: Cùng UUID -> open(..., "xb") ném FileExistsError -> 500
        res2 = client.post(
            "/api/knowledge/upload",
            files={"file": ("duplicate.txt", io.BytesIO(noi_dung_2), "text/plain")},
        )
        assert res2.status_code == 500
        assert "khởi tạo tập tin lưu trữ" in res2.json()["detail"].lower()

        # Nội dung file 1 ban đầu hoàn toàn được bảo toàn
        assert target_file.read_bytes() == noi_dung_1


def test_e5_loi_bat_thuong_truoc_commit_khong_de_lai_ban_ghi_va_file(
    client: TestClient, db_session: Session, override_upload_dir: Path
):
    dang_ky_va_dang_nhap(client, "unexpected_error@example.com")
    noi_dung = b"Sample text for unexpected error test"

    # Giả lập lỗi bất thường tại db.add
    with patch.object(Session, "add", side_effect=RuntimeError("Unexpected runtime failure")):
        response = client.post(
            "/api/knowledge/upload",
            files={"file": ("unexpected.txt", io.BytesIO(noi_dung), "text/plain")},
        )

    assert response.status_code == 500
    assert "bất ngờ" in response.json()["detail"].lower()
    # File được dọn dẹp
    assert list(override_upload_dir.iterdir()) == []
    # DB không có bản ghi
    assert db_session.scalar(
        select(KnowledgeSource).where(KnowledgeSource.original_filename == "unexpected.txt")
    ) is None


def test_e6_loi_bat_thuong_sau_flush_truoc_commit_rollback_va_xoa_file(
    client: TestClient, db_session: Session, override_upload_dir: Path
):
    dang_ky_va_dang_nhap(client, "after_flush_error@example.com")
    noi_dung = b"Sample text for post-flush failure test"

    # Giả lập lỗi bất thường tại PhanHoiUpload (sau db.flush(), trước db.commit())
    with patch("app.api.knowledge.PhanHoiUpload", side_effect=RuntimeError("Lỗi khởi tạo response")):
        response = client.post(
            "/api/knowledge/upload",
            files={"file": ("post_flush.txt", io.BytesIO(noi_dung), "text/plain")},
        )

    assert response.status_code == 500
    assert "bất ngờ" in response.json()["detail"].lower()
    # File được dọn dẹp
    assert list(override_upload_dir.iterdir()) == []
    # DB không có bản ghi lưu lại
    assert db_session.scalar(
        select(KnowledgeSource).where(KnowledgeSource.original_filename == "post_flush.txt")
    ) is None


def test_e7_xoa_file_an_toan_ghi_log_warning_khi_unlink_that_bai(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
):
    import logging
    from app.api.knowledge import _xoa_file_an_toan

    file_tam = tmp_path / "file_khong_the_xoa.txt"
    file_tam.write_text("dummy")

    with caplog.at_level(logging.WARNING), patch.object(
        Path, "unlink", side_effect=OSError("Permission denied")
    ):
        _xoa_file_an_toan(file_tam)

    # Không ném lỗi ra ngoài
    assert "Không thể dọn dẹp tệp tạm" in caplog.text
    assert file_tam.name in caplog.text
    # Không để lộ toàn bộ đường dẫn thư mục cha
    assert str(tmp_path) not in caplog.text
