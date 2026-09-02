"""Data access for job postings."""

import uuid
from collections.abc import Sequence

from sqlalchemy import ColumnExpressionArgument
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import JobStatus
from app.models.job import Job
from app.repositories.base import BaseRepository


class JobRepository(BaseRepository[Job]):
    """Reads and writes job postings, always scoped to a single company."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind the repository to a session.

        Args:
            session: The async session the statements are executed on.
        """
        super().__init__(session, Job)

    async def get_for_company(self, job_id: uuid.UUID, company_id: uuid.UUID) -> Job | None:
        """Retrieve a job that belongs to the given company.

        Args:
            job_id: The primary key to look up.
            company_id: The company the job must belong to.

        Returns:
            The matching job, or ``None`` if it does not exist within that
            company.
        """
        jobs = await self.list(Job.id == job_id, Job.company_id == company_id, limit=1)
        return jobs[0] if jobs else None

    async def list_for_company(
        self,
        company_id: uuid.UUID,
        *,
        status: JobStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Job]:
        """Retrieve a page of the company's jobs, newest first.

        Args:
            company_id: The company whose jobs are listed.
            status: Restricts the page to a single publication state when
                given.
            limit: Maximum number of rows to return.
            offset: Number of rows to skip before collecting the page.

        Returns:
            The matching jobs, at most ``limit`` of them.
        """
        return await self.list(
            *self._filters(company_id, status),
            limit=limit,
            offset=offset,
            order_by=Job.created_at.desc(),
        )

    async def count_for_company(
        self,
        company_id: uuid.UUID,
        *,
        status: JobStatus | None = None,
    ) -> int:
        """Count the company's jobs.

        Args:
            company_id: The company whose jobs are counted.
            status: Restricts the count to a single publication state when
                given.

        Returns:
            The number of matching jobs.
        """
        return await self.count(*self._filters(company_id, status))

    @staticmethod
    def _filters(
        company_id: uuid.UUID,
        status: JobStatus | None,
    ) -> list[ColumnExpressionArgument[bool]]:
        """Build the filter list shared by listing and counting.

        Args:
            company_id: The company the jobs must belong to.
            status: The publication state to restrict to, if any.

        Returns:
            The SQL expressions to combine with ``AND``.
        """
        filters: list[ColumnExpressionArgument[bool]] = [Job.company_id == company_id]
        if status is not None:
            filters.append(Job.status == status)
        return filters
