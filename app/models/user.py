"""ORM model for platform users."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKey
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.candidate import Candidate
    from app.models.company import Company
    from app.models.job import Job


class User(UUIDPrimaryKey, TimestampMixin, Base):
    """A member of a company, authenticated by email and password."""

    __tablename__ = "users"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(CITEXT(), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        default=UserRole.RECRUITER,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    company: Mapped["Company"] = relationship(back_populates="users")
    created_jobs: Mapped[list["Job"]] = relationship(back_populates="creator")
    uploaded_candidates: Mapped[list["Candidate"]] = relationship(back_populates="uploader")
