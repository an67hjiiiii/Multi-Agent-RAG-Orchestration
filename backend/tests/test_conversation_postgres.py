"""
CAPONE-30 — Phase 4B: PostgreSQL Integration Tests for HoiThoai, TinNhan, and LanXuLy.

Kiểm thử toàn diện trên cơ sở dữ liệu PostgreSQL thực tế (multi_agent_rag_test):
- Group A: PostgreSQL Schema & Metadata (PK, FK, Composite FK, UNIQUE, CHECK, Indexes)
- Group B: Server Defaults (Direct SQL INSERT)
- Group C: PostgreSQL Constraints (Valid & Invalid Data, NO ACTION)
- Group D: Transaction Behavior (Savepoint commit & Outer transaction rollback isolation)
- Group E: Data Integrity & Structural Isolation (Multi-user cross-reference protection)
"""
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
import os
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import HoiThoai, LanXuLy, TinNhan, User


# ============================================================================
# SAFETY GUARD — BẮT BUỘC TRƯỚC KHI TẠO ENGINE POSTGRESQL
# ============================================================================

def lay_url_kiem_thu_an_toan() -> str:
    """
    Xác minh đa tầng TEST_DATABASE_URL:
    - Bắt buộc phải là PostgreSQL
    - Host bắt buộc phải là localhost hoặc 127.0.0.1
    - Database đích bắt buộc là multi_agent_rag_test
    Tuyệt đối không kết nối database development multi_agent_rag.
    """
    url_str = os.getenv("TEST_DATABASE_URL")
    if not url_str or not url_str.strip():
        raise RuntimeError("Thiếu biến môi trường TEST_DATABASE_URL cho kiểm thử PostgreSQL")

    if url_str.startswith("postgresql://"):
        url_str = url_str.replace("postgresql://", "postgresql+psycopg://", 1)

    url_obj = make_url(url_str)
    ten_db = url_obj.database
    host_db = url_obj.host
    backend_name = url_obj.get_backend_name()

    if backend_name != "postgresql":
        raise RuntimeError(f"Backend không phải PostgreSQL: {backend_name}")

    if not ten_db or ten_db != "multi_agent_rag_test":
        raise RuntimeError(f"Database không an toàn cho kiểm thử: {ten_db}")

    if not host_db or host_db not in ("localhost", "127.0.0.1"):
        raise RuntimeError(f"Host không hợp lệ cho môi trường kiểm thử: {host_db}")

    return url_str


URL_KIEM_THU = lay_url_kiem_thu_an_toan()

postgres_test_engine = create_engine(
    URL_KIEM_THU,
    echo=False,
    pool_pre_ping=True,
)


# ============================================================================
# FIXTURES — TRANSACTION ISOLATION
# ============================================================================

@pytest.fixture(scope="session", autouse=True)
def xac_minh_an_toan_postgres():
    """
    Xác minh database identity và Alembic revision trước khi chạy bất kỳ test nào.
    """
    with postgres_test_engine.connect() as conn:
        curr_db = conn.execute(text("SELECT current_database()")).scalar()
        assert curr_db == "multi_agent_rag_test", f"Database không đúng: {curr_db}"

        rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert rev == "e5f6a1b2c3d4", f"Revision không đúng: {rev}"


@pytest.fixture
def pg_session() -> Generator[Session, None, None]:
    """
    Cung cấp Session cô lập trong outer transaction cho từng test case.
    Sử dụng join_transaction_mode="create_savepoint" để:
    - Các commit trong test chỉ commit vào Savepoint.
    - Fixture rollback outer transaction ở finally, đảm bảo 0 dữ liệu tồn dư trên PostgreSQL.
    """
    connection = postgres_test_engine.connect()
    trans = connection.begin()
    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
    )

    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        connection.close()


@pytest.fixture
def tao_nguoi_dung(pg_session: Session) -> User:
    """Tạo người dùng kiểm thử tạm thời trong savepoint."""
    user = User(
        email=f"pg_test_{datetime.now(timezone.utc).timestamp()}@example.com",
        password_hash="test_hash_value",
        name="Postgres Tester",
        role="USER",
    )
    pg_session.add(user)
    pg_session.commit()
    return user


# ============================================================================
# TEST GROUP A — POSTGRESQL SCHEMA METADATA
# ============================================================================

def test_a1_database_identity_and_alembic_revision():
    """A1: Xác minh kết nối thực tế tới multi_agent_rag_test và revision e5f6a1b2c3d4."""
    with postgres_test_engine.connect() as conn:
        curr_db = conn.execute(text("SELECT current_database()")).scalar()
        assert curr_db == "multi_agent_rag_test"
        rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert rev == "e5f6a1b2c3d4"


def test_a2_all_three_tables_exist():
    """A2: Xác minh tồn tại đầy đủ ba bảng mới trên schema public."""
    with postgres_test_engine.connect() as conn:
        query = text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        tables = [r[0] for r in conn.execute(query).fetchall()]
        assert "hoi_thoai" in tables
        assert "tin_nhan" in tables
        assert "lan_xu_ly" in tables


