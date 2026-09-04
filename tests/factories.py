"""Builders producing unpersisted ORM instances for tests.

Every builder fills each required column with a valid default and lets a
test override only the fields it actually asserts on, so a test reads as
the single thing it is about. Values derived from a process-wide counter
keep the natural keys unique across a run — company slug, user email,
resume hash — without callers having to invent them.

Builders never touch a session: persisting the instances and resolving
their foreign keys is the caller's responsibility.
"""

import datetime
import itertools
import uuid
from decimal import Decimal
from typing import Any

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

DEFAULT_PASSWORD = "test-password"
DEFAULT_PASSWORD_HASH = "$2b$12$94cB8pNQIospkO00PYCCdufR5NSrNpng9hfvP7EbwZ4fyl4xeq1u."
DEFAULT_MODEL_VERSION = "claude-sonnet-4-6/2026-09-01"
DEFAULT_PERIOD_START = datetime.date(2026, 1, 1)
DEFAULT_MONTHLY_CV_QUOTA = 100

_counter = itertools.count(1)


def next_sequence_value() -> int:
    """Return the next value of the shared uniqueness counter.

    Returns:
        An integer no earlier call in this process has returned.
    """
    return next(_counter)


def _or_default[T](value: T | None, default: T) -> T:
    """Resolve an optional override against its default.

    Args:
        value: The caller-supplied override, or ``None`` when the caller
            expressed no preference.
        default: The value to use when no override was given.

    Returns:
        ``value`` unless it is ``None``, in which case ``default``.
    """
    return default if value is None else value


def build_company(
    *,
    name: str | None = None,
    slug: str | None = None,
    stripe_customer_id: str | None = None,
) -> Company:
    """Build a tenant with a unique slug.

    Args:
        name: Display name of the company.
        slug: Tenant slug; unique across the run when omitted.
        stripe_customer_id: Identifier of the matching gateway customer.

    Returns:
        An unpersisted ``Company``.
    """
    sequence = next_sequence_value()
    return Company(
        name=_or_default(name, f"Northwind Talent {sequence}"),
        slug=_or_default(slug, f"northwind-talent-{sequence}"),
        stripe_customer_id=stripe_customer_id,
    )


def build_user(
    *,
    company_id: uuid.UUID,
    email: str | None = None,
    hashed_password: str = DEFAULT_PASSWORD_HASH,
    full_name: str = "Dana Reyes",
    role: UserRole = UserRole.RECRUITER,
    is_active: bool = True,
) -> User:
    """Build a member of a company with a unique email address.

    Args:
        company_id: Tenant the user belongs to.
        email: Login address; unique across the run when omitted.
        hashed_password: Stored password digest.
        full_name: Display name of the user.
        role: Role granting the user its permissions.
        is_active: Whether the account can authenticate.

    Returns:
        An unpersisted ``User``.
    """
    sequence = next_sequence_value()
    return User(
        company_id=company_id,
        email=_or_default(email, f"recruiter{sequence}@northwind.example"),
        hashed_password=hashed_password,
        full_name=full_name,
        role=role,
        is_active=is_active,
    )


def build_subscription(
    *,
    company_id: uuid.UUID,
    stripe_subscription_id: str | None = None,
    plan: SubscriptionPlan = SubscriptionPlan.PROFESSIONAL,
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
    monthly_cv_quota: int = DEFAULT_MONTHLY_CV_QUOTA,
    current_period_end: datetime.datetime | None = None,
) -> Subscription:
    """Build the subscription of a company.

    Args:
        company_id: Tenant the subscription belongs to.
        stripe_subscription_id: Identifier of the gateway subscription.
        plan: Commercial plan the company is on.
        status: Lifecycle state mirrored from the payment gateway.
        monthly_cv_quota: Resumes the plan allows per billing period.
        current_period_end: Instant the running period closes at.

    Returns:
        An unpersisted ``Subscription``.
    """
    return Subscription(
        company_id=company_id,
        stripe_subscription_id=stripe_subscription_id,
        plan=plan,
        status=status,
        monthly_cv_quota=monthly_cv_quota,
        current_period_end=current_period_end,
    )


def build_usage_record(
    *,
    company_id: uuid.UUID,
    period_start: datetime.date = DEFAULT_PERIOD_START,
    cv_processed_count: int = 0,
) -> UsageRecord:
    """Build the quota consumption of a company for one billing period.

    Args:
        company_id: Tenant the consumption belongs to.
        period_start: First day of the billing period.
        cv_processed_count: Resumes already processed in the period.

    Returns:
        An unpersisted ``UsageRecord``.
    """
    return UsageRecord(
        company_id=company_id,
        period_start=period_start,
        cv_processed_count=cv_processed_count,
    )


