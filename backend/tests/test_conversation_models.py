"""
CAPONE-30 — Phase 4A: SQLite Model Tests for HoiThoai, TinNhan, and LanXuLy.

Kiểm thử cấu trúc mô hình, ràng buộc dữ liệu, quan hệ ORM, lifecycle transaction
và cô lập dữ liệu người dùng trên môi trường SQLite In-Memory với PRAGMA foreign_keys=ON.
"""
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
import warnings
import pytest
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.exc import IntegrityError, SAWarning
from sqlalchemy.orm import Session, configure_mappers, sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, HoiThoai, LanXuLy, TinNhan, User


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sqlite_fk_engine():
    """
    Tạo engine SQLite In-Memory độc lập với PRAGMA foreign_keys=ON.
    Đảm bảo 100% ràng buộc khóa ngoại và check constraints được thực thi.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _bat_khoa_ngoai_sqlite(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Xác minh PRAGMA foreign_keys đã kích hoạt
    with engine.connect() as conn:
        fk_status = conn.execute(text("PRAGMA foreign_keys")).scalar()
        assert fk_status == 1, f"Không thể bật PRAGMA foreign_keys trên SQLite, kết quả: {fk_status}"

    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db(sqlite_fk_engine) -> Generator[Session, None, None]:
    """
    Cung cấp session cô lập cho từng test case.
    """
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=sqlite_fk_engine,
    )
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def nguoi_dung_mau(db: Session) -> User:
    """
    Tạo người dùng mẫu đáp ứng các trường bắt buộc của User model.
    """
    user = User(
        email="user_test@example.com",
        password_hash="hashed_password_sample",
        name="Người Dùng Mẫu",
        role="USER",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Test Group A — Model Structure
# ---------------------------------------------------------------------------

def test_a1_a2_a3_models_registered_in_metadata():
    """A1-A3: Kiểm tra ba model HoiThoai, TinNhan, LanXuLy được đăng ký trong Base.metadata."""
    tables = Base.metadata.tables
    assert "hoi_thoai" in tables
    assert "tin_nhan" in tables
    assert "lan_xu_ly" in tables


def test_a4_a5_table_names_columns_and_pks():
    """A4-A5: Kiểm tra đúng tên bảng, cột, khóa chính tiếng Việt không dấu, không có cột 'id'."""
    tables = Base.metadata.tables

    # hoi_thoai
    ht_cols = tables["hoi_thoai"].columns
    assert "ma_hoi_thoai" in ht_cols
    assert "id" not in ht_cols
    assert ht_cols["ma_hoi_thoai"].primary_key is True

    # tin_nhan
    tn_cols = tables["tin_nhan"].columns
    assert "ma_tin_nhan" in tn_cols
    assert "id" not in tn_cols
    assert tn_cols["ma_tin_nhan"].primary_key is True

    # lan_xu_ly
    lx_cols = tables["lan_xu_ly"].columns
    assert "ma_lan_xu_ly" in lx_cols
    assert "id" not in lx_cols
    assert lx_cols["ma_lan_xu_ly"].primary_key is True


def test_a6_constraints_definition():
    """A6: Kiểm tra định nghĩa đầy đủ các ràng buộc FK, UNIQUE và CHECK về tên, cột và đích tham chiếu."""
    from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint

    tables = Base.metadata.tables

    # 1. hoi_thoai constraints
    ht_fks = [c for c in tables["hoi_thoai"].constraints if isinstance(c, ForeignKeyConstraint)]
    assert len(ht_fks) == 1
    fk_ht = ht_fks[0]
    assert fk_ht.name == "fk_hoi_thoai_ma_nguoi_dung"
    assert [col.name for col in fk_ht.columns] == ["ma_nguoi_dung"]
    assert [el.target_fullname for el in fk_ht.elements] == ["users.id"]

    # 2. tin_nhan constraints
    tn_constraints = {c.name: c for c in tables["tin_nhan"].constraints}

    # FK tin_nhan -> hoi_thoai
    assert "fk_tin_nhan_ma_hoi_thoai" in tn_constraints
    fk_tn = tn_constraints["fk_tin_nhan_ma_hoi_thoai"]
    assert isinstance(fk_tn, ForeignKeyConstraint)
    assert [col.name for col in fk_tn.columns] == ["ma_hoi_thoai"]
    assert [el.target_fullname for el in fk_tn.elements] == ["hoi_thoai.ma_hoi_thoai"]

    # UNIQUE tin_nhan(ma_tin_nhan, ma_hoi_thoai)
    assert "uq_tin_nhan_ma_tin_nhan_ma_hoi_thoai" in tn_constraints
    uq_tn = tn_constraints["uq_tin_nhan_ma_tin_nhan_ma_hoi_thoai"]
    assert isinstance(uq_tn, UniqueConstraint)
    assert [col.name for col in uq_tn.columns] == ["ma_tin_nhan", "ma_hoi_thoai"]

    # CHECK vai_tro
    assert "ck_tin_nhan_vai_tro" in tn_constraints
    ck_tn = tn_constraints["ck_tin_nhan_vai_tro"]
    assert isinstance(ck_tn, CheckConstraint)
    assert str(ck_tn.sqltext) == "vai_tro IN ('USER', 'ASSISTANT', 'SYSTEM')"

    # 3. lan_xu_ly constraints
    lx_constraints = {c.name: c for c in tables["lan_xu_ly"].constraints}

    # FK đơn lan_xu_ly -> hoi_thoai
    assert "fk_lan_xu_ly_ma_hoi_thoai" in lx_constraints
    fk_lx_ht = lx_constraints["fk_lan_xu_ly_ma_hoi_thoai"]
    assert isinstance(fk_lx_ht, ForeignKeyConstraint)
    assert [col.name for col in fk_lx_ht.columns] == ["ma_hoi_thoai"]
    assert [el.target_fullname for el in fk_lx_ht.elements] == ["hoi_thoai.ma_hoi_thoai"]

    # FK kết hợp lan_xu_ly(ma_tin_nhan_dau_vao, ma_hoi_thoai) -> tin_nhan(ma_tin_nhan, ma_hoi_thoai)
    assert "fk_lan_xu_ly_tin_nhan_dau_vao" in lx_constraints
    fk_lx_comp = lx_constraints["fk_lan_xu_ly_tin_nhan_dau_vao"]
    assert isinstance(fk_lx_comp, ForeignKeyConstraint)
    assert [col.name for col in fk_lx_comp.columns] == ["ma_tin_nhan_dau_vao", "ma_hoi_thoai"]
    assert [el.target_fullname for el in fk_lx_comp.elements] == ["tin_nhan.ma_tin_nhan", "tin_nhan.ma_hoi_thoai"]

    # CHECK trang_thai
    assert "ck_lan_xu_ly_trang_thai" in lx_constraints
    ck_lx_status = lx_constraints["ck_lan_xu_ly_trang_thai"]
    assert isinstance(ck_lx_status, CheckConstraint)
    assert str(ck_lx_status.sqltext) == "trang_thai IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')"

    # CHECK thoi_gian
    assert "ck_lan_xu_ly_thoi_gian" in lx_constraints
    ck_lx_time = lx_constraints["ck_lan_xu_ly_thoi_gian"]
    assert isinstance(ck_lx_time, CheckConstraint)
    assert str(ck_lx_time.sqltext) == "thoi_gian_hoan_tat IS NULL OR thoi_gian_bat_dau IS NULL OR thoi_gian_hoan_tat >= thoi_gian_bat_dau"


def test_a7_indexes_definition():
    """A7: Kiểm tra định nghĩa các indexes cần thiết."""
    tables = Base.metadata.tables

    ht_indexes = [idx.name for idx in tables["hoi_thoai"].indexes]
    assert "ix_hoi_thoai_ma_nguoi_dung" in ht_indexes

    tn_indexes = [idx.name for idx in tables["tin_nhan"].indexes]
    assert "ix_tin_nhan_ma_hoi_thoai" in tn_indexes

    lx_indexes = [idx.name for idx in tables["lan_xu_ly"].indexes]
    assert "ix_lan_xu_ly_ma_hoi_thoai" in lx_indexes
    assert "ix_lan_xu_ly_ma_tin_nhan_dau_vao" in lx_indexes


def test_a8_no_orm_cascade_delete():
    """A8: Kiểm tra tuyệt đối không có ORM delete cascade hoặc delete-orphan."""
    from sqlalchemy.inspection import inspect

    for model_cls in (HoiThoai, TinNhan, LanXuLy):
        mapper = inspect(model_cls)
        for rel in mapper.relationships:
            cascade = rel.cascade
            assert "delete" not in cascade, f"{model_cls.__name__}.{rel.key} có cascade delete"
            assert "delete-orphan" not in cascade, f"{model_cls.__name__}.{rel.key} có cascade delete-orphan"


# ---------------------------------------------------------------------------
# Test Group B — Valid Data
# ---------------------------------------------------------------------------

def test_b1_create_valid_user_and_hoi_thoai(db: Session, nguoi_dung_mau: User):
    """B1: Tạo User hợp lệ và HoiThoai thuộc User đó."""
    ht = HoiThoai(ma_nguoi_dung=nguoi_dung_mau.id)
    db.add(ht)
    db.commit()
    db.refresh(ht)

    assert ht.ma_hoi_thoai is not None
    assert ht.ma_hoi_thoai > 0
    assert ht.ma_nguoi_dung == nguoi_dung_mau.id


def test_b2_create_multiple_tin_nhan(db: Session, nguoi_dung_mau: User):
    """B2: Tạo nhiều TinNhan thuộc cùng một HoiThoai."""
    ht = HoiThoai(ma_nguoi_dung=nguoi_dung_mau.id)
    db.add(ht)
    db.commit()

    tn1 = TinNhan(ma_hoi_thoai=ht.ma_hoi_thoai, vai_tro="USER", noi_dung="Tin nhắn 1")
    tn2 = TinNhan(ma_hoi_thoai=ht.ma_hoi_thoai, vai_tro="ASSISTANT", noi_dung="Tin nhắn 2")
    tn3 = TinNhan(ma_hoi_thoai=ht.ma_hoi_thoai, vai_tro="USER", noi_dung="Tin nhắn 3")
    db.add_all([tn1, tn2, tn3])
    db.commit()

    assert len({tn1.ma_tin_nhan, tn2.ma_tin_nhan, tn3.ma_tin_nhan}) == 3
    assert tn1.ma_hoi_thoai == tn2.ma_hoi_thoai == tn3.ma_hoi_thoai == ht.ma_hoi_thoai


def test_b3_valid_vai_tro_values(db: Session, nguoi_dung_mau: User):
    """B3: Kiểm tra 3 giá trị vai trò hợp lệ: USER, ASSISTANT, SYSTEM."""
    ht = HoiThoai(ma_nguoi_dung=nguoi_dung_mau.id)
    db.add(ht)
    db.commit()

    for role in ("USER", "ASSISTANT", "SYSTEM"):
        msg = TinNhan(ma_hoi_thoai=ht.ma_hoi_thoai, vai_tro=role, noi_dung=f"Nội dung {role}")
        db.add(msg)
    db.commit()

    saved_roles = db.scalars(
        select(TinNhan.vai_tro).where(TinNhan.ma_hoi_thoai == ht.ma_hoi_thoai)
    ).all()
    assert set(saved_roles) == {"USER", "ASSISTANT", "SYSTEM"}


def test_b4_create_lan_xu_ly_with_input_message(db: Session, nguoi_dung_mau: User):
    """B4: Tạo LanXuLy có input message hợp lệ cùng hội thoại."""
    ht = HoiThoai(ma_nguoi_dung=nguoi_dung_mau.id)
    db.add(ht)
    db.commit()

    tn = TinNhan(ma_hoi_thoai=ht.ma_hoi_thoai, vai_tro="USER", noi_dung="Câu hỏi người dùng")
    db.add(tn)
    db.commit()

    lx = LanXuLy(
        ma_hoi_thoai=ht.ma_hoi_thoai,
        ma_tin_nhan_dau_vao=tn.ma_tin_nhan,
        trang_thai="PENDING",
    )
    db.add(lx)
    db.commit()
    db.refresh(lx)

    assert lx.ma_lan_xu_ly is not None
    assert lx.ma_hoi_thoai == ht.ma_hoi_thoai
    assert lx.ma_tin_nhan_dau_vao == tn.ma_tin_nhan


def test_b5_create_lan_xu_ly_with_null_input_message(db: Session, nguoi_dung_mau: User):
    """B5: Tạo LanXuLy có input message bằng NULL."""
    ht = HoiThoai(ma_nguoi_dung=nguoi_dung_mau.id)
    db.add(ht)
    db.commit()

    lx = LanXuLy(
        ma_hoi_thoai=ht.ma_hoi_thoai,
        ma_tin_nhan_dau_vao=None,
        trang_thai="PENDING",
    )
    db.add(lx)
    db.commit()
    db.refresh(lx)

    assert lx.ma_lan_xu_ly is not None
    assert lx.ma_tin_nhan_dau_vao is None


def test_b6_one_message_referenced_by_multiple_runs(db: Session, nguoi_dung_mau: User):
    """B6: Một TinNhan có thể được tham chiếu bởi nhiều LanXuLy (ví dụ retry hoặc re-run)."""
    ht = HoiThoai(ma_nguoi_dung=nguoi_dung_mau.id)
    db.add(ht)
    db.commit()

    tn = TinNhan(ma_hoi_thoai=ht.ma_hoi_thoai, vai_tro="USER", noi_dung="Prompt gốc")
    db.add(tn)
    db.commit()

    run1 = LanXuLy(ma_hoi_thoai=ht.ma_hoi_thoai, ma_tin_nhan_dau_vao=tn.ma_tin_nhan, trang_thai="FAILED")
    run2 = LanXuLy(ma_hoi_thoai=ht.ma_hoi_thoai, ma_tin_nhan_dau_vao=tn.ma_tin_nhan, trang_thai="COMPLETED")
    db.add_all([run1, run2])
    db.commit()

    assert run1.ma_lan_xu_ly != run2.ma_lan_xu_ly
    assert run1.ma_tin_nhan_dau_vao == run2.ma_tin_nhan_dau_vao == tn.ma_tin_nhan


def test_b7_default_values(db: Session, nguoi_dung_mau: User):
    """B7: Kiểm tra các giá trị mặc định cho tiêu đề, trạng thái và thời gian tạo."""
    ht = HoiThoai(ma_nguoi_dung=nguoi_dung_mau.id)
    db.add(ht)
    db.commit()
    db.refresh(ht)

    assert ht.tieu_de == "Cuộc hội thoại mới"
    assert ht.thoi_gian_tao is not None
    assert ht.thoi_gian_cap_nhat is not None

    tn = TinNhan(ma_hoi_thoai=ht.ma_hoi_thoai, vai_tro="USER", noi_dung="Nội dung")
    db.add(tn)
    db.commit()
    db.refresh(tn)
    assert tn.thoi_gian_tao is not None

    lx = LanXuLy(ma_hoi_thoai=ht.ma_hoi_thoai)
    db.add(lx)
    db.commit()
    db.refresh(lx)
    assert lx.trang_thai == "PENDING"
    assert lx.thoi_gian_tao is not None
    assert lx.thoi_gian_bat_dau is None
    assert lx.thoi_gian_hoan_tat is None


def test_b8_orm_relationships(db: Session, nguoi_dung_mau: User):
    """B8: Kiểm tra điều hướng quan hệ ORM giữa User, HoiThoai, TinNhan và LanXuLy."""
    ht = HoiThoai(ma_nguoi_dung=nguoi_dung_mau.id)
    tn = TinNhan(hoi_thoai=ht, vai_tro="USER", noi_dung="Câu hỏi 1")
    lx = LanXuLy(hoi_thoai=ht, tin_nhan_dau_vao=tn)
    db.add_all([ht, tn, lx])
    db.commit()

    # Truy vấn lại từ session
    loaded_ht = db.get(HoiThoai, ht.ma_hoi_thoai)
    assert loaded_ht is not None
    assert loaded_ht.nguoi_dung.id == nguoi_dung_mau.id
    assert tn in loaded_ht.danh_sach_tin_nhan
    assert lx in loaded_ht.danh_sach_lan_xu_ly
    assert lx.tin_nhan_dau_vao == tn


def test_b9_tin_nhan_dau_vao_does_not_corrupt_ma_hoi_thoai(db: Session, nguoi_dung_mau: User):
    """B9: Gán tin_nhan_dau_vao không gây ghi đè sai ma_hoi_thoai."""
    ht = HoiThoai(ma_nguoi_dung=nguoi_dung_mau.id)
    db.add(ht)
    db.commit()

    tn = TinNhan(ma_hoi_thoai=ht.ma_hoi_thoai, vai_tro="USER", noi_dung="Test message")
    db.add(tn)
    db.commit()

    lx = LanXuLy(ma_hoi_thoai=ht.ma_hoi_thoai)
    lx.tin_nhan_dau_vao = tn
    db.add(lx)
    db.commit()
    db.refresh(lx)

    assert lx.ma_hoi_thoai == ht.ma_hoi_thoai
    assert lx.ma_tin_nhan_dau_vao == tn.ma_tin_nhan


# ---------------------------------------------------------------------------
# Test Group C — Invalid Data (Constraints Enforcement)
# ---------------------------------------------------------------------------

def test_c1_hoi_thoai_nonexistent_user(db: Session):
    """C1: Tạo HoiThoai với user_id không tồn tại -> bị FK từ chối."""
    ht = HoiThoai(ma_nguoi_dung=999999)
    db.add(ht)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_c2_tin_nhan_nonexistent_hoi_thoai(db: Session):
    """C2: Tạo TinNhan với ma_hoi_thoai không tồn tại -> bị FK từ chối."""
    tn = TinNhan(ma_hoi_thoai=999999, vai_tro="USER", noi_dung="No conversation")
    db.add(tn)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_c3_lan_xu_ly_nonexistent_hoi_thoai(db: Session):
    """C3: Tạo LanXuLy với ma_hoi_thoai không tồn tại -> bị FK từ chối."""
    lx = LanXuLy(ma_hoi_thoai=999999)
    db.add(lx)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_c4_lan_xu_ly_nonexistent_input_message(db: Session, nguoi_dung_mau: User):
    """C4: Tạo LanXuLy với ma_tin_nhan_dau_vao không tồn tại -> bị composite FK từ chối."""
    ht = HoiThoai(ma_nguoi_dung=nguoi_dung_mau.id)
    db.add(ht)
    db.commit()

    lx = LanXuLy(ma_hoi_thoai=ht.ma_hoi_thoai, ma_tin_nhan_dau_vao=999999)
    db.add(lx)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_c5_composite_fk_mismatch_different_conversation(db: Session, nguoi_dung_mau: User):
    """C5: TinNhan thuộc hội thoại B nhưng LanXuLy thuộc hội thoại A -> bị composite FK từ chối."""
    ht_a = HoiThoai(ma_nguoi_dung=nguoi_dung_mau.id, tieu_de="Hội thoại A")
    ht_b = HoiThoai(ma_nguoi_dung=nguoi_dung_mau.id, tieu_de="Hội thoại B")
    db.add_all([ht_a, ht_b])
    db.commit()

    # Tin nhắn thuộc hội thoại B
    tn_b = TinNhan(ma_hoi_thoai=ht_b.ma_hoi_thoai, vai_tro="USER", noi_dung="Tin nhắn trong B")
    db.add(tn_b)
    db.commit()

    # Lần xử lý thuộc hội thoại A, nhưng trỏ ma_tin_nhan_dau_vao vào tin nhắn của hội thoại B
    lx_a = LanXuLy(
        ma_hoi_thoai=ht_a.ma_hoi_thoai,
        ma_tin_nhan_dau_vao=tn_b.ma_tin_nhan,
        trang_thai="PENDING",
    )
    db.add(lx_a)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_c6_invalid_vai_tro_check_constraint(db: Session, nguoi_dung_mau: User):
    """C6: TinNhan có vai_tro ngoài USER/ASSISTANT/SYSTEM -> bị CHECK từ chối."""
    ht = HoiThoai(ma_nguoi_dung=nguoi_dung_mau.id)
    db.add(ht)
    db.commit()

    tn = TinNhan(ma_hoi_thoai=ht.ma_hoi_thoai, vai_tro="MODERATOR", noi_dung="Vai trò lạ")
    db.add(tn)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_c7_invalid_trang_thai_check_constraint(db: Session, nguoi_dung_mau: User):
    """C7: LanXuLy có trạng thái ngoài PENDING/RUNNING/COMPLETED/FAILED -> bị CHECK từ chối."""
    ht = HoiThoai(ma_nguoi_dung=nguoi_dung_mau.id)
    db.add(ht)
    db.commit()

    lx = LanXuLy(ma_hoi_thoai=ht.ma_hoi_thoai, trang_thai="UNKNOWN_STATUS")
    db.add(lx)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_c8_invalid_time_order_check_constraint(db: Session, nguoi_dung_mau: User):
    """C8: Thời gian hoàn tất sớm hơn thời gian bắt đầu -> bị CHECK từ chối."""
    ht = HoiThoai(ma_nguoi_dung=nguoi_dung_mau.id)
    db.add(ht)
    db.commit()

    now = datetime.now(timezone.utc)
    t_start = now
    t_finish_earlier = now - timedelta(hours=1)

    lx = LanXuLy(
        ma_hoi_thoai=ht.ma_hoi_thoai,
        thoi_gian_bat_dau=t_start,
        thoi_gian_hoan_tat=t_finish_earlier,
    )
    db.add(lx)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_c9_not_null_columns_reject_null(db: Session, nguoi_dung_mau: User):
    """C9: Các cột NOT NULL bắt buộc không chấp nhận NULL."""
    ht = HoiThoai(ma_nguoi_dung=nguoi_dung_mau.id)
    db.add(ht)
    db.commit()

    # TinNhan thiếu noi_dung
    tn_no_content = TinNhan(ma_hoi_thoai=ht.ma_hoi_thoai, vai_tro="USER", noi_dung=None)
    db.add(tn_no_content)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    # HoiThoai thiếu ma_nguoi_dung
    ht_no_user = HoiThoai(ma_nguoi_dung=None)
    db.add(ht_no_user)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_c10_delete_parent_blocked_by_foreign_key(db: Session, nguoi_dung_mau: User):
    """C10: DELETE parent khi child còn tham chiếu phải được FK ON DELETE NO ACTION ngăn chặn."""
    ht = HoiThoai(ma_nguoi_dung=nguoi_dung_mau.id)
    db.add(ht)
    db.commit()

    tn = TinNhan(ma_hoi_thoai=ht.ma_hoi_thoai, vai_tro="USER", noi_dung="Tin nhắn gắn liền")
    db.add(tn)
    db.commit()

    # Thực hiện lệnh DELETE trực tiếp qua SQL để kiểm tra ràng buộc database
    with pytest.raises(IntegrityError):
        db.execute(text(f"DELETE FROM hoi_thoai WHERE ma_hoi_thoai = {ht.ma_hoi_thoai}"))
        db.commit()
    db.rollback()


# ---------------------------------------------------------------------------
# Test Group D — Transaction & ORM
# ---------------------------------------------------------------------------

def test_d1_commit_persists_data(sqlite_fk_engine, nguoi_dung_mau: User):
    """D1: Commit thành công dữ liệu hợp lệ và đọc lại được từ session mới."""
    SessionLocal = sessionmaker(bind=sqlite_fk_engine)
    with SessionLocal() as session1:
        ht = HoiThoai(ma_nguoi_dung=nguoi_dung_mau.id, tieu_de="Cuộc trò chuyện đã commit")
        session1.add(ht)
        session1.commit()
        ht_id = ht.ma_hoi_thoai

    with SessionLocal() as session2:
        saved_ht = session2.get(HoiThoai, ht_id)
        assert saved_ht is not None
        assert saved_ht.tieu_de == "Cuộc trò chuyện đã commit"


def test_d2_rollback_discards_uncommitted_data(sqlite_fk_engine, nguoi_dung_mau: User):
    """D2: Rollback không giữ lại bản ghi chưa commit."""
    SessionLocal = sessionmaker(bind=sqlite_fk_engine)
    with SessionLocal() as session:
        ht = HoiThoai(ma_nguoi_dung=nguoi_dung_mau.id, tieu_de="Bản ghi chưa commit")
        session.add(ht)
        session.flush()
        ht_id = ht.ma_hoi_thoai
        session.rollback()

    with SessionLocal() as session:
        assert session.get(HoiThoai, ht_id) is None


def test_d3_session_operates_normally_after_rollback(db: Session, nguoi_dung_mau: User):
    """D3: Sau IntegrityError và rollback, Session có thể tiếp tục thao tác hợp lệ bình thường."""
    # Thao tác gây lỗi
    bad_ht = HoiThoai(ma_nguoi_dung=999999)
    db.add(bad_ht)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    # Thao tác hợp lệ ngay sau rollback
    good_ht = HoiThoai(ma_nguoi_dung=nguoi_dung_mau.id, tieu_de="Hội thoại thành công")
    db.add(good_ht)
    db.commit()
    db.refresh(good_ht)

    assert good_ht.ma_hoi_thoai is not None


def test_d4_configure_mappers_zero_warnings():
    """D4: configure_mappers() chạy từ tiến trình Python mới độc lập không phát sinh SAWarning nào."""
    import subprocess
    import sys

    # Chạy trong một process hoàn toàn mới để bắt SAWarning tại thời điểm cấu hình mapper ban đầu
    script = (
        "import sys, warnings\n"
        "from pathlib import Path\n"
        "sys.path.insert(0, '.')\n"
        "with warnings.catch_warnings(record=True) as recorded_warnings:\n"
        "    warnings.simplefilter('always')\n"
        "    from app.models import Base, HoiThoai, TinNhan, LanXuLy, User\n"
        "    from sqlalchemy.orm import configure_mappers\n"
        "    from sqlalchemy.exc import SAWarning\n"
        "    configure_mappers()\n"
        "    sa_warnings = [w for w in recorded_warnings if issubclass(w.category, SAWarning)]\n"
        "    if sa_warnings:\n"
        "        for w in sa_warnings:\n"
        "            print(f'SAWarning: {w.message}', file=sys.stderr)\n"
        "        sys.exit(1)\n"
    )

    res = subprocess.run(
        [sys.executable, "-B", "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"Phát hiện cảnh báo SQLAlchemy Mapper trong tiến trình mới: {res.stderr}"


def test_d5_one_to_many_collections(db: Session, nguoi_dung_mau: User):
    """D5: Kiểm tra quan hệ một-nhiều HoiThoai -> TinNhan và HoiThoai -> LanXuLy."""
    ht = HoiThoai(ma_nguoi_dung=nguoi_dung_mau.id)
    db.add(ht)
    db.commit()

    tn1 = TinNhan(hoi_thoai=ht, vai_tro="USER", noi_dung="A")
    tn2 = TinNhan(hoi_thoai=ht, vai_tro="ASSISTANT", noi_dung="B")
    lx1 = LanXuLy(hoi_thoai=ht)
    lx2 = LanXuLy(hoi_thoai=ht)
    db.add_all([tn1, tn2, lx1, lx2])
    db.commit()

    db.refresh(ht)
    assert len(ht.danh_sach_tin_nhan) == 2
    assert len(ht.danh_sach_lan_xu_ly) == 2


# ---------------------------------------------------------------------------
# Test Group E — Boundary / Isolation
# ---------------------------------------------------------------------------

def test_e1_user_isolation_structural_filtering(db: Session):
    """
    E1: Kiểm tra cấu trúc dữ liệu và truy vấn có điều kiện phân biệt rõ User A và User B.

    Bao gồm truy vấn HoiThoai, TinNhan và LanXuLy thông qua quan hệ với HoiThoai của từng User,
    xác nhận đúng ID và xác nhận không có bất kỳ bản ghi nào của User khác trong kết quả.

    LƯU Ý: Đây là kiểm tra cấu trúc dữ liệu và truy vấn SQL lọc theo owner_id.
    Không đại diện cho authorization guard tại tầng API hoặc application service (Phase 4C).
    """
    user_a = User(email="user_a@example.com", password_hash="hash_a", name="User A", role="USER")
    user_b = User(email="user_b@example.com", password_hash="hash_b", name="User B", role="USER")
    db.add_all([user_a, user_b])
    db.commit()

    # User A có 2 hội thoại
    ht_a1 = HoiThoai(ma_nguoi_dung=user_a.id, tieu_de="Hội thoại A1")
    ht_a2 = HoiThoai(ma_nguoi_dung=user_a.id, tieu_de="Hội thoại A2")
    # User B có 1 hội thoại
    ht_b1 = HoiThoai(ma_nguoi_dung=user_b.id, tieu_de="Hội thoại B1")
    db.add_all([ht_a1, ht_a2, ht_b1])
    db.commit()

    # 1. Tạo các TinNhan cho User A và User B
    tn_a1 = TinNhan(ma_hoi_thoai=ht_a1.ma_hoi_thoai, vai_tro="USER", noi_dung="Msg A1")
    tn_a2 = TinNhan(ma_hoi_thoai=ht_a2.ma_hoi_thoai, vai_tro="USER", noi_dung="Msg A2")
    tn_b1 = TinNhan(ma_hoi_thoai=ht_b1.ma_hoi_thoai, vai_tro="USER", noi_dung="Msg B1")

    # 2. Thêm vào Session và flush để sinh ma_tin_nhan trước khi tạo LanXuLy
    db.add_all([tn_a1, tn_a2, tn_b1])
    db.flush()

    # 3. Xác nhận các mã tin nhắn đã được sinh và khác nhau
    assert tn_a1.ma_tin_nhan is not None and tn_a1.ma_tin_nhan > 0
    assert tn_a2.ma_tin_nhan is not None and tn_a2.ma_tin_nhan > 0
    assert tn_b1.ma_tin_nhan is not None and tn_b1.ma_tin_nhan > 0
    assert len({tn_a1.ma_tin_nhan, tn_a2.ma_tin_nhan, tn_b1.ma_tin_nhan}) == 3

    # 4. Tạo các LanXuLy với ID tin nhắn đầu vào chính xác
    lx_a1 = LanXuLy(ma_hoi_thoai=ht_a1.ma_hoi_thoai, ma_tin_nhan_dau_vao=tn_a1.ma_tin_nhan)
    lx_a2 = LanXuLy(ma_hoi_thoai=ht_a2.ma_hoi_thoai, ma_tin_nhan_dau_vao=None)
    lx_b1 = LanXuLy(ma_hoi_thoai=ht_b1.ma_hoi_thoai, ma_tin_nhan_dau_vao=tn_b1.ma_tin_nhan)

    db.add_all([lx_a1, lx_a2, lx_b1])
    db.commit()

    # 5. Xác nhận tham chiếu Run và tin nhắn đầu vào sau commit
    assert lx_a1.ma_tin_nhan_dau_vao == tn_a1.ma_tin_nhan
    assert lx_a1.tin_nhan_dau_vao == tn_a1
    assert lx_b1.ma_tin_nhan_dau_vao == tn_b1.ma_tin_nhan
    assert lx_b1.tin_nhan_dau_vao == tn_b1
    assert lx_a2.ma_tin_nhan_dau_vao is None
    assert lx_a2.tin_nhan_dau_vao is None

    # 6. Truy vấn HoiThoai của User A và User B
    ht_cua_a = db.scalars(
        select(HoiThoai).where(HoiThoai.ma_nguoi_dung == user_a.id)
    ).all()
    id_ht_a = {ht.ma_hoi_thoai for ht in ht_cua_a}
    assert id_ht_a == {ht_a1.ma_hoi_thoai, ht_a2.ma_hoi_thoai}
    assert ht_b1.ma_hoi_thoai not in id_ht_a

    ht_cua_b = db.scalars(
        select(HoiThoai).where(HoiThoai.ma_nguoi_dung == user_b.id)
    ).all()
    id_ht_b = {ht.ma_hoi_thoai for ht in ht_cua_b}
    assert id_ht_b == {ht_b1.ma_hoi_thoai}
    assert ht_a1.ma_hoi_thoai not in id_ht_b
    assert ht_a2.ma_hoi_thoai not in id_ht_b

    # 7. Truy vấn TinNhan của User A và User B thông qua HoiThoai
    tn_cua_a = db.scalars(
        select(TinNhan).join(HoiThoai).where(HoiThoai.ma_nguoi_dung == user_a.id)
    ).all()
    id_tn_a = {tn.ma_tin_nhan for tn in tn_cua_a}
    assert id_tn_a == {tn_a1.ma_tin_nhan, tn_a2.ma_tin_nhan}
    assert tn_b1.ma_tin_nhan not in id_tn_a

    tn_cua_b = db.scalars(
        select(TinNhan).join(HoiThoai).where(HoiThoai.ma_nguoi_dung == user_b.id)
    ).all()
    id_tn_b = {tn.ma_tin_nhan for tn in tn_cua_b}
    assert id_tn_b == {tn_b1.ma_tin_nhan}
    assert tn_a1.ma_tin_nhan not in id_tn_b
    assert tn_a2.ma_tin_nhan not in id_tn_b

    # 8. Truy vấn LanXuLy của User A và User B thông qua HoiThoai
    lx_cua_a = db.scalars(
        select(LanXuLy).join(HoiThoai).where(HoiThoai.ma_nguoi_dung == user_a.id)
    ).all()
    id_lx_a = {lx.ma_lan_xu_ly for lx in lx_cua_a}
    assert id_lx_a == {lx_a1.ma_lan_xu_ly, lx_a2.ma_lan_xu_ly}
    assert lx_b1.ma_lan_xu_ly not in id_lx_a

    lx_cua_b = db.scalars(
        select(LanXuLy).join(HoiThoai).where(HoiThoai.ma_nguoi_dung == user_b.id)
    ).all()
    id_lx_b = {lx.ma_lan_xu_ly for lx in lx_cua_b}
    assert id_lx_b == {lx_b1.ma_lan_xu_ly}
    assert lx_a1.ma_lan_xu_ly not in id_lx_b
    assert lx_a2.ma_lan_xu_ly not in id_lx_b

