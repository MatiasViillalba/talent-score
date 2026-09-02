"""ORM models for subscription billing and quota consumption."""

import datetime
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKey
from app.models.enums import SubscriptionPlan, SubscriptionStatus

if TYPE_CHECKING:
    from app.models.company import Company


class Subscription(UUIDPrimaryKey, TimestampMixin, Base):
    """The single active subscription of a company.

    The row is the local projection of the payment gateway state: the
    gateway remains the source of truth and its webhooks keep ``status``,
    ``plan`` and ``current_period_end`` in sync.
    """

    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint("monthly_cv_quota >= 0", name="monthly_cv_quota_non_negative"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
    )
    plan: Mapped[SubscriptionPlan] = mapped_column(
        Enum(
            SubscriptionPlan,
            name="subscription_plan",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        default=SubscriptionPlan.STARTER,
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(
            SubscriptionStatus,
            name="subscription_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        default=SubscriptionStatus.TRIALING,
    )
    monthly_cv_quota: Mapped[int] = mapped_column(Integer, nullable=False)
    current_period_end: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    company: Mapped["Company"] = relationship(back_populates="subscription")


class UsageRecord(UUIDPrimaryKey, TimestampMixin, Base):
    """Resumes processed by a company within one billing period.

    One row per company and period start; the counter is incremented as
    resumes are parsed and checked against the subscription quota.
    """

    __tablename__ = "usage_records"
    __table_args__ = (
        UniqueConstraint("company_id", "period_start"),
        CheckConstraint("cv_processed_count >= 0", name="cv_processed_count_non_negative"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    period_start: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    cv_processed_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    company: Mapped["Company"] = relationship(back_populates="usage_records")
