"""ORM model registry.

Importing every model here binds it to the shared ``Base.metadata``, so
Alembic autogeneration and test schema creation see the full schema from
a single import.
"""

from app.models.candidate import Candidate, CandidateProfile
from app.models.company import Company
from app.models.enums import (
    CandidateStage,
    JobStatus,
    ParseStatus,
    SubscriptionPlan,
    SubscriptionStatus,
    UserRole,
    WebhookEventType,
)
from app.models.job import Job
from app.models.match import MatchScore
from app.models.note import Note
from app.models.pipeline import StageTransition
from app.models.subscription import Subscription, UsageRecord
from app.models.user import User
from app.models.webhook import Webhook, WebhookDelivery

__all__ = [
    "Candidate",
    "CandidateProfile",
    "CandidateStage",
    "Company",
    "Job",
    "JobStatus",
    "MatchScore",
    "Note",
    "ParseStatus",
    "StageTransition",
    "Subscription",
    "SubscriptionPlan",
    "SubscriptionStatus",
    "UsageRecord",
    "User",
    "UserRole",
    "Webhook",
    "WebhookDelivery",
    "WebhookEventType",
]
