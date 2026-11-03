"""Bounded, reversible reviewed same-game display deduplication.

Source SGFs and analysis identities never change. Callers own the transaction.
A full-operation collision is only a candidate; identity/date/metadata evidence
and the frozen preimages below are required before any pointer can be written.
"""

from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from hashlib import sha256
import json
import re

from sqlalchemy import delete, func, insert, or_, select, text, update
from sqlalchemy.exc import DBAPIError

from katrain.core.sgf_parser import SGF, ParseError
from katrain.web.core.models_db import (
    KifuAlbum,
    KifuAlbumSource,
    KifuDedupBatch,
    KifuDedupChange,
    KifuPlayer,
    KifuPlayerAlias,
    KifuPlayerName,
    KifuSource,
)
from katrain.web.kifu.identity import normalize_alias
from katrain.web.kifu.historical_ranks import (
    MAX_INCOMING_GAMES,
    MAX_OWNERS,
    MAX_BODY_ROWS,
    MAX_SGF_BYTES,
    MAX_BODY_BYTES,
    MAX_SCALAR_ROWS,
    MAX_SCALAR_BYTES,
    _body_length,
    _bounded_queries,
)

VERSION = "kifu-reviewed-dedup-v1"
_ALBUM_FIELDS = tuple(c.name for c in KifuAlbum.__table__.columns if c.name not in ("created_at", "search_text"))
_LINK_FIELDS = ("source_id", "origin_path", "match_method")


def _hash(value):
    return sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _operations(sgf):
    try:
        parser = SGF(sgf)
        _require(
            not sgf[: sgf.index("(")].strip().lstrip("\ufeff") and not sgf[parser.ix :].strip(),
            "incomplete or multi-game SGF",
        )
        root = parser.root
        size = root.board_size
    except (ParseError, TypeError, AttributeError, ValueError) as exc:
        raise ValueError("invalid complete SGF operations") from exc
    _require(all(0 < n <= 52 for n in size), "invalid board size")
    initial = root.get_property("PL") or ("W" if root.handicap >= 2 else "B")
    _require(initial in ("B", "W"), "invalid initial player")
    operations, moves, variants, node = [], 0, 0, root
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def point(raw):
        _require(isinstance(raw, str) and len(raw) == 2 and all(c in alphabet for c in raw), "invalid coordinate")
        x, y = (alphabet.index(c) for c in raw)
        _require(x < size[0] and y < size[1], "coordinate outside board")
        return x, y

    while True:
        variants += max(0, len(node.children) - 1)
        if node is not root and node.get_property("PL"):
            _require(node.get_property("PL") in ("B", "W"), "invalid player")
            operations.append(["PL", node.get_property("PL")])
        for prop in ("AE", "AB", "AW"):
            points = []
            for raw in node.get_list_property(prop, []):
                if ":" in raw:
                    bounds = raw.split(":")
                    _require(len(bounds) == 2, "invalid setup range")
                    lo, hi = map(point, bounds)
                    _require(lo[0] <= hi[0] and lo[1] <= hi[1], "invalid setup range")
                    points.extend((x, y) for x in range(lo[0], hi[0] + 1) for y in range(lo[1], hi[1] + 1))
                else:
                    points.append(point(raw))
            _require(len(points) == len(set(points)), "duplicate setup coordinate")
            if points:
                operations.append([prop, sorted(points)])
        raw_moves = [(color, raw) for color in ("B", "W") for raw in node.get_list_property(color, [])]
        _require(len(raw_moves) <= 1, "multiple moves in node")
        for color, raw in raw_moves:
            xy = None if raw == "" or (raw == "tt" and max(size) <= 19) else point(raw)
            operations.append(["move", [color, xy]])
            moves += 1
        if not node.children:
            break
        node = node.children[0]
    return _hash([size, initial, operations]), moves, variants


def full_operation_fingerprint(sgf: str) -> str:
    """Size, expanded setup, player-to-move and ordered colored moves/passes."""
    return _operations(sgf)[0]


def _links(conn, album_id):
    return [
        dict(row)
        for row in conn.execute(
            select(*(getattr(KifuAlbumSource, f) for f in _LINK_FIELDS))
            .where(KifuAlbumSource.album_id == album_id)
            .order_by(KifuAlbumSource.source_id, KifuAlbumSource.origin_path, KifuAlbumSource.match_method)
        ).mappings()
    ]


def _source_rows(conn, album_id):
    return [
        dict(row)
        for row in conn.execute(
            select(
                KifuAlbumSource.id,
                KifuAlbumSource.album_id,
                *(getattr(KifuAlbumSource, field) for field in _LINK_FIELDS),
            )
            .where(KifuAlbumSource.album_id == album_id)
            .order_by(KifuAlbumSource.id)
        ).mappings()
    ]


def _check_original_source_ids(conn, member):
    current = _source_rows(conn, member["album"]["id"])
    _require(
        all(row in current for row in member["original_source_rows"]), "original source link preimage identity changed"
    )


