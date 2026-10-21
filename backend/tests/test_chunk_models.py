import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.chunk import KnowledgeChunk
from app.models.knowledge import KnowledgeSource
from app.models.user import User
from app.schemas.chunk import ChunkCreateInput, KnowledgeChunkRead, QdrantChunkPayload
from app.services.chunks import (
    ChunkLifecycleError,
    ChunkNotFoundError,
    ChunkValidationError,
    build_qdrant_payload,
    get_chunk_by_id,
    list_chunks_for_source,
    replace_source_chunks,
)


# ==============================================================================
# FIXTURES
# ==============================================================================


@pytest.fixture
def test_users(db_session: Session) -> tuple[User, User]:
    """Tạo 2 user để kiểm thử phân quyền và chống IDOR."""
    user_a = User(
        email="user_a@example.com",
        password_hash="hashed_password_a",
        name="User A",
        role="user",
    )
    user_b = User(
        email="user_b@example.com",
        password_hash="hashed_password_b",
        name="User B",
        role="user",
    )
    db_session.add_all([user_a, user_b])
    db_session.commit()
    db_session.refresh(user_a)
    db_session.refresh(user_b)
    return user_a, user_b


@pytest.fixture
def extracted_source(db_session: Session, test_users: tuple[User, User]) -> KnowledgeSource:
    """Tạo KnowledgeSource thuộc User A ở trạng thái EXTRACTED."""
    user_a, _ = test_users
    source = KnowledgeSource(
        owner_id=user_a.id,
        original_filename="manual.pdf",
        stored_path="sources/manual_abc.pdf",
        mime_type="application/pdf",
        file_size=1024,
        status="EXTRACTED",
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)
    return source


# ==============================================================================
# 1. SCHEMA VALIDATION TESTS (ChunkCreateInput)
# ==============================================================================


def test_chunk_create_input_valid():
    """Tạo chunk hợp lệ thành công với đầy đủ metadata."""
    item = ChunkCreateInput(
        chunk_index=0,
        content="Đoạn văn bản hợp lệ số 1.",
        page_number=1,
        section="Chương 1",
        start_offset=0,
        end_offset=26,
    )
    assert item.chunk_index == 0
    assert item.content == "Đoạn văn bản hợp lệ số 1."
    assert item.page_number == 1
    assert item.section == "Chương 1"
    assert item.start_offset == 0
    assert item.end_offset == 26


def test_chunk_create_input_without_offsets():
    """Hợp lệ khi cả hai offset đều là None."""
    item = ChunkCreateInput(
        chunk_index=0,
        content="Nội dung không có offset.",
        page_number=None,
    )
    assert item.start_offset is None
    assert item.end_offset is None


def test_chunk_create_input_negative_chunk_index():
    """Từ chối chunk_index âm."""
    with pytest.raises(ValueError):
        ChunkCreateInput(
            chunk_index=-1,
            content="Nội dung.",
        )


def test_chunk_create_input_empty_content():
    """Từ chối nội dung chuỗi rỗng."""
    with pytest.raises(ValueError):
        ChunkCreateInput(
            chunk_index=0,
            content="",
        )


@pytest.mark.parametrize(
    "blank_str",
    [
        "   ",
        "\t\t\n",
        "\u00a0\u00a0",  # Non-breaking space
        "\u3000",        # Ideographic space
    ],
)
def test_chunk_create_input_whitespace_only_content(blank_str: str):
    """Từ chối nội dung chỉ chứa ký tự khoảng trắng (ASCII hoặc Unicode)."""
    with pytest.raises(ValueError, match="Nội dung chunk không được để trống hoặc chỉ chứa khoảng trắng"):
        ChunkCreateInput(
            chunk_index=0,
            content=blank_str,
        )


def test_chunk_create_input_invalid_page_number():
    """Từ chối page_number <= 0."""
    with pytest.raises(ValueError):
        ChunkCreateInput(
            chunk_index=0,
            content="Nội dung trang 0.",
            page_number=0,
        )


