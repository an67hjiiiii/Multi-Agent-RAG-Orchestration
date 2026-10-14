"""create knowledge chunks table

Revision ID: f1a2b3c4d5e6
Revises: d4f2a1b9e8c3
Create Date: 2026-10-13 21:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "d4f2a1b9e8c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section", sa.String(length=255), nullable=True),
        sa.Column("start_offset", sa.Integer(), nullable=True),
        sa.Column("end_offset", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["knowledge_sources.id"],
            name="fk_knowledge_chunks_source_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id",
            "chunk_index",
            name="uq_knowledge_chunks_source_chunk_index",
        ),
        sa.CheckConstraint(
            "chunk_index >= 0",
            name="ck_knowledge_chunks_index_non_negative",
        ),
        sa.CheckConstraint(
            "length(trim(content, ' \t\r\n\xa0\u3000')) > 0",
            name="ck_knowledge_chunks_content_not_empty",
        ),
        sa.CheckConstraint(
            "page_number IS NULL OR page_number >= 1",
            name="ck_knowledge_chunks_page_number",
        ),
        sa.CheckConstraint(
            "(start_offset IS NULL AND end_offset IS NULL) OR (start_offset >= 0 AND end_offset > start_offset)",
            name="ck_knowledge_chunks_offsets_valid",
        ),
    )


def downgrade() -> None:
    op.drop_table("knowledge_chunks")
