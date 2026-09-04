"""Data access for tenants."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.repositories.base import BaseRepository


class CompanyRepository(BaseRepository[Company]):
    """Reads and writes the tenant root entity."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind the repository to a session.

        Args:
            session: The async session the statements are executed on.
        """
        super().__init__(session, Company)

    async def get_by_slug(self, slug: str) -> Company | None:
        """Retrieve a company by slug.

        The column is ``CITEXT``, so the lookup is case-insensitive
        without lowering either side of the comparison.

        Args:
            slug: The slug to look up.

        Returns:
            The matching company, or ``None`` if the slug is unknown.
        """
        companies = await self.list(Company.slug == slug, limit=1)
        return companies[0] if companies else None

    async def slug_exists(self, slug: str) -> bool:
        """Report whether a slug is already taken.

        Args:
            slug: The slug to check.

        Returns:
            ``True`` if a company already uses that slug.
        """
        return await self.exists(Company.slug == slug)

    async def get_by_stripe_customer_id(self, stripe_customer_id: str) -> Company | None:
        """Retrieve the company a payment gateway customer belongs to.

        Args:
            stripe_customer_id: The gateway customer identifier.

        Returns:
            The matching company, or ``None`` if the identifier is
            unknown.
        """
        companies = await self.list(Company.stripe_customer_id == stripe_customer_id, limit=1)
        return companies[0] if companies else None
