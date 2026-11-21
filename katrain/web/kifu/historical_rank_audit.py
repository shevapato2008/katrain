"""Requalify protected v3 rank slots from original evidence without changing them."""

from collections import Counter, defaultdict

from sqlalchemy import and_, select
from sqlalchemy.exc import DBAPIError

from katrain.kifu_ingest.catalog import _RankPublicationProof, _cached_canonical_sha, _check_rank_dispositions
from katrain.kifu_ingest.ranks import FORMAT_V2
from katrain.web.core import models_db as m
from katrain.web.kifu import historical_rank_repair as repair, historical_ranks as ranks
from katrain.web.kifu.source_rank_normalization import digest, require

FORMAT = "kifu-historical-rank-v3-audit-v1"
_SNAPSHOT = m.KifuAlbumRankSnapshot.__table__


def _resource_failure(exc):
    if isinstance(exc, DBAPIError):
        if (getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)) != "57014":
            raise exc
        return True
    return isinstance(exc, ranks._Deferred) or any(tag in str(exc) for tag in ("resource limit", "budget exceeded"))


def _slot(items, album_id, side):
    require(isinstance(items, list) and len(items) <= repair.MAX_PART_CHANGES, "invalid frozen slot index")
    matching = [item for item in items if (item.get("album_id"), item.get("side")) == (album_id, side)]
    require(len(matching) == 1, "missing or ambiguous frozen slot")
    return matching[0]


def _native_membership(proof, artifact, batch_id, batch_sha):
    """Verify the bounded frozen indexes once for each native owning batch."""
    receipt, guard = artifact["receipt"], artifact["undo_guard"]
    manifest, sources = artifact["logical_manifest"], artifact["sources"]
    games, results = manifest["games"], receipt["games"]
    require(
        all(
            isinstance(items, list) and 0 < len(items) <= ranks.MAX_INCOMING_GAMES
            for items in (games, results, sources)
        ),
        "invalid native frozen game membership",
    )
    receipt_sha, sources_sha = digest(receipt), digest(sources)
    require(
        receipt.get("status") == "applied"
        and receipt.get("batch_id") == batch_id
        and receipt.get("manifest_sha256") == batch_sha
        and guard.get("receipt_sha256") == receipt_sha
        and guard.get("sources_sha256") == sources_sha
        and manifest.get("format") == FORMAT_V2
        and manifest.get("publication_key") == artifact["publication_key"],
        "frozen rank native receipt changed",
    )

    def index(items):
        indexed = {(item["source_key"], item["source_item_id"]): item for item in items}
        require(len(indexed) == len(items), "frozen native source membership has duplicates")
        return indexed

    by_game, by_result, by_source = index(games), index(results), index(sources)
    require(
        by_game.keys() == by_result.keys() == by_source.keys()
        and all(
            by_source[key]["album_id"] == by_result[key]["album_id"]
            and all(by_source[key][field] == game[field] for field in ("origin_path", "raw_sha256", "sgf_sha256"))
            for key, game in by_game.items()
        ),
        "frozen native source membership changed",
    )
    dispositions = artifact.get("rank_dispositions")
    require(
        dispositions is None or isinstance(dispositions, list) and len(dispositions) <= repair.MAX_PART_CHANGES,
        "native rank dispositions exceed resource limit",
    )
    dispositions = _check_rank_dispositions(
        proof.conn, manifest, artifact, resource=proof.resource, check_current=False
    )
    by_slot = {
        (item["outcome"]["source_key"], item["outcome"]["source_item_id"], item["outcome"]["side"]): item
        for item in dispositions or ()
    }
    return receipt_sha, sources_sha, by_game, by_source, by_slot


