"""Helpers turning the model builders into rows stored in the test database.

The builders in :mod:`tests.factories` leave every foreign key to the
caller. These helpers own the ordering instead: each one flushes the
parents a row depends on before the row itself, and creates the missing
ones when the test does not care which company or user it hangs off. A
test that needs a scored candidate says so in one call rather than in
eight statements of setup that assert nothing.

Helpers flush and never commit. The transaction boundary belongs to the
fixture that wraps the test, so the rows disappear with it.
"""

import datetime
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base
from app.models import (
    Candidate,
    CandidateProfile,
    CandidateStage,
    Company,
    Job,
    JobStatus,
    MatchScore,
    Note,
    ParseStatus,
    StageTransition,
    Subscription,
    SubscriptionPlan,
    SubscriptionStatus,
    UsageRecord,
    User,
    UserRole,
    Webhook,
    WebhookDelivery,
    WebhookEventType,
)
from tests.factories import (
    DEFAULT_MONTHLY_CV_QUOTA,
    DEFAULT_PERIOD_START,
    build_candidate,
    build_candidate_profile,
    build_company,
    build_job,
    build_match_score,
    build_note,
    build_stage_transition,
    build_subscription,
    build_usage_record,
    build_user,
    build_webhook,
    build_webhook_delivery,
)


@dataclass(frozen=True)
class Tenant:
    """A company and the rows most tests need alongside it.

    Attributes:
        company: The tenant every other row belongs to.
        owner: The user holding the ``owner`` role.
        recruiter: A user holding the ``recruiter`` role.
        subscription: The active subscription backing the quota.
        job: An open posting candidates can be scored against.
    """

    company: Company
    owner: User
    recruiter: User
    subscription: Subscription
    job: Job


@dataclass(frozen=True)
class ScreenedCandidate:
    """A resume that has been parsed and scored against a job.

    Attributes:
        candidate: The uploaded resume, parsing completed.
        profile: The structured data extracted from the resume.
        match_score: The score of the candidate against the job.
    """

    candidate: Candidate
    profile: CandidateProfile
    match_score: MatchScore


async def persist[EntityT: Base](session: AsyncSession, entity: EntityT) -> EntityT:
    """Store an entity and read back the columns the database fills in.

    This is the escape hatch for the cases the typed helpers below do not
    cover: build the instance with the matching factory, then persist it.

    Args:
        session: The session the entity is written through.
        entity: The instance to insert.

    Returns:
        The stored entity, refreshed so that its primary key, timestamps
        and other server-side defaults are readable.
    """
    session.add(entity)
    await session.flush()
    await session.refresh(entity)
    return entity


async def create_company(
    session: AsyncSession,
    *,
    name: str | None = None,
    slug: str | None = None,
    stripe_customer_id: str | None = None,
) -> Company:
    """Store a tenant.

    Args:
        session: The session the company is written through.
        name: Display name of the company.
        slug: Tenant slug; unique across the run when omitted.
        stripe_customer_id: Identifier of the matching gateway customer.

    Returns:
        The stored ``Company``.
    """
    return await persist(
        session,
        build_company(name=name, slug=slug, stripe_customer_id=stripe_customer_id),
    )


async def create_user(
    session: AsyncSession,
    *,
    company_id: uuid.UUID | None = None,
    email: str | None = None,
    full_name: str = "Dana Reyes",
    role: UserRole = UserRole.RECRUITER,
    is_active: bool = True,
) -> User:
    """Store a member of a company, creating the company when needed.

    Args:
        session: The session the user is written through.
        company_id: Tenant the user belongs to; a new tenant is created
            when omitted.
        email: Login address; unique across the run when omitted.
        full_name: Display name of the user.
        role: Role granting the user its permissions.
        is_active: Whether the account can authenticate.

    Returns:
        The stored ``User``.
    """
    if company_id is None:
        company_id = (await create_company(session)).id
    return await persist(
        session,
        build_user(
            company_id=company_id,
            email=email,
            full_name=full_name,
            role=role,
            is_active=is_active,
        ),
    )