def _image(conn, album_id):
    row = (
        conn.execute(select(*(getattr(KifuAlbum, f) for f in _ALBUM_FIELDS)).where(KifuAlbum.id == album_id))
        .mappings()
        .one_or_none()
    )
    return dict(row) if row else None


def _identities(conn, tokens=None):
    index = defaultdict(set)
    if tokens == set():
        return index
    for name, owner in conn.execute(select(KifuPlayer.canonical_name, KifuPlayer.id).execution_options(yield_per=500)):
        token = normalize_alias(name)
        if tokens is None or token in tokens:
            index[token].add(owner)
    aliases = select(KifuPlayerAlias.normalized_alias, KifuPlayerAlias.player_id)
    if tokens is not None:
        aliases = aliases.where(KifuPlayerAlias.normalized_alias.in_(tokens))
    for name, owner in conn.execute(aliases.execution_options(yield_per=500)):
        token = normalize_alias(name)
        if tokens is None or token in tokens:
            index[token].add(owner)
    for name, owner in conn.execute(
        select(KifuPlayerName.display_name, KifuPlayerName.player_id)
        .where(KifuPlayerName.status == "verified", KifuPlayerName.reference_url.isnot(None))
        .execution_options(yield_per=500)
    ):
        token = normalize_alias(name)
        if tokens is None or token in tokens:
            index[token].add(owner)
    return index


def _identity(row, side, index):
    owner, found = row[f"{side}_player_id"], index.get(normalize_alias(row.get(f"player_{side}") or ""), set())
    if owner is not None:
        return owner if not found or found == {owner} else None
    return next(iter(found)) if len(found) == 1 else None


def _sgf_identity_bound(row, identities):
    root = SGF.parse_sgf(row["sgf_content"])
    for side, prop in (("black", "PB"), ("white", "PW")):
        raw = root.get_property(prop)
        if not isinstance(raw, str) or not raw.strip():
            return False
        scalar = row.get(f"player_{side}") or ""
        if normalize_alias(raw) == normalize_alias(scalar):
            continue
        owners = identities.get(normalize_alias(raw), set())
        if len(owners) != 1 or next(iter(owners)) != _identity(row, side, identities):
            return False
    return True


def _precise_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) or value == "1900-01-01":
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def _metadata_compatible(rows):
    for row in rows:
        root = SGF.parse_sgf(row["sgf_content"])
        if not _precise_date(row.get("date_played")) or root.get_property("DT") != row["date_played"]:
            return False
    for field in ("komi", "handicap", "result", "rules"):
        values = set()
        observations = []
        for row in rows:
            observations.append(row.get(field))
            raw_property = {"komi": "KM", "handicap": "HA", "result": "RE", "rules": "RU"}[field]
            observations.append(SGF.parse_sgf(row["sgf_content"]).get_property(raw_property))
        for value in observations:
            if value in (None, ""):
                continue
            value = str(value).strip().casefold()
            if field in ("komi", "handicap"):
                try:
                    value = float(value)
                except ValueError:
                    return False
            elif field == "rules":
                value = {"cn": "chinese", "jp": "japanese", "ko": "korean"}.get(value, value)
            elif field == "result":
                value = {"黑中盘胜": "b+r", "白中盘胜": "w+r", "黑胜": "b+", "白胜": "w+"}.get(value, value)
            values.add(value)
        if len(values) > 1:
            return False
    return True


def _source_image(conn, source_ids=None):
    query = select(KifuSource.id, KifuSource.source_key)
    if source_ids is not None:
        query = query.where(KifuSource.id.in_(source_ids))
    return [dict(row) for row in conn.execute(query.order_by(KifuSource.id)).mappings()]


def _reviewed_yoda(rows, canonical_names):
    """One reviewed historical identity exception pinned to both original SGFs."""
    by_sha = {sha256(row["sgf_content"].encode()).hexdigest(): row for row in rows}
    legacy = by_sha.get("aaee773ebe2b3a7cbb222a92491b97bc0326bd39af879f3109ad18cbf1734f4c")
    starpoint = by_sha.get("5a0d787c704dd7bdda94559933c6e40ea90939737241ac9c0fe381a42fd88bb9")
    if not legacy or not starpoint:
        return None
    ids = [starpoint["black_player_id"], starpoint["white_player_id"]]
    if not (
        legacy["source_path"] == "data/kifu-album/Go_Seigen/1989-01-17.sgf"
        and starpoint["source_path"] == "data/kifu-album/19x19/41563564.sgf"
        and canonical_names.get(ids[0]) in {"依田纪基", "依田紀基"}
        and canonical_names.get(ids[1]) in {"吴清源", "吳清源"}
        and legacy["black_player_id"] in (None, ids[0])
        and legacy["white_player_id"] == ids[1]
    ):
        return None
    return {
        "kind": "reviewed_yoda_1989_exact_source_pair",
        "ordered_player_ids": ids,
        "legacy_album_id": legacy["id"],
        "counterpart_album_id": starpoint["id"],
        "official_historical_evidence": [
            "https://www.nihonkiin.or.jp/player/htm/ki000101.htm",
            "https://www.nihonkiin.or.jp/player/htm/ki001001.htm",
        ],
        "review_record": "2026-11-03-kifu-rank-investigation",
        "review_status": "approved",
    }


