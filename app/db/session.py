"""Async database engines and session factories."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

task_engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    poolclass=NullPool,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)

TaskSessionLocal = async_sessionmaker(
    bind=task_engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession]:
    """Yield a pooled async session for a single API request.

    Yields:
        An ``AsyncSession`` bound to the pooled engine, closed once the
        request finishes.
    """
    async with AsyncSessionLocal() as session:
        yield session


async def get_task_db() -> AsyncGenerator[AsyncSession]:
    """Yield a NullPool-backed async session for a Celery task.

    Each Celery worker task runs its own event loop; a pooled engine
    would leak connections bound to a closed loop across task
    invocations, so background tasks use a dedicated engine without
    connection pooling.

    Yields:
        An ``AsyncSession`` bound to the NullPool engine, closed once
        the task finishes.
    """
    async with TaskSessionLocal() as session:
        yield session