async def create_subscription(
    session: AsyncSession,
    *,
    company_id: uuid.UUID | None = None,
    plan: SubscriptionPlan = SubscriptionPlan.PROFESSIONAL,
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
    monthly_cv_quota: int = DEFAULT_MONTHLY_CV_QUOTA,
    current_period_end: datetime.datetime | None = None,
) -> Subscription:
    """Store the subscription of a company, creating the company when needed.

    Args:
        session: The session the subscription is written through.
        company_id: Tenant the subscription belongs to; a new tenant is
            created when omitted.
        plan: Commercial plan the company is on.
        status: Lifecycle state mirrored from the payment gateway.
        monthly_cv_quota: Resumes the plan allows per billing period.
        current_period_end: Instant the running period closes at.

    Returns:
        The stored ``Subscription``.
    """
    if company_id is None:
        company_id = (await create_company(session)).id
    return await persist(
        session,
        build_subscription(
            company_id=company_id,
            plan=plan,
            status=status,
            monthly_cv_quota=monthly_cv_quota,
            current_period_end=current_period_end,
        ),
    )


async def create_usage_record(
    session: AsyncSession,
    *,
    company_id: uuid.UUID | None = None,
    period_start: datetime.date = DEFAULT_PERIOD_START,
    cv_processed_count: int = 0,
) -> UsageRecord:
    """Store the quota consumption of a company for one billing period.

    Args:
        session: The session the record is written through.
        company_id: Tenant the consumption belongs to; a new tenant is
            created when omitted.
        period_start: First day of the billing period.
        cv_processed_count: Resumes already processed in the period.

    Returns:
        The stored ``UsageRecord``.
    """
    if company_id is None:
        company_id = (await create_company(session)).id
    return await persist(
        session,
        build_usage_record(
            company_id=company_id,
            period_start=period_start,
            cv_processed_count=cv_processed_count,
        ),
    )


async def create_job(
    session: AsyncSession,
    *,
    company_id: uuid.UUID | None = None,
    created_by: uuid.UUID | None = None,
    title: str | None = None,
    required_skills: list[dict[str, Any]] | None = None,
    min_years_experience: int = 3,
    salary_min: int | None = 90_000,
    salary_max: int | None = 130_000,
    location: str | None = "Buenos Aires, AR",
    remote_allowed: bool = True,
    status: JobStatus = JobStatus.OPEN,
) -> Job:
    """Store a job posting, creating the tenant and its author when needed.

    Args:
        session: The session the posting is written through.
        company_id: Tenant the posting belongs to; a new tenant is
            created when omitted.
        created_by: User who published the posting; an owner of the
            resolved tenant is created when omitted.
        title: Position title; unique across the run when omitted.
        required_skills: Weighted requirements consumed by the matching
            engine.
        min_years_experience: Minimum experience the role expects.
        salary_min: Lower bound of the posted salary range.
        salary_max: Upper bound of the posted salary range.
        location: Where the role is based.
        remote_allowed: Whether the role can be performed remotely.
        status: Publication state of the posting.

    Returns:
        The stored ``Job``.
    """
    if company_id is None:
        company_id = (await create_company(session)).id
    if created_by is None:
        created_by = (await create_user(session, company_id=company_id, role=UserRole.OWNER)).id
    return await persist(
        session,
        build_job(
            company_id=company_id,
            created_by=created_by,
            title=title,
            required_skills=required_skills,
            min_years_experience=min_years_experience,
            salary_min=salary_min,
            salary_max=salary_max,
            location=location,
            remote_allowed=remote_allowed,
            status=status,
        ),
    )


async def create_candidate(
    session: AsyncSession,
    *,
    company_id: uuid.UUID | None = None,
    uploaded_by: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
    original_filename: str | None = None,
    file_hash: str | None = None,
    raw_text: str | None = None,
    parse_status: ParseStatus = ParseStatus.PENDING,
    stage: CandidateStage = CandidateStage.SCREENING,
) -> Candidate:
    """Store an uploaded resume, creating the tenant and uploader when needed.

    Args:
        session: The session the resume is written through.
        company_id: Tenant the resume was uploaded to; a new tenant is
            created when omitted.
        uploaded_by: User who uploaded the file; a recruiter of the
            resolved tenant is created when omitted.
        job_id: Posting the resume was submitted for, if any.
        original_filename: Name the file was uploaded under.
        file_hash: Content digest backing deduplication; unique across
            the run when omitted.
        raw_text: Text extracted from the file, once extraction ran.
        parse_status: Progress of the parsing pipeline.
        stage: Position of the candidate in the recruitment pipeline.

    Returns:
        The stored ``Candidate``.
    """
    if company_id is None:
        company_id = (await create_company(session)).id
    if uploaded_by is None:
        uploaded_by = (await create_user(session, company_id=company_id)).id
    return await persist(
        session,
        build_candidate(
            company_id=company_id,
            uploaded_by=uploaded_by,
            job_id=job_id,
            original_filename=original_filename,
            file_hash=file_hash,
            raw_text=raw_text,
            parse_status=parse_status,
            stage=stage,
        ),
    )


