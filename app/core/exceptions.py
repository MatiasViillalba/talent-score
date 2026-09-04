"""Domain exceptions raised by the service layer.

Services describe what went wrong in the language of the domain and never
reach for an HTTP status: the mapping from these exceptions to responses
belongs to the API edge, which keeps the business logic usable from a
Celery task or a WebSocket handler as much as from a request.
"""


class DomainError(Exception):
    """Base class for every error the business logic raises deliberately."""


class EmailAlreadyRegisteredError(DomainError):
    """Raised when an email address already belongs to an account."""
