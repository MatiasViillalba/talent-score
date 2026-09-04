"""Request and response models for platform users."""

import datetime
import uuid

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.enums import UserRole


class UserRead(BaseModel):
    """A user as exposed by the API.

    The password digest is deliberately absent: it never leaves the
    persistence layer, not even to an authenticated owner.

    Attributes:
        id: Identifier of the user.
        company_id: Tenant the user belongs to.
        email: Login address of the user.
        full_name: Display name of the user.
        role: Role granting the user its permissions.
        is_active: Whether the account can authenticate.
        created_at: Instant the account was created.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime.datetime
