from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PhienDangNhap(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    ma_nguoi_dung: Mapped[int] = mapped_column(
        "user_id",
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    ma_bam_phien: Mapped[str] = mapped_column(
        "token_hash",
        String(64),
        unique=True,
        nullable=False,
    )
    thoi_gian_tao: Mapped[datetime] = mapped_column(
        "created_at",
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    thoi_gian_het_han: Mapped[datetime] = mapped_column(
        "expires_at",
        DateTime(timezone=True),
        nullable=False,
    )
    thoi_gian_thu_hoi: Mapped[datetime | None] = mapped_column(
        "revoked_at",
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