def _reviewed_identity_compatible(rows, expected_ids, identities):
    for row in rows:
        root = SGF.parse_sgf(row["sgf_content"])
        for side, prop, expected in zip(("black", "white"), ("PB", "PW"), expected_ids):
            if row[f"{side}_player_id"] not in (None, expected):
                return False
            for raw in (row.get(f"player_{side}"), root.get_property(prop)):
                owners = identities.get(normalize_alias(raw or ""), set())
                if owners and owners != {expected}:
                    return False
    return True


def _canonical_preference(member, source_keys):
    own = [
        link
        for link in member["source_links"]
        if link["origin_path"] == member["album"]["source_path"] and link["match_method"] != "reviewed_same_game"
    ]
    starpoint = any(source_keys.get(link["source_id"]) == "19x19" for link in own)
    return (not starpoint, member["album"]["id"])


def _finite_rows(conn, candidate_album_ids, body_budget):
    """Read complete exact-date/ordered-FK cohorts, refusing truncated evidence."""
    ids = set(candidate_album_ids)
    _require(
        len(ids) <= MAX_INCOMING_GAMES and all(type(i) is int and i > 0 for i in ids), "finite incoming album limit"
    )
    fields = ("id", "date_played", "black_player_id", "white_player_id")
    with _bounded_queries(conn):
        incoming = [
            dict(row)
            for row in conn.execute(
                select(*(getattr(KifuAlbum, f) for f in fields)).where(KifuAlbum.id.in_(ids))
            ).mappings()
        ]
    _require({row["id"] for row in incoming} == ids, "finite incoming album missing")
    owners = {row[f"{side}_player_id"] for row in incoming for side in ("black", "white")} - {None}
    _require(len(owners) <= MAX_OWNERS, "finite incoming owner limit")
    cohorts = defaultdict(list)
    excluded = []
    for row in incoming:
        key = (_precise_date(row["date_played"]), row["black_player_id"], row["white_player_id"])
        if key[0] and all(type(value) is int and value > 0 for value in key[1:]):
            cohorts[key].append(row["id"])
        else:
            excluded.append({"album_ids": [row["id"]], "reason": "precise_date_ordered_bound_identity_required"})
    rows, used = [], 0
    for (day, black, white), incoming_ids in sorted(cohorts.items()):
        predicate = (
            KifuAlbum.date_played == day,
            or_(KifuAlbum.black_player_id == black, KifuAlbum.black_player_id.is_(None)),
            or_(KifuAlbum.white_player_id == white, KifuAlbum.white_player_id.is_(None)),
        )
        try:
            with _bounded_queries(conn):
                length = _body_length(conn, KifuAlbum.sgf_content)
                count, maximum, size = conn.execute(
                    select(func.count(), func.coalesce(func.max(length), 0), func.coalesce(func.sum(length), 0)).where(
                        *predicate
                    )
                ).one()
                if count > MAX_BODY_ROWS or maximum > MAX_SGF_BYTES or used + size > body_budget:
                    excluded.append(
                        {
                            "album_ids": sorted(incoming_ids),
                            "reason": "resource_deferred",
                            "cohort": {"date": day, "ordered_player_ids": [black, white], "row_count": count},
                        }
                    )
                    continue
                selected = [
                    dict(row)
                    for row in conn.execute(
                        select(*(getattr(KifuAlbum, f) for f in _ALBUM_FIELDS)).where(*predicate).order_by(KifuAlbum.id)
                    ).mappings()
                ]
                # Counts/lengths precede bodies; protect callers without native table locks too.
                actual = sum(len(row["sgf_content"].encode()) for row in selected)
                if (
                    len(selected) != count
                    or any(len(row["sgf_content"].encode()) > MAX_SGF_BYTES for row in selected)
                    or used + actual > body_budget
                ):
                    excluded.append({"album_ids": sorted(incoming_ids), "reason": "resource_deferred"})
                    continue
                rows.extend(selected)
                used += actual
        except DBAPIError as exc:
            if getattr(exc.orig, "sqlstate", None) != "57014" and getattr(exc.orig, "pgcode", None) != "57014":
                raise
            excluded.append({"album_ids": sorted(incoming_ids), "reason": "resource_deferred"})
    return rows, excluded


def prepare_dedup_manifest(conn, *, reviewed_pairs=(), candidate_album_ids=None, body_budget=None):
    if candidate_album_ids is not None:
        body_budget = MAX_BODY_BYTES if body_budget is None else body_budget
        _require(type(body_budget) is int and 0 <= body_budget <= MAX_BODY_BYTES, "invalid finite body budget")
        with _bounded_queries(conn):
            return _prepare_dedup_manifest(
                conn, reviewed_pairs=reviewed_pairs, candidate_album_ids=candidate_album_ids, body_budget=body_budget
            )
    return _prepare_dedup_manifest(conn, reviewed_pairs=reviewed_pairs)