def _native_slot(proof, artifact, row, record, batch_sha):
    require(
        artifact.get("publication_format") == FORMAT_V2 and artifact.get("publication_key") == row["publication_key"],
        "invalid native frozen rank authority",
    )
    batch_id, album_id, side = row["native_batch_id"], row["album_id"], row["side"]
    if batch_id not in proof.parts:
        proof.parts[batch_id] = _native_membership(proof, artifact, batch_id, batch_sha)
    receipt_sha, sources_sha, games, sources, dispositions = proof.parts[batch_id]
    record["publication"].update(receipt_sha256=receipt_sha, sources_sha256=sources_sha)
    frozen = row["snapshot"]
    ref = frozen["source_ref"]
    original_keys = [
        key for key, game in games.items() if key[0] == ref["source_key"] and game["origin_path"] == ref["origin_path"]
    ]
    require(len(original_keys) == 1, "frozen native original source is ambiguous")
    key = original_keys[0]
    require(
        games[key]["rank_snapshots"][side] == frozen
        and sources[key]["album_id"] == album_id
        and sources[key]["album_sgf_sha256"] == sources[key]["sgf_sha256"] == ref["sgf_sha256"],
        "frozen rank native source slot changed",
    )
    require(
        _slot(artifact["rank_bindings"], album_id, side)
        == {
            "album_id": album_id,
            "side": side,
            "snapshot_id": row["id"],
            "snapshot_sha256": row["snapshot_sha256"],
            "rank_fact_id": None,
            "publication_key": row["publication_key"],
            "native_batch_id": batch_id,
        },
        "frozen rank native receipt slot changed",
    )
    return dispositions[(*key, side)] if artifact.get("rank_dispositions") is not None else None


def _frozen_authority(proof, row, record, sgf_content, canonical_hashes):
    """Verify the exact current slot's journal and stored local proof."""
    frozen = row["snapshot"]
    ranks.validate_rank_decision(frozen)
    require(row["snapshot_sha256"] == frozen["content_sha256"] and row["rank_fact_id"] is None, "invalid frozen rank")
    batch_id = row["native_batch_id"]
    album_id, side = row["album_id"], row["side"]
    batch = proof.batch(batch_id)
    require(batch is not None and batch["status"] == "applied", "frozen rank batch is not applied")
    artifact, batch_sha = batch["reviewed_artifact"], batch["bundle_sha256"]
    require(artifact.get("manifest_sha256") == batch_sha, "frozen rank batch hash changed")
    record["publication"]["manifest_sha256"] = batch_sha
    journal = proof.journal(batch_id, row["id"])
    require(journal["after_image"] == row, "frozen rank journal changed")

    artifact_format = artifact.get("format")
    disposition = None
    if artifact_format == repair.FORMAT:
        if batch_id not in proof.parts:
            part = repair._validate_part(artifact["part"])
            require(digest(part) == batch_sha and repair._artifact(part) == artifact, "historical repair part changed")
            proof.parts[batch_id] = part
        part = proof.parts[batch_id]
        change = _slot(part["changes"], album_id, side)
        require(
            row["publication_key"] == "historical-rank:" + batch_sha
            and change["snapshot_after"] == frozen
            and journal["before_image"] == change["snapshot_before"]
            and journal["sequence"] == part["changes"].index(change) + 1,
            "historical repair journal changed",
        )
    elif artifact_format == "kifu-numadate-canonical-correction-v1":
        from katrain.web.kifu.numadate_canonical_correction import verify_correction

        if batch_id not in proof.parts:
            proof.parts[batch_id] = verify_correction(proof.conn, batch_id, resource=proof.resource)
        require(row["id"] in proof.parts[batch_id]["rows"], "canonical correction slot changed")
    else:
        disposition = _native_slot(proof, artifact, row, record, batch_sha)

    bindings = artifact["basis_bindings"]
    require(isinstance(bindings, list) and len(bindings) <= repair.MAX_PART_CHANGES, "invalid frozen basis index")
    expected = [
        binding
        for binding in bindings
        if (binding["target"]["album_id"], binding["target"]["side"]) == (album_id, side)
    ]
    require(len(expected) == 1, "missing or ambiguous frozen local basis")
    live = ranks.bind_rank_decision(
        proof.conn, {"album": {"id": album_id}, "side": side}, frozen, lock=False, resource=proof.resource
    )
    require(live == expected[0], "frozen rank local basis changed")
    if disposition is not None:
        target, ref = live["target"], live["target"]["source_ref"]
        outcome = disposition["outcome"]
        canonical_sha = _cached_canonical_sha(sgf_content, canonical_hashes)
        require(
            outcome["status"] == "applied"
            and outcome["retained_snapshot"] is None
            and outcome["original_source_ref"] == ref
            and canonical_sha is not None
            and outcome["original_canonical_sgf_sha256"] == canonical_sha
            and disposition["retained_row"] is None
            and disposition["source_binding"]
            == {
                **{key: target[key] for key in ("album_id", "source_link_id", "source_id", "player_id")},
                **{key: ref[key] for key in ("source_key", "sgf_sha256", "slot")},
                "source_path": ref["origin_path"],
                "player_ref": frozen["player_ref"],
            },
            "frozen native rank disposition local source changed",
        )
    return live


