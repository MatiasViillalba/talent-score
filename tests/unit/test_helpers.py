"""Tests for the helpers that assemble test data in the database."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CandidateStage, ParseStatus, StageTransition, User, UserRole
from tests.factories import build_webhook
from tests.helpers import (
    create_candidate,
    create_company,
    create_screened_candidate,
    create_stage_transition,
    create_tenant,
    persist,
)


async def test_create_tenant_persists_a_consistent_graph(db_session: AsyncSession) -> None:
    """Every row a tenant is made of belongs to the same company."""
    tenant = await create_tenant(db_session)

    assert tenant.owner.role is UserRole.OWNER
    assert tenant.recruiter.role is UserRole.RECRUITER
    assert tenant.owner.company_id == tenant.company.id
    assert tenant.recruiter.company_id == tenant.company.id
    assert tenant.subscription.company_id == tenant.company.id
    assert tenant.job.company_id == tenant.company.id
    assert tenant.job.created_by == tenant.owner.id


async def test_create_screened_candidate_links_profile_and_score(
    db_session: AsyncSession,
) -> None:
    """A screened candidate carries its extracted profile and its score."""
    tenant = await create_tenant(db_session)

    screened = await create_screened_candidate(
        db_session,
        tenant,
        skills=["python", "asyncio"],
        overall_score=Decimal("91.25"),
    )

    assert screened.candidate.parse_status is ParseStatus.COMPLETED
    assert screened.candidate.job_id == tenant.job.id
    assert screened.profile.candidate_id == screened.candidate.id
    assert screened.profile.skills == ["python", "asyncio"]
    assert screened.match_score.candidate_id == screened.candidate.id
    assert screened.match_score.job_id == tenant.job.id
    assert screened.match_score.overall_score == Decimal("91.25")


async def test_helpers_create_the_parents_they_need(db_session: AsyncSession) -> None:
    """A candidate asked for on its own arrives with a tenant and an uploader."""
    candidate = await create_candidate(db_session)

    uploader = await db_session.get(User, candidate.uploaded_by)

    assert uploader is not None
    assert uploader.company_id == candidate.company_id


async def test_stage_transition_helper_records_a_move(db_session: AsyncSession) -> None:
    """The audit trail accepts a move between two different stages."""
    tenant = await create_tenant(db_session)
    screened = await create_screened_candidate(db_session, tenant)

    await create_stage_transition(
        db_session,
        candidate_id=screened.candidate.id,
        changed_by=tenant.recruiter.id,
        from_stage=CandidateStage.SCREENING,
        to_stage=CandidateStage.INTERVIEW,
        reason="Cleared the technical screen.",
    )

    recorded = await db_session.scalar(
        select(StageTransition).where(StageTransition.candidate_id == screened.candidate.id)
    )

    assert recorded is not None
    assert recorded.from_stage is CandidateStage.SCREENING
    assert recorded.to_stage is CandidateStage.INTERVIEW
    assert recorded.created_at is not None


async def test_persist_returns_the_row_the_database_stored(db_session: AsyncSession) -> None:
    """The escape hatch fills in the columns the database defaults."""
    company = await create_company(db_session)

    webhook = await persist(db_session, build_webhook(company_id=company.id, threshold=None))

    assert webhook.id is not None
    assert webhook.created_at is not None
    assert webhook.is_active is True
    assert webhook.threshold is None
