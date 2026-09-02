"""Data access for the pipeline audit trail."""

import uuid
from collections.abc import Mapping, Sequence
from typing import Any, NoReturn

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candidate import Candidate
from app.models.pipeline import StageTransition
from app.repositories.base import BaseRepository


class PipelineRepository(BaseRepository[StageTransition]):
    """Appends and reads stage transitions.

    The audit trail is append-only, so ``update`` and ``delete`` are
    closed off here: an invariant that only exists in documentation is one
    a future caller will break by accident.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Bind the repository to a session.

        Args:
            session: The async session the statements are executed on.
        """
        super().__init__(session, StageTransition)

    async def list_for_candidate(
        self,
        candidate_id: uuid.UUID,
        company_id: uuid.UUID,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[StageTransition]:
        """Retrieve a candidate's transition history, oldest first.

        Args:
            candidate_id: The candidate whose history is read.
            company_id: The company the candidate must belong to.
            limit: Maximum number of rows to return.
            offset: Number of rows to skip before collecting the page.

        Returns:
            The recorded transitions in chronological order, at most
            ``limit`` of them.
        """
        statement = (
            self._scoped(company_id)
            .where(StageTransition.candidate_id == candidate_id)
            .order_by(StageTransition.created_at)
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(statement)
        return result.scalars().all()

    async def get_latest_for_candidate(
        self,
        candidate_id: uuid.UUID,
        company_id: uuid.UUID,
    ) -> StageTransition | None:
        """Retrieve the most recent transition of a candidate.

        Args:
            candidate_id: The candidate whose last move is read.
            company_id: The company the candidate must belong to.

        Returns:
            The latest transition, or ``None`` if the candidate has never
            moved.
        """
        statement = (
            self._scoped(company_id)
            .where(StageTransition.candidate_id == candidate_id)
            .order_by(StageTransition.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(statement)
        return result.scalars().one_or_none()

    async def count_for_candidate(
        self,
        candidate_id: uuid.UUID,
        company_id: uuid.UUID,
    ) -> int:
        """Count a candidate's recorded transitions.

        Args:
            candidate_id: The candidate whose history is counted.
            company_id: The company the candidate must belong to.

        Returns:
            The number of recorded transitions.
        """
        statement = (
            select(func.count())
            .select_from(StageTransition)
            .join(Candidate, Candidate.id == StageTransition.candidate_id)
            .where(
                Candidate.company_id == company_id,
                StageTransition.candidate_id == candidate_id,
            )
        )
        result = await self._session.execute(statement)
        return result.scalar_one()

    async def update(self, entity: StageTransition, values: Mapping[str, Any]) -> NoReturn:
        """Reject any attempt to rewrite a recorded transition.

        Args:
            entity: The transition a caller tried to modify.
            values: The changes a caller tried to apply.

        Raises:
            NotImplementedError: Always; the audit trail is append-only.
        """
        raise NotImplementedError("Stage transitions are immutable once recorded")

    async def delete(self, entity: StageTransition) -> NoReturn:
        """Reject any attempt to erase a recorded transition.

        Args:
            entity: The transition a caller tried to remove.

        Raises:
            NotImplementedError: Always; the audit trail is append-only.
        """
        raise NotImplementedError("Stage transitions cannot be deleted")

    @staticmethod
    def _scoped(company_id: uuid.UUID) -> Select[tuple[StageTransition]]:
        """Build the tenant-scoped base statement.

        Args:
            company_id: The company the candidate must belong to.

        Returns:
            A ``SELECT`` over transitions restricted to that company.
        """
        return (
            select(StageTransition)
            .join(Candidate, Candidate.id == StageTransition.candidate_id)
            .where(Candidate.company_id == company_id)
        )
