import re


_GSTIN_CHARACTERS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_GSTIN_PATTERN = re.compile(
    r"^(?!00)\d{2}[A-Z]{5}\d{4}[A-Z][0-9A-Z]Z[0-9A-Z]$"
)


def normalize_gstin(value: str | None) -> str:
    """Return the canonical, whitespace-trimmed representation of a GSTIN."""

    return (value or "").strip().upper()


def is_valid_indian_gstin(value: str | None) -> bool:
    """Validate both the structure and base-36 checksum of an Indian GSTIN."""

    gstin = normalize_gstin(value)
    if _GSTIN_PATTERN.fullmatch(gstin) is None:
        return False

    checksum_total = 0
    factor = 2
    for character in reversed(gstin[:14]):
        product = factor * _GSTIN_CHARACTERS.index(character)
        checksum_total += (product // 36) + (product % 36)
        factor = 1 if factor == 2 else 2

    checksum_character = _GSTIN_CHARACTERS[(36 - (checksum_total % 36)) % 36]
    return gstin[-1] == checksum_character


def valid_indian_gstin(value: str | None) -> str | None:
    """Return a normalized GSTIN only when it is valid."""

    gstin = normalize_gstin(value)
    return gstin if is_valid_indian_gstin(gstin) else None