def _prepare_dedup_manifest(conn, *, reviewed_pairs=(), candidate_album_ids=None, body_budget=None):
    """Freeze eligible DB pairs; optional IDs restrict hourly evidence cohorts."""
    finite = candidate_album_ids is not None
    if finite:
        candidate_album_ids = set(candidate_album_ids)
    rows, deferred = _finite_rows(conn, candidate_album_ids, body_budget) if finite else (None, [])
    tokens = None
    if finite:
        tokens = {normalize_alias(row[f"player_{side}"] or "") for row in rows for side in ("black", "white")}
        for row in rows:
            try:
                root = SGF.parse_sgf(row["sgf_content"])
                tokens.update(normalize_alias(root.get_property(prop) or "") for prop in ("PB", "PW"))
            except (ParseError, ValueError, TypeError, IndexError):
                pass
    if finite:
        with _bounded_queries(conn):
            identities = _identities(conn, tokens)
    else:
        identities = _identities(conn)
    names_query = select(KifuPlayer.id, KifuPlayer.canonical_name)
    if finite:
        names_query = names_query.where(
            KifuPlayer.id.in_({row[f"{side}_player_id"] for row in rows for side in ("black", "white")})
        )
    canonical_names = dict(conn.execute(names_query).all())
    source_links = defaultdict(list)
    source_rows = defaultdict(list)
    links_query = select(
        KifuAlbumSource.album_id, KifuAlbumSource.id, *(getattr(KifuAlbumSource, f) for f in _LINK_FIELDS)
    )
    if finite:
        links_query = links_query.where(KifuAlbumSource.album_id.in_([row["id"] for row in rows]))
        with _bounded_queries(conn):
            sub = links_query.subquery()
            length = sum(func.coalesce(func.length(sub.c[field]), 0) for field in ("origin_path", "match_method"))
            count, size = conn.execute(select(func.count(), func.coalesce(func.sum(length), 0)).select_from(sub)).one()
            _require(
                count <= MAX_SCALAR_ROWS and size * 4 + count * 128 <= MAX_SCALAR_BYTES,
                "finite source link integrity resource limit",
            )
    for row in conn.execute(
        links_query.order_by(
            KifuAlbumSource.album_id,
            KifuAlbumSource.source_id,
            KifuAlbumSource.origin_path,
            KifuAlbumSource.match_method,
        )
    ).mappings():
        source_links[row["album_id"]].append({f: row[f] for f in _LINK_FIELDS})
        source_rows[row["album_id"]].append(dict(row))
    sources = _source_image(
        conn, {link["source_id"] for links in source_links.values() for link in links} if finite else None
    )
    source_keys = {s["id"]: s["source_key"] for s in sources}
    _require(not reviewed_pairs, "caller review flags cannot grant identity authority")
    collisions, rows_by_id, exclusions, counters = defaultdict(list), {}, deferred, Counter()
    if finite:
        counters["resource_deferred_cohorts"] = sum(row["reason"] == "resource_deferred" for row in deferred)
    album_rows = rows if finite else conn.execute(select(*(getattr(KifuAlbum, f) for f in _ALBUM_FIELDS))).mappings()
    for raw in album_rows:
        row = dict(raw)
        counters["albums_scanned"] += 1
        if row["duplicate_of_id"] is not None or row["list_hidden_reason"] is not None:
            counters["preexisting_hidden_preserved"] += 1
            continue
        counters["visible_scanned"] += 1
        try:
            fingerprint, moves, variants = _operations(row["sgf_content"])
            if moves < 30 or variants:
                counters["short_or_branched_report_only"] += 1
                continue
        except (ValueError, IndexError, TypeError, KeyError):
            counters["invalid_operations_report_only"] += 1
            continue
        # Retain full immutable beforeimages only for collisions, not every SGF.
        rows_by_id[row["id"]] = row
        collisions[fingerprint].append(row["id"])
    groups = []
    for fingerprint, ids in sorted(collisions.items()):
        if len(ids) < 2:
            continue
        counters["full_operation_candidate_groups"] += 1
        partitions = defaultdict(list)
        for album_id in ids:
            row = rows_by_id[album_id]
            if not _sgf_identity_bound(row, identities):
                continue
            pair = (_identity(row, "black", identities), _identity(row, "white", identities))
            partitions[(_precise_date(row["date_played"]), pair)].append(album_id)
        accepted = set()
        candidates = list(partitions.items())
        override = _reviewed_yoda([rows_by_id[i] for i in ids], canonical_names)
        if override and _reviewed_identity_compatible(
            [rows_by_id[i] for i in ids], override["ordered_player_ids"], identities
        ):
            pair_ids = [override["legacy_album_id"], override["counterpart_album_id"]]
            candidates.append((("1989-01-17", tuple(override["ordered_player_ids"])), pair_ids))
        for (played, player_ids), members in candidates:
            if len(members) != 2 or not played or not all(type(v) is int and v > 0 for v in player_ids):
                continue
            if set(members) & accepted:
                continue
            if finite and not set(members) & set(candidate_album_ids):
                continue
            rows = [rows_by_id[i] for i in members]
            if not _metadata_compatible(rows) or any(
                not any(
                    link["origin_path"] == rows_by_id[i]["source_path"] and link["match_method"] != "reviewed_same_game"
                    for link in source_links[i]
                )
                for i in members
            ):
                continue
            review = (
                override
                if override and set(members) == {override["legacy_album_id"], override["counterpart_album_id"]}
                else None
            )

            canonical = min(
                members,
                key=lambda album_id: _canonical_preference(
                    {"album": rows_by_id[album_id], "source_links": source_links[album_id]}, source_keys
                ),
            )
            if finite and conn.scalar(
                select(func.count())
                .select_from(KifuAlbum)
                .where(KifuAlbum.duplicate_of_id.in_(set(members) - {canonical}))
            ):
                continue
            groups.append(
                {
                    "canonical_album_id": canonical,
                    "duplicate_album_ids": sorted(set(members) - {canonical}),
                    "operation_sha256": fingerprint,
                    "date": played,
                    "ordered_player_ids": list(player_ids),
                    "reviewed_identity": review,
                    "members": [
                        {
                            "album": rows_by_id[i],
                            "source_links": source_links[i],
                            "original_source_rows": sorted(source_rows[i], key=lambda row: row["id"]),
                            "sgf_sha256": sha256(rows_by_id[i]["sgf_content"].encode()).hexdigest(),
                        }
                        for i in sorted(members)
                    ],
                }
            )
            accepted.update(members)
        if set(ids) != accepted:
            exclusions.append(
                {
                    "album_ids": sorted(set(ids) - accepted),
                    "operation_sha256": fingerprint,
                    "reason": "precise_date_approved_ordered_identity_compatible_metadata_or_pair_bound_required",
                }
            )
    groups.sort(key=lambda group: group["canonical_album_id"])
    counters.update(
        eligible_groups=len(groups),
        duplicates_to_hide=sum(len(g["duplicate_album_ids"]) for g in groups),
        excluded_candidate_groups=len(exclusions),
    )
    result = {
        "version": VERSION,
        "sources": sources,
        "groups": groups,
        "excluded": exclusions,
        "summary": dict(counters),
    }
    if finite:
        result["scope"] = {"candidate_album_ids": sorted(candidate_album_ids)}
    return result


