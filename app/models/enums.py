"""Enumerations shared by the ORM models and the API schemas.

Alongside each Python enum, the module exposes the single ``sa.Enum``
instance that maps it to a PostgreSQL enum type. Sharing one instance
across every table that references the type keeps Alembic from emitting
a duplicate ``CREATE TYPE`` for it.
"""

from enum import StrEnum

from sqlalchemy import Enum as SQLEnum


class UserRole(StrEnum):
    """Role granted to a user inside its company."""

    OWNER = "owner"
    ADMIN = "admin"
    RECRUITER = "recruiter"
    VIEWER = "viewer"


class SubscriptionPlan(StrEnum):
    """Commercial plan a company is subscribed to."""

    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(StrEnum):
    """Lifecycle state of a subscription, mirrored from the payment gateway."""

    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"


class JobStatus(StrEnum):
    """Publication state of a job posting."""

    OPEN = "open"
    CLOSED = "closed"
    ARCHIVED = "archived"


class ParseStatus(StrEnum):
    """Progress of the asynchronous resume parsing pipeline."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class CandidateStage(StrEnum):
    """Position of a candidate in the recruitment pipeline."""

    SCREENING = "screening"
    INTERVIEW = "interview"
    OFFER = "offer"
    HIRED = "hired"
    REJECTED = "rejected"


class WebhookEventType(StrEnum):
    """Domain event a company can subscribe an outgoing webhook to."""

    CANDIDATE_HIGH_MATCH = "candidate.high_match"
    CANDIDATE_STAGE_CHANGED = "candidate.stage_changed"


def _pg_enum(enum_class: type[StrEnum], type_name: str) -> SQLEnum:
    """Build the PostgreSQL enum type backing a Python enum.

    Args:
        enum_class: The Python enum whose members become type labels.
        type_name: The name of the resulting PostgreSQL enum type.

    Returns:
        A SQLAlchemy ``Enum`` type persisting member values rather than
        member names, so the database stores ``past_due`` and not
        ``PAST_DUE``.
    """
    return SQLEnum(
        enum_class,
        name=type_name,
        values_callable=lambda enum: [member.value for member in enum],
    )


USER_ROLE_ENUM = _pg_enum(UserRole, "user_role")
SUBSCRIPTION_PLAN_ENUM = _pg_enum(SubscriptionPlan, "subscription_plan")
SUBSCRIPTION_STATUS_ENUM = _pg_enum(SubscriptionStatus, "subscription_status")
JOB_STATUS_ENUM = _pg_enum(JobStatus, "job_status")
PARSE_STATUS_ENUM = _pg_enum(ParseStatus, "parse_status")
CANDIDATE_STAGE_ENUM = _pg_enum(CandidateStage, "candidate_stage")
WEBHOOK_EVENT_TYPE_ENUM = _pg_enum(WebhookEventType, "webhook_event_type")
