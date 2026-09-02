"""Data access for platform users."""

import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Reads and writes users, always scoped to a single company."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind the repository to a session.

        Args:
            session: The async session the statements are executed on.
        """
        super().__init__(session, User)

    async def get_by_email(self, email: str) -> User | None:
        """Retrieve a user by email address.

        The column is ``CITEXT``, so the lookup is case-insensitive
        without lowering either side of the comparison.

        Args:
            email: The address to look up.

        Returns:
            The matching user, or ``None`` if the address is unknown.
        """
        users = await self.list(User.email == email, limit=1)
        return users[0] if users else None

    async def get_for_company(self, user_id: uuid.UUID, company_id: uuid.UUID) -> User | None:
        """Retrieve a user that belongs to the given company.

        The company is part of the lookup rather than checked afterwards,
        so a valid identifier from another tenant reads as a missing row.

        Args:
            user_id: The primary key to look up.
            company_id: The company the user must belong to.

        Returns:
            The matching user, or ``None`` if it does not exist within
            that company.
        """
        users = await self.list(User.id == user_id, User.company_id == company_id, limit=1)
        return users[0] if users else None

    async def list_for_company(
        self,
        company_id: uuid.UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[User]:
        """Retrieve a page of the company's users, newest first.

        Args:
            company_id: The company whose users are listed.
            limit: Maximum number of rows to return.
            offset: Number of rows to skip before collecting the page.

        Returns:
            The company's users, at most ``limit`` of them.
        """
        return await self.list(
            User.company_id == company_id,
            limit=limit,
            offset=offset,
            order_by=User.created_at.desc(),
        )

    async def count_for_company(self, company_id: uuid.UUID) -> int:
        """Count the users of a company.

        Args:
            company_id: The company whose users are counted.

        Returns:
            The number of users in that company.
        """
        return await self.count(User.company_id == company_id)

    async def email_exists(self, email: str) -> bool:
        """Report whether an email address is already registered.

        Args:
            email: The address to check.

        Returns:
            ``True`` if a user already owns that address.
        """
        return await self.exists(User.email == email)
