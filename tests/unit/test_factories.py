"""Tests for the schema fixture and the model builders it supports."""

import uuid

from sqlalchemy import inspect
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.db.base import Base
from app.models import CandidateStage, ParseStatus, UserRole
from tests.factories import build_candidate, build_company, build_job, build_user


async def test_schema_exposes_every_mapped_table(db_engine: AsyncEngine) -> None:
    """The session fixture materializes the full ORM metadata."""

    def read_table_names(connection: Connection) -> set[str]:
        return set(inspect(connection).get_table_names())

    async with db_engine.connect() as connection:
        table_names = await connection.run_sync(read_table_names)

    assert set(Base.metadata.tables) <= table_names


async def test_company_builder_persists_with_server_generated_columns(
    db_session: AsyncSession,
) -> None:
    """A built company reaches the database and comes back fully populated."""
    company = build_company()

    db_session.add(company)
    await db_session.flush()
    await db_session.refresh(company)

    assert company.id is not None
    assert company.created_at is not None
    assert company.updated_at is not None
    assert company.stripe_customer_id is None


async def test_builders_wire_the_tenant_graph(db_session: AsyncSession) -> None:
    """Candidates, jobs and users persist against the company that owns them."""
    company = build_company()
    db_session.add(company)
    await db_session.flush()

    user = build_user(company_id=company.id, role=UserRole.OWNER)
    db_session.add(user)
    await db_session.flush()

    job = build_job(company_id=company.id, created_by=user.id)
    db_session.add(job)
    await db_session.flush()

    candidate = build_candidate(
        company_id=company.id,
        uploaded_by=user.id,
        job_id=job.id,
    )
    db_session.add(candidate)
    await db_session.flush()

    assert user.role is UserRole.OWNER
    assert job.company_id == company.id
    assert candidate.job_id == job.id
    assert candidate.parse_status is ParseStatus.PENDING
    assert candidate.stage is CandidateStage.SCREENING


def test_builders_generate_unique_natural_keys() -> None:
    """Repeated calls never collide on the columns constrained as unique."""
    company_id = uuid.uuid4()
    user_id = uuid.uuid4()

    companies = [build_company() for _ in range(3)]
    users = [build_user(company_id=company_id) for _ in range(3)]
    candidates = [build_candidate(company_id=company_id, uploaded_by=user_id) for _ in range(3)]

    assert len({company.slug for company in companies}) == len(companies)
    assert len({user.email for user in users}) == len(users)
    assert len({candidate.file_hash for candidate in candidates}) == len(candidates)
