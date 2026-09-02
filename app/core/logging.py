"""Structured logging configuration and request-id propagation."""

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"

_request_id_ctx_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    """Return the request id bound to the current execution context.

    Returns:
        The active request id, or ``None`` outside of a request scope.
    """
    return _request_id_ctx_var.get()


class RequestIDFilter(logging.Filter):
    """Injects the current request id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        return True


class JSONFormatter(logging.Formatter):
    """Renders log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(*, environment: str) -> None:
    """Configure the root logger for the process.

    Args:
        environment: The running environment name. ``"development"``
            uses a human-readable formatter; every other value uses
            structured JSON, suitable for log aggregation.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIDFilter())

    if environment == "development":
        formatter: logging.Formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(request_id)s | %(name)s | %(message)s"
        )
    else:
        formatter = JSONFormatter()

    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Binds a request id to a contextvar for the request lifecycle.

    Reuses an inbound ``X-Request-ID`` header when present, otherwise
    generates a new UUID4. The id is echoed back on the response so
    clients can correlate their request with server-side log lines.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER, str(uuid.uuid4()))
        token = _request_id_ctx_var.set(request_id)
        try:
            response = await call_next(request)
        finally:
            _request_id_ctx_var.reset(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