async def create_candidate_profile(
    session: AsyncSession,
    *,
    candidate_id: uuid.UUID,
    skills: list[str] | None = None,
    years_experience: Decimal | None = Decimal("6.5"),
    expected_salary: int | None = 110_000,
    location: str | None = "Buenos Aires, AR",
) -> CandidateProfile:
    """Store the structured data extracted from a resume.

    Args:
        session: The session the profile is written through.
        candidate_id: Resume the profile was extracted from.
        skills: Flat list of skills the candidate claims.
        years_experience: Total professional experience, in years.
        expected_salary: Compensation the candidate asks for.
        location: Where the candidate is based.

    Returns:
        The stored ``CandidateProfile``.
    """
    return await persist(
        session,
        build_candidate_profile(
            candidate_id=candidate_id,
            skills=skills,
            years_experience=years_experience,
            expected_salary=expected_salary,
            location=location,
        ),
    )


async def create_match_score(
    session: AsyncSession,
    *,
    candidate_id: uuid.UUID,
    job_id: uuid.UUID,
    overall_score: Decimal = Decimal("84.50"),
    breakdown: dict[str, Any] | None = None,
) -> MatchScore:
    """Store the score of one candidate against one job.

    Args:
        session: The session the score is written through.
        candidate_id: Candidate the score was computed for.
        job_id: Posting the candidate was scored against.
        overall_score: Weighted aggregate of the four dimensions.
        breakdown: Matched and missing skills justifying the result.

    Returns:
        The stored ``MatchScore``.
    """
    return await persist(
        session,
        build_match_score(
            candidate_id=candidate_id,
            job_id=job_id,
            overall_score=overall_score,
            breakdown=breakdown,
        ),
    )


async def create_note(
    session: AsyncSession,
    *,
    candidate_id: uuid.UUID,
    author_id: uuid.UUID,
    body: str = "Strong systems background, worth a technical screen.",
) -> Note:
    """Store a collaboration note left on a candidate.

    Args:
        session: The session the note is written through.
        candidate_id: Candidate the note is attached to.
        author_id: User who wrote the note.
        body: Text of the note.

    Returns:
        The stored ``Note``.
    """
    return await persist(
        session,
        build_note(candidate_id=candidate_id, author_id=author_id, body=body),
    )


async def create_stage_transition(
    session: AsyncSession,
    *,
    candidate_id: uuid.UUID,
    changed_by: uuid.UUID,
    from_stage: CandidateStage | None = None,
    to_stage: CandidateStage = CandidateStage.SCREENING,
    reason: str | None = None,
) -> StageTransition:
    """Store one recorded move of a candidate between pipeline stages.

    Args:
        session: The session the transition is written through.
        candidate_id: Candidate that moved.
        changed_by: User who performed the move.
        from_stage: Stage left behind; ``None`` marks pipeline entry.
        to_stage: Stage the candidate moved into.
        reason: Justification recorded alongside the move.

    Returns:
        The stored ``StageTransition``.
    """
    return await persist(
        session,
        build_stage_transition(
            candidate_id=candidate_id,
            changed_by=changed_by,
            from_stage=from_stage,
            to_stage=to_stage,
            reason=reason,
        ),
    )


async def create_webhook(
    session: AsyncSession,
    *,
    company_id: uuid.UUID | None = None,
    url: str | None = None,
    event_type: WebhookEventType = WebhookEventType.CANDIDATE_HIGH_MATCH,
    threshold: Decimal | None = Decimal("80.00"),
    is_active: bool = True,
) -> Webhook:
    """Store a webhook subscription, creating the company when needed.

    Args:
        session: The session the subscription is written through.
        company_id: Tenant that registered the endpoint; a new tenant is
            created when omitted.
        url: Address the payloads are delivered to.
        event_type: Event the endpoint is subscribed to.
        threshold: Score above which a score-driven event fires.
        is_active: Whether deliveries are currently dispatched.

    Returns:
        The stored ``Webhook``.
    """
    if company_id is None:
        company_id = (await create_company(session)).id
    return await persist(
        session,
        build_webhook(
            company_id=company_id,
            url=url,
            event_type=event_type,
            threshold=threshold,
            is_active=is_active,
        ),
    )


