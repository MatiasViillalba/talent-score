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
