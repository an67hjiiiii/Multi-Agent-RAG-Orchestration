from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd4f2a1b9e8c3'
down_revision: Union[str, Sequence[str], None] = 'c8e1a4b5d2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'knowledge_sources',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('stored_path', sa.String(length=500), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=50), server_default='UPLOADED', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], name='fk_knowledge_sources_owner_id'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_knowledge_sources_owner_id', 'knowledge_sources', ['owner_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_knowledge_sources_owner_id', table_name='knowledge_sources')
    op.drop_table('knowledge_sources')
