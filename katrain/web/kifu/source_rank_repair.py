"""Whole-corpus read-only preparation and transaction-owned guarded rank repair.

Only legacy unqualified dan needs a stored repair. Every slot is censused;
existing snapshots and global rank facts are never replaced. Callers export the
manifest and its SHA before opening an apply transaction. No function commits.
"""

from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import re

from sqlalchemy import and_, or_, select
from katrain.core.sgf_parser import SGF, ParseError
from katrain.web.core import models_db as m
from katrain.web.kifu import name_batch
from katrain.web.kifu.source_rank_normalization import (
    POLICY_VERSION,
    build_source_snapshot,
    digest,
    normalize_source_rank,
    require,
    trusted_source_link,
    validate_source_snapshot,
)

FORMAT = "kifu-source-rank-repair-v2"
REGISTRY = {
    "version": POLICY_VERSION,
    "sources": {"CWI": "historical generic dan", "19x19": "typed p/d/k"},
    "preserve_existing_snapshots": True,
}
_GENERIC_DAN = re.compile(r"\s*[1-9]\d?\s*(?:d|dan)\s*\Z", re.I)
_ALBUM_FIELDS = (
    "id",
    "source_path",
    "black_rank",
    "white_rank",
    "black_player_id",
    "white_player_id",
    "player_black",
    "player_white",
    "date_played",
    "date_sort",
)


def rank_manifest_sha256(manifest):
    return digest(manifest)


def _links(conn, album_ids=None, *, lock=False):
    t, s = m.KifuAlbumSource.__table__, m.KifuSource.__table__
    query = (
        select(t.c.id, t.c.album_id, t.c.source_id, t.c.origin_path, t.c.match_method, s.c.source_key)
        .join(s, t.c.source_id == s.c.id)
        .order_by(t.c.id)
    )
    if album_ids is not None:
        query = query.where(t.c.album_id.in_(album_ids))
    if lock:
        query = query.with_for_update()
    result = defaultdict(list)
    for row in conn.execute(query).mappings():
        result[row["album_id"]].append(dict(row))
    return result


def _album_image(album, links):
    return {
        **{key: album.get(key) for key in _ALBUM_FIELDS},
        "sgf_sha256": sha256(album["sgf_content"].encode()).hexdigest(),
        "source_links": deepcopy(links),
    }


def _precise_date(album):
    raw = album.get("date_played")
    if not isinstance(raw, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw) or raw == "1900-01-01":
        return None
    try:
        datetime.strptime(raw, "%Y-%m-%d")
    except ValueError:
        return None
    return raw


def _operation(album):
    from katrain.web.kifu.catalog_standardization import full_operation_fingerprint

    try:
        root = SGF.parse_sgf(album["sgf_content"])
    except ParseError as exc:
        raise ValueError("rank operation SGF parse invalid") from exc
    node = root
    while node is not None:
        require(len(node.children) <= 1, "rank counterpart has variations")
        node = node.children[0] if node.children else None
    return full_operation_fingerprint(album["sgf_content"])


def _reviewed_target(legacy, counterpart, canonical):
    """The reviewed Yoda/Go pair is one exact exception, never transliteration."""
    compact = lambda value: "".join((value or "").split())
    return (
        legacy["source_path"] == "data/kifu-album/Go_Seigen/1989-01-17.sgf"
        and counterpart["source_path"] == "data/kifu-album/19x19/41563564.sgf"
        and _precise_date(legacy) == _precise_date(counterpart) == "1989-01-17"
        and compact(legacy["player_black"]) == "YodaNorimoto"
        and compact(legacy["player_white"]) == "GoSeigen"
        and canonical.get(counterpart["black_player_id"]) in {"依田纪基", "依田紀基"}
        and canonical.get(counterpart["white_player_id"]) in {"吴清源", "吳清源"}
        and legacy["black_player_id"] in {None, counterpart["black_player_id"]}
        and legacy["white_player_id"] == counterpart["white_player_id"]
        and legacy["black_rank"] == "7d"
        and legacy["white_rank"] == "9d"
        and counterpart["black_rank"] == "7p"
        and counterpart["white_rank"] == "9p"
    )


