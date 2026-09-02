"""ORM models for uploaded resumes and their extracted structured data."""

import datetime
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKey
from app.models.enums import CandidateStage, ParseStatus

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.job import Job
    from app.models.user import User


class Candidate(UUIDPrimaryKey, TimestampMixin, Base):
    """A resume uploaded to the platform and its pipeline state.

    The row is created as soon as the file is stored, before parsing
    runs, so ``raw_text`` and the structured profile are populated later
    by the asynchronous extraction pipeline.
    """

    __tablename__ = "candidates"
    __table_args__ = (UniqueConstraint("company_id", "file_hash"),)

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    parse_status: Mapped[ParseStatus] = mapped_column(
        Enum(
            ParseStatus,
            name="parse_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        default=ParseStatus.PENDING,
    )
    stage: Mapped[CandidateStage] = mapped_column(
        Enum(
            CandidateStage,
            name="candidate_stage",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        default=CandidateStage.SCREENING,
    )

    company: Mapped["Company"] = relationship(back_populates="candidates")
    job: Mapped["Job | None"] = relationship(back_populates="candidates")
    uploader: Mapped["User"] = relationship(back_populates="uploaded_candidates")
    profile: Mapped["CandidateProfile | None"] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )


class CandidateProfile(UUIDPrimaryKey, TimestampMixin, Base):
    """Structured resume data extracted by the language model.

    ``model_version`` records which model and prompt revision produced
    the row, so profiles can be selectively re-parsed after a prompt
    change without rebuilding the whole corpus.
    """

    __tablename__ = "candidate_profiles"
    __table_args__ = (
        CheckConstraint(
            "years_experience IS NULL OR years_experience >= 0",
            name="years_experience_non_negative",
        ),
    )

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    years_experience: Mapped[Decimal | None] = mapped_column(Numeric(4, 1), nullable=True)
    skills: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    education: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    work_history: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    expected_salary: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    parsed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    candidate: Mapped["Candidate"] = relationship(back_populates="profile")
