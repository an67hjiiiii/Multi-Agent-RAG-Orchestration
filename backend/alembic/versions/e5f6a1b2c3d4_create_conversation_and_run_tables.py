"""create conversation and run tables

Revision ID: e5f6a1b2c3d4
Revises: d4f2a1b9e8c3
Create Date: 2026-10-11 12:38:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a1b2c3d4'
down_revision: Union[str, Sequence[str], None] = 'd4f2a1b9e8c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Tạo bảng hoi_thoai
    op.create_table(
        'hoi_thoai',
        sa.Column('ma_hoi_thoai', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ma_nguoi_dung', sa.Integer(), nullable=False),
        sa.Column('tieu_de', sa.String(length=255), server_default='Cuộc hội thoại mới', nullable=False),
        sa.Column('thoi_gian_tao', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('thoi_gian_cap_nhat', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['ma_nguoi_dung'], ['users.id'], name='fk_hoi_thoai_ma_nguoi_dung', ondelete='NO ACTION', onupdate='NO ACTION'),
        sa.PrimaryKeyConstraint('ma_hoi_thoai', name='pk_hoi_thoai'),
    )
    op.create_index('ix_hoi_thoai_ma_nguoi_dung', 'hoi_thoai', ['ma_nguoi_dung'], unique=False)

    # 2. Tạo bảng tin_nhan
    op.create_table(
        'tin_nhan',
        sa.Column('ma_tin_nhan', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ma_hoi_thoai', sa.Integer(), nullable=False),
        sa.Column('vai_tro', sa.String(length=50), nullable=False),
        sa.Column('noi_dung', sa.Text(), nullable=False),
        sa.Column('thoi_gian_tao', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.CheckConstraint("vai_tro IN ('USER', 'ASSISTANT', 'SYSTEM')", name='ck_tin_nhan_vai_tro'),
        sa.ForeignKeyConstraint(['ma_hoi_thoai'], ['hoi_thoai.ma_hoi_thoai'], name='fk_tin_nhan_ma_hoi_thoai', ondelete='NO ACTION', onupdate='NO ACTION'),
        sa.PrimaryKeyConstraint('ma_tin_nhan', name='pk_tin_nhan'),
        sa.UniqueConstraint('ma_tin_nhan', 'ma_hoi_thoai', name='uq_tin_nhan_ma_tin_nhan_ma_hoi_thoai'),
    )
    op.create_index('ix_tin_nhan_ma_hoi_thoai', 'tin_nhan', ['ma_hoi_thoai'], unique=False)

    # 3. Tạo bảng lan_xu_ly
    op.create_table(
        'lan_xu_ly',
        sa.Column('ma_lan_xu_ly', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ma_hoi_thoai', sa.Integer(), nullable=False),
        sa.Column('ma_tin_nhan_dau_vao', sa.Integer(), nullable=True),
        sa.Column('trang_thai', sa.String(length=50), server_default='PENDING', nullable=False),
        sa.Column('thong_bao_loi', sa.Text(), nullable=True),
        sa.Column('thoi_gian_tao', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('thoi_gian_bat_dau', sa.DateTime(timezone=True), nullable=True),
        sa.Column('thoi_gian_hoan_tat', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("trang_thai IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')", name='ck_lan_xu_ly_trang_thai'),
        sa.CheckConstraint('thoi_gian_hoan_tat IS NULL OR thoi_gian_bat_dau IS NULL OR thoi_gian_hoan_tat >= thoi_gian_bat_dau', name='ck_lan_xu_ly_thoi_gian'),
        sa.ForeignKeyConstraint(['ma_hoi_thoai'], ['hoi_thoai.ma_hoi_thoai'], name='fk_lan_xu_ly_ma_hoi_thoai', ondelete='NO ACTION', onupdate='NO ACTION'),
        sa.ForeignKeyConstraint(['ma_tin_nhan_dau_vao', 'ma_hoi_thoai'], ['tin_nhan.ma_tin_nhan', 'tin_nhan.ma_hoi_thoai'], name='fk_lan_xu_ly_tin_nhan_dau_vao', ondelete='NO ACTION', onupdate='NO ACTION'),
        sa.PrimaryKeyConstraint('ma_lan_xu_ly', name='pk_lan_xu_ly'),
    )
    op.create_index('ix_lan_xu_ly_ma_hoi_thoai', 'lan_xu_ly', ['ma_hoi_thoai'], unique=False)
    op.create_index('ix_lan_xu_ly_ma_tin_nhan_dau_vao', 'lan_xu_ly', ['ma_tin_nhan_dau_vao'], unique=False)


def downgrade() -> None:
    # 1. Xóa bảng lan_xu_ly
    op.drop_index('ix_lan_xu_ly_ma_tin_nhan_dau_vao', table_name='lan_xu_ly')
    op.drop_index('ix_lan_xu_ly_ma_hoi_thoai', table_name='lan_xu_ly')
    op.drop_table('lan_xu_ly')

    # 2. Xóa bảng tin_nhan
    op.drop_index('ix_tin_nhan_ma_hoi_thoai', table_name='tin_nhan')
    op.drop_table('tin_nhan')

    # 3. Xóa bảng hoi_thoai
    op.drop_index('ix_hoi_thoai_ma_nguoi_dung', table_name='hoi_thoai')
    op.drop_table('hoi_thoai')
