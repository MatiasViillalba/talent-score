"""Slug derivation for human-readable identifiers."""

import re
import unicodedata
from typing import Final

MAX_SLUG_LENGTH: Final = 64

_NON_SLUG_CHARACTERS = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    """Reduce a display name to a lowercase, URL-safe slug.

    Accented characters are folded to their ASCII base — ``Añón`` becomes
    ``anon`` — so that a tenant's slug stays typeable and stable across
    the systems that consume it.

    Args:
        value: The display name to derive the slug from.

    Returns:
        The slug, truncated to ``MAX_SLUG_LENGTH``. It is empty when the
        name carries no alphanumeric character at all, which callers are
        expected to resolve with a fallback of their own.
    """
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii")
    hyphenated = _NON_SLUG_CHARACTERS.sub("-", ascii_only.lower())
    return hyphenated.strip("-")[:MAX_SLUG_LENGTH].strip("-")
