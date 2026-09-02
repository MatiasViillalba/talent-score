"""Enumerations shared by the ORM models and the API schemas."""

from enum import StrEnum


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