def _historical_evidence(
    legacy, side, counterpart, link, *, canonical, operation, reviewed_pairs=(), identity_index=None
):
    day = _precise_date(legacy)
    ids = [legacy["black_player_id"], legacy["white_player_id"]]
    target = _reviewed_target(legacy, counterpart, canonical)
    require(day is not None and day == _precise_date(counterpart), "counterpart precise date mismatch")
    other_ids = [counterpart["black_player_id"], counterpart["white_player_id"]]
    require(
        all(isinstance(x, int) and x > 0 for x in other_ids) and (ids == other_ids or target),
        "counterpart ordered identity mismatch",
    )
    if identity_index is not None:
        from katrain.web.kifu.catalog_standardization import _sgf_identity_bound, _reviewed_identity_compatible

        require(
            all(_sgf_identity_bound(game, identity_index) for game in (legacy, counterpart))
            and _reviewed_identity_compatible((legacy, counterpart), other_ids, identity_index),
            "counterpart raw SGF ordered identity mismatch",
        )
    # Additional caller-supplied review flags never grant identity authority.
    if target:
        ids = other_ids
    raw, other_raw = legacy[f"{side}_rank"], counterpart[f"{side}_rank"]
    for game in (legacy, counterpart):
        root = SGF.parse_sgf(game["sgf_content"])
        require(root.get_property("DT") == game["date_played"], "counterpart SGF precise date mismatch")
        require(
            root.get_property("BR" if side == "black" else "WR") == game[f"{side}_rank"],
            "counterpart SGF grade mismatch",
        )
    grade = normalize_source_rank(raw, source_key="CWI")
    other_grade = normalize_source_rank(other_raw, source_key="19x19")
    require(
        grade
        and other_grade
        and grade["rank_value"] == other_grade["rank_value"]
        and other_grade["rank_system"] == "professional_dan",
        "counterpart professional grade mismatch",
    )
    require(operation == _operation(counterpart), "counterpart complete operation mismatch")
    evidence = {
        "kind": "same_game_historical_professional",
        "rank_value": grade["rank_value"],
        "date": day,
        "ordered_player_ids": ids,
        "counterpart": {
            "album_id": counterpart["id"],
            "source_link_id": link["id"],
            "source_id": link["source_id"],
            "source_key": link["source_key"],
            "source_path": link["origin_path"],
            "slot": side,
            "sgf_sha256": sha256(counterpart["sgf_content"].encode()).hexdigest(),
            "operation_sha256": operation,
            "raw_rank": other_raw,
            "date": day,
            "ordered_player_ids": ids,
        },
    }
    if target:
        evidence["reviewed_identity"] = {
            "review": "2026-11-03-kifu-rank-investigation",
            "legacy_black": "Yoda Norimoto",
            "canonical_black": canonical[counterpart["black_player_id"]],
            "historical_official": [
                {
                    "url": "https://www.nihonkiin.or.jp/player/htm/ki000101.htm",
                    "grade": "7p",
                    "valid_from": "1987",
                    "next_grade_year": "1990",
                },
                {"url": "https://www.nihonkiin.or.jp/player/htm/ki001001.htm", "grade": "9p", "valid_from": "1950"},
            ],
        }
    return evidence


def _cohort_context(evidence):
    return {
        "operation_sha256": evidence["counterpart"]["operation_sha256"],
        "date": evidence["date"],
        "ordered_player_ids": evidence["ordered_player_ids"],
    }