def test_a3_primary_keys_correct():
    """A3: Xác minh primary key tiếng Việt không dấu trên PostgreSQL, không có cột id."""
    with postgres_test_engine.connect() as conn:
        query = text("""
            SELECT tc.table_name, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = 'public'
              AND tc.table_name IN ('hoi_thoai', 'tin_nhan', 'lan_xu_ly')
        """)
        pks = {r[0]: r[1] for r in conn.execute(query).fetchall()}
        assert pks["hoi_thoai"] == "ma_hoi_thoai"
        assert pks["tin_nhan"] == "ma_tin_nhan"
        assert pks["lan_xu_ly"] == "ma_lan_xu_ly"


def test_a4_a5_foreign_keys_and_no_action():
    """A4-A5: Xác minh 4 foreign keys tồn tại và đều có ON DELETE / UPDATE NO ACTION."""
    with postgres_test_engine.connect() as conn:
        query = text("""
            SELECT conname, conrelid::regclass::text, confdeltype, confupdtype, pg_get_constraintdef(c.oid)
            FROM pg_constraint c
            WHERE conrelid::regclass::text IN ('hoi_thoai', 'tin_nhan', 'lan_xu_ly')
              AND contype = 'f'
        """)
        fks = {r[0]: (r[1], r[2], r[3], r[4]) for r in conn.execute(query).fetchall()}

        # 4 FKs
        assert "fk_hoi_thoai_ma_nguoi_dung" in fks
        assert "fk_tin_nhan_ma_hoi_thoai" in fks
        assert "fk_lan_xu_ly_ma_hoi_thoai" in fks
        assert "fk_lan_xu_ly_tin_nhan_dau_vao" in fks

        # NO ACTION: confdeltype == 'a', confupdtype == 'a'
        for name, (_, del_type, upd_type, defn) in fks.items():
            assert del_type == "a", f"{name} delete action không phải NO ACTION"
            assert upd_type == "a", f"{name} update action không phải NO ACTION"

        # Composite FK definition
        comp_def = fks["fk_lan_xu_ly_tin_nhan_dau_vao"][3]
        assert "FOREIGN KEY (ma_tin_nhan_dau_vao, ma_hoi_thoai) REFERENCES tin_nhan(ma_tin_nhan, ma_hoi_thoai)" in comp_def


def test_a6_composite_unique_on_tin_nhan():
    """A6: Xác minh UNIQUE (ma_tin_nhan, ma_hoi_thoai) trên PostgreSQL."""
    with postgres_test_engine.connect() as conn:
        query = text("""
            SELECT conname, pg_get_constraintdef(c.oid)
            FROM pg_constraint c
            WHERE conrelid::regclass::text = 'tin_nhan' AND contype = 'u'
        """)
        uqs = {r[0]: r[1] for r in conn.execute(query).fetchall()}
        assert "uq_tin_nhan_ma_tin_nhan_ma_hoi_thoai" in uqs
        assert "UNIQUE (ma_tin_nhan, ma_hoi_thoai)" in uqs["uq_tin_nhan_ma_tin_nhan_ma_hoi_thoai"]


def test_a7_check_constraints_exist():
    """A7: Xác minh 3 CHECK constraints thực tế trên PostgreSQL."""
    with postgres_test_engine.connect() as conn:
        query = text("""
            SELECT conname, pg_get_constraintdef(c.oid)
            FROM pg_constraint c
            WHERE conrelid::regclass::text IN ('tin_nhan', 'lan_xu_ly') AND contype = 'c'
        """)
        cks = {r[0]: r[1] for r in conn.execute(query).fetchall()}
        assert "ck_tin_nhan_vai_tro" in cks
        assert "ck_lan_xu_ly_trang_thai" in cks
        assert "ck_lan_xu_ly_thoi_gian" in cks


def test_a8_indexes_exist():
    """A8: Xác minh 4 indexes tồn tại trên PostgreSQL với phương pháp B-tree và đúng cột."""
    with postgres_test_engine.connect() as conn:
        query = text("""
            SELECT
                i.relname AS index_name,
                t.relname AS table_name,
                am.amname AS access_method,
                pg_get_indexdef(ix.indexrelid) AS index_def
            FROM pg_index ix
            JOIN pg_class t ON t.oid = ix.indrelid
            JOIN pg_class i ON i.oid = ix.indexrelid
            JOIN pg_am am ON i.relam = am.oid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE n.nspname = 'public'
              AND t.relname IN ('hoi_thoai', 'tin_nhan', 'lan_xu_ly')
              AND NOT ix.indisprimary
              AND NOT ix.indisunique
        """)
        idx_map = {r[0]: (r[1], r[2], r[3]) for r in conn.execute(query).fetchall()}

        expected = {
            "ix_hoi_thoai_ma_nguoi_dung": ("hoi_thoai", "ma_nguoi_dung"),
            "ix_tin_nhan_ma_hoi_thoai": ("tin_nhan", "ma_hoi_thoai"),
            "ix_lan_xu_ly_ma_hoi_thoai": ("lan_xu_ly", "ma_hoi_thoai"),
            "ix_lan_xu_ly_ma_tin_nhan_dau_vao": ("lan_xu_ly", "ma_tin_nhan_dau_vao"),
        }

        for idx_name, (tbl, col) in expected.items():
            assert idx_name in idx_map, f"Thiếu index {idx_name}"
            tbl_actual, am_actual, def_actual = idx_map[idx_name]
            assert tbl_actual == tbl, f"Index {idx_name} sai bảng: {tbl_actual} != {tbl}"
            assert am_actual == "btree", f"Index {idx_name} sai access method: {am_actual}"
            assert f"({col})" in def_actual, f"Index {idx_name} sai cột: {def_actual}"


