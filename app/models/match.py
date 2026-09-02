"""ORM model for the computed candidate-to-job match scores."""

import datetime
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKey

if TYPE_CHECKING:
    from app.models.candidate import Candidate
    from app.models.job import Job

_SCORE_COLUMNS = (
    "overall_score",
    "skill_score",
    "experience_score",
    "salary_score",
    "location_score",
)


class MatchScore(UUIDPrimaryKey, TimestampMixin, Base):
    """The score of one candidate against one job.

    Each dimension is normalized to the ``0..100`` range before being
    weighted into ``overall_score``; ``breakdown`` keeps the matched and
    missing skills that justify the result.
    """

    __tablename__ = "match_scores"
    __table_args__ = (
        UniqueConstraint("candidate_id", "job_id"),
        *(
            CheckConstraint(f"{column} BETWEEN 0 AND 100", name=f"{column}_within_range")
            for column in _SCORE_COLUMNS
        ),
    )

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    overall_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    skill_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    experience_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    salary_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    location_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    breakdown: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    computed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    candidate: Mapped["Candidate"] = relationship(back_populates="match_scores")
    job: Mapped["Job"] = relationship(back_populates="match_scores")
