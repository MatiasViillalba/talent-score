"""ORM model for collaboration notes left on a candidate."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPrimaryKey

if TYPE_CHECKING:
    from app.models.candidate import Candidate
    from app.models.user import User


class Note(UUIDPrimaryKey, TimestampMixin, Base):
    """A comment written by a recruiter on a candidate.

    Creating a note publishes a ``note_added`` event that is broadcast to
    every recruiter subscribed to the candidate's channel.
    """

    __tablename__ = "notes"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)

    candidate: Mapped["Candidate"] = relationship(back_populates="notes")
    author: Mapped["User"] = relationship(back_populates="notes")
