"""Password hashing and JSON Web Token issuance and verification.

Tokens carry the minimum needed to identify the caller: the user id, the
purpose the token was issued for, its validity window and a unique id.
Authorization data — company and role — is deliberately left out and read
from the database on each request, so revoking a role takes effect
immediately instead of when the last issued token happens to expire.
"""

import datetime
import uuid
from enum import StrEnum
from typing import Any, Final

import bcrypt
import jwt
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.config import get_settings

BCRYPT_ROUNDS: Final = 12
MAX_PASSWORD_BYTES: Final = 72
REQUIRED_CLAIMS: Final = ["sub", "type", "jti", "iat", "exp"]


class TokenType(StrEnum):
    """Purpose an issued token is valid for."""

    ACCESS = "access"
    REFRESH = "refresh"


class InvalidTokenError(Exception):
    """Raised when a token fails verification or carries unusable claims."""


class ExpiredTokenError(InvalidTokenError):
    """Raised when a token is well formed and signed but past its expiry."""


class PasswordTooLongError(ValueError):
    """Raised when a password exceeds what the hashing algorithm accepts."""


class TokenPayload(BaseModel):
    """The verified claims of a decoded token.

    Attributes:
        subject: Identifier of the user the token was issued for.
        token_type: Purpose the token is valid for.
        token_id: Unique identifier of this token, usable for revocation.
        issued_at: Instant the token was signed.
        expires_at: Instant the token stops being accepted.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    subject: uuid.UUID = Field(alias="sub")
    token_type: TokenType = Field(alias="type")
    token_id: uuid.UUID = Field(alias="jti")
    issued_at: datetime.datetime = Field(alias="iat")
    expires_at: datetime.datetime = Field(alias="exp")


def hash_password(password: str) -> str:
    """Derive a salted bcrypt digest from a plain-text password.

    Args:
        password: The password to hash.

    Returns:
        The digest, salt included, ready to be stored.

    Raises:
        PasswordTooLongError: If the password exceeds
            ``MAX_PASSWORD_BYTES`` once encoded. bcrypt ignores anything
            past that boundary, so accepting a longer password would let
            two different secrets unlock the same account.
    """
    encoded_password = password.encode("utf-8")
    if len(encoded_password) > MAX_PASSWORD_BYTES:
        raise PasswordTooLongError(
            f"A password may not exceed {MAX_PASSWORD_BYTES} bytes once UTF-8 encoded."
        )
    return bcrypt.hashpw(encoded_password, bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    """Check a plain-text password against a stored digest.

    A password too long to hash, or a digest the algorithm cannot read,
    is a failed authentication rather than an error: neither is worth
    turning a login attempt into a server fault.

    Args:
        password: The password supplied by the caller.
        hashed_password: The digest stored for the account.

    Returns:
        ``True`` if the password produced the stored digest.
    """
    encoded_password = password.encode("utf-8")
    if len(encoded_password) > MAX_PASSWORD_BYTES:
        return False
    try:
        return bcrypt.checkpw(encoded_password, hashed_password.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(subject: uuid.UUID) -> str:
    """Issue a short-lived token authenticating API requests.

    Args:
        subject: Identifier of the user the token is issued for.

    Returns:
        The encoded token.
    """
    settings = get_settings()
    return _create_token(
        subject=subject,
        token_type=TokenType.ACCESS,
        lifetime=datetime.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(subject: uuid.UUID) -> str:
    """Issue a long-lived token exchangeable for a new access token.

    Args:
        subject: Identifier of the user the token is issued for.

    Returns:
        The encoded token.
    """
    settings = get_settings()
    return _create_token(
        subject=subject,
        token_type=TokenType.REFRESH,
        lifetime=datetime.timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str, *, expected_type: TokenType) -> TokenPayload:
    """Verify a token's signature and claims.

    The expected type is part of the verification: a refresh token must
    never be accepted where an access token is required, or its longer
    lifetime would silently become the session lifetime.

    Args:
        token: The encoded token to verify.
        expected_type: The purpose the token has to have been issued for.

    Returns:
        The verified claims.

    Raises:
        ExpiredTokenError: If the token is past its expiry.
        InvalidTokenError: If the signature does not verify, a required
            claim is missing or unreadable, or the token was issued for a
            different purpose.
    """
    settings = get_settings()
    try:
        claims = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require": REQUIRED_CLAIMS},
        )
    except jwt.ExpiredSignatureError as error:
        raise ExpiredTokenError("The token has expired.") from error
    except jwt.PyJWTError as error:
        raise InvalidTokenError("The token could not be verified.") from error

    try:
        payload = TokenPayload.model_validate(claims)
    except ValidationError as error:
        raise InvalidTokenError("The token carries unusable claims.") from error

    if payload.token_type is not expected_type:
        raise InvalidTokenError(
            f"Expected a {expected_type.value} token, got a {payload.token_type.value} one."
        )
    return payload


def _create_token(
    *,
    subject: uuid.UUID,
    token_type: TokenType,
    lifetime: datetime.timedelta,
) -> str:
    """Sign a token for a subject, a purpose and a validity window.

    Args:
        subject: Identifier of the user the token is issued for.
        token_type: Purpose the token is valid for.
        lifetime: How long the token stays acceptable.

    Returns:
        The encoded token.
    """
    settings = get_settings()
    issued_at = datetime.datetime.now(datetime.UTC)
    claims: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type.value,
        "jti": str(uuid.uuid4()),
        "iat": issued_at,
        "exp": issued_at + lifetime,
    }
    return jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
