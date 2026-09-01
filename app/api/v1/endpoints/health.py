"""Liveness and readiness endpoint."""

from typing import Any

from fastapi import APIRouter
from redis.asyncio import Redis
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import engine

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Report process liveness plus a round trip to the database and Redis.

    Returns:
        A payload with an overall status and the individual status of
        each dependency, each one either ``"ok"`` or an error message.
    """
    settings = get_settings()
    dependencies: dict[str, str] = {}

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        dependencies["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        dependencies["database"] = f"error: {exc}"

    redis_client: Redis = Redis.from_url(settings.REDIS_URL)
    try:
        await redis_client.ping()
        dependencies["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        dependencies["redis"] = f"error: {exc}"
    finally:
        await redis_client.aclose()

    overall = "ok" if all(value == "ok" for value in dependencies.values()) else "degraded"
    return {"status": overall, "dependencies": dependencies}
