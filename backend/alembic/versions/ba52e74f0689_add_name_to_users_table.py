from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'ba52e74f0689'
down_revision: Union[str, Sequence[str], None] = 'a70518f81bfe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('name', sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'name')