def test_a9_column_types_and_defaults():
    """A9: Xác minh đầy đủ kiểu cột, nullable và server defaults trên cả ba bảng mới theo catalog PostgreSQL."""
    with postgres_test_engine.connect() as conn:
        query = text("""
            SELECT table_name, column_name, data_type, column_default, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name IN ('hoi_thoai', 'tin_nhan', 'lan_xu_ly')
        """)
        cols = {(r[0], r[1]): (r[2], r[3], r[4]) for r in conn.execute(query).fetchall()}

        # 1. Bảng hoi_thoai
        assert cols[("hoi_thoai", "ma_hoi_thoai")][0] == "integer"
        assert "nextval" in str(cols[("hoi_thoai", "ma_hoi_thoai")][1])
        assert cols[("hoi_thoai", "ma_hoi_thoai")][2] == "NO"

        assert cols[("hoi_thoai", "ma_nguoi_dung")] == ("integer", None, "NO")

        assert cols[("hoi_thoai", "tieu_de")][0] == "character varying"
        assert cols[("hoi_thoai", "tieu_de")][1] == "'Cuộc hội thoại mới'::character varying"
        assert cols[("hoi_thoai", "tieu_de")][2] == "NO"

        assert cols[("hoi_thoai", "thoi_gian_tao")] == ("timestamp with time zone", "CURRENT_TIMESTAMP", "NO")
        assert cols[("hoi_thoai", "thoi_gian_cap_nhat")] == ("timestamp with time zone", "CURRENT_TIMESTAMP", "NO")

        # 2. Bảng tin_nhan
        assert cols[("tin_nhan", "ma_tin_nhan")][0] == "integer"
        assert "nextval" in str(cols[("tin_nhan", "ma_tin_nhan")][1])
        assert cols[("tin_nhan", "ma_tin_nhan")][2] == "NO"

        assert cols[("tin_nhan", "ma_hoi_thoai")] == ("integer", None, "NO")
        assert cols[("tin_nhan", "vai_tro")] == ("character varying", None, "NO")
        assert cols[("tin_nhan", "noi_dung")] == ("text", None, "NO")
        assert cols[("tin_nhan", "thoi_gian_tao")] == ("timestamp with time zone", "CURRENT_TIMESTAMP", "NO")

        # 3. Bảng lan_xu_ly
        assert cols[("lan_xu_ly", "ma_lan_xu_ly")][0] == "integer"
        assert "nextval" in str(cols[("lan_xu_ly", "ma_lan_xu_ly")][1])
        assert cols[("lan_xu_ly", "ma_lan_xu_ly")][2] == "NO"

        assert cols[("lan_xu_ly", "ma_hoi_thoai")] == ("integer", None, "NO")
        assert cols[("lan_xu_ly", "ma_tin_nhan_dau_vao")] == ("integer", None, "YES")

        assert cols[("lan_xu_ly", "trang_thai")][0] == "character varying"
        assert cols[("lan_xu_ly", "trang_thai")][1] == "'PENDING'::character varying"
        assert cols[("lan_xu_ly", "trang_thai")][2] == "NO"

        assert cols[("lan_xu_ly", "thong_bao_loi")] == ("text", None, "YES")
        assert cols[("lan_xu_ly", "thoi_gian_bat_dau")] == ("timestamp with time zone", None, "YES")
        assert cols[("lan_xu_ly", "thoi_gian_hoan_tat")] == ("timestamp with time zone", None, "YES")
        assert cols[("lan_xu_ly", "thoi_gian_tao")] == ("timestamp with time zone", "CURRENT_TIMESTAMP", "NO")


# ============================================================================
# TEST GROUP B — SERVER DEFAULTS (DIRECT POSTGRESQL SQL INSERT)
# ============================================================================

def test_b1_server_default_tieu_de(pg_session: Session, tao_nguoi_dung: User):
    """B1: Bỏ trống tieu_de khi INSERT SQL: PostgreSQL tự đặt 'Cuộc hội thoại mới'."""
    row = pg_session.execute(
        text("INSERT INTO hoi_thoai (ma_nguoi_dung) VALUES (:uid) RETURNING tieu_de"),
        {"uid": tao_nguoi_dung.id},
    ).fetchone()
    assert row[0] == "Cuộc hội thoại mới"


def test_b2_server_default_trang_thai(pg_session: Session, tao_nguoi_dung: User):
    """B2: Bỏ trống trang_thai khi INSERT SQL: PostgreSQL tự đặt 'PENDING'."""
    ht_id = pg_session.execute(
        text("INSERT INTO hoi_thoai (ma_nguoi_dung) VALUES (:uid) RETURNING ma_hoi_thoai"),
        {"uid": tao_nguoi_dung.id},
    ).scalar()

    row = pg_session.execute(
        text("INSERT INTO lan_xu_ly (ma_hoi_thoai) VALUES (:ht_id) RETURNING trang_thai"),
        {"ht_id": ht_id},
    ).fetchone()
    assert row[0] == "PENDING"