def dedup_manifest_sha256(manifest):
    return _hash(manifest)


def validate_dedup_manifest(manifest):
    _require(isinstance(manifest, dict) and manifest.get("version") == VERSION, "invalid dedup manifest version")
    if "scope" in manifest:
        scope = manifest["scope"]
        _require(isinstance(scope, dict) and set(scope) == {"candidate_album_ids"}, "invalid finite dedup scope")
        ids = scope["candidate_album_ids"]
        _require(
            isinstance(ids, list)
            and len(ids) <= MAX_INCOMING_GAMES
            and all(type(i) is int and i > 0 for i in ids)
            and ids == sorted(set(ids)),
            "invalid finite dedup incoming IDs",
        )
    used = set()
    for group in manifest["groups"]:
        members = group["members"]
        ids = {m["album"]["id"] for m in members}
        canonical = group["canonical_album_id"]
        if "scope" in manifest:
            _require(set(manifest["scope"]["candidate_album_ids"]) & ids, "finite dedup group outside incoming scope")
        _require(
            len(members) == len(ids) == 2
            and canonical in ids
            and set(group["duplicate_album_ids"]) == ids - {canonical}
            and not used & ids,
            "invalid bounded dedup members",
        )
        used.update(ids)
        source_keys = {source["id"]: source["source_key"] for source in manifest["sources"]}
        _require(
            canonical == min(members, key=lambda member: _canonical_preference(member, source_keys))["album"]["id"],
            "canonical source preference changed",
        )
        for member in members:
            _require(
                any(
                    link["origin_path"] == member["album"]["source_path"]
                    and link["match_method"] != "reviewed_same_game"
                    for link in member["source_links"]
                ),
                "original source link evidence missing",
            )
            row = member["album"]
            _, moves, variants = _operations(row["sgf_content"])
            _require(moves >= 30 and variants == 0, "short or branched operation evidence is report-only")
            _require(
                row["duplicate_of_id"] is None
                and row["list_hidden_reason"] is None
                and sha256(row["sgf_content"].encode()).hexdigest() == member["sgf_sha256"]
                and full_operation_fingerprint(row["sgf_content"]) == group["operation_sha256"],
                "invalid dedup evidence",
            )
        _require(
            _metadata_compatible([m["album"] for m in members])
            and {_precise_date(m["album"]["date_played"]) for m in members} == {group["date"]}
            and group["date"],
            "invalid date or metadata evidence",
        )
    return manifest