def _decision_record(snapshot, *, binding=None):
    return {
        **{
            key: snapshot[key]
            for key in (
                "display_rank",
                "rank_value",
                "rank_system",
                "origin",
                "target_date",
                "player_ref",
                "source_ref",
                "basis",
                "qualification",
                "refusal_reason",
            )
        },
        "snapshot_sha256": snapshot["content_sha256"],
        **({"basis_binding": binding} if binding is not None else {}),
    }


def _status(record, status, reason=None):
    record.update(status=status, reason=reason)
    return record


def _failure(record, exc, reason):
    if _resource_failure(exc):
        return _status(record, "resource_deferred", "resource_deferred")
    return _status(record, "integrity_failure", reason)


def _audit_group(conn, albums, heads, matched_at):
    resource = ranks.EvidenceBudget()
    proof = _RankPublicationProof(conn, resource, lock=False)
    rows, pending = [], []
    canonical_hashes = {}
    link_error = None
    try:
        with ranks._bounded_queries(conn):
            links_by_album = ranks._links(conn, [album_id for album_id, album in albums if album is not None])
    except (ValueError, DBAPIError) as exc:
        link_error = exc
        links_by_album = {}
    for album_id, album in albums:
        records = [
            {
                "album_id": album_id,
                "side": head["side"],
                "snapshot_id": head["id"],
                "stored": {"snapshot_sha256": head["snapshot_sha256"]},
                "publication": {
                    "publication_key": head["publication_key"],
                    "native_batch_id": head["native_batch_id"],
                },
            }
            for head in heads[album_id]
        ]
        rows.extend(records)
        if album is None:
            for record in records:
                _status(record, "integrity_failure", "missing_original_album")
            continue
        for record in records:
            record["album_visibility"] = {
                "duplicate_of_id": album["duplicate_of_id"],
                "list_hidden_reason": album["list_hidden_reason"],
            }
        if link_error is not None:
            for record in records:
                _failure(record, link_error, "invalid_original_source")
            continue
        links = links_by_album.get(album_id, [])
        try:
            album = {**album, "sgf_content": ranks.load_rank_body(conn, album, resource=resource)}
        except (ValueError, DBAPIError) as exc:
            for record in records:
                _failure(record, exc, "invalid_original_source")
            continue
        for record in records:
            try:
                with ranks._bounded_queries(conn):
                    row = proof.image(_SNAPSHOT, record["snapshot_id"])
                    require(row is not None, "frozen rank slot disappeared")
                    binding = _frozen_authority(proof, row, record, album["sgf_content"], canonical_hashes)
                record["stored"] = _decision_record(row["snapshot"], binding=binding)
                pending.append((record, {"album": album, "side": row["side"], "source_links": links}, row["snapshot"]))
            except (ValueError, KeyError, TypeError, AttributeError, DBAPIError) as exc:
                _failure(record, exc, "invalid_frozen_authority")

    if not pending:
        return rows
    try:
        with ranks._bounded_queries(conn):
            decisions = ranks.prepare_rank_decisions(
                conn, [target for _, target, _ in pending], matched_at=matched_at, resource=resource
            )["decisions"]
    except (ValueError, DBAPIError) as exc:
        for record, _, _ in pending:
            _failure(record, exc, "invalid_original_binding")
        return rows
    for (record, target, frozen), proposed in zip(pending, decisions):
        record["proposed"] = _decision_record(proposed)
        reason = proposed["refusal_reason"]
        if reason == "resource_deferred":
            _status(record, "resource_deferred", reason)
        elif reason == "invalid_original_evidence":
            _status(record, "integrity_failure", reason)
        elif reason:
            _status(record, "refused", reason)
        elif repair._semantic(frozen) == repair._semantic(proposed):
            _status(record, "consistent")
        else:
            try:
                with ranks._bounded_queries(conn):
                    record["proposed"]["basis_binding"] = ranks.bind_rank_decision(
                        conn, target, proposed, lock=False, resource=resource
                    )
                record["retained_receipts_require_review"] = True
                _status(record, "supported_difference")
            except (ValueError, DBAPIError) as exc:
                _failure(record, exc, "invalid_proposed_binding")
    return rows