async def create_webhook_delivery(
    session: AsyncSession,
    *,
    webhook_id: uuid.UUID,
    event_type: str = WebhookEventType.CANDIDATE_HIGH_MATCH.value,
    payload: dict[str, Any] | None = None,
    response_status: int | None = None,
    attempts: int = 0,
    delivered: bool = False,
) -> WebhookDelivery:
    """Store one delivery attempt log for a registered webhook.

    Args:
        session: The session the log is written through.
        webhook_id: Endpoint the payload was addressed to.
        event_type: Event that triggered the delivery.
        payload: Body that was, or will be, sent.
        response_status: HTTP status the receiver answered with.
        attempts: Delivery attempts made so far.
        delivered: Whether the receiver acknowledged the payload.

    Returns:
        The stored ``WebhookDelivery``.
    """
    return await persist(
        session,
        build_webhook_delivery(
            webhook_id=webhook_id,
            event_type=event_type,
            payload=payload,
            response_status=response_status,
            attempts=attempts,
            delivered=delivered,
        ),
    )


async def create_tenant(
    session: AsyncSession,
    *,
    monthly_cv_quota: int = DEFAULT_MONTHLY_CV_QUOTA,
    subscription_status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
    required_skills: list[dict[str, Any]] | None = None,
) -> Tenant:
    """Store a company with the users, subscription and job tests start from.

    Args:
        session: The session the rows are written through.
        monthly_cv_quota: Resumes the subscription allows per period.
        subscription_status: Lifecycle state of the subscription.
        required_skills: Weighted requirements of the posting.

    Returns:
        A ``Tenant`` holding the stored rows.
    """
    company = await create_company(session)
    owner = await create_user(session, company_id=company.id, role=UserRole.OWNER)
    recruiter = await create_user(session, company_id=company.id, role=UserRole.RECRUITER)
    subscription = await create_subscription(
        session,
        company_id=company.id,
        status=subscription_status,
        monthly_cv_quota=monthly_cv_quota,
    )
    job = await create_job(
        session,
        company_id=company.id,
        created_by=owner.id,
        required_skills=required_skills,
    )
    return Tenant(
        company=company,
        owner=owner,
        recruiter=recruiter,
        subscription=subscription,
        job=job,
    )


async def create_screened_candidate(
    session: AsyncSession,
    tenant: Tenant,
    *,
    skills: list[str] | None = None,
    years_experience: Decimal | None = Decimal("6.5"),
    expected_salary: int | None = 110_000,
    overall_score: Decimal = Decimal("84.50"),
    stage: CandidateStage = CandidateStage.SCREENING,
) -> ScreenedCandidate:
    """Store a resume that has already been parsed and scored.

    Args:
        session: The session the rows are written through.
        tenant: The company, uploader and job the candidate belongs to.
        skills: Flat list of skills the candidate claims.
        years_experience: Total professional experience, in years.
        expected_salary: Compensation the candidate asks for.
        overall_score: Weighted aggregate the candidate scored.
        stage: Position of the candidate in the recruitment pipeline.

    Returns:
        A ``ScreenedCandidate`` holding the stored rows.
    """
    candidate = await create_candidate(
        session,
        company_id=tenant.company.id,
        uploaded_by=tenant.recruiter.id,
        job_id=tenant.job.id,
        raw_text="Backend engineer with production Python experience.",
        parse_status=ParseStatus.COMPLETED,
        stage=stage,
    )
    profile = await create_candidate_profile(
        session,
        candidate_id=candidate.id,
        skills=skills,
        years_experience=years_experience,
        expected_salary=expected_salary,
    )
    match_score = await create_match_score(
        session,
        candidate_id=candidate.id,
        job_id=tenant.job.id,
        overall_score=overall_score,
    )
    return ScreenedCandidate(candidate=candidate, profile=profile, match_score=match_score)