def _lock(conn, ids):
    if conn.dialect.name == "postgresql":
        from katrain.web.kifu.name_batch import _ADVISORY_LOCK_KEY

        conn.execute(text("SET LOCAL lock_timeout = '15s'"))
        # Use the existing native publication lock ordering. Legacy imports are
        # protected by the same physical table locks even without advisory use.
        conn.exec_driver_sql("SELECT pg_advisory_xact_lock(%s)", (_ADVISORY_LOCK_KEY,))
        conn.exec_driver_sql("SELECT pg_advisory_xact_lock(%s)", (720220261003,))
        conn.exec_driver_sql(
            "LOCK TABLE kifu_albums, kifu_album_sources, kifu_sources, "
            "kifu_players, kifu_player_aliases, kifu_player_names, kifu_dedup_batches, kifu_dedup_changes "
            "IN SHARE ROW EXCLUSIVE MODE"
        )
    list(conn.execute(select(KifuAlbum.id).where(KifuAlbum.id.in_(ids)).order_by(KifuAlbum.id).with_for_update()))
    list(
        conn.execute(
            select(KifuAlbumSource.id)
            .where(KifuAlbumSource.album_id.in_(ids))
            .order_by(KifuAlbumSource.id)
            .with_for_update()
        )
    )


def _expected_after(group):
    members = {m["album"]["id"]: m for m in group["members"]}
    canonical = group["canonical_album_id"]
    links = [dict(link) for link in members[canonical]["source_links"]]
    keys = {(link["source_id"], link["origin_path"]) for link in links}
    for duplicate_id in group["duplicate_album_ids"]:
        for link in members[duplicate_id]["source_links"]:
            if (link["source_id"], link["origin_path"]) not in keys:
                links.append({**link, "match_method": "reviewed_same_game"})
                keys.add((link["source_id"], link["origin_path"]))
    result = {}
    for album_id, member in members.items():
        album = dict(member["album"])
        if album_id != canonical:
            album["duplicate_of_id"] = canonical
        result[album_id] = {
            "album": album,
            "source_links": sorted(
                links if album_id == canonical else member["source_links"],
                key=lambda link: (link["source_id"], link["origin_path"], link["match_method"]),
            ),
        }
    return result


def _check_images(conn, manifest, *, after=False):
    identities = _identities(conn)
    canonical_names = dict(conn.execute(select(KifuPlayer.id, KifuPlayer.canonical_name)).all())
    source_ids = [row["id"] for row in manifest["sources"]] if "scope" in manifest else None
    _require(_source_image(conn, source_ids) == manifest["sources"], "source registry preimage changed")
    for group in manifest["groups"]:
        if "scope" in manifest:
            _require(
                not conn.scalar(
                    select(func.count())
                    .select_from(KifuAlbum)
                    .where(KifuAlbum.duplicate_of_id.in_(group["duplicate_album_ids"]))
                ),
                "existing duplicate dependents prevent canonical chain",
            )
        rows = [m["album"] for m in group["members"]]
        _require(all(_sgf_identity_bound(row, identities) for row in rows), "raw SGF ordered identity binding changed")
        reviewed = _reviewed_yoda(rows, canonical_names)
        _require(group.get("reviewed_identity") == reviewed, "reviewed identity evidence changed")
        expected_ids = group["ordered_player_ids"]
        _require(
            all(
                [_identity(row, "black", identities), _identity(row, "white", identities)] == expected_ids
                for row in rows
            )
            or reviewed
            and reviewed["ordered_player_ids"] == expected_ids
            and _reviewed_identity_compatible(rows, expected_ids, identities),
            "approved ordered identity evidence changed",
        )
        expected = _expected_after(group) if after else {m["album"]["id"]: m for m in group["members"]}
        for original_member in group["members"]:
            _check_original_source_ids(conn, original_member)
        for album_id, member in expected.items():
            _require(
                _image(conn, album_id) == member["album"] and _links(conn, album_id) == member["source_links"],
                f'album {album_id} {"afterimage" if after else "preimage"} changed',
            )


def _journal_check(conn, batch, manifest, *, group=None, changes=None):
    groups = [group] if group else manifest["groups"]
    expected = {m["album"]["id"]: (m, _expected_after(g)[m["album"]["id"]]) for g in groups for m in g["members"]}
    query = select(KifuDedupChange.__table__).where(KifuDedupChange.batch_id == batch["id"])
    if group:
        query = query.where(KifuDedupChange.album_id.in_(expected))
    changes = list(conn.execute(query).mappings()) if changes is None else changes
    _require(
        len(changes) == len(expected) and {row["album_id"] for row in changes} == set(expected),
        "dedup journal membership changed",
    )
    for change in changes:
        _require(change["album_id"] in expected, "dedup journal owner changed")
        before, after = expected[change["album_id"]]
        _require(
            change["duplicate_of_id_before"] == before["album"]["duplicate_of_id"]
            and change["duplicate_of_id_after"] == after["album"]["duplicate_of_id"]
            and change["sgf_sha256_before"] == before["sgf_sha256"]
            and change["source_links_before"] == before["source_links"]
            and change["source_links_after"] == after["source_links"],
            "dedup journal evidence changed",
        )


