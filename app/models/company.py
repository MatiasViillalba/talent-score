"""ORM model for the tenant root entity."""

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKey

if TYPE_CHECKING:
    from app.models.subscription import Subscription, UsageRecord
    from app.models.user import User


class Company(UUIDPrimaryKey, TimestampMixin, Base):
    """A tenant of the platform.

    Every business table carries a ``company_id`` pointing here, which is
    the boundary all tenant-scoped queries filter on.
    """

    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(CITEXT(), nullable=False, unique=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
    )

    users: Mapped[list["User"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    subscription: Mapped["Subscription | None"] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    usage_records: Mapped[list["UsageRecord"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
