from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.tin_nhan import TinNhan
    from app.models.lan_xu_ly import LanXuLy


class HoiThoai(Base):
    """
    Model đại diện cho cuộc hội thoại giữa người dùng và hệ thống Multi-Agent RAG.
    """
    __tablename__ = "hoi_thoai"

    ma_hoi_thoai: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    ma_nguoi_dung: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "users.id",
            name="fk_hoi_thoai_ma_nguoi_dung",
            ondelete="NO ACTION",
            onupdate="NO ACTION",
        ),
        nullable=False,
        index=True,
    )
    tieu_de: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="Cuộc hội thoại mới",
        server_default="Cuộc hội thoại mới",
    )
    thoi_gian_tao: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    thoi_gian_cap_nhat: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    # Quan hệ ORM
    nguoi_dung: Mapped["User"] = relationship("User")
    danh_sach_tin_nhan: Mapped[list["TinNhan"]] = relationship(
        "TinNhan",
        back_populates="hoi_thoai",
    )
    danh_sach_lan_xu_ly: Mapped[list["LanXuLy"]] = relationship(
        "LanXuLy",
        back_populates="hoi_thoai",
        foreign_keys="LanXuLy.ma_hoi_thoai",
    )
