"""Application factory: lifespan, middleware, and router mounting."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import RequestIDMiddleware, configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Run startup and shutdown hooks around the application's lifetime.

    Args:
        app: The FastAPI application instance being started.

    Yields:
        Control back to the ASGI server while the application serves
        requests.
    """
    settings = get_settings()
    configure_logging(environment=settings.ENVIRONMENT)
    yield


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    Returns:
        A fully configured ``FastAPI`` instance, ready to be served.
    """
    settings = get_settings()

    app = FastAPI(
        title="Resume Screening API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    return app


app = create_app()
