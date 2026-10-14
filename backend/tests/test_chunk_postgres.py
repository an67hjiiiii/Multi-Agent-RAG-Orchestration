from collections.abc import Generator
import os
import threading
import time
from uuid import uuid4
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.models.chunk import KnowledgeChunk
from app.models.knowledge import KnowledgeSource
from app.models.user import User
from app.schemas.chunk import ChunkCreateInput
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
# DATABASE SAFETY GUARD — CHỈ CHẤP NHẬN POSTGRESQL TẠI LOCALHOST VÀ
# DATABASE multi_agent_rag_chunk_test. TUYỆT ĐỐI KHÔNG CHẠM VÀO DATABASE KHÁC!
# ==============================================================================

TARGET_TEST_DB = "multi_agent_rag_chunk_test"


def lay_chunk_test_db_url_an_toan() -> str | None:
    """
    Xác minh và chuẩn hóa connection URL cho PostgreSQL chunk test.
    Ràng buộc an toàn:
    1. Phải là backend postgresql.
    2. Host phải là localhost hoặc 127.0.0.1.
    3. Tên database PHẢI LÀ CHÍNH XÁC 'multi_agent_rag_chunk_test'.
       Từ chối ngay lập tức nếu trỏ tới 'multi_agent_rag' hay 'multi_agent_rag_test'.
    """
    url_str = os.getenv("CHUNK_TEST_DATABASE_URL")
    if not url_str or not url_str.strip():
        return None

    if url_str.startswith("postgresql://"):
        url_str = url_str.replace("postgresql://", "postgresql+psycopg://", 1)

    url_obj = make_url(url_str)
    backend_name = url_obj.get_backend_name()
    ten_db = url_obj.database
    host_db = url_obj.host

    if backend_name != "postgresql":
        raise RuntimeError(f"[SAFETY GUARD] Backend khong phai PostgreSQL: {backend_name}")

    if host_db not in ("localhost", "127.0.0.1"):
        raise RuntimeError(f"[SAFETY GUARD] Host khong an toan: {host_db}. Chi chap nhan localhost hoac 127.0.0.1")

    if ten_db != TARGET_TEST_DB:
        raise RuntimeError(
            f"[SAFETY GUARD] TUYET DOI TU CHOI database '{ten_db}'! Chi duoc phep kiem thu tren '{TARGET_TEST_DB}'"
        )

    return url_str


SAFE_CHUNK_TEST_URL = lay_chunk_test_db_url_an_toan()


@pytest.fixture(scope="session")
def pg_chunk_engine():
    """Khởi tạo engine sau khi qua safety guard và xác minh current_database()."""
    if not SAFE_CHUNK_TEST_URL:
        pytest.skip(
            f"Chua thiet lap bien moi truong CHUNK_TEST_DATABASE_URL cho database '{TARGET_TEST_DB}'"
        )

    engine = create_engine(
        SAFE_CHUNK_TEST_URL,
        echo=False,
        pool_pre_ping=True,
        connect_args={
            "connect_timeout": 3,
            "options": "-c lock_timeout=3000ms -c statement_timeout=5000ms",
        },
    )

    # Runtime check: Kết nối thực tế và xác minh database name trực tiếp từ Postgres server
    try:
        with engine.connect() as conn:
            actual_db = conn.execute(text("SELECT current_database();")).scalar()
            if actual_db != TARGET_TEST_DB:
                raise RuntimeError(
                    f"[SAFETY GUARD] current_database() tren server la '{actual_db}', khong phai '{TARGET_TEST_DB}'"
                )
    except Exception as e:
        pytest.skip(f"Khong the ket noi toi test database '{TARGET_TEST_DB}': {e}")

    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def pg_session_factory(pg_chunk_engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=pg_chunk_engine)


