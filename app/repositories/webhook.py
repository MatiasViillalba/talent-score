"""Data access for outgoing webhooks and their delivery log."""

import uuid
from collections.abc import Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import WebhookEventType
from app.models.webhook import Webhook, WebhookDelivery
from app.repositories.base import BaseRepository


class WebhookRepository(BaseRepository[Webhook]):
    """Reads and writes webhook subscriptions, scoped to one company."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind the repository to a session.

        Args:
            session: The async session the statements are executed on.
        """
        super().__init__(session, Webhook)

    async def get_for_company(
        self,
        webhook_id: uuid.UUID,
        company_id: uuid.UUID,
    ) -> Webhook | None:
        """Retrieve a webhook that belongs to the given company.

        Args:
            webhook_id: The primary key to look up.
            company_id: The company the webhook must belong to.

        Returns:
            The matching webhook, or ``None`` if it does not exist within
            that company.
        """
        webhooks = await self.list(
            Webhook.id == webhook_id,
            Webhook.company_id == company_id,
            limit=1,
        )
        return webhooks[0] if webhooks else None

    async def list_for_company(
        self,
        company_id: uuid.UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Webhook]:
        """Retrieve a page of the company's webhooks, newest first.

        Args:
            company_id: The company whose webhooks are listed.
            limit: Maximum number of rows to return.
            offset: Number of rows to skip before collecting the page.

        Returns:
            The company's webhooks, at most ``limit`` of them.
        """
        return await self.list(
            Webhook.company_id == company_id,
            limit=limit,
            offset=offset,
            order_by=Webhook.created_at.desc(),
        )

    async def list_active_for_event(
        self,
        company_id: uuid.UUID,
        event_type: WebhookEventType,
    ) -> Sequence[Webhook]:
        """Retrieve the webhooks that should receive a given event.

        Args:
            company_id: The company the event originated in.
            event_type: The event about to be dispatched.

        Returns:
            Every active subscription of that company for the event.
        """
        return await self.list(
            Webhook.company_id == company_id,
            Webhook.event_type == event_type,
            Webhook.is_active.is_(True),
            limit=100,
            order_by=Webhook.created_at,
        )

    async def count_for_company(self, company_id: uuid.UUID) -> int:
        """Count the company's webhooks.

        Args:
            company_id: The company whose webhooks are counted.

        Returns:
            The number of registered webhooks.
        """
        return await self.count(Webhook.company_id == company_id)


class WebhookDeliveryRepository(BaseRepository[WebhookDelivery]):
    """Reads and writes delivery attempts.

    Deliveries belong to a tenant through their webhook, so every read
    joins the webhook rather than trusting the caller to have checked
    ownership beforehand.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Bind the repository to a session.

        Args:
            session: The async session the statements are executed on.
        """
        super().__init__(session, WebhookDelivery)

    async def list_for_webhook(
        self,
        webhook_id: uuid.UUID,
        company_id: uuid.UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[WebhookDelivery]:
        """Retrieve a page of a webhook's delivery log, newest first.

        Args:
            webhook_id: The webhook whose deliveries are listed.
            company_id: The company the webhook must belong to.
            limit: Maximum number of rows to return.
            offset: Number of rows to skip before collecting the page.

        Returns:
            The recorded deliveries, at most ``limit`` of them.
        """
        statement = (
            self._scoped(company_id)
            .where(WebhookDelivery.webhook_id == webhook_id)
            .order_by(WebhookDelivery.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(statement)
        return result.scalars().all()

    async def count_for_webhook(
        self,
        webhook_id: uuid.UUID,
        company_id: uuid.UUID,
    ) -> int:
        """Count a webhook's delivery attempts.

        Args:
            webhook_id: The webhook whose deliveries are counted.
            company_id: The company the webhook must belong to.

        Returns:
            The number of recorded deliveries.
        """
        statement = (
            select(func.count())
            .select_from(WebhookDelivery)
            .join(Webhook, Webhook.id == WebhookDelivery.webhook_id)
            .where(
                Webhook.company_id == company_id,
                WebhookDelivery.webhook_id == webhook_id,
            )
        )
        result = await self._session.execute(statement)
        return result.scalar_one()

    @staticmethod
    def _scoped(company_id: uuid.UUID) -> Select[tuple[WebhookDelivery]]:
        """Build the tenant-scoped base statement.

        Args:
            company_id: The company the webhook must belong to.

        Returns:
            A ``SELECT`` over deliveries restricted to that company.
        """
        return (
            select(WebhookDelivery)
            .join(Webhook, Webhook.id == WebhookDelivery.webhook_id)
            .where(Webhook.company_id == company_id)
        )
