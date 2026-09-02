"""Liveness and readiness endpoint."""

from typing import Any

from fastapi import APIRouter, Response, status
from redis.asyncio import Redis
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import engine

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(response: Response) -> dict[str, Any]:
    """Report process liveness plus a round trip to the database and Redis.

    A degraded result is reported as ``503`` and not only in the payload,
    because orchestrator health checks and load balancers route on the
    status code alone.

    Args:
        response: The outgoing response, whose status code is downgraded
            when a dependency is unreachable.

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

    healthy = all(value == "ok" for value in dependencies.values())
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if healthy else "degraded",
        "dependencies": dependencies,
    }