@pytest.fixture
def pg_session(pg_chunk_engine) -> Generator[Session, None, None]:
    """
    Fixture session với connection-level transaction và SAVEPOINT:
    - Mở 1 connection độc lập và transaction gốc: connection.begin().
    - Gắn Session vào connection với join_transaction_mode="create_savepoint".
    - Mọi lệnh session.commit() trong test sẽ chỉ release SAVEPOINT, không commit ra connection gốc.
    - Khi kết thúc test (hoặc test fail), trans.rollback() hoàn tác 100% mọi thay đổi,
      đảm bảo Zero Residual Data mà không cần TRUNCATE.
    """
    with pg_chunk_engine.connect() as connection:
        trans = connection.begin()
        session = Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        try:
            yield session
        finally:
            session.close()
            trans.rollback()


@pytest.fixture
def pg_users(pg_session: Session) -> tuple[User, User]:
    """Tạo User A và User B với email độc nhất sử dụng uuid để không trùng lặp constraint."""
    suffix = uuid4().hex[:8]
    user_a = User(
        email=f"pg_chunk_a_{suffix}@example.com",
        name="PG User A",
        password_hash="hashed_pw_a",
        role="user",
    )
    user_b = User(
        email=f"pg_chunk_b_{suffix}@example.com",
        name="PG User B",
        password_hash="hashed_pw_b",
        role="user",
    )
    pg_session.add_all([user_a, user_b])
    pg_session.commit()
    pg_session.refresh(user_a)
    pg_session.refresh(user_b)
    return user_a, user_b


@pytest.fixture
def pg_extracted_source(pg_session: Session, pg_users: tuple[User, User]) -> KnowledgeSource:
    user_a, _ = pg_users
    source = KnowledgeSource(
        owner_id=user_a.id,
        original_filename="pg_manual.pdf",
        stored_path="sources/pg_manual.pdf",
        file_size=2048,
        mime_type="application/pdf",
        status="EXTRACTED",
    )
    pg_session.add(source)
    pg_session.commit()
    pg_session.refresh(source)
    return source


# ==============================================================================
# 1. POSTGRESQL SCHEMA & CONSTRAINT TESTS
# ==============================================================================


def test_pg_schema_inspection(pg_chunk_engine):
    """Kiểm tra schema bảng knowledge_chunks trên PostgreSQL qua information_schema."""
    with pg_chunk_engine.connect() as conn:
        cols = conn.execute(
            text(
                "SELECT column_name, data_type, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_name = 'knowledge_chunks' "
                "ORDER BY ordinal_position;"
            )
        ).fetchall()

    col_dict = {c[0]: (c[1], c[2]) for c in cols}
    assert "id" in col_dict
    assert "source_id" in col_dict
    assert "chunk_index" in col_dict
    assert "content" in col_dict
    assert "page_number" in col_dict
    assert "section" in col_dict
    assert "start_offset" in col_dict
    assert "end_offset" in col_dict
    assert "created_at" in col_dict


def test_pg_indexes_no_redundant_single_index(pg_chunk_engine):
    """Xác nhận không có index đơn trùng lặp trên source_id; chỉ có PK index và composite UNIQUE index."""
    with pg_chunk_engine.connect() as conn:
        indexes = conn.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'knowledge_chunks' "
                "ORDER BY indexname;"
            )
        ).fetchall()

    index_names = [idx[0] for idx in indexes]
    assert "knowledge_chunks_pkey" in index_names
    assert "uq_knowledge_chunks_source_chunk_index" in index_names
    # Không có index thừa dạng 'ix_knowledge_chunks_source_id'
    assert "ix_knowledge_chunks_source_id" not in index_names


def test_pg_foreign_key_cascade_delete(pg_session: Session, pg_extracted_source: KnowledgeSource, pg_users: tuple[User, User]):
    """Trên PostgreSQL thật, xóa KnowledgeSource tự động xóa các KnowledgeChunk (CASCADE)."""
    user_a, _ = pg_users
    batch = [
        ChunkCreateInput(chunk_index=0, content="PG Chunk 0"),
        ChunkCreateInput(chunk_index=1, content="PG Chunk 1"),
    ]
    created = replace_source_chunks(pg_session, pg_extracted_source.id, user_a.id, batch)
    pg_session.commit()
    chunk_ids = [c.id for c in created]

    # Xóa parent KnowledgeSource
    pg_session.delete(pg_extracted_source)
    pg_session.commit()

    # Xác nhận các chunks đã bị CASCADE xóa trên PostgreSQL
    remaining = pg_session.query(KnowledgeChunk).filter(KnowledgeChunk.id.in_(chunk_ids)).all()
    assert len(remaining) == 0


