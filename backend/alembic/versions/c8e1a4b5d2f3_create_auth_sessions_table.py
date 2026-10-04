from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c8e1a4b5d2f3'
down_revision: Union[str, Sequence[str], None] = 'ba52e74f0689'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'auth_sessions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_auth_sessions_user_id', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash', name='uq_auth_sessions_token_hash'),
    )


def downgrade() -> None:
    op.drop_table('auth_sessions')
