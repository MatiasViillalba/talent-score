"""Integration tests for the registration endpoint."""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.models import Company, User, UserRole

REGISTER_URL = "/api/v1/auth/register"
PASSWORD = "correct-horse-battery-staple"


def _registration(**overrides: Any) -> dict[str, Any]:
    """Build a valid registration payload with the given overrides.

    Args:
        **overrides: Fields replacing the defaults.

    Returns:
        The payload to post.
    """
    payload: dict[str, Any] = {
        "company_name": "Northwind Talent",
        "email": "owner@northwind.example",
        "password": PASSWORD,
        "full_name": "Dana Reyes",
    }
    payload.update(overrides)
    return payload


async def test_registration_creates_a_company_and_its_owner(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """A first registration provisions the tenant and its administrator."""
    response = await client.post(REGISTER_URL, json=_registration())

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "owner@northwind.example"
    assert body["role"] == UserRole.OWNER.value
    assert body["is_active"] is True

    owner = await db_session.get(User, body["id"])
    assert owner is not None
    company = await db_session.get(Company, owner.company_id)
    assert company is not None
    assert company.name == "Northwind Talent"
    assert company.slug == "northwind-talent"


async def test_registration_never_returns_the_password(client: AsyncClient) -> None:
    """Neither the plain password nor its digest reaches the response."""
    response = await client.post(REGISTER_URL, json=_registration())

    body = response.json()
    assert "password" not in body
    assert "hashed_password" not in body


async def test_registration_stores_a_verifiable_digest(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """The password is stored hashed and verifies against the original."""
    response = await client.post(REGISTER_URL, json=_registration())

    owner = await db_session.get(User, response.json()["id"])
    assert owner is not None
    assert owner.hashed_password != PASSWORD
    assert verify_password(PASSWORD, owner.hashed_password) is True


async def test_duplicate_email_is_rejected(client: AsyncClient) -> None:
    """A second account cannot claim an address already registered."""
    await client.post(REGISTER_URL, json=_registration())

    response = await client.post(
        REGISTER_URL,
        json=_registration(company_name="Another Company"),
    )

    assert response.status_code == 409
    assert "detail" in response.json()


async def test_duplicate_email_is_matched_case_insensitively(client: AsyncClient) -> None:
    """Addresses differing only in case belong to the same account."""
    await client.post(REGISTER_URL, json=_registration())

    response = await client.post(
        REGISTER_URL,
        json=_registration(email="OWNER@NORTHWIND.EXAMPLE"),
    )

    assert response.status_code == 409


async def test_colliding_company_names_get_distinct_slugs(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """A second tenant with the same name still gets a unique slug."""
    await client.post(REGISTER_URL, json=_registration())
    await client.post(REGISTER_URL, json=_registration(email="second@northwind.example"))

    slugs = (await db_session.scalars(select(Company.slug))).all()

    assert len(slugs) == 2
    assert len(set(slugs)) == 2
    assert "northwind-talent" in slugs


async def test_company_name_without_alphanumerics_still_yields_a_slug(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """A name the slug rules reduce to nothing falls back to a usable value."""
    response = await client.post(REGISTER_URL, json=_registration(company_name="///"))

    assert response.status_code == 201
    owner = await db_session.get(User, response.json()["id"])
    assert owner is not None
    company = await db_session.get(Company, owner.company_id)
    assert company is not None
    assert company.slug == "company"


@pytest.mark.parametrize(
    "overrides",
    [
        {"email": "not-an-address"},
        {"password": "short"},
        {"password": "a" * 73},
        {"company_name": "   "},
        {"full_name": ""},
    ],
)
async def test_invalid_payloads_are_rejected(
    client: AsyncClient,
    overrides: dict[str, Any],
) -> None:
    """Malformed registration details never reach the database."""
    response = await client.post(REGISTER_URL, json=_registration(**overrides))

    assert response.status_code == 422