def test_pg_unique_constraint(pg_session: Session, pg_extracted_source: KnowledgeSource):
    """Trên PostgreSQL thật, trùng cặp (source_id, chunk_index) kích hoạt IntegrityError."""
    chunk1 = KnowledgeChunk(source_id=pg_extracted_source.id, chunk_index=0, content="Lần 1")
    pg_session.add(chunk1)
    pg_session.commit()

    chunk2 = KnowledgeChunk(source_id=pg_extracted_source.id, chunk_index=0, content="Lần 2 trùng")
    pg_session.add(chunk2)
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()


def test_pg_check_constraint_negative_chunk_index(pg_session: Session, pg_extracted_source: KnowledgeSource):
    """Trên PostgreSQL thật, chunk_index < 0 bị chặn."""
    chunk = KnowledgeChunk(source_id=pg_extracted_source.id, chunk_index=-1, content="Text")
    pg_session.add(chunk)
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()


@pytest.mark.parametrize(
    "blank_text",
    [
        "",
        "   ",
        "\t\t\n",
        "  \r\n\t  ",
        "\u00a0\u00a0",
        "\u3000",
    ],
)
def test_pg_check_constraint_empty_content(pg_session: Session, pg_extracted_source: KnowledgeSource, blank_text: str):
    """Trên PostgreSQL thật, ck_knowledge_chunks_content_not_empty chặn trực tiếp tab, newline và unicode whitespace."""
    chunk = KnowledgeChunk(source_id=pg_extracted_source.id, chunk_index=0, content=blank_text)
    pg_session.add(chunk)
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()


def test_pg_check_constraint_page_number(pg_session: Session, pg_extracted_source: KnowledgeSource):
    """Trên PostgreSQL thật, page_number < 1 bị chặn."""
    chunk = KnowledgeChunk(source_id=pg_extracted_source.id, chunk_index=0, content="Text", page_number=0)
    pg_session.add(chunk)
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()


def test_pg_check_constraint_invalid_offsets(pg_session: Session, pg_extracted_source: KnowledgeSource):
    """Trên PostgreSQL thật, end_offset <= start_offset bị chặn."""
    chunk = KnowledgeChunk(source_id=pg_extracted_source.id, chunk_index=0, content="Text", start_offset=100, end_offset=50)
    pg_session.add(chunk)
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()


# ==============================================================================
# 2. ATOMIC REPLACEMENT & TRANSACTION TESTS
# ==============================================================================


def test_pg_replace_source_chunks_happy_path(
    pg_session: Session,
    pg_extracted_source: KnowledgeSource,
    pg_users: tuple[User, User],
):
    """Thay thế chunks thành công trên PostgreSQL và trả về đúng DTOs."""
    user_a, _ = pg_users
    batch = [
        ChunkCreateInput(chunk_index=0, content="Nội dung trang 1", page_number=1, start_offset=0, end_offset=15),
        ChunkCreateInput(chunk_index=1, content="Nội dung trang 2", page_number=2, start_offset=16, end_offset=30),
    ]
    created = replace_source_chunks(pg_session, pg_extracted_source.id, user_a.id, batch)
    pg_session.commit()

    assert len(created) == 2
    assert created[0].chunk_index == 0
    assert created[1].chunk_index == 1
    assert created[0].char_count == len("Nội dung trang 1")
    assert created[0].char_count == 16
    assert created[1].page_number == 2


def test_pg_transaction_ownership_caller_rollback(pg_session: Session, pg_extracted_source: KnowledgeSource, pg_users: tuple[User, User]):
    """Trên PostgreSQL, nếu caller rollback thì không có chunk nào được ghi."""
    user_a, _ = pg_users
    batch = [ChunkCreateInput(chunk_index=0, content="Tạm thời")]
    replace_source_chunks(pg_session, pg_extracted_source.id, user_a.id, batch)
    pg_session.rollback()

    assert pg_session.query(KnowledgeChunk).filter_by(source_id=pg_extracted_source.id).count() == 0