def test_chunk_create_input_offset_pair_validation():
    """Kiểm tra tính toàn vẹn của cặp offset (phải cùng None hoặc cùng có giá trị hợp lệ)."""
    # Chỉ có start_offset
    with pytest.raises(ValueError, match="start_offset và end_offset phải đồng thời có giá trị"):
        ChunkCreateInput(
            chunk_index=0,
            content="Nội dung test",
            start_offset=0,
            end_offset=None,
        )

    # Chỉ có end_offset
    with pytest.raises(ValueError, match="start_offset và end_offset phải đồng thời có giá trị"):
        ChunkCreateInput(
            chunk_index=0,
            content="Nội dung test",
            start_offset=None,
            end_offset=10,
        )

    # end_offset <= start_offset
    with pytest.raises(ValueError, match="end_offset phải lớn hơn start_offset"):
        ChunkCreateInput(
            chunk_index=0,
            content="Nội dung test",
            start_offset=10,
            end_offset=10,
        )

    with pytest.raises(ValueError, match="end_offset phải lớn hơn start_offset"):
        ChunkCreateInput(
            chunk_index=0,
            content="Nội dung test",
            start_offset=20,
            end_offset=10,
        )


# ==============================================================================
# 2. SCHEMA DTO PROPERTY & PAYLOAD TESTS
# ==============================================================================


def test_knowledge_chunk_read_char_count():
    """char_count được tính động chính xác từ độ dài chuỗi content."""
    text = "Xin chào Việt Nam!"
    dto = KnowledgeChunkRead(
        id=1,
        source_id=10,
        chunk_index=0,
        content=text,
        page_number=1,
        section=None,
        start_offset=0,
        end_offset=len(text),
    )
    assert dto.char_count == len(text)
    assert dto.char_count == 18


def test_knowledge_chunk_read_model_dump_includes_char_count():
    """KnowledgeChunkRead serialize qua model_dump() và model_dump_json() chứa trường char_count."""
    text = "Đoạn văn bản kiểm thử serialization."
    dto = KnowledgeChunkRead(
        id=1,
        source_id=10,
        chunk_index=0,
        content=text,
    )
    dumped = dto.model_dump()
    assert "char_count" in dumped
    assert dumped["char_count"] == len(text)

    json_str = dto.model_dump_json()
    assert '"char_count":' in json_str


def test_qdrant_chunk_payload_structure():
    """QdrantChunkPayload lưu giữ đầy đủ provenance metadata."""
    payload = QdrantChunkPayload(
        chunk_id=1,
        source_id=10,
        owner_id=2,
        chunk_index=0,
        content="Đoạn văn bản trích xuất",
        page_number=2,
        section="2.1 Cài đặt",
        start_offset=100,
        end_offset=124,
    )
    assert payload.chunk_id == 1
    assert payload.source_id == 10
    assert payload.owner_id == 2
    assert payload.page_number == 2
    assert payload.section == "2.1 Cài đặt"


# ==============================================================================
# 3. DATABASE MODEL & CONSTRAINT TESTS (SQLite Engine)
# ==============================================================================


