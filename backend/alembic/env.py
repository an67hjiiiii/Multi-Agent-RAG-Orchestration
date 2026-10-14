from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.db.database import DATABASE_URL
from app.db.safety import get_target_database_url, verify_alembic_safety_guard
from app.models.base import Base
import app.models

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = get_target_database_url(default_url=config.get_main_option("sqlalchemy.url") or DATABASE_URL)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    target_url = get_target_database_url(default_url=config.get_main_option("sqlalchemy.url") or DATABASE_URL)

    # Khởi tạo engine độc lập cho target_url tại runtime
    connectable = create_engine(
        target_url,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Kích hoạt fail-closed safety guard trên chính connection trước khi migrate
        verify_alembic_safety_guard(connection, target_url)

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()
        connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