def test_pg_invalid_batch_preserves_existing_chunks(
    pg_session: Session,
    pg_extracted_source: KnowledgeSource,
    pg_users: tuple[User, User],
):
    """Khi batch mới không hợp lệ (empty batch hoặc non-consecutive), batch cũ trên PostgreSQL vẫn nguyên vẹn."""
    user_a, _ = pg_users
    valid_batch = [ChunkCreateInput(chunk_index=0, content="Chunk cũ giữ nguyên")]
    replace_source_chunks(pg_session, pg_extracted_source.id, user_a.id, valid_batch)
    pg_session.commit()

    # Thử thay thế bằng empty batch
    with pytest.raises(ChunkValidationError):
        replace_source_chunks(pg_session, pg_extracted_source.id, user_a.id, [])

    # Thử thay thế bằng non-consecutive batch
    invalid_batch = [ChunkCreateInput(chunk_index=1, content="Bắt đầu từ 1")]
    with pytest.raises(ChunkValidationError):
        replace_source_chunks(pg_session, pg_extracted_source.id, user_a.id, invalid_batch)

    # Kiểm tra dữ liệu cũ trên PostgreSQL còn nguyên
    current_chunks = pg_session.query(KnowledgeChunk).filter_by(source_id=pg_extracted_source.id).all()
    assert len(current_chunks) == 1
    assert current_chunks[0].content == "Chunk cũ giữ nguyên"


def test_pg_flush_failure_and_caller_rollback(
    pg_session: Session,
    pg_extracted_source: KnowledgeSource,
    pg_users: tuple[User, User],
    monkeypatch: pytest.MonkeyPatch,
):
    """Khi db.flush() gặp sự cố trên PostgreSQL, caller rollback và dữ liệu cũ được giữ nguyên."""
    user_a, _ = pg_users
    init_batch = [ChunkCreateInput(chunk_index=0, content="Ban đầu")]
    replace_source_chunks(pg_session, pg_extracted_source.id, user_a.id, init_batch)
    pg_session.commit()

    def fake_flush():
        raise IntegrityError("Simulated flush failure", params=None, orig=Exception("DB constraint"))

    new_batch = [ChunkCreateInput(chunk_index=0, content="Thay thế lỗi")]
    with monkeypatch.context() as m:
        m.setattr(pg_session, "flush", fake_flush)
        with pytest.raises(IntegrityError):
            replace_source_chunks(pg_session, pg_extracted_source.id, user_a.id, new_batch)

    pg_session.rollback()
    assert pg_session.query(KnowledgeChunk).filter_by(source_id=pg_extracted_source.id).count() == 1


@pytest.mark.parametrize("bad_status", ["READY", "FAILED", "UPLOADED"])
def test_pg_lifecycle_guard_rejects_non_extracted(
    pg_session: Session,
    pg_users: tuple[User, User],
    bad_status: str,
):
    """Trên PostgreSQL thật, chỉ tài liệu status 'EXTRACTED' mới được thay thế chunks."""
    user_a, _ = pg_users
    source = KnowledgeSource(
        owner_id=user_a.id,
        original_filename="bad_status.pdf",
        stored_path="sources/bad.pdf",
        file_size=1024,
        mime_type="application/pdf",
        status=bad_status,
    )
    pg_session.add(source)
    pg_session.commit()

    batch = [ChunkCreateInput(chunk_index=0, content="Text")]
    with pytest.raises(ChunkLifecycleError):
        replace_source_chunks(pg_session, source.id, user_a.id, batch)


# ==============================================================================
# 3. POSTGRESQL CONCURRENCY & ROW LOCKING
# ==============================================================================