def build_job(
    *,
    company_id: uuid.UUID,
    created_by: uuid.UUID,
    title: str | None = None,
    description: str = "Design and operate the services behind the hiring platform.",
    required_skills: list[dict[str, Any]] | None = None,
    min_years_experience: int = 3,
    salary_min: int | None = 90_000,
    salary_max: int | None = 130_000,
    currency: str = "USD",
    location: str | None = "Buenos Aires, AR",
    remote_allowed: bool = True,
    status: JobStatus = JobStatus.OPEN,
) -> Job:
    """Build a job posting with a weighted requirement list.

    Args:
        company_id: Tenant the posting belongs to.
        created_by: User who published the posting.
        title: Position title; unique across the run when omitted.
        description: Free-form description of the role.
        required_skills: Weighted requirements consumed by the matching
            engine, shaped as ``[{"skill": ..., "weight": ...}]``.
        min_years_experience: Minimum experience the role expects.
        salary_min: Lower bound of the posted salary range.
        salary_max: Upper bound of the posted salary range.
        currency: ISO 4217 code the salary range is expressed in.
        location: Where the role is based.
        remote_allowed: Whether the role can be performed remotely.
        status: Publication state of the posting.

    Returns:
        An unpersisted ``Job``.
    """
    sequence = next_sequence_value()
    return Job(
        company_id=company_id,
        created_by=created_by,
        title=_or_default(title, f"Senior Backend Engineer {sequence}"),
        description=description,
        required_skills=_or_default(
            required_skills,
            [
                {"skill": "python", "weight": 5},
                {"skill": "fastapi", "weight": 3},
                {"skill": "postgresql", "weight": 2},
            ],
        ),
        min_years_experience=min_years_experience,
        salary_min=salary_min,
        salary_max=salary_max,
        currency=currency,
        location=location,
        remote_allowed=remote_allowed,
        status=status,
    )


def build_candidate(
    *,
    company_id: uuid.UUID,
    uploaded_by: uuid.UUID,
    job_id: uuid.UUID | None = None,
    original_filename: str | None = None,
    storage_path: str | None = None,
    content_type: str = "application/pdf",
    file_hash: str | None = None,
    raw_text: str | None = None,
    parse_status: ParseStatus = ParseStatus.PENDING,
    stage: CandidateStage = CandidateStage.SCREENING,
) -> Candidate:
    """Build an uploaded resume in its initial pipeline state.

    Args:
        company_id: Tenant the resume was uploaded to.
        uploaded_by: User who uploaded the file.
        job_id: Posting the resume was submitted for, if any.
        original_filename: Name the file was uploaded under.
        storage_path: Location the file was persisted at.
        content_type: MIME type of the uploaded file.
        file_hash: Content digest backing deduplication; unique across
            the run when omitted.
        raw_text: Text extracted from the file, once extraction ran.
        parse_status: Progress of the parsing pipeline.
        stage: Position of the candidate in the recruitment pipeline.

    Returns:
        An unpersisted ``Candidate``.
    """
    sequence = next_sequence_value()
    return Candidate(
        company_id=company_id,
        job_id=job_id,
        uploaded_by=uploaded_by,
        original_filename=_or_default(original_filename, f"dana-reyes-{sequence}.pdf"),
        storage_path=_or_default(storage_path, f"resumes/{sequence:08d}/resume.pdf"),
        content_type=content_type,
        file_hash=_or_default(file_hash, f"{sequence:064x}"),
        raw_text=raw_text,
        parse_status=parse_status,
        stage=stage,
    )


def build_candidate_profile(
    *,
    candidate_id: uuid.UUID,
    full_name: str | None = "Dana Reyes",
    email: str | None = None,
    phone: str | None = "+54-11-5555-0100",
    location: str | None = "Buenos Aires, AR",
    years_experience: Decimal | None = Decimal("6.5"),
    skills: list[str] | None = None,
    education: list[dict[str, Any]] | None = None,
    work_history: list[dict[str, Any]] | None = None,
    expected_salary: int | None = 110_000,
    summary: str | None = "Backend engineer focused on distributed Python services.",
    model_version: str = DEFAULT_MODEL_VERSION,
) -> CandidateProfile:
    """Build the structured data a language model extracted from a resume.

    Args:
        candidate_id: Resume the profile was extracted from.
        full_name: Name read off the resume.
        email: Contact address; unique across the run when omitted.
        phone: Contact phone number.
        location: Where the candidate is based.
        years_experience: Total professional experience, in years.
        skills: Flat list of skills the candidate claims.
        education: Degrees and institutions read off the resume.
        work_history: Positions the candidate held.
        expected_salary: Compensation the candidate asks for.
        summary: Short narrative describing the candidate.
        model_version: Model and prompt revision that produced the row.

    Returns:
        An unpersisted ``CandidateProfile``.
    """
    sequence = next_sequence_value()
    return CandidateProfile(
        candidate_id=candidate_id,
        full_name=full_name,
        email=_or_default(email, f"dana.reyes{sequence}@example.com"),
        phone=phone,
        location=location,
        years_experience=years_experience,
        skills=_or_default(skills, ["python", "fastapi", "postgresql"]),
        education=_or_default(
            education,
            [
                {
                    "degree": "BSc Computer Science",
                    "institution": "University of Buenos Aires",
                    "graduation_year": 2018,
                }
            ],
        ),
        work_history=_or_default(
            work_history,
            [
                {
                    "company": "Northwind",
                    "title": "Backend Engineer",
                    "start_year": 2019,
                    "end_year": 2026,
                }
            ],
        ),
        expected_salary=expected_salary,
        summary=summary,
        model_version=model_version,
    )


