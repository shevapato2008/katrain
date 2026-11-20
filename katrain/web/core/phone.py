"""Pure mainland-mobile identity normalization; never echo rejected input."""

import re

_MOBILE = re.compile(r"1[0-9]{10}")
_E164 = re.compile(r"\+861[0-9]{10}")
_SEPARATORS = str.maketrans("", "", " -().")
_INVALID = "Invalid mainland mobile number"


def normalize_phone(raw: str) -> str:
    """Accept common ASCII separators and explicit +86/0086 prefixes only."""
    if not isinstance(raw, str):
        raise ValueError(_INVALID)
    compact = raw.translate(_SEPARATORS)
    if compact.startswith("+86"):
        compact = compact[3:]
    elif compact.startswith("0086"):
        compact = compact[4:]
    if not _MOBILE.fullmatch(compact):
        raise ValueError(_INVALID)
    return "+86" + compact


def mask_phone(e164: str) -> str:
    """Display a canonical mainland number without exposing its middle digits."""
    if not isinstance(e164, str) or not _E164.fullmatch(e164):
        raise ValueError(_INVALID)
    return f"+86 {e164[3:6]}****{e164[-4:]}"