def apply_dedup_manifest(conn, manifest, *, expected_sha256):
    validate_dedup_manifest(manifest)
    digest = dedup_manifest_sha256(manifest)
    _require(digest == expected_sha256, "dedup manifest hash mismatch")
    key = "reviewed-same-game:" + digest
    ids = [m["album"]["id"] for g in manifest["groups"] for m in g["members"]]
    _lock(conn, ids)
    previous = (
        conn.execute(select(KifuDedupBatch.__table__).where(KifuDedupBatch.batch_key == key)).mappings().one_or_none()
    )
    if previous:
        _require(
            previous["status"] == "complete"
            and previous["summary"] == {"manifest": manifest, "manifest_sha256": digest},
            "dedup immutable batch evidence changed",
        )
        _check_images(conn, manifest, after=True)
        _journal_check(conn, previous, manifest)
        return {"batch_key": key, "duplicates_hidden": manifest["summary"]["duplicates_to_hide"], "idempotent": True}
    _check_images(conn, manifest)
    # All validation completes before the first write; caller rolls back any DB error.
    batch_id = conn.execute(
        insert(KifuDedupBatch)
        .values(batch_key=key, status="running", summary={"manifest": manifest, "manifest_sha256": digest})
        .returning(KifuDedupBatch.id)
    ).scalar_one()
    for group in manifest["groups"]:
        after = _expected_after(group)
        for member in group["members"]:
            album_id = member["album"]["id"]
            image = after[album_id]
            old_keys = {(l["source_id"], l["origin_path"]) for l in member["source_links"]}
            for link in image["source_links"]:
                if (link["source_id"], link["origin_path"]) not in old_keys:
                    conn.execute(insert(KifuAlbumSource).values(album_id=album_id, **link))
            conn.execute(
                update(KifuAlbum)
                .where(KifuAlbum.id == album_id)
                .values(duplicate_of_id=image["album"]["duplicate_of_id"])
            )
            conn.execute(
                insert(KifuDedupChange).values(
                    batch_id=batch_id,
                    album_id=album_id,
                    duplicate_of_id_before=member["album"]["duplicate_of_id"],
                    duplicate_of_id_after=image["album"]["duplicate_of_id"],
                    source_links_before=member["source_links"],
                    source_links_after=image["source_links"],
                    sgf_sha256_before=member["sgf_sha256"],
                )
            )
    conn.execute(
        update(KifuDedupBatch)
        .where(KifuDedupBatch.id == batch_id)
        .values(status="complete", finished_at=datetime.now(timezone.utc))
    )
    return {"batch_key": key, "duplicates_hidden": manifest["summary"]["duplicates_to_hide"], "idempotent": False}


def undo_dedup_manifest(conn, manifest, *, expected_sha256):
    validate_dedup_manifest(manifest)
    digest = dedup_manifest_sha256(manifest)
    _require(digest == expected_sha256, "dedup manifest hash mismatch")
    _lock(conn, [m["album"]["id"] for g in manifest["groups"] for m in g["members"]])
    batch = (
        conn.execute(select(KifuDedupBatch.__table__).where(KifuDedupBatch.batch_key == "reviewed-same-game:" + digest))
        .mappings()
        .one_or_none()
    )
    _require(
        batch and batch["summary"] == {"manifest": manifest, "manifest_sha256": digest},
        "immutable dedup evidence missing",
    )
    if batch["status"] == "undone":
        _check_images(conn, manifest)
        return {"idempotent": True}
    _require(batch["status"] == "complete", "dedup batch is not complete")
    _check_images(conn, manifest, after=True)
    _journal_check(conn, batch, manifest)
    for group in manifest["groups"]:
        for member in group["members"]:
            album_id = member["album"]["id"]
            before = {(l["source_id"], l["origin_path"]) for l in member["source_links"]}
            for link in _expected_after(group)[album_id]["source_links"]:
                if (link["source_id"], link["origin_path"]) not in before:
                    conn.execute(
                        delete(KifuAlbumSource).where(
                            KifuAlbumSource.album_id == album_id,
                            KifuAlbumSource.source_id == link["source_id"],
                            KifuAlbumSource.origin_path == link["origin_path"],
                            KifuAlbumSource.match_method == "reviewed_same_game",
                        )
                    )
            conn.execute(
                update(KifuAlbum)
                .where(KifuAlbum.id == album_id)
                .values(duplicate_of_id=member["album"]["duplicate_of_id"])
            )
    conn.execute(
        update(KifuDedupBatch)
        .where(KifuDedupBatch.id == batch["id"])
        .values(status="undone", finished_at=datetime.now(timezone.utc))
    )
    return {"idempotent": False}


