"""Generic asynchronous CRUD repository shared by the concrete repositories."""

import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import ColumnExpressionArgument, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base


class BaseRepository[ModelT: Base]:
    """Data access for a single ORM model.

    A repository owns persistence concerns only: it holds no business
    rules and never commits. Write operations flush so that constraint
    violations surface at the point of the offending statement, while the
    calling service keeps ownership of the transaction boundary.
    """

    def __init__(self, session: AsyncSession, model: type[ModelT]) -> None:
        """Bind the repository to a session and the model it manages.

        Args:
            session: The async session the statements are executed on.
            model: The mapped class this repository reads and writes.
        """
        self._session = session
        self._model = model

    async def get(self, entity_id: uuid.UUID) -> ModelT | None:
        """Retrieve a single entity by primary key.

        Args:
            entity_id: The primary key to look up.

        Returns:
            The matching entity, or ``None`` if no row has that key.
        """
        return await self._session.get(self._model, entity_id)

    async def list(
        self,
        *filters: ColumnExpressionArgument[bool],
        limit: int = 50,
        offset: int = 0,
        order_by: ColumnExpressionArgument[Any] | None = None,
    ) -> Sequence[ModelT]:
        """Retrieve a page of entities matching the given filters.

        Args:
            *filters: SQL expressions combined with ``AND``.
            limit: Maximum number of rows to return.
            offset: Number of rows to skip before collecting the page.
            order_by: Ordering expression; the database decides the order
                when omitted, so callers that paginate should always
                provide one.

        Returns:
            The matching entities, at most ``limit`` of them.
        """
        statement = select(self._model).where(*filters).limit(limit).offset(offset)
        if order_by is not None:
            statement = statement.order_by(order_by)
        result = await self._session.execute(statement)
        return result.scalars().all()

    async def count(self, *filters: ColumnExpressionArgument[bool]) -> int:
        """Count the entities matching the given filters.

        Args:
            *filters: SQL expressions combined with ``AND``.

        Returns:
            The number of matching rows.
        """
        statement = select(func.count()).select_from(self._model).where(*filters)
        result = await self._session.execute(statement)
        return result.scalar_one()

    async def exists(self, *filters: ColumnExpressionArgument[bool]) -> bool:
        """Report whether any entity matches the given filters.

        Args:
            *filters: SQL expressions combined with ``AND``.

        Returns:
            ``True`` if at least one row matches, ``False`` otherwise.
        """
        statement = select(select(self._model).where(*filters).exists())
        result = await self._session.execute(statement)
        return result.scalar_one()

    async def create(self, entity: ModelT) -> ModelT:
        """Persist a new entity.

        The entity is refreshed after the flush so that server-generated
        values such as the primary key and the timestamps are readable
        without triggering a lazy load.

        Args:
            entity: The instance to insert.

        Returns:
            The persisted entity, refreshed from the database.
        """
        self._session.add(entity)
        await self._session.flush()
        await self._session.refresh(entity)
        return entity

    async def update(self, entity: ModelT, values: Mapping[str, Any]) -> ModelT:
        """Apply a set of attribute changes to an existing entity.

        Args:
            entity: The instance to modify.
            values: Attribute names mapped to their new values.

        Returns:
            The updated entity, refreshed from the database.
        """
        for attribute, value in values.items():
            setattr(entity, attribute, value)
        await self._session.flush()
        await self._session.refresh(entity)
        return entity

    async def delete(self, entity: ModelT) -> None:
        """Remove an entity.

        Args:
            entity: The instance to delete.
        """
        await self._session.delete(entity)
        await self._session.flush()