def _live_historical_cohorts(conn, frozen_cohorts):
    """Read exact source-authorized peer membership after obtaining writer locks."""
    if not frozen_cohorts:
        return []
    contexts = [
        {key: cohort[key] for key in ("operation_sha256", "date", "ordered_player_ids")} for cohort in frozen_cohorts
    ]
    by_context = {digest(context): {**context, "members": []} for context in contexts}
    pairs = {tuple(context["ordered_player_ids"]) for context in contexts}
    predicates = [
        and_(m.KifuAlbum.black_player_id == black, m.KifuAlbum.white_player_id == white)
        for black, white in sorted(pairs)
    ]
    query = (
        select(m.KifuAlbum.__table__)
        .where(m.KifuAlbum.date_played.in_({context["date"] for context in contexts}), or_(*predicates))
        .order_by(m.KifuAlbum.id)
    )
    albums = [dict(row) for row in conn.execute(query).mappings()]
    links = _links(conn, [album["id"] for album in albums])
    for album in albums:
        link = trusted_source_link(album, links[album["id"]])
        if link is None or link["source_key"] != "19x19":
            continue
        try:
            operation = _operation(album)
        except ValueError:
            continue
        key = digest(
            {
                "operation_sha256": operation,
                "date": _precise_date(album),
                "ordered_player_ids": [album["black_player_id"], album["white_player_id"]],
            }
        )
        if key in by_context:
            by_context[key]["members"].append(_album_image(album, links[album["id"]]))
    return [by_context[digest(context)] for context in contexts]