def test_b3_server_default_timestamps(pg_session: Session, tao_nguoi_dung: User):
    """B3: Bỏ trống timestamps: PostgreSQL tự tạo giá trị CURRENT_TIMESTAMP hợp lệ."""
    row = pg_session.execute(
        text("INSERT INTO hoi_thoai (ma_nguoi_dung) VALUES (:uid) RETURNING thoi_gian_tao, thoi_gian_cap_nhat"),
        {"uid": tao_nguoi_dung.id},
    ).fetchone()
    assert row[0] is not None
    assert row[1] is not None


def test_b4_timestamptz_and_timezone_handling(pg_session: Session, tao_nguoi_dung: User):
    """B4: Kiểm tra cột TIMESTAMPTZ trả về datetime có timezone trong PostgreSQL."""
    row = pg_session.execute(
        text("INSERT INTO hoi_thoai (ma_nguoi_dung) VALUES (:uid) RETURNING thoi_gian_tao"),
        {"uid": tao_nguoi_dung.id},
    ).fetchone()
    dt = row[0]
    assert dt.tzinfo is not None


def test_b5_optional_run_timestamps_are_null_by_default(pg_session: Session, tao_nguoi_dung: User):
    """B5: Xác nhận thoi_gian_bat_dau và thoi_gian_hoan_tat mặc định NULL khi không cung cấp."""
    ht_id = pg_session.execute(
        text("INSERT INTO hoi_thoai (ma_nguoi_dung) VALUES (:uid) RETURNING ma_hoi_thoai"),
        {"uid": tao_nguoi_dung.id},
    ).scalar()

    row = pg_session.execute(
        text("INSERT INTO lan_xu_ly (ma_hoi_thoai) VALUES (:ht_id) RETURNING thoi_gian_bat_dau, thoi_gian_hoan_tat"),
        {"ht_id": ht_id},
    ).fetchone()
    assert row[0] is None
    assert row[1] is None


# ============================================================================
# TEST GROUP C — POSTGRESQL CONSTRAINTS
# ============================================================================

def test_c1_valid_hoi_thoai(pg_session: Session, tao_nguoi_dung: User):
    """C1: Tạo HoiThoai với User hợp lệ thành công."""
    ht = HoiThoai(ma_nguoi_dung=tao_nguoi_dung.id)
    pg_session.add(ht)
    pg_session.commit()
    assert ht.ma_hoi_thoai > 0


def test_c2_reject_hoi_thoai_nonexistent_user(pg_session: Session):
    """C2: PostgreSQL FK từ chối HoiThoai tham chiếu User không tồn tại."""
    ht = HoiThoai(ma_nguoi_dung=999999)
    pg_session.add(ht)
    with pytest.raises(IntegrityError) as exc_info:
        pg_session.commit()
    assert "fk_hoi_thoai_ma_nguoi_dung" in str(exc_info.value)
    pg_session.rollback()


def test_c3_valid_tin_nhan_roles(pg_session: Session, tao_nguoi_dung: User):
    """C3: Chấp nhận vai trò USER, ASSISTANT, SYSTEM."""
    ht = HoiThoai(ma_nguoi_dung=tao_nguoi_dung.id)
    pg_session.add(ht)
    pg_session.commit()

    for role in ("USER", "ASSISTANT", "SYSTEM"):
        tn = TinNhan(ma_hoi_thoai=ht.ma_hoi_thoai, vai_tro=role, noi_dung=f"Msg {role}")
        pg_session.add(tn)
    pg_session.commit()

    roles = pg_session.scalars(select(TinNhan.vai_tro).where(TinNhan.ma_hoi_thoai == ht.ma_hoi_thoai)).all()
    assert set(roles) == {"USER", "ASSISTANT", "SYSTEM"}


def test_c4_reject_invalid_vai_tro(pg_session: Session, tao_nguoi_dung: User):
    """C4: PostgreSQL CHECK ck_tin_nhan_vai_tro từ chối vai trò không hợp lệ."""
    ht = HoiThoai(ma_nguoi_dung=tao_nguoi_dung.id)
    pg_session.add(ht)
    pg_session.commit()

    tn = TinNhan(ma_hoi_thoai=ht.ma_hoi_thoai, vai_tro="HACKER", noi_dung="Bad role")
    pg_session.add(tn)
    with pytest.raises(IntegrityError) as exc_info:
        pg_session.commit()
    assert "ck_tin_nhan_vai_tro" in str(exc_info.value)
    pg_session.rollback()


def test_c5_reject_tin_nhan_nonexistent_hoi_thoai(pg_session: Session):
    """C5: PostgreSQL FK từ chối TinNhan tham chiếu HoiThoai không tồn tại."""
    tn = TinNhan(ma_hoi_thoai=999999, vai_tro="USER", noi_dung="No conversation")
    pg_session.add(tn)
    with pytest.raises(IntegrityError) as exc_info:
        pg_session.commit()
    assert "fk_tin_nhan_ma_hoi_thoai" in str(exc_info.value)
    pg_session.rollback()


