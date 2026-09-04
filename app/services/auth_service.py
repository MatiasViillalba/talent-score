"""Business logic for account creation and authentication."""

import uuid
from typing import Final

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import EmailAlreadyRegisteredError
from app.core.security import hash_password
from app.models.company import Company
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.company import CompanyRepository
from app.repositories.user import UserRepository
from app.schemas.auth import RegisterRequest
from app.utils.slug import slugify

FALLBACK_COMPANY_SLUG: Final = "company"
SLUG_DISAMBIGUATOR_LENGTH: Final = 8


class AuthService:
    """Creates accounts and verifies credentials."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind the service to the session that owns its transaction.

        Args:
            session: The async session every write is issued through.
        """
        self._session = session
        self._companies = CompanyRepository(session)
        self._users = UserRepository(session)

    async def register(self, payload: RegisterRequest) -> User:
        """Create a company and the owner account that administers it.

        Registration is the only way a tenant comes into existence, so
        the first user is always an ``owner``: every later account is
        invited by that one and receives a role explicitly.

        A unique violation raised during the insert is reported as the
        same conflict the pre-check guards against. The email is the only
        caller-controlled value under a unique constraint in this
        transaction — a colliding slug is disambiguated before the insert
        — so the sole way to reach it is a registration that raced.

        Args:
            payload: The submitted registration details.

        Returns:
            The created owner, committed and readable.

        Raises:
            EmailAlreadyRegisteredError: If the address already belongs
                to an account.
        """
        if await self._users.email_exists(payload.email):
            raise EmailAlreadyRegisteredError("That email address is already registered.")

        try:
            company = await self._companies.create(
                Company(
                    name=payload.company_name,
                    slug=await self._allocate_slug(payload.company_name),
                )
            )
            owner = await self._users.create(
                User(
                    company_id=company.id,
                    email=payload.email,
                    hashed_password=hash_password(payload.password),
                    full_name=payload.full_name,
                    role=UserRole.OWNER,
                )
            )
        except IntegrityError as error:
            await self._session.rollback()
            raise EmailAlreadyRegisteredError(
                "That email address is already registered."
            ) from error

        await self._session.commit()
        return owner

    async def _allocate_slug(self, company_name: str) -> str:
        """Derive a slug for a company name that no tenant holds yet.

        Args:
            company_name: The display name to derive the slug from.

        Returns:
            The derived slug, suffixed with a random disambiguator when
            the plain form is taken, and falling back to a generic base
            when the name yields no slug at all.
        """
        base = slugify(company_name) or FALLBACK_COMPANY_SLUG
        if not await self._companies.slug_exists(base):
            return base
        return f"{base}-{uuid.uuid4().hex[:SLUG_DISAMBIGUATOR_LENGTH]}"
