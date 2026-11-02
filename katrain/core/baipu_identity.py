"""Shared identity for an exact SGF interpreted by a versioned replay schema."""

import hashlib

BAIPU_REPLAY_VERSION = 2


def sgf_sha256(sgf_content: str) -> str:
    return hashlib.sha256(sgf_content.encode("utf-8")).hexdigest()


def baipu_record_identity(sgf_content: str, replay_version: int = BAIPU_REPLAY_VERSION) -> str:
    return hashlib.sha256(f"baipu:{replay_version}:{sgf_sha256(sgf_content)}".encode("ascii")).hexdigest()