def test_c6_valid_lan_xu_ly_with_input_message(pg_session: Session, tao_nguoi_dung: User):
    """C6: Tạo LanXuLy với input message hợp lệ cùng hội thoại."""
    ht = HoiThoai(ma_nguoi_dung=tao_nguoi_dung.id)
    pg_session.add(ht)
    pg_session.commit()

    tn = TinNhan(ma_hoi_thoai=ht.ma_hoi_thoai, vai_tro="USER", noi_dung="Prompt")
    pg_session.add(tn)
    pg_session.commit()

    lx = LanXuLy(ma_hoi_thoai=ht.ma_hoi_thoai, ma_tin_nhan_dau_vao=tn.ma_tin_nhan)
    pg_session.add(lx)
    pg_session.commit()
    assert lx.ma_lan_xu_ly > 0
    assert lx.ma_tin_nhan_dau_vao == tn.ma_tin_nhan


def test_c7_valid_lan_xu_ly_with_null_input_message(pg_session: Session, tao_nguoi_dung: User):
    """C7: Tạo LanXuLy với input message NULL thành công."""
    ht = HoiThoai(ma_nguoi_dung=tao_nguoi_dung.id)
    pg_session.add(ht)
    pg_session.commit()

    lx = LanXuLy(ma_hoi_thoai=ht.ma_hoi_thoai, ma_tin_nhan_dau_vao=None)
    pg_session.add(lx)
    pg_session.commit()
    assert lx.ma_lan_xu_ly > 0
    assert lx.ma_tin_nhan_dau_vao is None


def test_c8_reject_nonexistent_input_message(pg_session: Session, tao_nguoi_dung: User):
    """C8: Từ chối LanXuLy tham chiếu tin nhắn đầu vào không tồn tại."""
    ht = HoiThoai(ma_nguoi_dung=tao_nguoi_dung.id)
    pg_session.add(ht)
    pg_session.commit()

    lx = LanXuLy(ma_hoi_thoai=ht.ma_hoi_thoai, ma_tin_nhan_dau_vao=999999)
    pg_session.add(lx)
    with pytest.raises(IntegrityError) as exc_info:
        pg_session.commit()
    assert "fk_lan_xu_ly_tin_nhan_dau_vao" in str(exc_info.value)
    pg_session.rollback()


def test_c9_reject_cross_conversation_message_reference(pg_session: Session, tao_nguoi_dung: User):
    """C9: COMPOSITE FK ENFORCEMENT: Từ chối Run của hội thoại A trỏ tin nhắn của hội thoại B."""
    ht_a = HoiThoai(ma_nguoi_dung=tao_nguoi_dung.id, tieu_de="HT A")
    ht_b = HoiThoai(ma_nguoi_dung=tao_nguoi_dung.id, tieu_de="HT B")
    pg_session.add_all([ht_a, ht_b])
    pg_session.commit()

    tn_b = TinNhan(ma_hoi_thoai=ht_b.ma_hoi_thoai, vai_tro="USER", noi_dung="Msg in B")
    pg_session.add(tn_b)
    pg_session.commit()

    # LanXuLy thuộc HT A nhưng trỏ tới tin nhắn thuộc HT B
    lx_a = LanXuLy(ma_hoi_thoai=ht_a.ma_hoi_thoai, ma_tin_nhan_dau_vao=tn_b.ma_tin_nhan)
    pg_session.add(lx_a)
    with pytest.raises(IntegrityError) as exc_info:
        pg_session.commit()
    assert "fk_lan_xu_ly_tin_nhan_dau_vao" in str(exc_info.value)
    pg_session.rollback()


def test_c10_multiple_runs_referencing_same_message(pg_session: Session, tao_nguoi_dung: User):
    """C10: Chấp nhận nhiều Run tham chiếu cùng một TinNhan."""
    ht = HoiThoai(ma_nguoi_dung=tao_nguoi_dung.id)
    pg_session.add(ht)
    pg_session.commit()

    tn = TinNhan(ma_hoi_thoai=ht.ma_hoi_thoai, vai_tro="USER", noi_dung="Prompt")
    pg_session.add(tn)
    pg_session.commit()

    r1 = LanXuLy(ma_hoi_thoai=ht.ma_hoi_thoai, ma_tin_nhan_dau_vao=tn.ma_tin_nhan, trang_thai="FAILED")
    r2 = LanXuLy(ma_hoi_thoai=ht.ma_hoi_thoai, ma_tin_nhan_dau_vao=tn.ma_tin_nhan, trang_thai="COMPLETED")
    pg_session.add_all([r1, r2])
    pg_session.commit()
    assert r1.ma_lan_xu_ly != r2.ma_lan_xu_ly


def test_c11_valid_statuses(pg_session: Session, tao_nguoi_dung: User):
    """C11: Chấp nhận các trạng thái PENDING, RUNNING, COMPLETED, FAILED."""
    ht = HoiThoai(ma_nguoi_dung=tao_nguoi_dung.id)
    pg_session.add(ht)
    pg_session.commit()

    for st in ("PENDING", "RUNNING", "COMPLETED", "FAILED"):
        lx = LanXuLy(ma_hoi_thoai=ht.ma_hoi_thoai, trang_thai=st)
        pg_session.add(lx)
    pg_session.commit()

    statuses = pg_session.scalars(select(LanXuLy.trang_thai).where(LanXuLy.ma_hoi_thoai == ht.ma_hoi_thoai)).all()
    assert set(statuses) == {"PENDING", "RUNNING", "COMPLETED", "FAILED"}


