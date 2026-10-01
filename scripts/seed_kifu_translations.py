"""Validate audited kifu names and report coverage of distinct raw album names.

This script only issues SELECTs when --database-url is supplied. It does not
read SGF files or write to a database. The JSON seed is the import artifact.
"""

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import create_engine, text
from katrain.web.kifu.identity import identity_lookup_name


LANGUAGES = ("en", "cn", "tw", "jp", "ko", "de", "es", "fr", "ru", "tr", "ua")
KINDS = ("player", "event")
DEFAULT_SEED = Path(__file__).resolve().parents[1] / "docs" / "resource" / "kifu-name-seed.json"


def load_seed(path: Path = DEFAULT_SEED) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _source_ok(url: object) -> bool:
    if not isinstance(url, str):
        return False
    parsed = urlparse(url)
    return parsed.scheme == "https" and bool(parsed.netloc)


def _index(seed: dict) -> dict[tuple[str, str], list[dict]]:
    index: dict[tuple[str, str], list[dict]] = {}
    for entity in seed.get("entities", []):
        seen_names = set()
        for name in [entity.get("canonical"), *entity.get("aliases", [])]:
            if isinstance(name, str) and name.strip():
                key = (entity.get("kind"), name.strip().casefold())
                if key not in seen_names:
                    index.setdefault(key, []).append(entity)
                    seen_names.add(key)
    return index


def validate_seed(seed: dict) -> list[str]:
    problems = []
    if seed.get("schema_version") != 1:
        problems.append("schema_version must be 1")
    if seed.get("languages") != list(LANGUAGES):
        problems.append("languages must list all eleven supported codes in order")
    keys = set()
    for entity in seed.get("entities", []):
        key = entity.get("key")
        if not isinstance(key, str) or not key or key in keys:
            problems.append(f"duplicate or missing entity key: {key!r}")
        keys.add(key)
        if entity.get("kind") not in KINDS:
            problems.append(f"{key}: invalid kind")
        if not isinstance(entity.get("canonical"), str) or not entity["canonical"].strip():
            problems.append(f"{key}: missing canonical name")
        aliases = entity.get("aliases", [])
        if not isinstance(aliases, list) or any(not isinstance(alias, str) or not alias.strip() for alias in aliases):
            problems.append(f"{key}: invalid aliases")
            continue
        alias_sources = entity.get("alias_sources", {})
        for alias in aliases:
            if not _source_ok(alias_sources.get(alias)):
                problems.append(f"{key}: alias {alias!r} needs source_url")
        names = entity.get("names", {})
        if not isinstance(names, dict):
            problems.append(f"{key}: names must be an object")
            continue
        for lang, record in names.items():
            if lang not in LANGUAGES:
                problems.append(f"{key}: unsupported language {lang}")
            if not isinstance(record, dict) or not isinstance(record.get("value"), str) or not record["value"].strip():
                problems.append(f"{key}/{lang}: missing value")
                continue
            if record.get("status") not in ("verified", "review"):
                problems.append(f"{key}/{lang}: status must be verified or review")
            if not _source_ok(record.get("source_url")):
                problems.append(f"{key}/{lang}: source_url must be an HTTPS page")
    for (kind, alias), entities in _index(seed).items():
        if len({entity.get("key") for entity in entities}) > 1:
            problems.append(f"{kind}: alias {alias!r} matches multiple entities")
    return problems


def display_name(seed: dict, kind: str, original: str, lang: str) -> str:
    """Use only verified names; unknown languages, aliases, and candidates fall back."""
    if lang not in LANGUAGES or not original:
        return original
    lookup = identity_lookup_name(kind, original)
    entities = _index(seed).get((kind, lookup.strip().casefold()), [])
    if len(entities) != 1:
        return original
    record = entities[0].get("names", {}).get(lang, {})
    return record["value"] if record.get("status") == "verified" else original


def coverage(seed: dict, inventory: list[dict]) -> dict:
    """Use unique (kind, raw name) pairs as the denominator, never album rows."""
    distinct = set()
    for item in inventory:
        kind, name = item.get("kind"), item.get("name")
        if kind not in KINDS:
            raise ValueError(f"invalid inventory kind: {kind!r}")
        if isinstance(name, str) and name.strip():
            distinct.add((kind, name.strip()))

    index = _index(seed)
    report = {}
    for kind in KINDS:
        raw_names = sorted(name for name_kind, name in distinct if name_kind == kind)
        stats = {
            "distinct_names": len(raw_names),
            "linked": 0,
            "ambiguous": 0,
            "unlinked": 0,
            "languages": {lang: {"verified": 0, "review": 0, "fallback_total": 0} for lang in LANGUAGES},
        }
        for name in raw_names:
            lookup = identity_lookup_name(kind, name)
            entities = index.get((kind, lookup.casefold()), [])
            if len(entities) > 1:
                stats["ambiguous"] += 1
            elif not entities:
                stats["unlinked"] += 1
            else:
                stats["linked"] += 1
            for lang in LANGUAGES:
                status = entities[0].get("names", {}).get(lang, {}).get("status") if len(entities) == 1 else None
                lang_stats = stats["languages"][lang]
                if status == "verified":
                    lang_stats["verified"] += 1
                else:
                    lang_stats["fallback_total"] += 1
                    if status == "review":
                        lang_stats["review"] += 1
        denominator = stats["distinct_names"]
        stats["linked_rate"] = stats["linked"] / denominator if denominator else 0.0
        for lang_stats in stats["languages"].values():
            lang_stats["verified_rate"] = lang_stats["verified"] / denominator if denominator else 0.0
        report[kind] = stats
    return report


def inventory_from_database(database_url: str) -> list[dict]:
    """Read unique raw player and event names; force a read-only transaction."""
    engine = create_engine(database_url)
    try:
        if engine.dialect.name not in ("sqlite", "postgresql"):
            raise ValueError("Only SQLite and PostgreSQL read-only inventory are supported")
        with engine.connect() as connection:
            if engine.dialect.name == "postgresql":
                connection.execute(text("SET TRANSACTION READ ONLY"))
            else:
                connection.execute(text("PRAGMA query_only = ON"))
            rows = connection.execute(
                text(
                    "SELECT 'player' AS kind, player_black AS name FROM kifu_albums "
                    "UNION SELECT 'player', player_white FROM kifu_albums "
                    "UNION SELECT 'event', event FROM kifu_albums"
                )
            )
            return [{"kind": kind, "name": name} for kind, name in rows if name and name.strip()]
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--inventory", type=Path, help="JSON array of {kind, name} raw names")
    source.add_argument("--database-url", help="read-only SQLite/PostgreSQL URL for the kifu_albums table")
    args = parser.parse_args()
    seed = load_seed(args.seed)
    problems = validate_seed(seed)
    if problems:
        parser.error("invalid seed:\n" + "\n".join(problems))
    if args.inventory:
        inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    elif args.database_url:
        inventory = inventory_from_database(args.database_url)
    else:
        inventory = None
    print(
        json.dumps(
            {
                "seed_entities": len(seed["entities"]),
                "coverage": coverage(seed, inventory) if inventory is not None else None,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
