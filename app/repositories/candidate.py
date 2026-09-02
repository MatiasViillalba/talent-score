"""Data access for uploaded resumes."""

import uuid
from collections.abc import Sequence

from sqlalchemy import ColumnExpressionArgument, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.candidate import Candidate
from app.models.enums import CandidateStage
from app.repositories.base import BaseRepository


class CandidateRepository(BaseRepository[Candidate]):
    """Reads and writes candidates, always scoped to a single company."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind the repository to a session.

        Args:
            session: The async session the statements are executed on.
        """
        super().__init__(session, Candidate)

    async def get_for_company(
        self,
        candidate_id: uuid.UUID,
        company_id: uuid.UUID,
    ) -> Candidate | None:
        """Retrieve a candidate that belongs to the given company.

        Args:
            candidate_id: The primary key to look up.
            company_id: The company the candidate must belong to.

        Returns:
            The matching candidate, or ``None`` if it does not exist
            within that company.
        """
        candidates = await self.list(
            Candidate.id == candidate_id,
            Candidate.company_id == company_id,
            limit=1,
        )
        return candidates[0] if candidates else None

    async def get_with_profile(
        self,
        candidate_id: uuid.UUID,
        company_id: uuid.UUID,
    ) -> Candidate | None:
        """Retrieve a candidate together with its parsed profile.

        The profile is eager loaded, because reading a lazy relationship
        outside the loading context raises in an async session.

        Args:
            candidate_id: The primary key to look up.
            company_id: The company the candidate must belong to.

        Returns:
            The matching candidate with ``profile`` populated, or ``None``
            if it does not exist within that company.
        """
        statement = (
            select(Candidate)
            .where(Candidate.id == candidate_id, Candidate.company_id == company_id)
            .options(selectinload(Candidate.profile))
        )
        result = await self._session.execute(statement)
        return result.scalars().one_or_none()

    async def get_by_file_hash(
        self,
        company_id: uuid.UUID,
        file_hash: str,
    ) -> Candidate | None:
        """Retrieve the candidate a previously uploaded file produced.

        Deduplication is per tenant: the same resume may legitimately be
        uploaded by two different companies.

        Args:
            company_id: The company the upload belongs to.
            file_hash: The content hash of the uploaded file.

        Returns:
            The candidate created by an earlier upload of the same
            content, or ``None`` if the content is new to that company.
        """
        candidates = await self.list(
            Candidate.company_id == company_id,
            Candidate.file_hash == file_hash,
            limit=1,
        )
        return candidates[0] if candidates else None

    async def list_for_company(
        self,
        company_id: uuid.UUID,
        *,
        job_id: uuid.UUID | None = None,
        stage: CandidateStage | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Candidate]:
        """Retrieve a page of the company's candidates, newest first.

        Args:
            company_id: The company whose candidates are listed.
            job_id: Restricts the page to the candidates of one job when
                given.
            stage: Restricts the page to a single pipeline stage when
                given.
            limit: Maximum number of rows to return.
            offset: Number of rows to skip before collecting the page.

        Returns:
            The matching candidates, at most ``limit`` of them.
        """
        return await self.list(
            *self._filters(company_id, job_id, stage),
            limit=limit,
            offset=offset,
            order_by=Candidate.created_at.desc(),
        )

    async def count_for_company(
        self,
        company_id: uuid.UUID,
        *,
        job_id: uuid.UUID | None = None,
        stage: CandidateStage | None = None,
    ) -> int:
        """Count the company's candidates.

        Args:
            company_id: The company whose candidates are counted.
            job_id: Restricts the count to the candidates of one job when
                given.
            stage: Restricts the count to a single pipeline stage when
                given.

        Returns:
            The number of matching candidates.
        """
        return await self.count(*self._filters(company_id, job_id, stage))

    @staticmethod
    def _filters(
        company_id: uuid.UUID,
        job_id: uuid.UUID | None,
        stage: CandidateStage | None,
    ) -> list[ColumnExpressionArgument[bool]]:
        """Build the filter list shared by listing and counting.

        Args:
            company_id: The company the candidates must belong to.
            job_id: The job to restrict to, if any.
            stage: The pipeline stage to restrict to, if any.

        Returns:
            The SQL expressions to combine with ``AND``.
        """
        filters: list[ColumnExpressionArgument[bool]] = [Candidate.company_id == company_id]
        if job_id is not None:
            filters.append(Candidate.job_id == job_id)
        if stage is not None:
            filters.append(Candidate.stage == stage)
        return filters