def test_c12_reject_invalid_status(pg_session: Session, tao_nguoi_dung: User):
    """C12: CHECK ck_lan_xu_ly_trang_thai từ chối trạng thái không hợp lệ."""
    ht = HoiThoai(ma_nguoi_dung=tao_nguoi_dung.id)
    pg_session.add(ht)
    pg_session.commit()

    lx = LanXuLy(ma_hoi_thoai=ht.ma_hoi_thoai, trang_thai="CANCELLED")
    pg_session.add(lx)
    with pytest.raises(IntegrityError) as exc_info:
        pg_session.commit()
    assert "ck_lan_xu_ly_trang_thai" in str(exc_info.value)
    pg_session.rollback()


def test_c13_reject_finish_time_earlier_than_start_time(pg_session: Session, tao_nguoi_dung: User):
    """C13: CHECK ck_lan_xu_ly_thoi_gian từ chối thời gian kết thúc sớm hơn bắt đầu."""
    ht = HoiThoai(ma_nguoi_dung=tao_nguoi_dung.id)
    pg_session.add(ht)
    pg_session.commit()

    now = datetime.now(timezone.utc)
    lx = LanXuLy(
        ma_hoi_thoai=ht.ma_hoi_thoai,
        thoi_gian_bat_dau=now,
        thoi_gian_hoan_tat=now - timedelta(minutes=10),
    )
    pg_session.add(lx)
    with pytest.raises(IntegrityError) as exc_info:
        pg_session.commit()
    assert "ck_lan_xu_ly_thoi_gian" in str(exc_info.value)
    pg_session.rollback()


def test_c14_accept_finish_time_equal_or_later(pg_session: Session, tao_nguoi_dung: User):
    """C14: Chấp nhận thời gian kết thúc bằng hoặc muộn hơn thời gian bắt đầu (độc lập 2 runs)."""
    ht = HoiThoai(ma_nguoi_dung=tao_nguoi_dung.id)
    pg_session.add(ht)
    pg_session.commit()

    now = datetime.now(timezone.utc)

    # 1. Trường hợp thời gian kết thúc BẰNG thời gian bắt đầu
    lx_equal = LanXuLy(
        ma_hoi_thoai=ht.ma_hoi_thoai,
        thoi_gian_bat_dau=now,
        thoi_gian_hoan_tat=now,
    )
    pg_session.add(lx_equal)
    pg_session.commit()
    assert lx_equal.ma_lan_xu_ly > 0
    assert lx_equal.thoi_gian_hoan_tat == lx_equal.thoi_gian_bat_dau

    # 2. Trường hợp thời gian kết thúc MUỘN HƠN thời gian bắt đầu
    lx_later = LanXuLy(
        ma_hoi_thoai=ht.ma_hoi_thoai,
        thoi_gian_bat_dau=now,
        thoi_gian_hoan_tat=now + timedelta(seconds=10),
    )
    pg_session.add(lx_later)
    pg_session.commit()
    assert lx_later.ma_lan_xu_ly > 0
    assert lx_later.ma_lan_xu_ly != lx_equal.ma_lan_xu_ly
    assert lx_later.thoi_gian_hoan_tat > lx_later.thoi_gian_bat_dau


def test_c15_not_null_columns_enforcement(pg_session: Session, tao_nguoi_dung: User):
    """C15: Từ chối giá trị NULL ở các cột bắt buộc (xác minh SQLSTATE 23502 và cột noi_dung)."""
    ht = HoiThoai(ma_nguoi_dung=tao_nguoi_dung.id)
    pg_session.add(ht)
    pg_session.commit()

    tn = TinNhan(ma_hoi_thoai=ht.ma_hoi_thoai, vai_tro="USER", noi_dung=None)
    pg_session.add(tn)
    with pytest.raises(IntegrityError) as exc_info:
        pg_session.commit()

    # Xác minh SQLSTATE 23502 (NOT NULL violation)
    orig_err = getattr(exc_info.value, "orig", None)
    sqlstate = getattr(orig_err, "sqlstate", None) or getattr(orig_err, "pgcode", None)
    if sqlstate is not None:
        assert sqlstate == "23502"
    else:
        assert "23502" in str(exc_info.value) or "NotNullViolation" in str(exc_info.value)

    # Xác minh cột vi phạm là noi_dung
    diag = getattr(orig_err, "diag", None)
    col_name = getattr(diag, "column_name", None)
    if col_name is not None:
        assert col_name == "noi_dung"
    else:
        assert "noi_dung" in str(exc_info.value)

    pg_session.rollback()


