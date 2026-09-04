"""Tests for the per-test transaction isolation of the database fixtures.

The guarantee under test is that a test never observes, and never leaves
behind, rows belonging to another one — including when the code under
test commits its own session.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.models import Company
from tests.factories import build_company

LEAKED_COMPANY_SLUG = "savepoint-isolation-probe"


async def test_committed_row_is_visible_inside_the_test(db_session: AsyncSession) -> None:
    """A commit behaves normally from the point of view of its own session."""
    db_session.add(build_company(slug=LEAKED_COMPANY_SLUG))
    await db_session.commit()

    stored = await db_session.scalar(select(Company).where(Company.slug == LEAKED_COMPANY_SLUG))

    assert stored is not None


async def test_committed_row_does_not_leak_into_the_next_test(db_session: AsyncSession) -> None:
    """The row committed by the preceding test died with its transaction."""
    leaked = await db_session.scalar(select(Company).where(Company.slug == LEAKED_COMPANY_SLUG))

    assert leaked is None


async def test_commit_is_invisible_to_a_concurrent_connection(
    db_session: AsyncSession,
    db_engine: AsyncEngine,
) -> None:
    """The commit releases a savepoint, so nothing reaches the database."""
    company = build_company()
    db_session.add(company)
    await db_session.commit()

    async with db_engine.connect() as connection:
        visible_elsewhere = await connection.scalar(
            select(Company.id).where(Company.slug == company.slug)
        )

    assert visible_elsewhere is None
    assert await db_session.get(Company, company.id) is not None


async def test_session_stays_usable_after_a_commit(db_session: AsyncSession) -> None:
    """Releasing the savepoint opens the next one instead of ending the test."""
    committed = build_company()
    db_session.add(committed)
    await db_session.commit()

    written_afterwards = build_company()
    db_session.add(written_afterwards)
    await db_session.flush()

    assert committed.id is not None
    assert written_afterwards.id is not None


async def test_session_stays_usable_after_a_constraint_violation(
    db_session: AsyncSession,
) -> None:
    """A rollback unwinds to the savepoint and leaves the test transaction alive."""
    duplicated_slug = "duplicate-slug-probe"
    db_session.add(build_company(slug=duplicated_slug))
    await db_session.flush()

    db_session.add(build_company(slug=duplicated_slug))
    with pytest.raises(IntegrityError):
        await db_session.flush()

    await db_session.rollback()

    written_afterwards = build_company()
    db_session.add(written_afterwards)
    await db_session.flush()

    assert written_afterwards.id is not None
