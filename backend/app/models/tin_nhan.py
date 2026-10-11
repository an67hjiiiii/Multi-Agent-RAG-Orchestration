from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.hoi_thoai import HoiThoai


class TinNhan(Base):
    """
    Model đại diện cho từng tin nhắn (lượt trao đổi) trong cuộc hội thoại.
    """
    __tablename__ = "tin_nhan"
    __table_args__ = (
        UniqueConstraint(
            "ma_tin_nhan",
            "ma_hoi_thoai",
            name="uq_tin_nhan_ma_tin_nhan_ma_hoi_thoai",
        ),
        CheckConstraint(
            "vai_tro IN ('USER', 'ASSISTANT', 'SYSTEM')",
            name="ck_tin_nhan_vai_tro",
        ),
    )

    ma_tin_nhan: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    ma_hoi_thoai: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "hoi_thoai.ma_hoi_thoai",
            name="fk_tin_nhan_ma_hoi_thoai",
            ondelete="NO ACTION",
            onupdate="NO ACTION",
        ),
        nullable=False,
        index=True,
    )
    vai_tro: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    noi_dung: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    thoi_gian_tao: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    # Quan hệ ORM
    hoi_thoai: Mapped["HoiThoai"] = relationship(
        "HoiThoai",
        back_populates="danh_sach_tin_nhan",
        foreign_keys=[ma_hoi_thoai],
    )