def test_c16_foreign_key_no_action_prevents_parent_delete(pg_session: Session, tao_nguoi_dung: User):
    """C16: ON DELETE NO ACTION ngăn chặn xóa bảng cha khi bảng con còn tham chiếu."""
    ht = HoiThoai(ma_nguoi_dung=tao_nguoi_dung.id)
    pg_session.add(ht)
    pg_session.commit()

    tn = TinNhan(ma_hoi_thoai=ht.ma_hoi_thoai, vai_tro="USER", noi_dung="Child message")
    pg_session.add(tn)
    pg_session.commit()

    # Lệnh DELETE SQL trực tiếp vào bảng cha bị chặn
    with pytest.raises(IntegrityError) as exc_info:
        pg_session.execute(text(f"DELETE FROM hoi_thoai WHERE ma_hoi_thoai = {ht.ma_hoi_thoai}"))
        pg_session.commit()
    assert "fk_tin_nhan_ma_hoi_thoai" in str(exc_info.value)
    pg_session.rollback()


# ============================================================================
# TEST GROUP D — TRANSACTION BEHAVIOR
# ============================================================================

def test_d1_data_visible_after_savepoint_commit(pg_session: Session, tao_nguoi_dung: User):
    """D1: Dữ liệu commit vào Savepoint nhìn thấy được trong cùng test transaction."""
    ht = HoiThoai(ma_nguoi_dung=tao_nguoi_dung.id, tieu_de="Visible Savepoint")
    pg_session.add(ht)
    pg_session.commit()

    fetched = pg_session.get(HoiThoai, ht.ma_hoi_thoai)
    assert fetched is not None
    assert fetched.tieu_de == "Visible Savepoint"


def test_d2_rollback_discards_uncommitted_savepoint_changes(pg_session: Session, tao_nguoi_dung: User):
    """D2: Rollback loại bỏ các thay đổi chưa được commit vào savepoint."""
    ht = HoiThoai(ma_nguoi_dung=tao_nguoi_dung.id, tieu_de="Will Rollback")
    pg_session.add(ht)
    pg_session.flush()
    ht_id = ht.ma_hoi_thoai
    pg_session.rollback()

    assert pg_session.get(HoiThoai, ht_id) is None


def test_d3_session_operates_normally_after_integrity_error_and_rollback(pg_session: Session, tao_nguoi_dung: User):
    """D3: Sau IntegrityError và rollback về savepoint, Session tiếp tục thực hiện lệnh hợp lệ."""
    bad_ht = HoiThoai(ma_nguoi_dung=999999)
    pg_session.add(bad_ht)
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()

    # Lệnh hợp lệ ngay sau rollback
    good_ht = HoiThoai(ma_nguoi_dung=tao_nguoi_dung.id, tieu_de="Good HT")
    pg_session.add(good_ht)
    pg_session.commit()
    assert good_ht.ma_hoi_thoai > 0


def test_d4_data_does_not_persist_after_outer_transaction_rollback():
    """D4: Xác minh dữ liệu tạo trong outer transaction được dọn dẹp sạch sẽ sau khi rollback."""
    # 1. Đếm số lượng ban đầu
    with postgres_test_engine.connect() as conn:
        count_before = conn.execute(text("SELECT count(*) FROM hoi_thoai")).scalar()

    # 2. Tạo một transaction riêng và commit savepoint bên trong
    conn = postgres_test_engine.connect()
    trans = conn.begin()
    sess = Session(bind=conn, join_transaction_mode="create_savepoint")
    try:
        u = User(email="outer_test@example.com", password_hash="h", name="Outer", role="USER")
        sess.add(u)
        sess.commit()

        ht = HoiThoai(ma_nguoi_dung=u.id, tieu_de="Outer Check")
        sess.add(ht)
        sess.commit()
        assert ht.ma_hoi_thoai > 0
    finally:
        sess.close()
        trans.rollback()
        conn.close()

    # 3. Đếm số lượng sau rollback outer transaction: bảo đảm không đổi
    with postgres_test_engine.connect() as conn:
        count_after = conn.execute(text("SELECT count(*) FROM hoi_thoai")).scalar()
        assert count_after == count_before


def test_d5_test_isolation_independence(pg_session: Session, tao_nguoi_dung: User):
    """D5: Kiểm tra tính độc lập: không phụ thuộc thứ tự chạy và không bị ảnh hưởng bởi dữ liệu từ test khác."""
    # 1. Xác minh ban đầu trong session này không thấy bất kỳ hội thoại nào từ các test trước
    existing_count = pg_session.execute(text("SELECT count(*) FROM hoi_thoai")).scalar()
    assert existing_count == 0, f"Phát hiện rò rỉ dữ liệu ngoài mong muốn: {existing_count} bản ghi"

    # 2. Tạo dữ liệu độc lập
    ht = HoiThoai(ma_nguoi_dung=tao_nguoi_dung.id, tieu_de="Test D5 Isolated")
    pg_session.add(ht)
    pg_session.commit()

    # 3. Xác minh chỉ có duy nhất 1 bản ghi vừa tạo được nhìn thấy trong session
    hts = pg_session.scalars(select(HoiThoai)).all()
    assert len(hts) == 1
    assert hts[0].ma_hoi_thoai == ht.ma_hoi_thoai
    assert hts[0].tieu_de == "Test D5 Isolated"