def audit_existing_v3(conn, *, matched_at, album_ids=None, from_album_id=None, emit=None):
    """Walk current v3 slots on the caller's read-only, stable database snapshot."""
    matched_at = ranks._utc(matched_at)
    if album_ids is not None:
        require(
            0 < len(album_ids) <= ranks.MAX_INCOMING_GAMES and all(type(album_id) is int for album_id in album_ids),
            "v3 audit album scope invalid",
        )
        album_ids = sorted(set(album_ids))
    require(from_album_id is None or type(from_album_id) is int, "v3 audit album cursor invalid")
    identity = repair._database_identity(conn)
    counts = Counter(
        albums=0,
        v3_slots=0,
        consistent_slots=0,
        refused_slots=0,
        supported_difference_slots=0,
        resource_deferred_slots=0,
        integrity_failure_slots=0,
        excluded_from_repair_slots=0,
    )
    reasons = Counter()
    a = m.KifuAlbum.__table__
    v3 = _SNAPSHOT.c.snapshot["version"].as_string() == ranks.SNAPSHOT_VERSION
    inventory = select(_SNAPSHOT.c.album_id).where(v3)
    if album_ids is not None:
        inventory = inventory.where(_SNAPSHOT.c.album_id.in_(album_ids))
    if from_album_id is not None:
        inventory = inventory.where(_SNAPSHOT.c.album_id >= from_album_id)
    last_id = None

    def audit(group):
        for row in _audit_group(conn, group, heads, matched_at):
            counts["v3_slots"] += 1
            counts[row["status"] + "_slots"] += 1
            visibility = row.get("album_visibility")
            if visibility is not None and not repair._public(visibility):
                counts["excluded_from_repair_slots"] += 1
            if row["reason"]:
                reasons[row["reason"]] += 1
            if emit is not None:
                emit(row)

    while True:
        page = inventory if last_id is None else inventory.where(_SNAPSHOT.c.album_id > last_id)
        with ranks._bounded_queries(conn):
            ids = list(conn.scalars(page.distinct().order_by(_SNAPSHOT.c.album_id).limit(ranks.MAX_INCOMING_GAMES)))
            if not ids:
                break
            last_id = ids[-1]
            heads = defaultdict(list)
            query = (
                select(*(column for column in _SNAPSHOT.c if column.name != "snapshot"))
                .where(and_(v3, _SNAPSHOT.c.album_id.in_(ids)))
                .order_by(_SNAPSHOT.c.album_id, _SNAPSHOT.c.side)
            )
            for head in conn.execute(query).mappings():
                heads[head["album_id"]].append(head)
            album_rows = conn.execute(
                select(
                    *[a.c[key] for key in ranks._SCALARS],
                    a.c.duplicate_of_id,
                    a.c.list_hidden_reason,
                    ranks._body_length(conn, a.c.sgf_content).label("sgf_bytes"),
                ).where(a.c.id.in_(ids))
            ).mappings()
            albums = {album["id"]: dict(album) for album in album_rows}
        counts["albums"] += len(ids)
        group, target_bytes = [], 0
        for album_id in ids:
            album = albums.get(album_id)
            size = album["sgf_bytes"] if album is not None else 0
            size = size if type(size) is int and 0 < size <= ranks.MAX_SGF_BYTES else 0
            if group and target_bytes + size > repair.TARGET_BODY_BYTES:
                audit(group)
                group, target_bytes = [], 0
            group.append((album_id, album))
            target_bytes += size
        audit(group)

    return {
        "format": FORMAT,
        "policy_version": ranks.POLICY_VERSION,
        "matched_at": matched_at,
        "database_identity": identity,
        "scope_album_ids": album_ids,
        "from_album_id": from_album_id,
        "census": dict(counts),
        "reasons": dict(reasons),
    }