def test_pg_concurrency_row_locking(pg_session_factory):
    """
    Kiểm tra row locking with_for_update() trên PostgreSQL giữa 2 luồng độc lập:
    Luồng 1 khóa dòng KnowledgeSource và giữ trong 0.4s.
    Luồng 2 bắt buộc phải đợi Luồng 1 commit mới được thực thi, tuần tự hóa 100%.
    Server có lock_timeout=3000ms bảo vệ deadlock, client có timeout 5s.
    Dọn dẹp chính xác các bản ghi do test sinh ra trong khối finally, không để lại tồn dư.
    """
    setup_sess = pg_session_factory()
    suffix = uuid4().hex[:8]
    user_a = User(
        email=f"pg_concur_a_{suffix}@example.com",
        name="PG Concur User A",
        password_hash="hashed_pw",
        role="user",
    )
    setup_sess.add(user_a)
    setup_sess.commit()
    setup_sess.refresh(user_a)
    user_a_id = user_a.id

    source = KnowledgeSource(
        owner_id=user_a_id,
        original_filename="pg_concurrency.pdf",
        stored_path="sources/concurrency.pdf",
        file_size=1024,
        mime_type="application/pdf",
        status="EXTRACTED",
    )
    setup_sess.add(source)
    setup_sess.commit()
    setup_sess.refresh(source)
    source_id = source.id
    setup_sess.close()

    thread1_done_event = threading.Event()
    results = {}

    try:
        def worker_1():
            sess1 = pg_session_factory()
            try:
                batch1 = [ChunkCreateInput(chunk_index=0, content="Từ Luồng 1")]
                replace_source_chunks(sess1, source_id, user_a_id, batch1)
                # Giữ lock trong 0.4s
                time.sleep(0.4)
                sess1.commit()
                results["thread1"] = "SUCCESS"
            except Exception as e:
                results["thread1"] = str(e)
                sess1.rollback()
            finally:
                sess1.close()
                thread1_done_event.set()

        def worker_2():
            # Đợi một chút để Luồng 1 chắc chắn đã chiếm lock
            time.sleep(0.1)
            sess2 = pg_session_factory()
            try:
                batch2 = [ChunkCreateInput(chunk_index=0, content="Từ Luồng 2 (chiến thắng sau cùng)")]
                # Lệnh này sẽ bị block ở PostgreSQL engine cho đến khi Luồng 1 commit
                replace_source_chunks(sess2, source_id, user_a_id, batch2)
                sess2.commit()
                results["thread2"] = "SUCCESS"
            except Exception as e:
                results["thread2"] = str(e)
                sess2.rollback()
            finally:
                sess2.close()

        t1 = threading.Thread(target=worker_1)
        t2 = threading.Thread(target=worker_2)

        t1.start()
        t2.start()

        t1.join(timeout=5.0)
        t2.join(timeout=5.0)

        assert not t1.is_alive(), "Luồng 1 bị timeout và vẫn còn chạy!"
        assert not t2.is_alive(), "Luồng 2 bị timeout và vẫn còn chạy!"
        assert results.get("thread1") == "SUCCESS"
        assert results.get("thread2") == "SUCCESS"

        # Kiểm tra kết quả cuối cùng trên PostgreSQL: đúng 1 batch hoàn chỉnh của Luồng 2
        verify_session = pg_session_factory()
        try:
            final_chunks = list_chunks_for_source(verify_session, source_id, user_a_id)
            assert len(final_chunks) == 1
            assert final_chunks[0].content == "Từ Luồng 2 (chiến thắng sau cùng)"
        finally:
            verify_session.close()

    finally:
        # Targeted Cleanup: Xóa chính xác các bản ghi do test này sinh ra, không dùng TRUNCATE
        cleanup_sess = pg_session_factory()
        try:
            cleanup_sess.query(KnowledgeChunk).filter(KnowledgeChunk.source_id == source_id).delete()
            cleanup_sess.query(KnowledgeSource).filter(KnowledgeSource.id == source_id).delete()
            cleanup_sess.query(User).filter(User.id == user_a_id).delete()
            cleanup_sess.commit()
        finally:
            cleanup_sess.close()


# ==============================================================================
# 4. SECURITY & IDOR ISOLATION TESTS
# ==============================================================================


