"""Data access for candidate-to-job match scores."""

import uuid
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.match import MatchScore
from app.repositories.base import BaseRepository


class MatchRepository(BaseRepository[MatchScore]):
    """Reads and writes match scores.

    ``match_scores`` carries no ``company_id`` of its own, so every read
    reaches the tenant through the job it scores against rather than
    trusting the caller to have checked ownership beforehand.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Bind the repository to a session.

        Args:
            session: The async session the statements are executed on.
        """
        super().__init__(session, MatchScore)

    async def get_for_pair(
        self,
        candidate_id: uuid.UUID,
        job_id: uuid.UUID,
        company_id: uuid.UUID,
    ) -> MatchScore | None:
        """Retrieve the score of one candidate against one job.

        Args:
            candidate_id: The scored candidate.
            job_id: The job the candidate was scored against.
            company_id: The company both must belong to.

        Returns:
            The matching score, or ``None`` if the pair has not been
            scored within that company.
        """
        statement = self._scoped(company_id).where(
            MatchScore.candidate_id == candidate_id,
            MatchScore.job_id == job_id,
        )
        result = await self._session.execute(statement)
        return result.scalars().one_or_none()

    async def list_for_job(
        self,
        job_id: uuid.UUID,
        company_id: uuid.UUID,
        *,
        min_score: Decimal | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[MatchScore]:
        """Retrieve a page of a job's scores, best match first.

        Args:
            job_id: The job whose scores are listed.
            company_id: The company the job must belong to.
            min_score: Excludes scores below this value when given.
            limit: Maximum number of rows to return.
            offset: Number of rows to skip before collecting the page.

        Returns:
            The matching scores ordered by ``overall_score`` descending,
            at most ``limit`` of them.
        """
        statement = (
            self._scoped(company_id)
            .where(MatchScore.job_id == job_id)
            .order_by(MatchScore.overall_score.desc(), MatchScore.candidate_id)
            .limit(limit)
            .offset(offset)
        )
        if min_score is not None:
            statement = statement.where(MatchScore.overall_score >= min_score)
        result = await self._session.execute(statement)
        return result.scalars().all()

    async def count_for_job(
        self,
        job_id: uuid.UUID,
        company_id: uuid.UUID,
        *,
        min_score: Decimal | None = None,
    ) -> int:
        """Count a job's scores.

        Args:
            job_id: The job whose scores are counted.
            company_id: The company the job must belong to.
            min_score: Excludes scores below this value when given.

        Returns:
            The number of matching scores.
        """
        statement = (
            select(func.count())
            .select_from(MatchScore)
            .join(Job, Job.id == MatchScore.job_id)
            .where(Job.company_id == company_id, MatchScore.job_id == job_id)
        )
        if min_score is not None:
            statement = statement.where(MatchScore.overall_score >= min_score)
        result = await self._session.execute(statement)
        return result.scalar_one()

    async def upsert(
        self,
        candidate_id: uuid.UUID,
        job_id: uuid.UUID,
        values: Mapping[str, Any],
    ) -> MatchScore:
        """Insert a score, or overwrite the existing one for the pair.

        Recomputing a job re-scores candidates that may already have a
        row. Resolving that against the ``(candidate_id, job_id)`` unique
        constraint in a single statement keeps concurrent recomputes from
        racing between a read and a write.

        ``populate_existing`` is required for the returned entity to carry
        the new values: without it, a score already loaded in the session
        is handed back with its previous attributes even though the row
        was overwritten.

        Args:
            candidate_id: The scored candidate.
            job_id: The job the candidate was scored against.
            values: The score columns to write.

        Returns:
            The inserted or updated score.
        """
        updates: dict[str, Any] = {**values, "computed_at": func.now()}
        statement = (
            pg_insert(MatchScore)
            .values(candidate_id=candidate_id, job_id=job_id, **values)
            .on_conflict_do_update(
                index_elements=[MatchScore.candidate_id, MatchScore.job_id],
                set_=updates,
            )
            .returning(MatchScore)
        )
        result = await self._session.execute(
            statement,
            execution_options={"populate_existing": True},
        )
        return result.scalars().one()

    @staticmethod
    def _scoped(company_id: uuid.UUID) -> Select[tuple[MatchScore]]:
        """Build the tenant-scoped base statement.

        Args:
            company_id: The company the scored job must belong to.

        Returns:
            A ``SELECT`` over scores restricted to that company.
        """
        return (
            select(MatchScore)
            .join(Job, Job.id == MatchScore.job_id)
            .where(Job.company_id == company_id)
        )