def prepare_rank_manifest(conn, *, reviewed_pairs=(), observed_at=None):
    """Scan all rows and freeze only absent legacy generic-dan slot repairs."""
    links = _links(conn)
    snapshots = {
        (r.album_id, r.side): r.id
        for r in conn.execute(
            select(m.KifuAlbumRankSnapshot.album_id, m.KifuAlbumRankSnapshot.side, m.KifuAlbumRankSnapshot.id)
        )
    }
    canonical = dict(conn.execute(select(m.KifuPlayer.id, m.KifuPlayer.canonical_name)).all())
    from katrain.web.kifu.catalog_standardization import _identities

    identity_index = _identities(conn)
    census = Counter(albums=0, slots=0, existing_snapshot_slots=0)
    source_counts, systems, candidates, counterparts = Counter(), Counter(), [], defaultdict(list)
    inventory = sha256()
    for row in conn.execute(
        select(m.KifuAlbum.__table__).order_by(m.KifuAlbum.id).execution_options(yield_per=500)
    ).mappings():
        album = dict(row)
        census["albums"] += 1
        source = trusted_source_link(album, links[album["id"]])
        family = source["source_key"] if source else "unknown_or_ambiguous"
        source_counts[family] += 1
        image = _album_image(album, links[album["id"]])
        inventory.update((digest(image) + "\n").encode())
        legacy = []
        for side in ("black", "white"):
            census["slots"] += 1
            raw = album[f"{side}_rank"] or ""
            decision = normalize_source_rank(raw, source_key=source["source_key"] if source else None)
            systems[family + ":" + (decision["rank_system"] if decision else "empty" if not raw else "unparsed")] += 1
            if (album["id"], side) in snapshots:
                census["existing_snapshot_slots"] += 1
                continue
            if source and family == "CWI" and _GENERIC_DAN.fullmatch(raw) and decision:
                legacy.append(side)
        if legacy:
            candidates.append((album, source, image, legacy))
    # Grade conflict detection includes typed amateur and bare-dan counterparts.
    # Restrict expensive SGF parsing to precise legacy dates and operation keys.
    operations = {}
    for album, _, _, _ in candidates:
        try:
            operations[album["id"]] = _operation(album)
        except ValueError:
            operations[album["id"]] = None
    days = {_precise_date(album) for album, _, _, _ in candidates} - {None}
    operation_keys = set(operations.values()) - {None}
    if days and operation_keys:
        query = (
            select(m.KifuAlbum.__table__)
            .where(m.KifuAlbum.date_played.in_(days))
            .order_by(m.KifuAlbum.id)
            .execution_options(yield_per=500)
        )
        for row in conn.execute(query).mappings():
            album = dict(row)
            source = trusted_source_link(album, links[album["id"]])
            if source is None or source["source_key"] != "19x19":
                continue
            try:
                operation = _operation(album)
                if operation in operation_keys:
                    counterparts[operation].append((album, source, _album_image(album, links[album["id"]])))
            except ValueError:
                census["counterpart_operation_unusable"] += 1
    changes, unresolved, historical_cohorts = [], Counter(), {}
    for album, source, image, sides in candidates:
        operation = operations[album["id"]]
        for side in sides:
            proofs = []
            potential = counterparts.get(operation, ()) if operation else ()
            for other, other_link, other_image in potential:
                try:
                    proof = _historical_evidence(
                        album,
                        side,
                        other,
                        other_link,
                        canonical=canonical,
                        operation=operation,
                        reviewed_pairs=reviewed_pairs,
                        identity_index=identity_index,
                    )
                    proofs.append((proof, other_image))
                except ValueError as exc:
                    unresolved[str(exc)] += 1
            # A conflicting same-game same-date same-identity grade refuses all refinement.
            conflict = False
            for other, _, _ in potential:
                if (
                    _precise_date(album) == _precise_date(other)
                    and [album["black_player_id"], album["white_player_id"]]
                    == [other["black_player_id"], other["white_player_id"]]
                    and all(album[f"{s}_player_id"] for s in ("black", "white"))
                ):
                    grade = normalize_source_rank(other[f"{side}_rank"], source_key="19x19")
                    original = normalize_source_rank(album[f"{side}_rank"], source_key="CWI")
                    if grade and (
                        grade["rank_value"] != original["rank_value"]
                        or grade["rank_system"] not in {"professional_dan", "dan_unspecified"}
                    ):
                        conflict = True
            chosen = (
                min(proofs, key=lambda item: item[0]["counterpart"]["album_id"]) if proofs and not conflict else None
            )
            if conflict:
                unresolved["conflicting_counterpart_grade"] += 1
            if not chosen:
                unresolved["slots_without_qualified_historical_proof"] += 1
            after = build_source_snapshot(album, side, source, historical_evidence=chosen[0] if chosen else None)
            census["professional_refinements" if chosen else "unspecified_repairs"] += 1
            if chosen:
                context = _cohort_context(chosen[0])
                historical_cohorts[digest(context)] = {
                    **context,
                    "members": sorted(
                        [
                            other_image
                            for other, _, other_image in potential
                            if _precise_date(other) == context["date"]
                            and [other["black_player_id"], other["white_player_id"]] == context["ordered_player_ids"]
                        ],
                        key=lambda image: image["id"],
                    ),
                }
            if chosen and chosen[0].get("reviewed_identity"):
                census["reviewed_target_slots"] += 1
            changes.append(
                {
                    "album_id": album["id"],
                    "side": side,
                    "album_before": image,
                    "snapshot_before": None,
                    "snapshot_after": after,
                    "counterpart_before": chosen[1] if chosen else None,
                }
            )
    return {
        "format": FORMAT,
        "policy_version": POLICY_VERSION,
        "observed_at": observed_at or datetime.now(timezone.utc).isoformat(),
        "corpus_sha256": inventory.hexdigest(),
        "census": dict(census),
        "source_albums": dict(source_counts),
        "systems": dict(systems),
        "unresolved": dict(unresolved),
        "changes": changes,
        "historical_cohorts": [historical_cohorts[key] for key in sorted(historical_cohorts)],
    }


