"""Request and response models for the authentication endpoints."""

from typing import Annotated, Final

from pydantic import BaseModel, EmailStr, Field, StringConstraints, field_validator

from app.core.security import MAX_PASSWORD_BYTES

MIN_PASSWORD_LENGTH: Final = 8

DisplayName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]


class RegisterRequest(BaseModel):
    """Payload creating a company together with its first user.

    Attributes:
        company_name: Display name of the company being created.
        email: Login address of the owner account.
        password: Plain-text password of the owner account.
        full_name: Display name of the owner.
    """

    company_name: DisplayName
    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LENGTH)
    full_name: DisplayName

    @field_validator("password")
    @classmethod
    def _reject_password_the_hash_would_truncate(cls, value: str) -> str:
        """Reject a password longer than the hashing algorithm reads.

        The limit is expressed in bytes rather than characters because
        that is the boundary bcrypt truncates at, and a name written in a
        non-Latin script reaches it well before 72 characters.

        Args:
            value: The submitted password.

        Returns:
            The password unchanged.

        Raises:
            ValueError: If the password exceeds the hashing limit.
        """
        if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise ValueError(
                f"A password may not exceed {MAX_PASSWORD_BYTES} bytes once UTF-8 encoded."
            )
        return value
