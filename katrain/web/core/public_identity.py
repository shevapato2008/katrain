"""Pure rules for newly claimed public names and passwords, never old identities."""

import re
import unicodedata


def is_generated_phone_username(username: str) -> bool:
    return re.fullmatch(r"u_[0-9a-f]{20}", username) is not None


def validate_public_username(username: str) -> None:
    folded = username.casefold()
    if (
        not 2 <= len(username) <= 24
        or folded in {"guest", "admin"}
        or folded.startswith(("admin:", "u_"))
        or any(char not in "_-" and unicodedata.category(char)[0] not in "LN" for char in username)
    ):
        raise ValueError("username_invalid")


def validate_signup_password(password: str) -> None:
    try:
        valid = len(password) >= 15 and "\0" not in password and len(password.encode("utf-8")) <= 72
    except UnicodeEncodeError:
        valid = False
    if not valid:
        raise ValueError("password_invalid")
