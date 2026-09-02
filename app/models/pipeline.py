"""ORM model for the immutable pipeline audit trail."""

import datetime
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UUIDPrimaryKey
from app.models.enums import CANDIDATE_STAGE_ENUM, CandidateStage

if TYPE_CHECKING:
    from app.models.candidate import Candidate
    from app.models.user import User


class StageTransition(UUIDPrimaryKey, Base):
    """One recorded move of a candidate between pipeline stages.

    Rows are append-only: they are never updated or deleted, which is why
    the table carries a ``created_at`` and no ``updated_at``. A null
    ``from_stage`` marks the candidate's entry into the pipeline.

    ``created_at`` defaults to ``clock_timestamp()`` rather than ``now()``:
    the latter is the transaction timestamp and stays frozen for the whole
    transaction, which would give two transitions written together an
    identical value and leave their chronological order undefined.
    """

    __tablename__ = "stage_transitions"
    __table_args__ = (
        CheckConstraint("from_stage IS DISTINCT FROM to_stage", name="stage_actually_changed"),
    )

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    changed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    from_stage: Mapped[CandidateStage | None] = mapped_column(
        CANDIDATE_STAGE_ENUM,
        nullable=True,
    )
    to_stage: Mapped[CandidateStage] = mapped_column(CANDIDATE_STAGE_ENUM, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.clock_timestamp(),
    )

    candidate: Mapped["Candidate"] = relationship(back_populates="stage_transitions")
    changed_by_user: Mapped["User"] = relationship(back_populates="stage_transitions")
