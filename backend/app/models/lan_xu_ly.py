from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.hoi_thoai import HoiThoai
    from app.models.tin_nhan import TinNhan


class LanXuLy(Base):
    """
    Model đại diện cho một lần thực thi AI/Multi-Agent Run trong một hội thoại.
    """
    __tablename__ = "lan_xu_ly"
    __table_args__ = (
        ForeignKeyConstraint(
            ["ma_tin_nhan_dau_vao", "ma_hoi_thoai"],
            ["tin_nhan.ma_tin_nhan", "tin_nhan.ma_hoi_thoai"],
            name="fk_lan_xu_ly_tin_nhan_dau_vao",
            ondelete="NO ACTION",
            onupdate="NO ACTION",
        ),
        CheckConstraint(
            "trang_thai IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')",
            name="ck_lan_xu_ly_trang_thai",
        ),
        CheckConstraint(
            "thoi_gian_hoan_tat IS NULL OR thoi_gian_bat_dau IS NULL OR thoi_gian_hoan_tat >= thoi_gian_bat_dau",
            name="ck_lan_xu_ly_thoi_gian",
        ),
    )

    ma_lan_xu_ly: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    ma_hoi_thoai: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "hoi_thoai.ma_hoi_thoai",
            name="fk_lan_xu_ly_ma_hoi_thoai",
            ondelete="NO ACTION",
            onupdate="NO ACTION",
        ),
        nullable=False,
        index=True,
    )
    ma_tin_nhan_dau_vao: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )
    trang_thai: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="PENDING",
        server_default="PENDING",
    )
    thong_bao_loi: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    thoi_gian_tao: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    thoi_gian_bat_dau: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    thoi_gian_hoan_tat: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Quan hệ ORM
    hoi_thoai: Mapped["HoiThoai"] = relationship(
        "HoiThoai",
        back_populates="danh_sach_lan_xu_ly",
        foreign_keys=[ma_hoi_thoai],
    )
    tin_nhan_dau_vao: Mapped["TinNhan | None"] = relationship(
        "TinNhan",
        primaryjoin="and_(LanXuLy.ma_tin_nhan_dau_vao == TinNhan.ma_tin_nhan, LanXuLy.ma_hoi_thoai == TinNhan.ma_hoi_thoai)",
        foreign_keys=[ma_tin_nhan_dau_vao],
    )
