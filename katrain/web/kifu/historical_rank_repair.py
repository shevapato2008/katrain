"""Read-only historical census and finite, caller-owned CAS repair transactions.

Original SGFs, raw metadata, old snapshots' journals and publication receipts
remain untouched. An envelope is an audit of the corpus; each part is a separate
reviewed atomic operation. Never pass a multi-part envelope as one transaction.
"""

from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path

from sqlalchemy import select, text

from katrain.web.core import models_db as m
from katrain.web.kifu import historical_ranks as ranks, name_batch
from katrain.web.kifu.source_rank_normalization import (
    SNAPSHOT_VERSION as SOURCE_VERSION,
    digest,
    normalize_source_rank,
    require,
    snapshot_digest,
    trusted_source_link,
)

FORMAT = "kifu-historical-rank-repair-v1"
PART_FORMAT = "kifu-historical-rank-repair-part-v1"
CODE_VERSION = "historical-rank-repair-v1"
MAX_PART_CHANGES = 200
MAX_PART_BYTES = 4 * 1024 * 1024
TARGET_BODY_BYTES = ranks.MAX_BODY_BYTES // 2
REGISTRY = {"version": ranks.POLICY_VERSION, "repair": CODE_VERSION, "rank_only": True}
_PART_FIELDS = {
    "format",
    "policy_version",
    "code_version",
    "code_sha256",
    "database_identity",
    "matched_at",
    "changes",
    "basis_bindings",
}
_CHANGE_FIELDS = {"album_id", "side", "album_before", "snapshot_before", "snapshot_after", "basis_binding"}


def manifest_sha256(manifest):
    return digest(manifest)


def _code_sha256():
    return digest([sha256(Path(path).read_bytes()).hexdigest() for path in (__file__, ranks.__file__)])


def _json_image(row):
    return {key: value.isoformat() if isinstance(value, (datetime, date)) else value for key, value in row.items()}


def _database_identity(conn):
    if conn.dialect.name == "postgresql":
        row = (
            conn.execute(
                text(
                    "SELECT current_database() AS database, current_schema() AS schema, "
                    "(SELECT oid FROM pg_database WHERE datname=current_database()) AS database_oid, "
                    "inet_server_addr()::text AS address, inet_server_port() AS port"
                )
            )
            .mappings()
            .one()
        )
        return {
            "dialect": "postgresql",
            "database": row["database"],
            "schema": row["schema"],
            "database_oid": row["database_oid"],
            "server_sha256": digest([row["address"], row["port"], conn.engine.url.host, conn.engine.url.port]),
        }
    require(conn.dialect.name == "sqlite", "historical rank repair database unsupported")
    # No URL, credentials or local path is placed in the artifact or logs.
    return {"dialect": "sqlite", "database_sha256": digest(str(conn.engine.url.database))}


def _links(conn, album_ids, *, lock=False):
    t, s = m.KifuAlbumSource.__table__, m.KifuSource.__table__
    query = (
        select(t, s.c.source_key).join(s, s.c.id == t.c.source_id).where(t.c.album_id.in_(album_ids)).order_by(t.c.id)
    )
    if lock:
        query = query.with_for_update(of=t)
    result = defaultdict(list)
    for row in conn.execute(query).mappings():
        result[row["album_id"]].append(_json_image(row))
    return result


def _snapshots(conn, album_ids, *, lock=False):
    t = m.KifuAlbumRankSnapshot.__table__
    query = select(t).where(t.c.album_id.in_(album_ids)).order_by(t.c.album_id, t.c.side)
    if lock:
        query = query.with_for_update()
    return {(row["album_id"], row["side"]): _json_image(row) for row in conn.execute(query).mappings()}


def _album_image(album, links):
    result = _json_image({key: value for key, value in album.items() if key not in {"sgf_content", "sgf_bytes"}})
    result["sgf_sha256"] = sha256(album["sgf_content"].encode()).hexdigest()
    result["source_links"] = deepcopy(links)
    return result


