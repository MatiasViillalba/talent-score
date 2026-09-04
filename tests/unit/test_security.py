"""Tests for password hashing and token issuance."""

import datetime
import uuid
from typing import Any

import jwt
import pytest

from app.core.config import get_settings
from app.core.security import (
    MAX_PASSWORD_BYTES,
    ExpiredTokenError,
    InvalidTokenError,
    PasswordTooLongError,
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

PASSWORD = "correct-horse-battery-staple"


def _forge_token(claims: dict[str, Any], *, signing_key: str | None = None) -> str:
    """Sign arbitrary claims the way the application would.

    Args:
        claims: The claim set to encode.
        signing_key: Key to sign with; the application key when omitted.

    Returns:
        The encoded token.
    """
    settings = get_settings()
    return jwt.encode(
        claims,
        signing_key if signing_key is not None else settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def _valid_claims(**overrides: Any) -> dict[str, Any]:
    """Build a complete claim set, overriding the fields a test targets.

    Args:
        **overrides: Claims replacing the defaults.

    Returns:
        A claim set carrying every required claim.
    """
    issued_at = datetime.datetime.now(datetime.UTC)
    claims: dict[str, Any] = {
        "sub": str(uuid.uuid4()),
        "type": TokenType.ACCESS.value,
        "jti": str(uuid.uuid4()),
        "iat": issued_at,
        "exp": issued_at + datetime.timedelta(minutes=5),
    }
    claims.update(overrides)
    return claims


def test_hashing_round_trip() -> None:
    """A password verifies against the digest derived from it."""
    assert verify_password(PASSWORD, hash_password(PASSWORD)) is True


def test_verification_rejects_the_wrong_password() -> None:
    """A different password does not verify against the digest."""
    assert verify_password("not-the-password", hash_password(PASSWORD)) is False


def test_each_hash_gets_its_own_salt() -> None:
    """Hashing the same password twice yields two distinct digests."""
    first = hash_password(PASSWORD)
    second = hash_password(PASSWORD)

    assert first != second
    assert verify_password(PASSWORD, first) is True
    assert verify_password(PASSWORD, second) is True


def test_hashing_rejects_a_password_bcrypt_would_truncate() -> None:
    """Storing a digest of a silently truncated password is refused."""
    with pytest.raises(PasswordTooLongError):
        hash_password("a" * (MAX_PASSWORD_BYTES + 1))


def test_verification_rejects_an_oversized_password() -> None:
    """A long password sharing its first bytes with the real one fails."""
    accepted_password = "b" * MAX_PASSWORD_BYTES
    digest = hash_password(accepted_password)

    assert verify_password(accepted_password + "extra", digest) is False


def test_verification_rejects_a_malformed_digest() -> None:
    """An unreadable stored digest fails the check instead of raising."""
    assert verify_password(PASSWORD, "not-a-bcrypt-digest") is False


def test_access_token_round_trip() -> None:
    """A freshly issued access token decodes back to its subject."""
    subject = uuid.uuid4()

    payload = decode_token(create_access_token(subject), expected_type=TokenType.ACCESS)

    assert payload.subject == subject
    assert payload.token_type is TokenType.ACCESS
    assert payload.expires_at > payload.issued_at


def test_refresh_token_round_trip() -> None:
    """A freshly issued refresh token decodes back to its subject."""
    subject = uuid.uuid4()

    payload = decode_token(create_refresh_token(subject), expected_type=TokenType.REFRESH)

    assert payload.subject == subject
    assert payload.token_type is TokenType.REFRESH


def test_refresh_token_is_rejected_where_an_access_token_is_required() -> None:
    """The longer refresh lifetime cannot leak into the request path."""
    token = create_refresh_token(uuid.uuid4())

    with pytest.raises(InvalidTokenError):
        decode_token(token, expected_type=TokenType.ACCESS)


def test_each_token_carries_its_own_identifier() -> None:
    """Two tokens issued for the same subject stay individually revocable."""
    subject = uuid.uuid4()

    first = decode_token(create_access_token(subject), expected_type=TokenType.ACCESS)
    second = decode_token(create_access_token(subject), expected_type=TokenType.ACCESS)

    assert first.token_id != second.token_id


def test_expired_token_is_rejected() -> None:
    """A token past its expiry is reported as expired, not as malformed."""
    expired_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=1)
    token = _forge_token(
        _valid_claims(iat=expired_at - datetime.timedelta(minutes=5), exp=expired_at)
    )

    with pytest.raises(ExpiredTokenError):
        decode_token(token, expected_type=TokenType.ACCESS)


def test_token_signed_with_another_key_is_rejected() -> None:
    """A token this application did not sign never verifies."""
    token = _forge_token(_valid_claims(), signing_key="a-key-this-application-does-not-use")

    with pytest.raises(InvalidTokenError):
        decode_token(token, expected_type=TokenType.ACCESS)


def test_token_missing_a_required_claim_is_rejected() -> None:
    """A claim set without an identifier cannot be accepted."""
    claims = _valid_claims()
    del claims["jti"]

    with pytest.raises(InvalidTokenError):
        decode_token(_forge_token(claims), expected_type=TokenType.ACCESS)


def test_token_with_an_unreadable_subject_is_rejected() -> None:
    """A subject that is not a user identifier fails validation."""
    token = _forge_token(_valid_claims(sub="not-a-uuid"))

    with pytest.raises(InvalidTokenError):
        decode_token(token, expected_type=TokenType.ACCESS)


def test_malformed_token_is_rejected() -> None:
    """A string that is not a token at all is rejected."""
    with pytest.raises(InvalidTokenError):
        decode_token("not.a.token", expected_type=TokenType.ACCESS)
