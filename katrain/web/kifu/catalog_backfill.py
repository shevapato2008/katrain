#!/usr/bin/env python3
"""Backfill audited kifu identities and provenance without reading SGF files.

Dry run is the CLI default. --apply writes in bounded album batches. The
--undo-dedup-batch option restores only duplicate pointers and source links
aggregated onto masters by that batch. It does not undo identity FKs, ordinary
source links, or migrated review names. Keep a table backup before applying.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from katrain.web.core.models_db import (
    KifuAlbum,
    KifuAlbumSource,
    KifuDedupBatch,
    KifuDedupChange,
    KifuEvent,
    KifuEventAlias,
    KifuEventName,
    KifuPlayer,
    KifuPlayerAlias,
    KifuPlayerName,
    KifuSource,
    PlayerTranslationDB,
    TournamentTranslationDB,
)
from katrain.web.kifu.identity import normalize_alias
from katrain.web.kifu.provenance import (
    classify_source_path,
    mainline_signature,
    sgf_sha256,
    source_links_snapshot,
)


LANGUAGES = ("en", "cn", "tw", "jp", "ko", "de", "es", "fr", "ru", "tr", "ua")


def load_seed(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_seed(seed: dict) -> list[str]:
    problems = []
    if seed.get("schema_version") != 1 or seed.get("languages") != list(LANGUAGES):
        problems.append("seed schema or language list differs from the audited format")
    keys = set()
    aliases_by_kind: dict[str, dict[str, str]] = {"player": {}, "event": {}}
    for entity in seed.get("entities", []):
        key, kind = entity.get("key"), entity.get("kind")
        if not key or key in keys or kind not in aliases_by_kind:
            problems.append(f"invalid entity key or kind: {key!r}")
            continue
        keys.add(key)
        canonical = entity.get("canonical")
        if not isinstance(canonical, str) or not canonical.strip():
            problems.append(f"{key}: missing canonical name")
            continue
        for alias in entity.get("aliases", []):
            url = entity.get("alias_sources", {}).get(alias)
            if not isinstance(url, str) or urlparse(url).scheme != "https":
                problems.append(f"{key}: alias {alias!r} lacks an HTTPS source")
        for alias in [canonical, *entity.get("aliases", [])]:
            normalized = normalize_alias(alias)
            owner = aliases_by_kind[kind].setdefault(normalized, key)
            if owner != key:
                problems.append(f"{kind}: ambiguous audited alias {alias!r}")
        for lang, value in entity.get("names", {}).items():
            url = value.get("source_url")
            if (
                lang not in LANGUAGES
                or value.get("status") not in ("verified", "review")
                or not value.get("value")
                or not isinstance(url, str)
                or urlparse(url).scheme != "https"
            ):
                problems.append(f"{key}/{lang}: invalid translation or source")
    return problems


def seed_coverage(seed: dict, raw_names: set[tuple[str, str]], review_map: dict[tuple[str, str], set[str]]) -> dict:
    aliases = _audited_aliases_from_seed(seed)
    result = {}
    for kind in ("player", "event"):
        names = {name for item_kind, name in raw_names if item_kind == kind and name.strip()}
        linked = sum(len(aliases[kind].get(normalize_alias(name), [])) == 1 for name in names)
        languages = {}
        for lang in LANGUAGES:
            verified = review = 0
            for name in names:
                matching = aliases[kind].get(normalize_alias(name), [])
                status = matching[0].get("names", {}).get(lang, {}).get("status") if len(matching) == 1 else None
                if status != "verified" and lang in review_map.get((kind, name), set()):
                    status = "review"
                verified += status == "verified"
                review += status == "review"
            languages[lang] = {
                "verified": verified,
                "review": review,
                "fallback_total": len(names) - verified,
                "verified_rate": verified / len(names) if names else 0.0,
            }
        result[kind] = {
            "distinct_names": len(names),
            "linked": linked,
            "ambiguous": sum(len(aliases[kind].get(normalize_alias(name), [])) > 1 for name in names),
            "unlinked": len(names)
            - linked
            - sum(len(aliases[kind].get(normalize_alias(name), [])) > 1 for name in names),
            "linked_rate": linked / len(names) if names else 0.0,
            "languages": languages,
        }
    return result


def _audited_aliases_from_seed(seed: dict) -> dict[str, dict[str, list[dict]]]:
    result: dict[str, dict[str, list[dict]]] = {"player": {}, "event": {}}
    for entity in seed["entities"]:
        names = {entity["canonical"], *entity["aliases"]}
        names.update(value["value"] for value in entity["names"].values() if value["status"] == "verified")
        seen = set()
        for name in names:
            normalized = normalize_alias(name)
            if normalized not in seen:
                result[entity["kind"]].setdefault(normalized, []).append(entity)
                seen.add(normalized)
    return result


def _migrate_legacy_reviews(
    db: Session,
    raw_names: set[tuple[str, str]],
    non_event_labels: set[str],
    audited_aliases: dict[str, dict[str, set]],
    *,
    dry_run: bool,
) -> tuple[dict, dict[tuple[str, str], set[str]]]:
    """Copy old five-language values as review only; never make search aliases."""
    stats = {
        "legacy_review_names_added": 0,
        "legacy_review_entities_added": 0,
        "legacy_aliases_pending_review": 0,
        "legacy_tournaments_pending_review": 0,
        "legacy_ambiguous_pending_review": 0,
    }
    review_map: dict[tuple[str, str], set[str]] = {}
    event_names = {name for kind, name in raw_names if kind == "event"}
    for legacy_model, entity_model, name_model, fk, kind, canonical_field in (
        (PlayerTranslationDB, KifuPlayer, KifuPlayerName, "player_id", "player", "canonical_name"),
        (TournamentTranslationDB, KifuEvent, KifuEventName, "event_id", "event", "original"),
    ):
        last_id = 0
        while True:
            records = (
                db.query(legacy_model).filter(legacy_model.id > last_id).order_by(legacy_model.id).limit(500).all()
            )
            if not records:
                break
            for old in records:
                last_id = old.id
                canonical = getattr(old, canonical_field)
                if kind == "event" and (canonical not in event_names or canonical in non_event_labels):
                    stats["legacy_tournaments_pending_review"] += 1
                    continue
                if len(audited_aliases[kind].get(normalize_alias(canonical), set())) > 1:
                    stats["legacy_ambiguous_pending_review"] += 1
                    continue
                if kind == "player" and isinstance(old.aliases, list):
                    stats["legacy_aliases_pending_review"] += len(old.aliases)
                present = {lang: getattr(old, lang) for lang in ("en", "cn", "tw", "jp", "ko") if getattr(old, lang)}
                if not present:
                    continue
                review_map.setdefault((kind, canonical), set()).update(present)
                audited_target = _resolve(audited_aliases, kind, canonical)
                entity = db.get(entity_model, audited_target) if isinstance(audited_target, int) else None
                if entity is None and audited_target is None:
                    entity = (
                        db.query(entity_model).filter_by(canonical_name=canonical).order_by(entity_model.id).first()
                    )
                if entity is None:
                    if audited_target is None:
                        stats["legacy_review_entities_added"] += 1
                    if not dry_run:
                        entity = entity_model(canonical_name=canonical)
                        db.add(entity)
                        db.flush()
                for lang, value in present.items():
                    existing = (
                        db.query(name_model.id).filter_by(**{fk: entity.id}, lang=lang).first() if entity else None
                    )
                    if existing:
                        continue
                    stats["legacy_review_names_added"] += 1
                    if not dry_run:
                        db.add(
                            name_model(
                                **{fk: entity.id},
                                lang=lang,
                                display_name=value,
                                status="review",
                                reference_kind="legacy_unverified",
                            )
                        )
            if not dry_run:
                db.commit()
    return stats, review_map


def _seed_entities(db: Session, seed: dict) -> dict[str, int]:
    ids = {}
    for entity in seed["entities"]:
        is_player = entity["kind"] == "player"
        model = KifuPlayer if is_player else KifuEvent
        alias_model = KifuPlayerAlias if is_player else KifuEventAlias
        name_model = KifuPlayerName if is_player else KifuEventName
        fk = "player_id" if is_player else "event_id"
        record = db.query(model).filter_by(canonical_name=entity["canonical"]).order_by(model.id).first()
        if record is None:
            record = model(canonical_name=entity["canonical"])
            db.add(record)
            db.flush()
        ids[entity["key"]] = record.id
        aliases = {entity["canonical"], *entity["aliases"]}
        aliases.update(value["value"] for value in entity["names"].values() if value["status"] == "verified")
        for alias in sorted(aliases):
            normalized = normalize_alias(alias)
            if not db.query(alias_model.id).filter_by(**{fk: record.id}, normalized_alias=normalized).first():
                db.add(alias_model(**{fk: record.id}, alias=alias, normalized_alias=normalized))
        for lang, value in entity["names"].items():
            existing = db.query(name_model).filter_by(**{fk: record.id}, lang=lang).one_or_none()
            if existing is None:
                db.add(
                    name_model(
                        **{fk: record.id},
                        lang=lang,
                        display_name=value["value"],
                        status=value["status"],
                        reference_url=value["source_url"],
                        reference_kind="audited_seed",
                        verified_at=datetime.now(timezone.utc) if value["status"] == "verified" else None,
                    )
                )
            elif value["status"] == "verified":
                if existing.status == "verified" and existing.display_name != value["value"]:
                    raise ValueError(
                        f"verified name conflict for {entity['key']}/{lang}: "
                        f"existing {existing.display_name!r}, seed {value['value']!r}"
                    )
                if existing.status != "verified":
                    existing.display_name = value["value"]
                    existing.status = "verified"
                    existing.reference_url = value["source_url"]
                    existing.reference_kind = "audited_seed"
                    existing.verified_at = datetime.now(timezone.utc)
                elif not existing.reference_url:
                    existing.reference_url = value["source_url"]
                    existing.reference_kind = "audited_seed"
                    existing.verified_at = existing.verified_at or datetime.now(timezone.utc)
        db.flush()
    return ids


def _audited_aliases(db: Session, seed: dict, ids: dict[str, int] | None) -> dict[str, dict[str, set]]:
    result: dict[str, dict[str, set]] = {"player": {}, "event": {}}
    if seed is None:
        return result
    canonical_by_key = {entity["key"]: entity["canonical"] for entity in seed["entities"]}
    for entity in seed["entities"]:
        key = ids[entity["key"]] if ids is not None else entity["key"]
        aliases = {entity["canonical"], *entity["aliases"]}
        aliases.update(value["value"] for value in entity["names"].values() if value["status"] == "verified")
        for alias in aliases:
            result[entity["kind"]].setdefault(normalize_alias(alias), set()).add(key)
    for kind, alias_model, entity_model, fk in (
        ("player", KifuPlayerAlias, KifuPlayer, "player_id"),
        ("event", KifuEventAlias, KifuEvent, "event_id"),
    ):
        normalized_values = list(result[kind])
        for start in range(0, len(normalized_values), 500):
            rows = (
                db.query(alias_model.normalized_alias, getattr(alias_model, fk), entity_model.canonical_name)
                .join(entity_model, getattr(alias_model, fk) == entity_model.id)
                .filter(alias_model.normalized_alias.in_(normalized_values[start : start + 500]))
            )
            for normalized, existing_id, canonical in rows:
                expected = result[kind][normalized]
                if ids is not None:
                    if existing_id not in expected:
                        expected.add(("existing", existing_id))
                elif all(canonical_by_key.get(key) != canonical for key in expected):
                    expected.add(("existing", existing_id))
    return result


def _resolve(aliases: dict[str, dict[str, set]], kind: str, raw: str | None):
    matched = aliases[kind].get(normalize_alias(raw or ""), set())
    return next(iter(matched)) if len(matched) == 1 else None


def _record_change(db: Session, batch_id: int, album: KifuAlbum, before_pointer: int | None, before_links: list[dict]):
    after_links = source_links_snapshot(db, album.id)
    if album.duplicate_of_id != before_pointer or after_links != before_links:
        existing = db.query(KifuDedupChange).filter_by(batch_id=batch_id, album_id=album.id).one_or_none()
        before_keys = {(link["source_id"], link["origin_path"], link["match_method"]) for link in before_links}
        newly_added = [
            link
            for link in after_links
            if (link["source_id"], link["origin_path"], link["match_method"]) not in before_keys
        ]
        if existing:
            existing.duplicate_of_id_after = album.duplicate_of_id
            recorded = {
                (link["source_id"], link["origin_path"], link["match_method"]): link
                for link in existing.source_links_after
            }
            recorded.update(
                {(link["source_id"], link["origin_path"], link["match_method"]): link for link in newly_added}
            )
            existing.source_links_after = [recorded[key] for key in sorted(recorded)]
        else:
            db.add(
                KifuDedupChange(
                    batch_id=batch_id,
                    album_id=album.id,
                    duplicate_of_id_before=before_pointer,
                    duplicate_of_id_after=album.duplicate_of_id,
                    source_links_before=before_links,
                    source_links_after=before_links + newly_added,
                    sgf_sha256_before=sgf_sha256(album.sgf_content),
                )
            )


def _aggregate_duplicate_sources(db: Session, master: KifuAlbum, duplicate: KifuAlbum, dry_run: bool):
    """Attach every source of a content-identical row to its visible master."""
    master_before = source_links_snapshot(db, master.id)
    duplicate_links = source_links_snapshot(db, duplicate.id)
    if not any(link["origin_path"] == duplicate.source_path for link in duplicate_links):
        duplicate_links.append(
            {"source_id": None, "origin_path": duplicate.source_path, "match_method": "source_path"}
        )
    existing = {(link["source_id"], link["origin_path"]) for link in master_before}
    added = 0
    for link in duplicate_links:
        key = (link["source_id"], link["origin_path"])
        if key in existing or (link["source_id"] is None and any(path == link["origin_path"] for _, path in existing)):
            continue
        added += 1
        existing.add(key)
        if not dry_run:
            if link["source_id"] is None:
                raise ValueError(f"album {duplicate.id} lacks its own source link")
            db.add(
                KifuAlbumSource(
                    album_id=master.id,
                    source_id=link["source_id"],
                    origin_path=link["origin_path"],
                    match_method="exact_sgf" if link["match_method"] == "source_path" else link["match_method"],
                )
            )
    if added and not dry_run:
        db.flush()
    return added, master_before


def backfill_catalog(
    db: Session,
    seed: dict | None,
    *,
    dry_run: bool = True,
    dedupe: bool = True,
    scan_mainlines: bool = True,
    batch_key: str | None = None,
    batch_size: int = 500,
) -> dict:
    """Scan existing rows by ID, linking only source-audited entity names."""
    problems = validate_seed(seed) if seed is not None else []
    if problems:
        raise ValueError("invalid seed: " + "; ".join(problems))
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    batch = None
    if dedupe and not dry_run:
        batch_key = batch_key or f"kifu-{uuid4().hex}"
        batch = db.query(KifuDedupBatch).filter_by(batch_key=batch_key).one_or_none()
        if batch is not None and batch.status != "running":
            raise ValueError(f"batch_key already exists: {batch_key} ({batch.status})")
    resumed_running_batch = batch is not None
    ids = None if dry_run or seed is None else _seed_entities(db, seed)
    if not dry_run:
        db.commit()
    aliases = _audited_aliases(db, seed, ids)
    if dedupe and not dry_run and batch is None:
        batch = KifuDedupBatch(batch_key=batch_key, status="running")
        db.add(batch)
        db.commit()

    report = {
        "batch_key": batch_key if batch else None,
        "resumed_running_batch": resumed_running_batch,
        "dry_run": dry_run,
        "albums_scanned": 0,
        "identity_updates": 0,
        "identity_conflicts": 0,
        "ambiguous_names": 0,
        "pointer_conflicts": 0,
        "source_links_added": 0,
        "exact_duplicates": 0,
        "mainline_candidates": 0 if scan_mainlines else None,
        "candidate_pairs": [],
    }
    raw_names: set[tuple[str, str]] = set()
    non_event_labels: set[str] = set()
    identity_state: dict[tuple[str, str], set] = {}
    seen_content: dict[str, int] = {}
    seen_mainline: dict[str, tuple[int, str]] = {}
    source_ids: dict[str, int] = {}
    last_id = 0
    while True:
        rows = db.query(KifuAlbum).filter(KifuAlbum.id > last_id).order_by(KifuAlbum.id).limit(batch_size).all()
        if not rows:
            break
        album_ids = [album.id for album in rows]
        existing_links = {
            (album_id, path)
            for album_id, path in db.query(KifuAlbumSource.album_id, KifuAlbumSource.origin_path).filter(
                KifuAlbumSource.album_id.in_(album_ids)
            )
        }
        if not dry_run:
            keys = {classify_source_path(album.source_path) for album in rows} - source_ids.keys()
            if keys:
                source_ids.update(
                    (key, source_id)
                    for source_id, key in db.query(KifuSource.id, KifuSource.source_key).filter(
                        KifuSource.source_key.in_(keys)
                    )
                )
                for key in keys - source_ids.keys():
                    source = KifuSource(source_key=key, display_name=key)
                    db.add(source)
                    db.flush()
                    source_ids[key] = source.id
        for album in rows:
            last_id = album.id
            report["albums_scanned"] += 1
            if album.round_name:
                non_event_labels.add(album.round_name)
            if album.rules:
                non_event_labels.add(album.rules)
            for kind, raw, field in (
                ("player", album.player_black, "black_player_id"),
                ("player", album.player_white, "white_player_id"),
                ("event", album.event, "event_id"),
            ):
                if raw and raw.strip():
                    raw_names.add((kind, raw))
                target = _resolve(aliases, kind, raw)
                if target is None:
                    if len(aliases[kind].get(normalize_alias(raw or ""), set())) > 1:
                        report["ambiguous_names"] += 1
                    if raw and raw.strip():
                        identity_state.setdefault((kind, raw), set()).add(getattr(album, field))
                    continue
                current = getattr(album, field)
                if current is None:
                    report["identity_updates"] += 1
                    if not dry_run:
                        setattr(album, field, target)
                elif ids is not None and current != target:
                    report["identity_conflicts"] += 1
                if raw and raw.strip():
                    identity_state.setdefault((kind, raw), set()).add(current if current is not None else target)
            own_link = (album.id, album.source_path)
            if own_link not in existing_links:
                report["source_links_added"] += 1
                if not dry_run:
                    db.add(
                        KifuAlbumSource(
                            album_id=album.id,
                            source_id=source_ids[classify_source_path(album.source_path)],
                            origin_path=album.source_path,
                            match_method="source_path",
                        )
                    )
                existing_links.add(own_link)

            if not dedupe:
                continue
            digest = sgf_sha256(album.sgf_content)
            if album.duplicate_of_id is not None:
                existing_master = db.get(KifuAlbum, album.duplicate_of_id)
                if (
                    existing_master is None
                    or existing_master.duplicate_of_id is not None
                    or existing_master.sgf_content != album.sgf_content
                ):
                    report["pointer_conflicts"] += 1
                    continue
                seen_content.setdefault(digest, existing_master.id)
                added, before = _aggregate_duplicate_sources(db, existing_master, album, dry_run)
                report["source_links_added"] += added
                if added and not dry_run:
                    _record_change(db, batch.id, existing_master, existing_master.duplicate_of_id, before)
                continue
            master_id = seen_content.get(digest)
            if (
                master_id is not None
                and master_id != album.id
                and db.get(KifuAlbum, master_id).sgf_content == album.sgf_content
            ):
                report["exact_duplicates"] += 1
                added, master_before = _aggregate_duplicate_sources(db, db.get(KifuAlbum, master_id), album, dry_run)
                report["source_links_added"] += added
                if not dry_run:
                    master = db.get(KifuAlbum, master_id)
                    duplicate_before = source_links_snapshot(db, album.id)
                    album.duplicate_of_id = master.id
                    db.flush()
                    _record_change(db, batch.id, master, master.duplicate_of_id, master_before)
                    _record_change(db, batch.id, album, None, duplicate_before)
                continue
            seen_content.setdefault(digest, album.id)
            signature = None
            if scan_mainlines:
                try:
                    signature = mainline_signature(album.sgf_content)
                except (ValueError, IndexError, TypeError):
                    pass
            if signature:
                prior = seen_mainline.get(signature)
                if prior and prior[1] != digest:
                    report["mainline_candidates"] += 1
                    if len(report["candidate_pairs"]) < 100:
                        report["candidate_pairs"].append([prior[0], album.id])
                else:
                    seen_mainline.setdefault(signature, (album.id, digest))
        if not dry_run:
            db.commit()
        if report["albums_scanned"] // 5000 > (report["albums_scanned"] - len(rows)) // 5000:
            print(
                f"kifu backfill: {report['albums_scanned']} albums, {report['exact_duplicates']} exact duplicates, "
                f"{report['source_links_added']} source links",
                file=sys.stderr,
            )
    review_map: dict[tuple[str, str], set[str]] = {}
    if seed is not None:
        legacy_stats, review_map = _migrate_legacy_reviews(db, raw_names, non_event_labels, aliases, dry_run=dry_run)
        report.update(legacy_stats)
    else:
        report["legacy_reviews_skipped_no_seed"] = True
    if batch:
        report["exact_duplicates_in_batch"] = (
            db.query(KifuDedupChange)
            .filter(
                KifuDedupChange.batch_id == batch.id,
                KifuDedupChange.duplicate_of_id_before.is_(None),
                KifuDedupChange.duplicate_of_id_after.isnot(None),
            )
            .count()
        )
        batch.status = "complete"
        batch.summary = {key: value for key, value in report.items() if key != "candidate_pairs"}
        batch.finished_at = datetime.now(timezone.utc)
        db.commit()
    identity_coverage = {}
    for kind in ("player", "event"):
        grouped = [values for (name_kind, _), values in identity_state.items() if name_kind == kind]
        linked = sum(len(values) == 1 and None not in values for values in grouped)
        ambiguous = sum(len(values - {None}) > 1 for values in grouped)
        identity_coverage[kind] = {
            "distinct_names": len(grouped),
            "linked": linked,
            "ambiguous": ambiguous,
            "unlinked": len(grouped) - linked - ambiguous,
            "linked_rate": linked / len(grouped) if grouped else 0.0,
        }
    report["identity_coverage"] = identity_coverage
    report["name_seed_coverage"] = seed_coverage(seed, raw_names, review_map) if seed is not None else None
    return report


def undo_dedup_batch(db: Session, batch_key: str) -> int:
    batch = db.query(KifuDedupBatch).filter_by(batch_key=batch_key).one()
    if batch.status != "complete":
        raise ValueError(f"batch is not complete: {batch.status}")
    changes = db.query(KifuDedupChange).filter_by(batch_id=batch.id).order_by(KifuDedupChange.id.desc()).all()
    for change in changes:
        album = db.get(KifuAlbum, change.album_id)
        if not album or sgf_sha256(album.sgf_content) != change.sgf_sha256_before:
            raise ValueError(f"album {change.album_id} content changed; undo refused")
        if album.duplicate_of_id != change.duplicate_of_id_after:
            raise ValueError(f"album {change.album_id} duplicate pointer changed; undo refused")
    for change in changes:
        album = db.get(KifuAlbum, change.album_id)
        old_links = {
            (link["source_id"], link["origin_path"], link["match_method"]) for link in change.source_links_before
        }
        for link in change.source_links_after:
            key = (link["source_id"], link["origin_path"], link["match_method"])
            if key not in old_links:
                db.query(KifuAlbumSource).filter_by(
                    album_id=album.id,
                    source_id=link["source_id"],
                    origin_path=link["origin_path"],
                    match_method=link["match_method"],
                ).delete(synchronize_session=False)
        album.duplicate_of_id = change.duplicate_of_id_before
    batch.status = "undone"
    batch.finished_at = datetime.now(timezone.utc)
    db.commit()
    return len(changes)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", help="database URL; defaults to KATRAIN_DATABASE_URL")
    parser.add_argument("--seed", type=Path, help="audited seed JSON mounted into the runtime; optional")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--batch-key")
    parser.add_argument("--apply", action="store_true", help="write changes; omitted means dry-run")
    parser.add_argument(
        "--skip-mainline-candidates",
        action="store_true",
        help="skip costly mainline parsing; report candidates as unavailable",
    )
    parser.add_argument(
        "--undo-dedup-batch",
        "--undo-batch",
        dest="undo_dedup_batch",
        help="undo only duplicate pointers and aggregated master sources in one completed batch",
    )
    args = parser.parse_args()
    database_url = args.database_url or os.getenv("KATRAIN_DATABASE_URL")
    if not database_url:
        parser.error("set KATRAIN_DATABASE_URL or pass --database-url")
    engine = create_engine(database_url)
    try:
        with Session(engine) as db:
            if args.undo_dedup_batch:
                print(
                    json.dumps(
                        {"dedup_changes_undone": undo_dedup_batch(db, args.undo_dedup_batch)}, ensure_ascii=False
                    )
                )
            else:
                report = backfill_catalog(
                    db,
                    load_seed(args.seed) if args.seed else None,
                    dry_run=not args.apply,
                    batch_key=args.batch_key,
                    batch_size=args.batch_size,
                    scan_mainlines=not args.skip_mainline_candidates,
                )
                print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