# ============================================================================
# TEST GROUP E — DATA INTEGRITY & STRUCTURAL ISOLATION
# ============================================================================

def test_e1_e2_e3_e4_two_users_structural_isolation(pg_session: Session):
    """
    E1-E4: Xác minh tính toàn vẹn dữ liệu và phân tách cấu trúc giữa User A và User B.

    Bao gồm:
    - User A và B có hội thoại, tin nhắn và runs riêng.
    - Composite FK ngăn chặn Run của User A trỏ vào tin nhắn của User B.
    - Truy vấn lọc theo owner trả về chính xác ID của từng User (cả User A và User B đối xứng).

    LƯU Ý: Đây là kiểm chứng tính toàn vẹn database (Database Integrity) và lọc SQL.
    Không đại diện cho API Authorization Guard (thuộc Phase 4C).
    """
    u_a = User(email="ua_pg@example.com", password_hash="ha", name="User A", role="USER")
    u_b = User(email="ub_pg@example.com", password_hash="hb", name="User B", role="USER")
    pg_session.add_all([u_a, u_b])
    pg_session.commit()

    ht_a1 = HoiThoai(ma_nguoi_dung=u_a.id, tieu_de="A1")
    ht_a2 = HoiThoai(ma_nguoi_dung=u_a.id, tieu_de="A2")
    ht_b1 = HoiThoai(ma_nguoi_dung=u_b.id, tieu_de="B1")
    pg_session.add_all([ht_a1, ht_a2, ht_b1])
    pg_session.commit()

    tn_a1 = TinNhan(ma_hoi_thoai=ht_a1.ma_hoi_thoai, vai_tro="USER", noi_dung="Msg A1")
    tn_b1 = TinNhan(ma_hoi_thoai=ht_b1.ma_hoi_thoai, vai_tro="USER", noi_dung="Msg B1")
    pg_session.add_all([tn_a1, tn_b1])
    pg_session.flush()

    # Run của User A trỏ tin nhắn A1
    lx_a1 = LanXuLy(ma_hoi_thoai=ht_a1.ma_hoi_thoai, ma_tin_nhan_dau_vao=tn_a1.ma_tin_nhan)
    # Run của User B trỏ tin nhắn B1
    lx_b1 = LanXuLy(ma_hoi_thoai=ht_b1.ma_hoi_thoai, ma_tin_nhan_dau_vao=tn_b1.ma_tin_nhan)
    pg_session.add_all([lx_a1, lx_b1])
    pg_session.commit()

    # Composite FK chặn Run của A trỏ vào tin nhắn của B
    bad_run_a = LanXuLy(ma_hoi_thoai=ht_a2.ma_hoi_thoai, ma_tin_nhan_dau_vao=tn_b1.ma_tin_nhan)
    pg_session.add(bad_run_a)
    with pytest.raises(IntegrityError) as exc_info:
        pg_session.commit()
    assert "fk_lan_xu_ly_tin_nhan_dau_vao" in str(exc_info.value)
    pg_session.rollback()

    # 1. Truy vấn lọc theo User A
    ht_a_ids = set(pg_session.scalars(select(HoiThoai.ma_hoi_thoai).where(HoiThoai.ma_nguoi_dung == u_a.id)).all())
    assert ht_a_ids == {ht_a1.ma_hoi_thoai, ht_a2.ma_hoi_thoai}
    assert ht_b1.ma_hoi_thoai not in ht_a_ids

    tn_a_ids = set(pg_session.scalars(select(TinNhan.ma_tin_nhan).join(HoiThoai).where(HoiThoai.ma_nguoi_dung == u_a.id)).all())
    assert tn_a_ids == {tn_a1.ma_tin_nhan}
    assert tn_b1.ma_tin_nhan not in tn_a_ids

    lx_a_ids = set(pg_session.scalars(select(LanXuLy.ma_lan_xu_ly).join(HoiThoai).where(HoiThoai.ma_nguoi_dung == u_a.id)).all())
    assert lx_a_ids == {lx_a1.ma_lan_xu_ly}
    assert lx_b1.ma_lan_xu_ly not in lx_a_ids

    # 2. Truy vấn lọc theo User B (đối xứng)
    ht_b_ids = set(pg_session.scalars(select(HoiThoai.ma_hoi_thoai).where(HoiThoai.ma_nguoi_dung == u_b.id)).all())
    assert ht_b_ids == {ht_b1.ma_hoi_thoai}
    assert ht_a1.ma_hoi_thoai not in ht_b_ids
    assert ht_a2.ma_hoi_thoai not in ht_b_ids

    tn_b_ids = set(pg_session.scalars(select(TinNhan.ma_tin_nhan).join(HoiThoai).where(HoiThoai.ma_nguoi_dung == u_b.id)).all())
    assert tn_b_ids == {tn_b1.ma_tin_nhan}
    assert tn_a1.ma_tin_nhan not in tn_b_ids

    lx_b_ids = set(pg_session.scalars(select(LanXuLy.ma_lan_xu_ly).join(HoiThoai).where(HoiThoai.ma_nguoi_dung == u_b.id)).all())
    assert lx_b_ids == {lx_b1.ma_lan_xu_ly}
    assert lx_a1.ma_lan_xu_ly not in lx_b_ids
