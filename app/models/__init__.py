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
)
from app.models.job import Job
from app.models.subscription import Subscription, UsageRecord
from app.models.user import User

__all__ = [
    "Candidate",
    "CandidateProfile",
    "CandidateStage",
    "Company",
    "Job",
    "JobStatus",
    "ParseStatus",
    "Subscription",
    "SubscriptionPlan",
    "SubscriptionStatus",
    "UsageRecord",
    "User",
    "UserRole",
]