def build_match_score(
    *,
    candidate_id: uuid.UUID,
    job_id: uuid.UUID,
    overall_score: Decimal = Decimal("84.50"),
    skill_score: Decimal = Decimal("90.00"),
    experience_score: Decimal = Decimal("80.00"),
    salary_score: Decimal = Decimal("70.00"),
    location_score: Decimal = Decimal("100.00"),
    breakdown: dict[str, Any] | None = None,
) -> MatchScore:
    """Build the score of one candidate against one job.

    Args:
        candidate_id: Candidate the score was computed for.
        job_id: Posting the candidate was scored against.
        overall_score: Weighted aggregate of the four dimensions.
        skill_score: Skill overlap dimension, normalized to ``0..100``.
        experience_score: Experience dimension, normalized to ``0..100``.
        salary_score: Salary fit dimension, normalized to ``0..100``.
        location_score: Location fit dimension, normalized to ``0..100``.
        breakdown: Matched and missing skills justifying the result.

    Returns:
        An unpersisted ``MatchScore``.
    """
    return MatchScore(
        candidate_id=candidate_id,
        job_id=job_id,
        overall_score=overall_score,
        skill_score=skill_score,
        experience_score=experience_score,
        salary_score=salary_score,
        location_score=location_score,
        breakdown=_or_default(
            breakdown,
            {
                "matched_skills": ["python", "fastapi", "postgresql"],
                "missing_skills": [],
            },
        ),
    )


def build_note(
    *,
    candidate_id: uuid.UUID,
    author_id: uuid.UUID,
    body: str = "Strong systems background, worth a technical screen.",
) -> Note:
    """Build a collaboration note left on a candidate.

    Args:
        candidate_id: Candidate the note is attached to.
        author_id: User who wrote the note.
        body: Text of the note.

    Returns:
        An unpersisted ``Note``.
    """
    return Note(candidate_id=candidate_id, author_id=author_id, body=body)


def build_stage_transition(
    *,
    candidate_id: uuid.UUID,
    changed_by: uuid.UUID,
    from_stage: CandidateStage | None = None,
    to_stage: CandidateStage = CandidateStage.SCREENING,
    reason: str | None = None,
) -> StageTransition:
    """Build one recorded move of a candidate between pipeline stages.

    Args:
        candidate_id: Candidate that moved.
        changed_by: User who performed the move.
        from_stage: Stage left behind; ``None`` marks pipeline entry.
        to_stage: Stage the candidate moved into.
        reason: Justification recorded alongside the move.

    Returns:
        An unpersisted ``StageTransition``.
    """
    return StageTransition(
        candidate_id=candidate_id,
        changed_by=changed_by,
        from_stage=from_stage,
        to_stage=to_stage,
        reason=reason,
    )


def build_webhook(
    *,
    company_id: uuid.UUID,
    url: str | None = None,
    event_type: WebhookEventType = WebhookEventType.CANDIDATE_HIGH_MATCH,
    secret: str | None = None,
    threshold: Decimal | None = Decimal("80.00"),
    is_active: bool = True,
) -> Webhook:
    """Build an endpoint subscribed to a company's domain events.

    Args:
        company_id: Tenant that registered the endpoint.
        url: Address the payloads are delivered to.
        event_type: Event the endpoint is subscribed to.
        secret: Key the outgoing payloads are signed with.
        threshold: Score above which a score-driven event fires.
        is_active: Whether deliveries are currently dispatched.

    Returns:
        An unpersisted ``Webhook``.
    """
    sequence = next_sequence_value()
    return Webhook(
        company_id=company_id,
        url=_or_default(url, f"https://hooks.example.com/{sequence:08d}"),
        event_type=event_type,
        secret=_or_default(secret, f"webhook-secret-{sequence:08d}"),
        threshold=threshold,
        is_active=is_active,
    )


def build_webhook_delivery(
    *,
    webhook_id: uuid.UUID,
    event_type: str = WebhookEventType.CANDIDATE_HIGH_MATCH.value,
    payload: dict[str, Any] | None = None,
    response_status: int | None = None,
    attempts: int = 0,
    delivered: bool = False,
    last_attempt_at: datetime.datetime | None = None,
) -> WebhookDelivery:
    """Build one delivery attempt log for a registered webhook.

    Args:
        webhook_id: Endpoint the payload was addressed to.
        event_type: Event that triggered the delivery.
        payload: Body that was, or will be, sent.
        response_status: HTTP status the receiver answered with.
        attempts: Delivery attempts made so far.
        delivered: Whether the receiver acknowledged the payload.
        last_attempt_at: Instant of the most recent attempt.

    Returns:
        An unpersisted ``WebhookDelivery``.
    """
    return WebhookDelivery(
        webhook_id=webhook_id,
        event_type=event_type,
        payload=_or_default(payload, {"overall_score": 84.5}),
        response_status=response_status,
        attempts=attempts,
        delivered=delivered,
        last_attempt_at=last_attempt_at,
    )