def test_pg_ownership_idor_isolation(pg_session: Session, pg_extracted_source: KnowledgeSource, pg_users: tuple[User, User]):
    """User B không thể truy cập, liệt kê, thay thế hay tạo payload từ chunk của User A trên PostgreSQL."""
    user_a, user_b = pg_users
    batch = [ChunkCreateInput(chunk_index=0, content="Bảo mật IDOR trên PostgreSQL")]
    created = replace_source_chunks(pg_session, pg_extracted_source.id, user_a.id, batch)
    pg_session.commit()
    chunk_id = created[0].id

    # 1. User B cố đọc chunk theo ID
    with pytest.raises(ChunkNotFoundError):
        get_chunk_by_id(pg_session, chunk_id, user_b.id)

    # 2. User B cố liệt kê chunks của User A
    with pytest.raises(ChunkNotFoundError):
        list_chunks_for_source(pg_session, pg_extracted_source.id, user_b.id)

    # 3. User B cố thay thế chunks của User A
    attack_batch = [ChunkCreateInput(chunk_index=0, content="Tấn công IDOR thay thế")]
    with pytest.raises(ChunkNotFoundError):
        replace_source_chunks(pg_session, pg_extracted_source.id, user_b.id, attack_batch)

    # 4. User B cố tạo vector payload
    with pytest.raises(ChunkNotFoundError):
        build_qdrant_payload(pg_session, chunk_id, user_b.id)


# ==============================================================================
# 5. PROVENANCE, RETRY & STALE EVIDENCE INVALIDATION
# ==============================================================================


def test_pg_retry_stale_evidence_invalidation(pg_session: Session, pg_extracted_source: KnowledgeSource, pg_users: tuple[User, User]):
    """
    Trên PostgreSQL thật:
    Khi retry/replace batch mới, sequence sinh ID mới và xóa sạch ID cũ.
    Truy vấn ID cũ trả về 404, bảo đảm chứng cứ vector/citation cũ bị vô hiệu hóa an toàn.
    """
    user_a, _ = pg_users
    batch_v1 = [ChunkCreateInput(chunk_index=0, content="Phiên bản 1")]
    res_v1 = replace_source_chunks(pg_session, pg_extracted_source.id, user_a.id, batch_v1)
    pg_session.commit()
    old_id = res_v1[0].id

    batch_v2 = [ChunkCreateInput(chunk_index=0, content="Phiên bản 2 (retry)")]
    res_v2 = replace_source_chunks(pg_session, pg_extracted_source.id, user_a.id, batch_v2)
    pg_session.commit()
    new_id = res_v2[0].id

    # PostgreSQL sequences tăng dần, ID mới phải lớn hơn ID cũ
    assert new_id > old_id

    # ID cũ không còn tồn tại
    with pytest.raises(ChunkNotFoundError):
        get_chunk_by_id(pg_session, old_id, user_a.id)

    # ID mới truy vấn thành công
    new_chunk = get_chunk_by_id(pg_session, new_id, user_a.id)
    assert new_chunk.id == new_id
    assert new_chunk.content == "Phiên bản 2 (retry)"


def test_pg_qdrant_payload_provenance_verification(pg_session: Session, pg_extracted_source: KnowledgeSource, pg_users: tuple[User, User]):
    """Qdrant payload trích xuất owner_id đã xác minh từ KnowledgeSource trên PostgreSQL."""
    user_a, _ = pg_users
    batch = [
        ChunkCreateInput(
            chunk_index=0,
            content="Nội dung trích dẫn",
            page_number=5,
            section="Mục 5.1",
            start_offset=200,
            end_offset=250,
        )
    ]
    created = replace_source_chunks(pg_session, pg_extracted_source.id, user_a.id, batch)
    pg_session.commit()

    payload = build_qdrant_payload(pg_session, created[0].id, user_a.id)
    assert payload.chunk_id == created[0].id
    assert payload.source_id == pg_extracted_source.id
    assert payload.owner_id == user_a.id
    assert payload.page_number == 5
    assert payload.section == "Mục 5.1"
    assert payload.start_offset == 200
    assert payload.end_offset == 250
