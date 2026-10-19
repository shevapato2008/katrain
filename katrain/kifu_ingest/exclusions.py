"""Versioned historical source exclusion and existing-source discovery."""

from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import re

from sqlalchemy import select

from katrain.web.core.models_db import KifuAlbum, KifuAlbumSource, KifuSource


_PATH = Path(__file__).parent / "data" / "historical-exclusions-20261011.json"
_ORIGIN = re.compile(r"data/kifu-album/19x19/([0-9]+)\.sgf\Z")


@lru_cache(maxsize=1)
def historical_excluded_ids():
    payload = json.loads(_PATH.read_text(encoding="utf-8"))
    ids = payload["excluded_source_ids"]
    digest = sha256(
        json.dumps(ids, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if (
        payload.get("source_key") != "19x19"
        or payload.get("version") != "kifu-historical-source-exclusions-20261011-v1"
        or not isinstance(ids, list)
        or len(ids) != 1752
        or len(set(ids)) != len(ids)
        or digest != payload.get("ids_sha256")
    ):
        raise ValueError("historical exclusion proof is invalid")
    return frozenset(ids)


def assert_source_allowed(source_key, source_item_id):
    if (
        source_key != "19x19"
        or not isinstance(source_item_id, str)
        or not source_item_id.isascii()
        or not source_item_id.isdigit()
    ):
        raise ValueError("only numeric 19x19 source IDs are allowed")
    if source_item_id in historical_excluded_ids():
        raise ValueError("historically excluded 19x19 source ID")


def known_source_ids(engine):
    """Read both primary paths and provenance links so old games are not redownloaded."""
    found = set()
    with engine.connect() as connection:
        paths = connection.execute(
            select(KifuAlbum.source_path).where(KifuAlbum.source_path.like("data/kifu-album/19x19/%"))
        )
        links = connection.execute(
            select(KifuAlbumSource.origin_path)
            .join(KifuSource, KifuSource.id == KifuAlbumSource.source_id)
            .where(KifuSource.source_key == "19x19")
        )
        for path in (*paths.scalars(), *links.scalars()):
            match = _ORIGIN.fullmatch(path or "")
            if match:
                found.add(match[1])
    return found