def verified_display_duplicate(conn, album_id):
    """Return bounded public proof only after verifying immutable journal ancestry."""
    album = _image(conn, album_id)
    _require(album is not None, "dedup journal album missing")
    canonical_id = album["duplicate_of_id"]
    if canonical_id is None:
        return None
    candidates = conn.execute(
        select(KifuDedupBatch.__table__)
        .join(KifuDedupChange, KifuDedupChange.batch_id == KifuDedupBatch.id)
        .where(
            KifuDedupChange.album_id == album_id,
            KifuDedupChange.duplicate_of_id_after == canonical_id,
            KifuDedupBatch.status == "complete",
        )
    ).mappings()
    for batch in candidates:
        summary = batch["summary"] or {}
        manifest = summary.get("manifest")
        if not isinstance(manifest, dict) or manifest.get("version") != VERSION:
            continue
        digest = dedup_manifest_sha256(manifest)
        _require(
            summary.get("manifest_sha256") == digest and batch["batch_key"] == "reviewed-same-game:" + digest,
            "dedup journal immutable manifest changed",
        )
        for group in manifest["groups"]:
            if album_id not in group["duplicate_album_ids"]:
                continue
            validate_dedup_manifest({**manifest, "groups": [group]})
            _journal_check(conn, batch, manifest, group=group)
            after = _expected_after(group)
            for original_member in group["members"]:
                _check_original_source_ids(conn, original_member)
            for owner_id, expected in after.items():
                current = _image(conn, owner_id)
                # Later exact imports may add sources. Original journal links must remain intact.
                _require(
                    current == expected["album"]
                    and all(link in _links(conn, owner_id) for link in expected["source_links"]),
                    "dedup journal current record or source evidence changed",
                )
            canonical = after[canonical_id]["album"]
            return {
                "version": "reviewed-same-game-v1",
                "album_id": album_id,
                "canonical_album_id": canonical_id,
                "sgf_sha256": sha256(album["sgf_content"].encode()).hexdigest(),
                "canonical_sgf_sha256": sha256(canonical["sgf_content"].encode()).hexdigest(),
                "operation_sha256": group["operation_sha256"],
                "batch_key": batch["batch_key"],
                "manifest_sha256": digest,
            }
    raise ValueError("verified same-game dedup journal missing")


def validate_existing_pointer(conn, album_id):
    """Retain exact-byte pointers; cross-SGF pointers require the reviewed journal."""
    album = _image(conn, album_id)
    _require(album is not None, "duplicate album missing")
    master = _image(conn, album["duplicate_of_id"]) if album["duplicate_of_id"] is not None else None
    _require(
        master is not None and master["duplicate_of_id"] is None and master["list_hidden_reason"] is None,
        "duplicate master is missing, chained or hidden",
    )
    if master["sgf_content"] != album["sgf_content"]:
        verified_display_duplicate(conn, album_id)
    return master["id"]


def retained_source_links(conn, album_id):
    """Project only journal-added aggregate links out of an original rank scope.

    Physical source IDs and all later unrelated links remain visible to the
    caller's preimage comparison. Nothing here updates provenance or visibility.
    """
    current = [
        dict(row)
        for row in conn.execute(
            select(KifuAlbumSource.__table__, KifuSource.source_key)
            .join(KifuSource, KifuSource.id == KifuAlbumSource.source_id)
            .where(KifuAlbumSource.album_id == album_id)
            .order_by(KifuAlbumSource.id)
        ).mappings()
    ]
    added = set()
    batches = conn.execute(
        select(KifuDedupBatch.__table__)
        .join(KifuDedupChange, KifuDedupChange.batch_id == KifuDedupBatch.id)
        .where(KifuDedupChange.album_id == album_id, KifuDedupBatch.status == "complete")
    ).mappings()
    for batch in batches:
        manifest = (batch["summary"] or {}).get("manifest", {})
        if manifest.get("version") != VERSION:
            continue
        for group in manifest["groups"]:
            if group["canonical_album_id"] != album_id:
                continue
            # The duplicate validator checks current canonical fields, complete
            # relevant journal entries, original links and immutable evidence.
            verified_display_duplicate(conn, group["duplicate_album_ids"][0])
            before = next(m["source_links"] for m in group["members"] if m["album"]["id"] == album_id)
            before_keys = {(l["source_id"], l["origin_path"], l["match_method"]) for l in before}
            added.update(
                (l["source_id"], l["origin_path"], l["match_method"])
                for l in _expected_after(group)[album_id]["source_links"]
                if (l["source_id"], l["origin_path"], l["match_method"]) not in before_keys
            )
    keys = ("id", "album_id", "source_id", "origin_path", "match_method", "source_key")
    return [
        {key: row[key] for key in keys}
        for row in current
        if (row["source_id"], row["origin_path"], row["match_method"]) not in added
    ]
