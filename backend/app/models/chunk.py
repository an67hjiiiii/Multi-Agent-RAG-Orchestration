from datetime import datetime, timezone
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    source_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("knowledge_sources.id", ondelete="CASCADE", name="fk_knowledge_chunks_source_id"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    page_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    section: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    start_offset: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    end_offset: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    source = relationship("KnowledgeSource", back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("source_id", "chunk_index", name="uq_knowledge_chunks_source_chunk_index"),
        CheckConstraint("chunk_index >= 0", name="ck_knowledge_chunks_index_non_negative"),
        CheckConstraint("length(trim(content, ' \t\r\n\xa0\u3000')) > 0", name="ck_knowledge_chunks_content_not_empty"),
        CheckConstraint("page_number IS NULL OR page_number >= 1", name="ck_knowledge_chunks_page_number"),
        CheckConstraint(
            "(start_offset IS NULL AND end_offset IS NULL) OR (start_offset >= 0 AND end_offset > start_offset)",
            name="ck_knowledge_chunks_offsets_valid",
        ),
        {"sqlite_autoincrement": True},
    )