def validate_rank_manifest(manifest):
    require(
        isinstance(manifest, dict)
        and set(manifest)
        == {
            "format",
            "policy_version",
            "observed_at",
            "corpus_sha256",
            "census",
            "source_albums",
            "systems",
            "unresolved",
            "changes",
            "historical_cohorts",
        }
        and manifest["format"] == FORMAT
        and manifest["policy_version"] == POLICY_VERSION,
        "rank manifest shape invalid",
    )
    require(
        isinstance(manifest["changes"], list) and len(manifest["changes"]) <= 400000, "rank manifest changes invalid"
    )
    require(
        isinstance(manifest["historical_cohorts"], list)
        and len(manifest["historical_cohorts"]) <= len(manifest["changes"]),
        "rank historical cohort bounds invalid",
    )
    cohorts = {}
    for cohort in manifest["historical_cohorts"]:
        require(
            isinstance(cohort, dict)
            and set(cohort) == {"operation_sha256", "date", "ordered_player_ids", "members"}
            and isinstance(cohort["members"], list)
            and 1 <= len(cohort["members"]) <= 400000,
            "rank historical cohort shape invalid",
        )
        context = {key: cohort[key] for key in ("operation_sha256", "date", "ordered_player_ids")}
        key = digest(context)
        require(
            key not in cohorts
            and cohort["members"] == sorted(cohort["members"], key=lambda image: image["id"])
            and len({image["id"] for image in cohort["members"]}) == len(cohort["members"]),
            "rank historical cohort membership invalid",
        )
        cohorts[key] = cohort
    used_cohorts = set()
    seen = set()
    for change in manifest["changes"]:
        require(
            set(change)
            == {"album_id", "side", "album_before", "snapshot_before", "snapshot_after", "counterpart_before"}
            and change["snapshot_before"] is None,
            "rank preimage shape invalid",
        )
        key = (change["album_id"], change["side"])
        require(key not in seen, "duplicate rank slot")
        seen.add(key)
        before = change["album_before"]
        snapshot = change["snapshot_after"]
        require(
            before["id"] == change["album_id"]
            and snapshot["source_ref"]["album_id"] == change["album_id"]
            and snapshot["source_ref"]["slot"] == change["side"]
            and snapshot["source_ref"]["sgf_sha256"] == before["sgf_sha256"]
            and snapshot["raw_rank"] == (before[f"{change['side']}_rank"] or "")
            and snapshot["player_id"] == before[f"{change['side']}_player_id"],
            "rank manifest binding invalid",
        )
        require(
            _GENERIC_DAN.fullmatch(snapshot["raw_rank"]) and snapshot["source_ref"]["source_key"] == "CWI",
            "rank repair scope invalid",
        )
        require(
            (change["counterpart_before"] is None) == (snapshot["evidence"] == {"kind": "source_convention"}),
            "rank counterpart preimage invalid",
        )
        if change["counterpart_before"] is not None:
            context_key = digest(_cohort_context(snapshot["evidence"]))
            require(
                context_key in cohorts and change["counterpart_before"] in cohorts[context_key]["members"],
                "rank historical cohort proof missing",
            )
            used_cohorts.add(context_key)
    require(used_cohorts == set(cohorts), "unreferenced rank historical cohort")
    return manifest


