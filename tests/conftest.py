"""Shared fixtures backing the database-driven test suite.

Tests execute against a real PostgreSQL instance. Enum types, JSONB
columns, partial uniqueness and row locking all behave differently on any
other engine, and the repositories are written against those exact
semantics, so an in-memory substitute would validate the wrong thing.

The schema is built from the ORM metadata once per session rather than by
replaying the migration history: it keeps the fixture fast and pins the
suite to the mapping the repositories consume. Migration correctness is a
separate concern, asserted by applying them in CI against an empty
database.
"""

import os
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import URL, make_url, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app import models  # noqa: F401
from app.core.config import get_settings
from app.db.base import Base

TEST_DATABASE_SUFFIX = "_test"
MAINTENANCE_DATABASE = "postgres"


def _quote_identifier(identifier: str) -> str:
    """Quote a SQL identifier that cannot be passed as a bind parameter.

    Args:
        identifier: The identifier to quote.

    Returns:
        The identifier wrapped in double quotes, with any embedded double
        quote doubled.
    """
    escaped = identifier.replace('"', '""')
    return f'"{escaped}"'


def _resolve_test_database_url() -> URL:
    """Resolve the URL of the database the suite runs against.

    ``TEST_DATABASE_URL`` takes precedence when it is set; otherwise the
    application URL is reused with a suffixed database name, so a fresh
    checkout needs no extra configuration to run the tests.

    Returns:
        The resolved test database URL.

    Raises:
        RuntimeError: If the URL names no database, or names the database
            the application itself is configured against.
    """
    application_url = make_url(get_settings().DATABASE_URL)
    override = os.environ.get("TEST_DATABASE_URL")

    if override:
        url = make_url(override)
    elif application_url.database is None:
        raise RuntimeError(
            "DATABASE_URL names no database, so the test database name cannot be derived "
            "from it. Set TEST_DATABASE_URL explicitly."
        )
    else:
        url = application_url.set(database=f"{application_url.database}{TEST_DATABASE_SUFFIX}")

    if url.database is None:
        raise RuntimeError("TEST_DATABASE_URL must name a database.")

    if (url.host, url.port, url.database) == (
        application_url.host,
        application_url.port,
        application_url.database,
    ):
        raise RuntimeError(
            "The test database must differ from the application database: the suite drops "
            "and recreates every table it maps."
        )

    return url


async def _create_database_if_missing(url: URL) -> None:
    """Create the database named by ``url`` unless it already exists.

    ``CREATE DATABASE`` cannot run inside a transaction block, so the
    maintenance connection is opened in autocommit.

    Args:
        url: The URL of the database to create.

    Raises:
        ValueError: If the URL names no database.
        RuntimeError: If the database is missing and the configured role
            is not allowed to create it.
    """
    database_name = url.database
    if database_name is None:
        raise ValueError("The database URL must name a database.")

    engine = create_async_engine(
        url.set(database=MAINTENANCE_DATABASE),
        poolclass=NullPool,
        isolation_level="AUTOCOMMIT",
    )
    try:
        async with engine.connect() as connection:
            already_exists = await connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": database_name},
            )
            if already_exists is not None:
                return
            try:
                await connection.execute(
                    text(f"CREATE DATABASE {_quote_identifier(database_name)}")
                )
            except ProgrammingError as error:
                raise RuntimeError(
                    f"The test database {database_name!r} does not exist and the role "
                    f"{url.username!r} is not allowed to create it. Create it once as a "
                    f"superuser with: CREATE DATABASE {_quote_identifier(database_name)} "
                    f"OWNER {_quote_identifier(url.username or MAINTENANCE_DATABASE)};"
                ) from error
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def test_database_url() -> URL:
    """Provide the URL of the database the suite runs against.

    Returns:
        The resolved test database URL.
    """
    return _resolve_test_database_url()


@pytest.fixture(scope="session")
async def db_engine(test_database_url: URL) -> AsyncGenerator[AsyncEngine]:
    """Provide an engine bound to a freshly built test schema.

    The schema is dropped and recreated at the start of the session, so a
    run always begins from a known state while the tables stay available
    for inspection after a failure instead of vanishing on teardown.

    Args:
        test_database_url: The URL of the database to build the schema in.

    Yields:
        An ``AsyncEngine`` connected to the prepared test database.
    """
    await _create_database_if_missing(test_database_url)

    engine = create_async_engine(test_database_url, poolclass=NullPool)
    async with engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    """Provide a session whose writes are discarded once the test ends.

    Args:
        db_engine: The session-scoped engine bound to the test schema.

    Yields:
        An ``AsyncSession`` rolled back when the test returns.
    """
    async with AsyncSession(bind=db_engine, expire_on_commit=False) as session:
        try:
            yield session
        finally:
            await session.rollback()
