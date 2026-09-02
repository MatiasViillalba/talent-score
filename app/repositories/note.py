"""Data access for collaboration notes."""

import uuid
from collections.abc import Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candidate import Candidate
from app.models.note import Note
from app.repositories.base import BaseRepository


class NoteRepository(BaseRepository[Note]):
    """Reads and writes notes.

    Notes belong to a tenant through their candidate, so every read joins
    the candidate rather than trusting the caller to have checked
    ownership beforehand.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Bind the repository to a session.

        Args:
            session: The async session the statements are executed on.
        """
        super().__init__(session, Note)

    async def list_for_candidate(
        self,
        candidate_id: uuid.UUID,
        company_id: uuid.UUID,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Note]:
        """Retrieve a candidate's notes in the order they were written.

        Args:
            candidate_id: The candidate the notes belong to.
            company_id: The company the candidate must belong to.
            limit: Maximum number of rows to return.
            offset: Number of rows to skip before collecting the page.

        Returns:
            The candidate's notes, oldest first, at most ``limit`` of
            them.
        """
        statement = (
            self._scoped(company_id)
            .where(Note.candidate_id == candidate_id)
            .order_by(Note.created_at)
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(statement)
        return result.scalars().all()

    async def count_for_candidate(
        self,
        candidate_id: uuid.UUID,
        company_id: uuid.UUID,
    ) -> int:
        """Count a candidate's notes.

        Args:
            candidate_id: The candidate the notes belong to.
            company_id: The company the candidate must belong to.

        Returns:
            The number of notes on that candidate.
        """
        statement = (
            select(func.count())
            .select_from(Note)
            .join(Candidate, Candidate.id == Note.candidate_id)
            .where(Candidate.company_id == company_id, Note.candidate_id == candidate_id)
        )
        result = await self._session.execute(statement)
        return result.scalar_one()

    @staticmethod
    def _scoped(company_id: uuid.UUID) -> Select[tuple[Note]]:
        """Build the tenant-scoped base statement.

        Args:
            company_id: The company the candidate must belong to.

        Returns:
            A ``SELECT`` over notes restricted to that company.
        """
        return (
            select(Note)
            .join(Candidate, Candidate.id == Note.candidate_id)
            .where(Candidate.company_id == company_id)
        )