def _live_preflight(conn, manifest, *, absent_snapshots):
    if absent_snapshots and manifest["historical_cohorts"] and conn.dialect.name == "postgresql":
        # Row locks cannot protect absence of a newly imported competing peer.
        # READ COMMITTED gives the recheck a fresh view after the writer locks.
        require(
            conn.get_isolation_level() == "READ COMMITTED",
            "rank historical cohort first apply requires READ COMMITTED isolation",
        )
        conn.exec_driver_sql(
            "LOCK TABLE kifu_albums, kifu_album_sources, kifu_sources, "
            "kifu_players, kifu_player_aliases, kifu_player_names, "
            "kifu_album_rank_snapshots IN SHARE ROW EXCLUSIVE MODE"
        )
    ids = {c["album_id"] for c in manifest["changes"]} | {
        c["counterpart_before"]["id"] for c in manifest["changes"] if c["counterpart_before"]
    }
    albums = {
        r["id"]: dict(r)
        for r in conn.execute(
            select(m.KifuAlbum.__table__).where(m.KifuAlbum.id.in_(ids)).order_by(m.KifuAlbum.id).with_for_update()
        ).mappings()
    }
    links = _links(conn, ids, lock=True)
    if conn.dialect.name == "postgresql":
        conn.exec_driver_sql("LOCK TABLE kifu_album_rank_snapshots IN SHARE ROW EXCLUSIVE MODE")
    existing = {
        (r.album_id, r.side)
        for r in conn.execute(
            select(m.KifuAlbumRankSnapshot.album_id, m.KifuAlbumRankSnapshot.side).where(
                m.KifuAlbumRankSnapshot.album_id.in_(ids)
            )
        )
    }
    canonical = dict(conn.execute(select(m.KifuPlayer.id, m.KifuPlayer.canonical_name)).all())
    identity_index = None
    if absent_snapshots and manifest["historical_cohorts"]:
        from katrain.web.kifu.catalog_standardization import _identities

        identity_index = _identities(conn)
    for change in manifest["changes"]:
        album, side = albums.get(change["album_id"]), change["side"]
        require(album is not None, "rank album/source preimage changed")
        current_image = _album_image(album, links[album["id"]])
        if current_image != change["album_before"] and not absent_snapshots:
            from katrain.web.kifu.catalog_standardization import retained_source_links

            current_image = _album_image(album, retained_source_links(conn, album["id"]))
        require(current_image == change["album_before"], "rank album/source preimage changed")
        if absent_snapshots:
            require((album["id"], side) not in existing, "rank snapshot preimage changed")
        snapshot = change["snapshot_after"]
        validate_source_snapshot(snapshot, album=album, side=side, source_links=links[album["id"]])
        other_image = change["counterpart_before"]
        if other_image:
            other = albums.get(other_image["id"])
            require(other is not None, "rank counterpart preimage changed")
            current_other = _album_image(other, links[other["id"]])
            if current_other != other_image and not absent_snapshots:
                from katrain.web.kifu.catalog_standardization import retained_source_links

                current_other = _album_image(other, retained_source_links(conn, other["id"]))
            require(current_other == other_image, "rank counterpart preimage changed")
            link = trusted_source_link(other, links[other["id"]])
            require(link is not None, "rank counterpart source preimage changed")
            proof = _historical_evidence(
                album,
                side,
                other,
                link,
                canonical=canonical,
                operation=_operation(album),
                identity_index=identity_index,
            )
            require(proof == snapshot["evidence"], "rank historical evidence changed")
    if absent_snapshots:
        require(
            _live_historical_cohorts(conn, manifest["historical_cohorts"]) == manifest["historical_cohorts"],
            "rank historical counterpart cohort preimage changed",
        )


def _batch(conn, manifest_sha):
    return (
        conn.execute(
            select(m.KifuNameBatch.__table__).where(m.KifuNameBatch.bundle_sha256 == manifest_sha).with_for_update()
        )
        .mappings()
        .one_or_none()
    )


def _journal_preflight(conn, batch, manifest):
    changes = list(
        conn.execute(
            select(m.KifuNameChange.__table__)
            .where(m.KifuNameChange.batch_id == batch["id"])
            .order_by(m.KifuNameChange.sequence)
        ).mappings()
    )
    require(len(changes) == len(manifest["changes"]), "rank journal count changed")
    for row, change in zip(changes, manifest["changes"]):
        after = row["after_image"]
        require(
            row["target_table"] == m.KifuAlbumRankSnapshot.__tablename__
            and row["before_image"] is None
            and after["album_id"] == change["album_id"]
            and after["side"] == change["side"]
            and after["snapshot"] == change["snapshot_after"]
            and after["publication_key"] == "source-rank:" + batch["bundle_sha256"]
            and after["native_batch_id"] == batch["id"]
            and after["rank_fact_id"] is None,
            "rank journal binding changed",
        )
        require(
            name_batch._image(conn, m.KifuAlbumRankSnapshot.__table__, row["target_row_id"]) == after,
            "rank journal target changed",
        )
    return changes


