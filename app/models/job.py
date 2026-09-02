"""ORM model for job postings and their weighted requirements."""

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKey
from app.models.enums import JOB_STATUS_ENUM, JobStatus

if TYPE_CHECKING:
    from app.models.candidate import Candidate
    from app.models.company import Company
    from app.models.match import MatchScore
    from app.models.user import User


class Job(UUIDPrimaryKey, TimestampMixin, Base):
    """An open position candidates are screened and scored against.

    ``required_skills`` holds the weighted requirement list consumed by
    the matching engine, shaped as ``[{"skill": "python", "weight": 5}]``.
    """

    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint("min_years_experience >= 0", name="min_years_experience_non_negative"),
        CheckConstraint(
            "salary_min IS NULL OR salary_max IS NULL OR salary_min <= salary_max",
            name="salary_range_ordered",
        ),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    required_skills: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    min_years_experience: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="USD",
        server_default=text("'USD'"),
    )
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remote_allowed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    status: Mapped[JobStatus] = mapped_column(
        JOB_STATUS_ENUM,
        nullable=False,
        default=JobStatus.OPEN,
    )

    company: Mapped["Company"] = relationship(back_populates="jobs")
    creator: Mapped["User"] = relationship(back_populates="created_jobs")
    candidates: Mapped[list["Candidate"]] = relationship(
        back_populates="job",
        passive_deletes=True,
    )
    match_scores: Mapped[list["MatchScore"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
