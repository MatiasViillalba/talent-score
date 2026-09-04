"""Authentication endpoints."""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession
from app.core.exceptions import EmailAlreadyRegisteredError
from app.schemas.auth import RegisterRequest
from app.schemas.user import UserRead
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_409_CONFLICT: {"description": "Email already registered"}},
)
async def register(payload: RegisterRequest, session: DbSession) -> UserRead:
    """Create a company and the owner account that administers it.

    Args:
        payload: The submitted registration details.
        session: The database session backing the request.

    Returns:
        The created owner.

    Raises:
        HTTPException: With status ``409`` if the email address already
            belongs to an account.
    """
    try:
        owner = await AuthService(session).register(payload)
    except EmailAlreadyRegisteredError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    return UserRead.model_validate(owner)