def _lock_writer(conn):
    if conn.dialect.name == "postgresql":
        # Match native publication and combined dedup ordering before row/table locks.
        conn.exec_driver_sql("SET LOCAL lock_timeout = '15s'")
        conn.exec_driver_sql("SELECT pg_advisory_xact_lock(%s)", (name_batch._ADVISORY_LOCK_KEY,))
        conn.exec_driver_sql("SELECT pg_advisory_xact_lock(%s)", (720220261003,))


def apply_rank_manifest(conn, manifest, *, expected_sha256):
    validate_rank_manifest(manifest)
    manifest_sha = rank_manifest_sha256(manifest)
    require(manifest_sha == expected_sha256, "rank manifest SHA mismatch")
    with conn.begin_nested():
        _lock_writer(conn)
        batch = _batch(conn, manifest_sha)
        if batch:
            require(
                batch["reviewed_artifact"] == manifest and batch["status"] == "applied", "rank batch changed or undone"
            )
            _live_preflight(conn, manifest, absent_snapshots=False)
            _journal_preflight(conn, batch, manifest)
            return {"status": "already_applied", "batch_id": batch["id"], "changes": len(manifest["changes"])}
        _live_preflight(conn, manifest, absent_snapshots=True)
        registry = m.KifuNameSourceRegistry.__table__
        registry_sha = digest(REGISTRY)
        registry_id = conn.execute(
            select(registry.c.id).where(registry.c.version == POLICY_VERSION, registry.c.sha256 == registry_sha)
        ).scalar_one_or_none()
        if registry_id is None:
            registry_id = conn.execute(
                registry.insert().values(version=POLICY_VERSION, sha256=registry_sha, registry=REGISTRY)
            ).inserted_primary_key[0]
        batch_id = conn.execute(
            m.KifuNameBatch.__table__.insert().values(
                bundle_sha256=manifest_sha,
                inventory_sha256=manifest["corpus_sha256"],
                source_registry_id=registry_id,
                reviewed_artifact=manifest,
                status="applied",
                applied_at=datetime.now(timezone.utc),
            )
        ).inserted_primary_key[0]
        for sequence, change in enumerate(manifest["changes"], 1):
            snapshot = change["snapshot_after"]
            row_id, after = name_batch._insert(
                conn,
                m.KifuAlbumRankSnapshot,
                {
                    "album_id": change["album_id"],
                    "side": change["side"],
                    "rank_fact_id": None,
                    "snapshot": snapshot,
                    "snapshot_sha256": snapshot["content_sha256"],
                    "publication_key": "source-rank:" + manifest_sha,
                    "native_batch_id": batch_id,
                },
            )
            name_batch._record_change(conn, batch_id, sequence, m.KifuAlbumRankSnapshot, row_id, None, after)
        return {"status": "applied", "batch_id": batch_id, "changes": len(manifest["changes"])}


def undo_rank_manifest(conn, manifest, *, expected_sha256):
    validate_rank_manifest(manifest)
    manifest_sha = rank_manifest_sha256(manifest)
    require(manifest_sha == expected_sha256, "rank manifest SHA mismatch")
    with conn.begin_nested():
        _lock_writer(conn)
        batch = _batch(conn, manifest_sha)
        require(batch is not None and batch["reviewed_artifact"] == manifest, "rank batch missing or changed")
        if batch["status"] == "undone":
            return {"status": "already_undone", "batch_id": batch["id"], "changes": 0}
        require(batch["status"] == "applied", "rank batch status changed")
        _live_preflight(conn, manifest, absent_snapshots=False)
        journal = _journal_preflight(conn, batch, manifest)
        for change in reversed(journal):
            conn.execute(
                m.KifuAlbumRankSnapshot.__table__.delete().where(m.KifuAlbumRankSnapshot.id == change["target_row_id"])
            )
        conn.execute(
            m.KifuNameBatch.__table__.update().where(m.KifuNameBatch.id == batch["id"]).values(status="undone")
        )
        return {"status": "undone", "batch_id": batch["id"], "changes": len(journal)}
