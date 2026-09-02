"""ORM models for outgoing webhook subscriptions and their deliveries."""

import datetime
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKey
from app.models.enums import WEBHOOK_EVENT_TYPE_ENUM, WebhookEventType

if TYPE_CHECKING:
    from app.models.company import Company


class Webhook(UUIDPrimaryKey, TimestampMixin, Base):
    """An endpoint a company registered to receive domain events.

    Every payload is signed with the per-webhook ``secret``, so the
    receiver can verify the request originated from this platform.
    ``threshold`` applies to score-driven events and is null otherwise.
    """

    __tablename__ = "webhooks"
    __table_args__ = (
        CheckConstraint(
            "threshold IS NULL OR threshold BETWEEN 0 AND 100",
            name="threshold_within_range",
        ),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    event_type: Mapped[WebhookEventType] = mapped_column(
        WEBHOOK_EVENT_TYPE_ENUM,
        nullable=False,
    )
    secret: Mapped[str] = mapped_column(String(255), nullable=False)
    threshold: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    company: Mapped["Company"] = relationship(back_populates="webhooks")
    deliveries: Mapped[list["WebhookDelivery"]] = relationship(
        back_populates="webhook",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class WebhookDelivery(UUIDPrimaryKey, Base):
    """One delivery attempt log for a registered webhook.

    Rows are append-only in the sense that they are never removed: the
    retry logic only advances ``attempts``, ``response_status`` and
    ``delivered`` on the existing row, so the table records the full
    delivery history without an ``updated_at``.

    ``created_at`` defaults to ``clock_timestamp()`` rather than ``now()``:
    the latter is the transaction timestamp and stays frozen for the whole
    transaction, which would give deliveries fanned out to several
    webhooks at once an identical value and leave their order undefined.
    """

    __tablename__ = "webhook_deliveries"
    __table_args__ = (CheckConstraint("attempts >= 0", name="attempts_non_negative"),)

    webhook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("webhooks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    delivered: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    last_attempt_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.clock_timestamp(),
    )

    webhook: Mapped["Webhook"] = relationship(back_populates="deliveries")
