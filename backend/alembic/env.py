"""Alembic environment configured for SQLAlchemy's async engine.

Migrations target the metadata of the declarative ``Base`` defined in
``app.memory.models`` and run through an ``AsyncEngine``.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Import the declarative Base and register all ORM models on ``Base.metadata``
# so autogenerate can see every table.
from app.memory.models import Base
from app.models.chat_session import ChatSession  # noqa: F401
from app.models.user import User  # noqa: F401

# Prefer the application's configured DATABASE_URL when available so local/CI
# and deployed environments override the placeholder in alembic.ini.
try:  # pragma: no cover - optional convenience, safe if config import fails
    from app.config import get_settings
except Exception:  # noqa: BLE001
    get_settings = None  # type: ignore[assignment]

# The Alembic Config object provides access to values in alembic.ini.
config = context.config

# Override the ini URL with the app setting when we can resolve one.
if get_settings is not None:
    database_url = get_settings().database_url
    if database_url:
        config.set_main_option("sqlalchemy.url", database_url)

# Configure Python logging from the ini file.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata used for 'autogenerate' support.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without a DBAPI)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Configure the context with a live connection and run migrations."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations within an async connection."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using the async engine."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
