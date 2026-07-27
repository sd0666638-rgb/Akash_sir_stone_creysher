import re


_MOBILE_INPUT = re.compile(r"^[+\d\s()-]+$")


def normalize_mobile_number(value: str) -> str:
    """Return a stable 10-digit mobile identifier.

    Common Indian prefixes (``+91`` and a leading trunk ``0``) are removed so
    the same mobile cannot be registered in multiple display formats.
    """

    if not isinstance(value, str):
        raise ValueError("Mobile number must be text")
    text = value.strip()
    if not text or not _MOBILE_INPUT.fullmatch(text):
        raise ValueError("Enter a valid 10-digit mobile number")

    digits = re.sub(r"\D", "", text)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]

    if len(digits) != 10:
        raise ValueError("Enter a valid 10-digit mobile number")
    return digits


def mobile_search_digits(value: str) -> str:
    """Normalize a full or partial mobile search without rejecting name text."""

    digits = re.sub(r"\D", "", value)
    if len(digits) == 12 and digits.startswith("91"):
        return digits[2:]
    if len(digits) == 11 and digits.startswith("0"):
        return digits[1:]
    return digits
