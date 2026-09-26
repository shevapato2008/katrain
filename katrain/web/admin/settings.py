"""Required settings for the dedicated admin process."""

import os
import re
from dataclasses import dataclass

from katrain.web.core.config import INSECURE_DEFAULT_SECRET_KEY

ADMIN_ENVS = frozenset({"local", "test", "prod"})
ADMIN_USERNAME = "admin:fan"
_BCRYPT = re.compile(r"^\$2[aby]\$(\d\d)\$[./A-Za-z0-9]{53}$")


@dataclass(frozen=True)
class AdminConfig:
    username: str
    password_hash: str
    session_secret: str
    env: str


def local_vision_requested() -> bool:
    return os.getenv("KATRAIN_ADMIN_ENV") == "local" and os.getenv("KATRAIN_ADMIN_VISION_LOCAL") == "1"


def test_training_requested() -> bool:
    return os.getenv("KATRAIN_ADMIN_ENV") == "test" and os.getenv("KATRAIN_ADMIN_VISION_TRAINING") == "1"


def check_startup() -> AdminConfig:
    """Reject missing or unsafe admin credentials before the app accepts requests."""
    if os.getenv("KATRAIN_MODE", "server") != "server":
        raise RuntimeError("KATRAIN_MODE must be server for katrain-admin")

    username = os.getenv("KATRAIN_ADMIN_USERNAME")
    if username != ADMIN_USERNAME:
        raise RuntimeError("KATRAIN_ADMIN_USERNAME must identify the dedicated admin account")

    password_hash = os.getenv("KATRAIN_ADMIN_PASSWORD_HASH", "")
    match = _BCRYPT.fullmatch(password_hash)
    if match is None or int(match.group(1)) < 12:
        raise RuntimeError("KATRAIN_ADMIN_PASSWORD_HASH must be a bcrypt hash with cost at least 12")

    session_secret = os.getenv("KATRAIN_ADMIN_SESSION_SECRET", "")
    if (
        len(session_secret) < 32
        or session_secret != session_secret.strip()
        or session_secret == INSECURE_DEFAULT_SECRET_KEY
        or session_secret == os.getenv("KATRAIN_SECRET_KEY")
    ):
        raise RuntimeError("KATRAIN_ADMIN_SESSION_SECRET must be strong and distinct from the public key")

    env = os.getenv("KATRAIN_ADMIN_ENV")
    if env not in ADMIN_ENVS:
        raise RuntimeError("KATRAIN_ADMIN_ENV must be local, test, or prod")

    return AdminConfig(username=username, password_hash=password_hash, session_secret=session_secret, env=env)