def _public(album):
    return album.get("duplicate_of_id") is None and album.get("list_hidden_reason") is None


def _replaceable(before):
    if before is None:
        return True
    snapshot = before.get("snapshot")
    return (
        isinstance(snapshot, dict)
        and snapshot.get("version") in {SOURCE_VERSION, "kifu-rank-snapshot-v1"}
        and before.get("snapshot_sha256") == snapshot.get("content_sha256") == snapshot_digest(snapshot)
        and (
            before.get("publication_key", "").startswith("source-rank:")
            or snapshot.get("version") == "kifu-rank-snapshot-v1"
        )
    )


def _semantic(snapshot):
    return tuple(snapshot.get(key) for key in ("display_rank", "rank_value", "rank_system"))


def _legacy_afterimage_valid(conn, before):
    if before is None:
        return True
    b, j = m.KifuNameBatch.__table__, m.KifuNameChange.__table__
    row = (
        conn.execute(
            select(
                b.c.bundle_sha256,
                b.c.status,
                b.c.reviewed_artifact["publication_format"].as_string().label("publication_format"),
                b.c.reviewed_artifact["publication_key"].as_string().label("publication_key"),
                j.c.after_image,
            )
            .join(j, j.c.batch_id == b.c.id)
            .where(
                b.c.id == before["native_batch_id"],
                j.c.target_table == m.KifuAlbumRankSnapshot.__tablename__,
                j.c.target_row_id == before["id"],
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None or row["status"] != "applied" or row["after_image"] != before:
        return False
    if before["snapshot"]["version"] == SOURCE_VERSION:
        return before["publication_key"] == "source-rank:" + row["bundle_sha256"]
    return (
        row["publication_format"] == "kifu-incremental-manifest-v2"
        and row["publication_key"] == before["publication_key"]
    )


def _needs_change(before, decision, raw):
    if decision["origin"] == "unknown" or decision["rank_value"] is None:
        return False
    if before:
        return _semantic(before["snapshot"]) != _semantic(decision)
    return decision["origin"] in {"historical_type", "historical_prior"} or decision["display_rank"] != raw


def _new_part(common, changes):
    part = {
        "format": PART_FORMAT,
        **common,
        "changes": changes,
        "basis_bindings": [c["basis_binding"] for c in changes],
    }
    require(
        len(changes) <= MAX_PART_CHANGES and len({c["album_id"] for c in changes}) <= ranks.MAX_INCOMING_GAMES,
        "historical rank part target limit exceeded",
    )
    require(ranks._json_size(part) <= MAX_PART_BYTES, "historical rank part byte limit exceeded")
    return part


def prepare_manifest(conn, *, matched_at, album_ids=None):
    """Census every database slot, streaming bodies only for eligible candidates.

    album_ids limits writes, never the all-slot census. Each emitted part has at
    most 100 target games/200 slots; original evidence is resolved from SQL only.
    Refused historical inference may still have an independently meaningful
    source normalization, which is counted separately from qualified history.
    """
    matched_at = ranks._utc(matched_at)
    if album_ids is not None:
        require(
            isinstance(album_ids, (list, tuple, set)) and all(type(x) is int and x > 0 for x in album_ids),
            "historical rank album scope invalid",
        )
        album_ids = set(album_ids)
    common = {
        "policy_version": ranks.POLICY_VERSION,
        "code_version": CODE_VERSION,
        "code_sha256": _code_sha256(),
        "database_identity": _database_identity(conn),
        "matched_at": matched_at,
    }
    census = Counter(
        albums=0,
        slots=0,
        source_links=0,
        excluded_slots=0,
        out_of_scope_slots=0,
        existing_snapshot_slots=0,
        existing_v3_slots=0,
        unchanged_source_slots=0,
        qualified_missing_slots=0,
        qualified_refinable_slots=0,
        source_normalization_slots=0,
        missing_raw_slots=0,
        generic_dan_slots=0,
        changed_slots=0,
    )
    refusals, sources, systems, parts = Counter(), Counter(), Counter(), []
    inventory, pending, pending_bytes = sha256(), [], 0
    pending_resource = ranks.EvidenceBudget()

    def flush():
        nonlocal pending, pending_bytes, pending_resource
        if not pending:
            return
        try:
            decisions = ranks.prepare_rank_decisions(conn, pending, matched_at=matched_at, resource=pending_resource)[
                "decisions"
            ]
        except ValueError:
            # An invalid original refuses that target; it does not abort the
            # complete census or weaken the remaining targets' qualification.
            decisions = []
            for target in pending:
                try:
                    decisions.append(
                        ranks.prepare_rank_decisions(conn, [target], matched_at=matched_at, resource=pending_resource)[
                            "decisions"
                        ][0]
                    )
                except ValueError:
                    decisions.append(None)
        changes = []
        for target, decision in zip(pending, decisions):
            album, side = target["album"], target["side"]
            if decision is None:
                refusals["invalid_original_binding"] += 1
                continue
            if decision["refusal_reason"]:
                refusals[decision["refusal_reason"]] += 1
            before = target["snapshot_before"]
            if not _needs_change(before, decision, album.get(f"{side}_rank") or ""):
                census["unchanged_source_slots"] += int(decision["origin"] == "source")
                continue
            try:
                binding = ranks.bind_rank_decision(conn, target, decision, lock=False, resource=pending_resource)
            except ValueError:
                refusals["invalid_local_basis_binding"] += 1
                continue
            changes.append(
                {
                    "album_id": album["id"],
                    "side": side,
                    "album_before": _album_image(album, target["source_links"]),
                    "snapshot_before": deepcopy(before),
                    "snapshot_after": decision,
                    "basis_binding": binding,
                }
            )
            census["changed_slots"] += 1
            census[
                {
                    "historical_prior": "qualified_missing_slots",
                    "historical_type": "qualified_refinable_slots",
                    "source": "source_normalization_slots",
                }[decision["origin"]]
            ] += 1
        if changes:
            parts.append(_new_part(common, changes))
        pending, pending_bytes, pending_resource = [], 0, ranks.EvidenceBudget()

    a, last_id = m.KifuAlbum.__table__, None
    columns = [col for col in a.c if col.name != "sgf_content"]
    while True:
        query = select(*columns, ranks._body_length(conn, a.c.sgf_content).label("sgf_bytes"))
        if last_id is not None:
            query = query.where(a.c.id > last_id)
        rows = list(conn.execute(query.order_by(a.c.id).limit(ranks.MAX_INCOMING_GAMES)).mappings())
        if not rows:
            break
        ids = [row["id"] for row in rows]
        links, snapshots = _links(conn, ids), _snapshots(conn, ids)
        for row in rows:
            album = dict(row)
            last_id = album["id"]
            census["albums"] += 1
            census["source_links"] += len(links[last_id])
            inventory.update((digest({"album": _json_image(album), "links": links[last_id]}) + "\n").encode())
            source = trusted_source_link(album, links[last_id])
            family = source["source_key"] if source else "unknown_or_ambiguous"
            sources[family] += 1
            needed = []
            for side in ("black", "white"):
                census["slots"] += 1
                before = snapshots.get((last_id, side))
                raw = album.get(f"{side}_rank") or ""
                grade = normalize_source_rank(raw, source_key=family)
                census["missing_raw_slots"] += int(not raw)
                census["generic_dan_slots"] += int(bool(grade and grade["rank_system"] == "dan_unspecified"))
                systems[family + ":" + (grade["rank_system"] if grade else "missing" if not raw else "unparsed")] += 1
                census["existing_snapshot_slots"] += int(before is not None)
                if not _public(album):
                    census["excluded_slots"] += 1
                    continue
                if album_ids is not None and last_id not in album_ids:
                    census["out_of_scope_slots"] += 1
                    continue
                if (
                    before
                    and isinstance(before["snapshot"], dict)
                    and before["snapshot"].get("version") == ranks.SNAPSHOT_VERSION
                ):
                    census["existing_v3_slots"] += 1
                    continue
                if not _replaceable(before):
                    refusals["existing_correction_preserved"] += 1
                    continue
                if not _legacy_afterimage_valid(conn, before):
                    refusals["invalid_legacy_afterimage"] += 1
                    continue
                if source is None:
                    refusals["untrusted_source"] += 1
                    continue
                if (
                    before is None
                    and grade
                    and grade["rank_system"] != "dan_unspecified"
                    and grade["display_rank"] == raw
                ):
                    census["unchanged_source_slots"] += 1
                    continue
                needed.append((side, before))
            if not needed:
                continue
            cost = album["sgf_bytes"] * len(needed)
            if not 0 < album["sgf_bytes"] <= ranks.MAX_SGF_BYTES:
                refusals["resource_deferred"] += len(needed)
                continue
            if pending and (
                len(pending) + len(needed) > MAX_PART_CHANGES
                or len({x["album"]["id"] for x in pending} | {last_id}) > ranks.MAX_INCOMING_GAMES
                or pending_bytes + cost > TARGET_BODY_BYTES
            ):
                flush()
            pending_resource.reserve(album["sgf_bytes"])
            album["sgf_content"] = conn.execute(select(a.c.sgf_content).where(a.c.id == last_id)).scalar_one()
            pending_resource.remember_body(album["sgf_content"], album_id=last_id, reserved=True)
            for side, before in needed:
                pending.append(
                    {"album": album, "side": side, "source_links": links[last_id], "snapshot_before": before}
                )
            pending_bytes += cost
        # Resolve a bounded chunk before fetching more album bodies.
        flush()
    return {
        "format": FORMAT,
        **common,
        "scope_album_ids": sorted(album_ids) if album_ids is not None else None,
        "inventory_sha256": inventory.hexdigest(),
        "census": dict(census),
        "source_albums": dict(sources),
        "systems": dict(systems),
        "refusals": dict(refusals),
        "parts": parts,
        "part_sha256": [manifest_sha256(part) for part in parts],
    }


def validate_manifest(manifest):
    require(isinstance(manifest, dict) and manifest.get("format") == FORMAT, "historical rank manifest invalid")
    require(
        isinstance(manifest.get("parts"), list)
        and manifest.get("part_sha256") == [digest(p) for p in manifest["parts"]],
        "historical rank part SHA binding invalid",
    )
    seen = set()
    for part in manifest["parts"]:
        _validate_part(part)
        require(
            all(part[key] == manifest[key] for key in _PART_FIELDS - {"format", "changes", "basis_bindings"}),
            "historical rank part envelope binding invalid",
        )
        for change in part["changes"]:
            key = (change["album_id"], change["side"])
            require(key not in seen, "historical rank duplicate target")
            seen.add(key)
    return manifest


def _validate_part(part):
    require(
        isinstance(part, dict) and set(part) == _PART_FIELDS and part["format"] == PART_FORMAT,
        "historical rank part shape invalid",
    )
    require(
        part["policy_version"] == ranks.POLICY_VERSION
        and part["code_version"] == CODE_VERSION
        and part["code_sha256"] == _code_sha256(),
        "historical rank policy/code binding changed",
    )
    require(
        isinstance(part["changes"], list) and 0 < len(part["changes"]) <= MAX_PART_CHANGES,
        "historical rank part changes invalid",
    )
    require(
        len({c["album_id"] for c in part["changes"]}) <= ranks.MAX_INCOMING_GAMES
        and ranks._json_size(part) <= MAX_PART_BYTES,
        "historical rank part resource limit",
    )
    require(
        part["basis_bindings"] == [c["basis_binding"] for c in part["changes"]], "historical rank basis binding changed"
    )
    seen = set()
    for change in part["changes"]:
        require(
            set(change) == _CHANGE_FIELDS and change["side"] in {"black", "white"},
            "historical rank change shape invalid",
        )
        key = (change["album_id"], change["side"])
        require(key not in seen, "historical rank duplicate target")
        seen.add(key)
        before, decision, binding = change["album_before"], change["snapshot_after"], change["basis_binding"]
        ranks.validate_rank_decision(decision)
        require(decision["matched_at"] == part["matched_at"], "historical rank freeze timestamp changed")
        require(
            _public(before) and before["id"] == change["album_id"] and _replaceable(change["snapshot_before"]),
            "historical rank target scope invalid",
        )
        require(
            _needs_change(change["snapshot_before"], decision, before.get(f"{change['side']}_rank") or ""),
            "historical rank change is not meaningful",
        )
        require(
            binding.get("content_sha256") == snapshot_digest(binding)
            and binding["target"]["album_id"] == change["album_id"]
            and binding["target"]["side"] == change["side"]
            and binding["target"]["snapshot_sha256"] == decision["content_sha256"],
            "historical rank local binding invalid",
        )
    return part


def _selected_part(manifest, expected_sha256):
    require(digest(manifest) == expected_sha256, "historical rank manifest SHA mismatch")
    if manifest.get("format") == FORMAT:
        validate_manifest(manifest)
        require(len(manifest["parts"]) == 1, "historical rank transaction requires one finite part")
        return manifest["parts"][0]
    return _validate_part(manifest)


def _lock_writer(conn):
    require(
        conn.in_transaction() and conn.get_execution_options().get("isolation_level") != "AUTOCOMMIT",
        "historical rank caller transaction required",
    )
    if conn.dialect.name == "postgresql":
        require(conn.get_isolation_level() == "READ COMMITTED", "historical rank repair requires READ COMMITTED")
        conn.exec_driver_sql("SET LOCAL lock_timeout = '15s'")
        for key in (name_batch._ADVISORY_LOCK_KEY, 720220261003):
            conn.exec_driver_sql("SELECT pg_advisory_xact_lock(%s)", (key,))
        conn.exec_driver_sql(
            "LOCK TABLE kifu_albums, kifu_album_sources, kifu_sources, kifu_players, "
            "kifu_player_aliases, kifu_player_names, kifu_album_rank_snapshots, "
            "kifu_name_source_registry, kifu_name_batches, kifu_name_changes IN SHARE ROW EXCLUSIVE MODE"
        )
    elif conn.dialect.name == "sqlite" and not conn.connection.driver_connection.in_transaction:
        # A first SAVEPOINT otherwise becomes SQLite's real outer transaction.
        conn.exec_driver_sql("BEGIN IMMEDIATE")


def _targets_preflight(conn, part, *, initial):
    resource = ranks.EvidenceBudget()
    ids = sorted({c["album_id"] for c in part["changes"]})
    table = m.KifuAlbum.__table__
    lengths = dict(
        conn.execute(
            select(table.c.id, ranks._body_length(conn, table.c.sgf_content))
            .where(table.c.id.in_(ids))
            .order_by(table.c.id)
            .with_for_update()
        ).all()
    )
    require(
        len(lengths) == len(ids)
        and all(0 < value <= ranks.MAX_SGF_BYTES for value in lengths.values())
        and sum(lengths.values()) <= ranks.MAX_BODY_BYTES,
        "historical rank target body preimage/resource changed",
    )
    resource.reserve(sum(lengths.values()))
    albums = {
        r["id"]: dict(r)
        for r in conn.execute(
            select(table).where(table.c.id.in_(ids)).order_by(table.c.id).with_for_update()
        ).mappings()
    }
    for ident, album in albums.items():
        resource.remember_body(album["sgf_content"], album_id=ident, reserved=True)
    links, snapshots = _links(conn, ids, lock=True), _snapshots(conn, ids, lock=True)
    targets = []
    for change in part["changes"]:
        ident, side = change["album_id"], change["side"]
        album = albums.get(ident)
        require(
            album is not None and _album_image(album, links[ident]) == change["album_before"],
            "historical rank album/source complete beforeimage changed",
        )
        if initial:
            require(
                snapshots.get((ident, side)) == change["snapshot_before"], "historical rank snapshot preimage changed"
            )
            require(
                _legacy_afterimage_valid(conn, change["snapshot_before"]),
                "historical rank legacy journal preimage changed",
            )
        target = {"album": album, "side": side, "source_links": links[ident]}
        require(
            ranks.bind_rank_decision(conn, target, change["snapshot_after"], resource=resource)
            == change["basis_binding"],
            "historical rank exact target/basis binding changed",
        )
        targets.append(target)
    if initial:
        ranks.verify_initial_rank_decisions(
            conn, targets, [c["snapshot_after"] for c in part["changes"]], resource=resource
        )
    return targets


def _batch(conn, part_sha):
    return (
        conn.execute(
            select(m.KifuNameBatch.__table__).where(m.KifuNameBatch.bundle_sha256 == part_sha).with_for_update()
        )
        .mappings()
        .one_or_none()
    )


def _journal_preflight(conn, batch, part, *, current=True):
    require(batch["reviewed_artifact"] == _artifact(part), "historical rank applied artifact changed")
    changes = list(
        conn.execute(
            select(m.KifuNameChange.__table__)
            .where(m.KifuNameChange.batch_id == batch["id"])
            .order_by(m.KifuNameChange.sequence)
        ).mappings()
    )
    require(len(changes) == len(part["changes"]), "historical rank journal count changed")
    for sequence, (row, frozen) in enumerate(zip(changes, part["changes"]), 1):
        after = row["after_image"]
        require(
            row["sequence"] == sequence
            and row["target_table"] == m.KifuAlbumRankSnapshot.__tablename__
            and row["before_image"] == frozen["snapshot_before"]
            and isinstance(after, dict)
            and after["id"] == row["target_row_id"]
            and after["album_id"] == frozen["album_id"]
            and after["side"] == frozen["side"]
            and after["snapshot"] == frozen["snapshot_after"]
            and after["snapshot_sha256"] == frozen["snapshot_after"]["content_sha256"]
            and after["rank_fact_id"] is None
            and after["native_batch_id"] == batch["id"]
            and after["publication_key"] == "historical-rank:" + batch["bundle_sha256"],
            "historical rank journal binding changed",
        )
        if frozen["snapshot_before"]:
            require(after["id"] == frozen["snapshot_before"]["id"], "historical rank journal row changed")
        if current:
            require(
                name_batch._image(conn, m.KifuAlbumRankSnapshot.__table__, row["target_row_id"]) == after,
                "historical rank current afterimage/journal changed",
            )
    return changes


def _artifact(part):
    return {"format": FORMAT, "manifest_sha256": digest(part), "part": part, "basis_bindings": part["basis_bindings"]}


def apply_in_transaction(conn, manifest, *, expected_sha256):
    """Apply exactly one reviewed part; caller owns transaction and commit."""
    part = _selected_part(manifest, expected_sha256)
    _lock_writer(conn)
    require(_database_identity(conn) == part["database_identity"], "historical rank database identity changed")
    part_sha = digest(part)
    with conn.begin_nested():
        batch = _batch(conn, part_sha)
        if batch:
            require(batch["status"] == "applied", "historical rank batch already undone or changed")
            _journal_preflight(conn, batch, part)
            _targets_preflight(conn, part, initial=False)
            return {
                "status": "already_applied",
                "batch_id": batch["id"],
                "changes": len(part["changes"]),
                "part_sha256": part_sha,
            }
        _targets_preflight(conn, part, initial=True)
        registry = m.KifuNameSourceRegistry.__table__
        registry_sha = digest(REGISTRY)
        registry_id = conn.execute(
            select(registry.c.id).where(registry.c.version == ranks.POLICY_VERSION, registry.c.sha256 == registry_sha)
        ).scalar_one_or_none()
        if registry_id is None:
            registry_id = conn.execute(
                registry.insert().values(version=ranks.POLICY_VERSION, sha256=registry_sha, registry=REGISTRY)
            ).inserted_primary_key[0]
        batch_id = conn.execute(
            m.KifuNameBatch.__table__.insert().values(
                bundle_sha256=part_sha,
                inventory_sha256=digest([c["album_before"] for c in part["changes"]]),
                source_registry_id=registry_id,
                reviewed_artifact=_artifact(part),
                status="applied",
                applied_at=datetime.now(timezone.utc),
            )
        ).inserted_primary_key[0]
        for sequence, change in enumerate(part["changes"], 1):
            before, snapshot = change["snapshot_before"], change["snapshot_after"]
            values = {
                "album_id": change["album_id"],
                "side": change["side"],
                "rank_fact_id": None,
                "snapshot": snapshot,
                "snapshot_sha256": snapshot["content_sha256"],
                "publication_key": "historical-rank:" + part_sha,
                "native_batch_id": batch_id,
            }
            if before is None:
                row_id, after = name_batch._insert(conn, m.KifuAlbumRankSnapshot, values)
            else:
                row_id = before["id"]
                conn.execute(
                    m.KifuAlbumRankSnapshot.__table__.update()
                    .where(m.KifuAlbumRankSnapshot.id == row_id)
                    .values(**values)
                )
                after = name_batch._image(conn, m.KifuAlbumRankSnapshot.__table__, row_id)
            name_batch._record_change(conn, batch_id, sequence, m.KifuAlbumRankSnapshot, row_id, before, after)
        return {"status": "applied", "batch_id": batch_id, "changes": len(part["changes"]), "part_sha256": part_sha}


def undo_in_transaction(conn, manifest, *, expected_sha256):
    """Restore exact old rows, or remove only rows inserted by this journal."""
    part = _selected_part(manifest, expected_sha256)
    _lock_writer(conn)
    require(_database_identity(conn) == part["database_identity"], "historical rank database identity changed")
    with conn.begin_nested():
        batch = _batch(conn, digest(part))
        require(batch is not None, "historical rank batch missing")
        changes = _journal_preflight(conn, batch, part, current=batch["status"] != "undone")
        if batch["status"] == "undone":
            # Even idempotent undo must not claim restoration after later drift.
            for change in changes:
                require(
                    name_batch._image(conn, m.KifuAlbumRankSnapshot.__table__, change["target_row_id"])
                    == change["before_image"],
                    "historical rank undone beforeimage changed",
                )
            return {"status": "already_undone", "batch_id": batch["id"], "changes": 0, "part_sha256": digest(part)}
        require(batch["status"] == "applied", "historical rank batch status changed")
        _targets_preflight(conn, part, initial=False)
        table = m.KifuAlbumRankSnapshot.__table__
        for change in reversed(changes):
            if change["before_image"] is None:
                conn.execute(table.delete().where(table.c.id == change["target_row_id"]))
            else:
                conn.execute(
                    table.update()
                    .where(table.c.id == change["target_row_id"])
                    .values(**name_batch._values_for_table(table, change["before_image"]))
                )
        conn.execute(
            m.KifuNameBatch.__table__.update().where(m.KifuNameBatch.id == batch["id"]).values(status="undone")
        )
        return {"status": "undone", "batch_id": batch["id"], "changes": len(changes), "part_sha256": digest(part)}