def test_db_unique_constraint_source_and_chunk_index(db_session: Session, extracted_source: KnowledgeSource):
    """Trùng cặp (source_id, chunk_index) kích hoạt IntegrityError."""
    chunk1 = KnowledgeChunk(
        source_id=extracted_source.id,
        chunk_index=0,
        content="Chunk index 0 lần đầu",
    )
    db_session.add(chunk1)
    db_session.commit()

    chunk2 = KnowledgeChunk(
        source_id=extracted_source.id,
        chunk_index=0,
        content="Chunk index 0 trùng lặp",
    )
    db_session.add(chunk2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_db_check_constraint_negative_chunk_index(db_session: Session, extracted_source: KnowledgeSource):
    """Check constraint ck_knowledge_chunks_index_non_negative chặn chunk_index âm."""
    chunk = KnowledgeChunk(
        source_id=extracted_source.id,
        chunk_index=-1,
        content="Nội dung chunk",
    )
    db_session.add(chunk)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize(
    "blank_text",
    [
        "",
        "   ",
        "\t\t\n",
        "  \r\n\t  ",
        "\u00a0\u00a0",  # Non-breaking space
        "\u3000",        # Ideographic space
    ],
)
def test_db_check_constraint_empty_content(db_session: Session, extracted_source: KnowledgeSource, blank_text: str):
    """Check constraint ck_knowledge_chunks_content_not_empty chặn trực tiếp ở DB chuỗi rỗng và khoảng trắng Unicode."""
    chunk = KnowledgeChunk(
        source_id=extracted_source.id,
        chunk_index=0,
        content=blank_text,
    )
    db_session.add(chunk)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_db_check_constraint_page_number(db_session: Session, extracted_source: KnowledgeSource):
    """Check constraint ck_knowledge_chunks_page_number chặn page_number < 1."""
    chunk = KnowledgeChunk(
        source_id=extracted_source.id,
        chunk_index=0,
        content="Nội dung trang 0",
        page_number=0,
    )
    db_session.add(chunk)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_db_check_constraint_invalid_offsets(db_session: Session, extracted_source: KnowledgeSource):
    """Check constraint ck_knowledge_chunks_offsets_valid chặn cặp offset không hợp lệ."""
    chunk = KnowledgeChunk(
        source_id=extracted_source.id,
        chunk_index=0,
        content="Nội dung sai offset",
        start_offset=100,
        end_offset=50,
    )
    db_session.add(chunk)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_db_cascade_delete_source_removes_chunks(db_session: Session, extracted_source: KnowledgeSource):
    """Xóa KnowledgeSource tự động xóa các KnowledgeChunk trực thuộc (ON DELETE CASCADE)."""
    # Kích hoạt foreign key pragma cho kết nối SQLite hiện hành để kiểm tra CASCADE
    db_session.execute(KnowledgeChunk.__table__.select().limit(1))
    db_session.connection().connection.execute("PRAGMA foreign_keys=ON")

    chunk = KnowledgeChunk(
        source_id=extracted_source.id,
        chunk_index=0,
        content="Đoạn văn bản sẽ bị xóa theo source.",
    )
    db_session.add(chunk)
    db_session.commit()

    chunk_id = chunk.id
    source_id = extracted_source.id

    # Xóa KnowledgeSource
    db_session.delete(extracted_source)
    db_session.commit()

    # Kiểm tra chunk đã bị xóa
    remaining_chunk = db_session.query(KnowledgeChunk).filter(KnowledgeChunk.id == chunk_id).first()
    assert remaining_chunk is None


# ==============================================================================
# 4. SERVICE LAYER: replace_source_chunks
# ==============================================================================


def test_service_replace_source_chunks_happy_path(
    db_session: Session,
    extracted_source: KnowledgeSource,
    test_users: tuple[User, User],
):
    """Thay thế chunks thành công với thứ tự liên tục 0, 1, 2."""
    user_a, _ = test_users
    chunks_in = [
        ChunkCreateInput(chunk_index=0, content="Đoạn 1", page_number=1, start_offset=0, end_offset=10),
        ChunkCreateInput(chunk_index=1, content="Đoạn 2", page_number=1, start_offset=11, end_offset=25),
        ChunkCreateInput(chunk_index=2, content="Đoạn 3", page_number=2, start_offset=26, end_offset=40),
    ]

    result = replace_source_chunks(
        db=db_session,
        source_id=extracted_source.id,
        trusted_owner_id=user_a.id,
        chunks_in=chunks_in,
    )
    db_session.commit()

    assert len(result) == 3
    assert result[0].chunk_index == 0
    assert result[1].chunk_index == 1
    assert result[2].chunk_index == 2
    assert result[0].content == "Đoạn 1"
    assert result[2].page_number == 2


def test_service_replace_source_chunks_atomic_replacement(
    db_session: Session,
    extracted_source: KnowledgeSource,
    test_users: tuple[User, User],
):
    """Lần gọi thứ hai thay thế hoàn toàn tập chunks cũ bằng tập mới."""
    user_a, _ = test_users

    # Lần 1: Chèn 3 chunks
    batch_1 = [
        ChunkCreateInput(chunk_index=0, content="Cũ 0"),
        ChunkCreateInput(chunk_index=1, content="Cũ 1"),
        ChunkCreateInput(chunk_index=2, content="Cũ 2"),
    ]
    replace_source_chunks(db_session, extracted_source.id, user_a.id, batch_1)
    db_session.commit()

    assert db_session.query(KnowledgeChunk).filter_by(source_id=extracted_source.id).count() == 3

    # Lần 2: Thay thế bằng 2 chunks mới
    batch_2 = [
        ChunkCreateInput(chunk_index=0, content="Mới 0"),
        ChunkCreateInput(chunk_index=1, content="Mới 1"),
    ]
    replace_source_chunks(db_session, extracted_source.id, user_a.id, batch_2)
    db_session.commit()

    chunks_in_db = (
        db_session.query(KnowledgeChunk)
        .filter_by(source_id=extracted_source.id)
        .order_by(KnowledgeChunk.chunk_index.asc())
        .all()
    )
    assert len(chunks_in_db) == 2
    assert chunks_in_db[0].content == "Mới 0"
    assert chunks_in_db[1].content == "Mới 1"


def test_service_replace_source_chunks_caller_owns_transaction_rollback(
    db_session: Session,
    extracted_source: KnowledgeSource,
    test_users: tuple[User, User],
):
    """Caller sở hữu transaction: nếu caller rollback, không có chunk nào được lưu."""
    user_a, _ = test_users
    batch = [
        ChunkCreateInput(chunk_index=0, content="Tạm thời 0"),
    ]
    replace_source_chunks(db_session, extracted_source.id, user_a.id, batch)
    # Caller quyết định rollback thay vì commit
    db_session.rollback()

    assert db_session.query(KnowledgeChunk).filter_by(source_id=extracted_source.id).count() == 0


def test_service_replace_source_chunks_rejects_empty_batch(
    db_session: Session,
    extracted_source: KnowledgeSource,
    test_users: tuple[User, User],
):
    """Từ chối batch rỗng và ném ChunkValidationError trước khi thao tác DB."""
    user_a, _ = test_users
    with pytest.raises(ChunkValidationError, match="Danh sách chunk không được để trống"):
        replace_source_chunks(
            db=db_session,
            source_id=extracted_source.id,
            trusted_owner_id=user_a.id,
            chunks_in=[],
        )


@pytest.mark.parametrize(
    "invalid_indices",
    [
        [1, 2, 3],       # Không bắt đầu từ 0
        [0, 2],          # Bị ngắt quãng
        [0, 0, 1],       # Trùng lặp
        [0, 1, 3],       # Bỏ sót index 2
    ],
)
def test_service_replace_source_chunks_rejects_non_consecutive_indices(
    db_session: Session,
    extracted_source: KnowledgeSource,
    test_users: tuple[User, User],
    invalid_indices: list[int],
):
    """Từ chối batch nếu chunk_index không bắt đầu từ 0 hoặc không liên tục."""
    user_a, _ = test_users
    batch = [ChunkCreateInput(chunk_index=idx, content=f"Chunk {idx}") for idx in invalid_indices]

    with pytest.raises(ChunkValidationError, match="Thứ tự chunk_index phải bắt đầu từ 0 và liên tục"):
        replace_source_chunks(
            db=db_session,
            source_id=extracted_source.id,
            trusted_owner_id=user_a.id,
            chunks_in=batch,
        )


@pytest.mark.parametrize("disallowed_status", ["READY", "FAILED", "UPLOADED"])
def test_service_replace_source_chunks_lifecycle_guard(
    db_session: Session,
    test_users: tuple[User, User],
    disallowed_status: str,
):
    """Từ chối thay thế chunks nếu KnowledgeSource có status READY, FAILED hoặc UPLOADED."""
    user_a, _ = test_users
    source = KnowledgeSource(
        owner_id=user_a.id,
        original_filename="status_test.pdf",
        stored_path="sources/test.pdf",
        mime_type="application/pdf",
        file_size=512,
        status=disallowed_status,
    )
    db_session.add(source)
    db_session.commit()

    batch = [ChunkCreateInput(chunk_index=0, content="Nội dung chunk")]
    with pytest.raises(ChunkLifecycleError, match=f"Tài liệu đang ở trạng thái '{disallowed_status}'"):
        replace_source_chunks(
            db=db_session,
            source_id=source.id,
            trusted_owner_id=user_a.id,
            chunks_in=batch,
        )


def test_service_replace_source_chunks_idor_protection(
    db_session: Session,
    extracted_source: KnowledgeSource,
    test_users: tuple[User, User],
):
    """User B không thể thay thế chunks của tài liệu thuộc sở hữu User A."""
    _, user_b = test_users
    batch = [ChunkCreateInput(chunk_index=0, content="Tấn công IDOR")]

    with pytest.raises(ChunkNotFoundError, match="Không tìm thấy tài liệu hoặc bạn không có quyền truy cập"):
        replace_source_chunks(
            db=db_session,
            source_id=extracted_source.id,
            trusted_owner_id=user_b.id,
            chunks_in=batch,
        )


# ==============================================================================
# 5. SERVICE LAYER: READ & PAYLOAD BUILDER TESTS
# ==============================================================================


def test_service_get_chunk_by_id_and_idor(
    db_session: Session,
    extracted_source: KnowledgeSource,
    test_users: tuple[User, User],
):
    """Đọc chunk theo ID và bảo vệ chống IDOR."""
    user_a, user_b = test_users
    batch = [ChunkCreateInput(chunk_index=0, content="Nội dung kiểm tra get_by_id")]
    created = replace_source_chunks(db_session, extracted_source.id, user_a.id, batch)
    db_session.commit()
    chunk_id = created[0].id

    # User A (chủ sở hữu hợp pháp) đọc thành công
    chunk_read = get_chunk_by_id(db_session, chunk_id, user_a.id)
    assert chunk_read.id == chunk_id
    assert chunk_read.content == "Nội dung kiểm tra get_by_id"

    # User B truy cập chunk của User A bị chặn và ném ChunkNotFoundError
    with pytest.raises(ChunkNotFoundError):
        get_chunk_by_id(db_session, chunk_id, user_b.id)

    # Chunk không tồn tại ném ChunkNotFoundError
    with pytest.raises(ChunkNotFoundError):
        get_chunk_by_id(db_session, 999999, user_a.id)


def test_service_list_chunks_for_source_and_idor(
    db_session: Session,
    extracted_source: KnowledgeSource,
    test_users: tuple[User, User],
):
    """Liệt kê chunks theo thứ tự chunk_index và bảo vệ IDOR."""
    user_a, user_b = test_users
    batch = [
        ChunkCreateInput(chunk_index=0, content="Đoạn 0"),
        ChunkCreateInput(chunk_index=1, content="Đoạn 1"),
    ]
    replace_source_chunks(db_session, extracted_source.id, user_a.id, batch)
    db_session.commit()

    # User A đọc thành công danh sách
    chunks = list_chunks_for_source(db_session, extracted_source.id, user_a.id)
    assert len(chunks) == 2
    assert chunks[0].chunk_index == 0
    assert chunks[1].chunk_index == 1

    # User B cố đọc danh sách chunks của User A bị chặn
    with pytest.raises(ChunkNotFoundError):
        list_chunks_for_source(db_session, extracted_source.id, user_b.id)


def test_service_build_qdrant_payload(
    db_session: Session,
    extracted_source: KnowledgeSource,
    test_users: tuple[User, User],
):
    """Đóng gói payload Qdrant với owner_id đã xác minh từ DB."""
    user_a, user_b = test_users
    batch = [
        ChunkCreateInput(
            chunk_index=0,
            content="Nội dung đóng gói Qdrant",
            page_number=3,
            section="Mục 3.2",
            start_offset=50,
            end_offset=80,
        )
    ]
    created = replace_source_chunks(db_session, extracted_source.id, user_a.id, batch)
    db_session.commit()
    chunk_id = created[0].id

    payload = build_qdrant_payload(db_session, chunk_id, user_a.id)
    assert payload.chunk_id == chunk_id
    assert payload.source_id == extracted_source.id
    assert payload.owner_id == user_a.id
    assert payload.page_number == 3
    assert payload.section == "Mục 3.2"
    assert payload.start_offset == 50
    assert payload.end_offset == 80

    # User B không thể tạo payload từ chunk của User A
    with pytest.raises(ChunkNotFoundError):
        build_qdrant_payload(db_session, chunk_id, user_b.id)


def test_service_replace_source_chunks_flush_failure_and_caller_rollback(
    db_session: Session,
    extracted_source: KnowledgeSource,
    test_users: tuple[User, User],
    monkeypatch: pytest.MonkeyPatch,
):
    """Khi db.flush() gặp lỗi nội bộ, exception được ném ra caller và caller rollback an toàn."""
    user_a, _ = test_users

    # Tạo trước 1 chunk hợp lệ
    init_batch = [ChunkCreateInput(chunk_index=0, content="Chunk ban đầu")]
    replace_source_chunks(db_session, extracted_source.id, user_a.id, init_batch)
    db_session.commit()
    assert db_session.query(KnowledgeChunk).filter_by(source_id=extracted_source.id).count() == 1

    # Mô phỏng lỗi khi flush
    def fake_flush():
        raise IntegrityError("Simulated DB Flush Error", params=None, orig=Exception("DB constraint error"))

    monkeypatch.setattr(db_session, "flush", fake_flush)

    new_batch = [
        ChunkCreateInput(chunk_index=0, content="Chunk mới 0"),
        ChunkCreateInput(chunk_index=1, content="Chunk mới 1"),
    ]

    with pytest.raises(IntegrityError):
        replace_source_chunks(db_session, extracted_source.id, user_a.id, new_batch)

    # Caller thực hiện rollback sau khi bắt ngoại lệ
    db_session.rollback()

    # Dữ liệu ban đầu vẫn nguyên vẹn
    chunks = db_session.query(KnowledgeChunk).filter_by(source_id=extracted_source.id).all()
    assert len(chunks) == 1
    assert chunks[0].content == "Chunk ban đầu"


def test_service_replace_source_chunks_retry_invalidates_old_chunk_ids(
    db_session: Session,
    extracted_source: KnowledgeSource,
    test_users: tuple[User, User],
):
    """Khi retry/thay thế batch mới, các Chunk ID cũ bị xóa hoàn toàn; ID cũ không thể truy cập (invalidate old evidence)."""
    user_a, _ = test_users

    # Lần 1: Tạo batch ban đầu
    batch_1 = [
        ChunkCreateInput(chunk_index=0, content="Nội dung phiên bản 1"),
    ]
    res_1 = replace_source_chunks(db_session, extracted_source.id, user_a.id, batch_1)
    db_session.commit()
    old_chunk_id = res_1[0].id

    # Xác nhận old_chunk_id tồn tại
    old_chunk = get_chunk_by_id(db_session, old_chunk_id, user_a.id)
    assert old_chunk.id == old_chunk_id

    # Lần 2: Retry / thay thế batch mới
    batch_2 = [
        ChunkCreateInput(chunk_index=0, content="Nội dung phiên bản 2 (retry)"),
    ]
    res_2 = replace_source_chunks(db_session, extracted_source.id, user_a.id, batch_2)
    db_session.commit()
    new_chunk_id = res_2[0].id

    # ID mới phải khác ID cũ (do ID là auto-increment và bản ghi cũ đã bị xóa)
    assert new_chunk_id != old_chunk_id

    # Truy vấn ID cũ phải báo lỗi NOT FOUND (chứng cứ cũ bị vô hiệu hóa)
    with pytest.raises(ChunkNotFoundError):
        get_chunk_by_id(db_session, old_chunk_id, user_a.id)

    # Truy vấn ID mới thành công
    new_chunk = get_chunk_by_id(db_session, new_chunk_id, user_a.id)
    assert new_chunk.id == new_chunk_id
    assert new_chunk.content == "Nội dung phiên bản 2 (retry)"
