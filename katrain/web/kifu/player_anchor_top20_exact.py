"""Execute only the independently frozen top20 existing-player FK decisions."""

import copy
import unicodedata

from sqlalchemy import bindparam, text, update
from sqlalchemy.orm import Session

from katrain.web.core.models_db import KifuAlbum
from katrain.web.kifu import player_safe6_exact as safe6

base = safe6.base
DATABASES = base.DATABASES
DECISION_PATH = "docs/resource/kifu-player-exact-anchor-top20-independent-decision-astra-2026-10-04.json"
DECISION_SHA = "6d53699a34bbcc4006020b9089977d4ca44eb4e192cd70db6021edb21dc5f39b"
REBASE_SHA = "565423c67b7f4aa2533ab0951110ddeef812953e8d5d436aa5b2f3346f5ea75a"
SOURCE_SHA = "6f69d06d3f64b37a0299a7bfcc1e16f60084c3fab9e81d0804032455d90c6c3d"
FORMAT = "kifu-player-anchor-top20-exact-plan-v1"
COUNTS = {"approved": 1933, "held": 1415}
GUARDS = (
    "albums",
    "slots",
    "album_sources",
    "sources",
    "events",
    "event_editions",
    "event_aliases",
    "catalog",
    "raw_staging",
    "existing_owner_context",
    "global_counts",
    "owner_hits",
    "variant_scan_inputs",
)
TABLES = {
    "sources": "kifu_sources",
    "events": "kifu_events",
    "event_editions": "kifu_event_editions",
    "event_aliases": "kifu_event_aliases",
    "players": "kifu_players",
    "aliases": "kifu_player_aliases",
    "names": "kifu_player_names",
}


def _pin(item):
    return base._pin(item["path"], item["file_sha256"])


def _owner_hits(decision, catalog, variants):
    policy = decision["normalization_policy"]
    charmap = str.maketrans(policy["han_from"], policy["han_to"])

    def key(value):
        normalized = unicodedata.normalize("NFKC", value).casefold().translate(charmap)
        return "".join(ch for ch in normalized if not ch.isspace() and not unicodedata.category(ch).startswith("P"))

    result = {}
    for raw, spellings in variants.items():
        keys, hits = {key(value) for value in spellings}, []
        for table, fields, owner in (
            ("players", ("canonical_name",), "id"),
            ("aliases", ("alias", "normalized_alias"), "player_id"),
            ("names", ("display_name",), "player_id"),
        ):
            for row in catalog[table]:
                matched = [field for field in fields if row.get(field) and key(row[field]) in keys]
                if matched:
                    hits.append(
                        {
                            "table": table,
                            "row_id": row["id"],
                            "owner_id": row[owner],
                            "matched_fields": matched,
                            "row": row,
                            "row_sha256": base._digest(row),
                        }
                    )
        result[raw] = hits
    return result


def _rebase(decision, rebase, environment):
    label = environment.upper()
    info = rebase["environments"][label]
    original, post, final, plan = [
        _pin(info[key])
        for key in ("original_preimage", "post_korean_preimage", "final_expanded_preimage", "korean_applied_plan")
    ]
    korean = _pin(rebase["korean_decision"])
    _pin(rebase["commit_receipt"])
    approved = {row["id"]: row for row in korean["approved"]}
    if (
        info["database"] != DATABASES[environment]
        or any(item["database"] != DATABASES[environment] for item in (original, post, final, plan))
        or plan["decision_sha256"] != rebase["korean_decision"]["file_sha256"]
        or plan["environment"] != environment
        or plan["counts"]["approved"] != 737
        or sorted(set(row["id"] for row in original["albums"]) & set(approved)) != [70944]
    ):
        raise ValueError("Korean exact rebase identity/overlap differs")
    wanted = copy.deepcopy(original)
    plan_rows = {row["id"]: row for row in plan["snapshot"]["albums"]}
    deltas = []
    for section, rows in (
        ("albums", wanted["albums"]),
        ("existing_owner_context.albums", wanted["existing_owner_context"]["albums"]),
    ):
        for row in rows:
            if row["id"] == 70944:
                before = copy.deepcopy(row)
                if before["event_id"] is not None or before != plan_rows[70944]:
                    raise ValueError("Korean overlap full preimage differs")
                row["event_id"] = 92
                deltas.append(
                    {
                        "table_scope": section,
                        "album_id": 70944,
                        "field": "event_id",
                        "before": None,
                        "after": 92,
                        "before_full_row_sha256": base._digest(before),
                        "after_full_row_sha256": base._digest(row),
                        "korean_approved_record_sha256": base._digest(approved[70944]),
                    }
                )
    additions = info["new_full_event_rows"]
    if (
        deltas != info["exact_event_deltas"]
        or [(row["id"], row["canonical_name"]) for row in additions] != [(92, "韩国GS加德士杯"), (93, "韩国女子国手战")]
        or {row["id"] for row in additions} & {row["id"] for row in wanted["events"]}
    ):
        raise ValueError("Korean enumerated rebase delta differs")
    wanted["events"] += additions
    wanted["global_counts"]["event_links"] += 737
    wanted["captured_at_db_utc"] = post["captured_at_db_utc"]
    if (
        wanted != post
        or original["global_counts"] != info["global_counts_before"]
        or post["global_counts"] != info["global_counts_after"]
    ):
        raise ValueError("Korean complete postimage differs")
    for key in post:
        if (
            key not in ("captured_at_db_utc", "existing_owner_context", "variant_scan_inputs", "owner_hits")
            and post[key] != final[key]
        ):
            raise ValueError(f"expanded snapshot changed original {key}")
    old, new = post["existing_owner_context"], final["existing_owner_context"]
    original_rows = {row["id"]: row for row in old["albums"]}
    expanded_rows = {row["id"]: row for row in new["albums"]}
    original_sources = {row["id"]: row for row in old["album_sources"]}
    expanded_sources = {row["id"]: row for row in new["album_sources"]}
    if (
        any(expanded_rows.get(key) != row for key, row in original_rows.items())
        or any(expanded_sources.get(key) != row for key, row in original_sources.items())
        or sorted(set(expanded_rows) - set(original_rows)) != info["additional_context_album_ids"]
        or sorted(set(new["owner_ids"]) - set(old["owner_ids"])) != info["additional_owner_ids"]
        or not set(old["owner_ids"]) <= set(new["owner_ids"])
        or new["owner_ids"] != info["expanded_owner_ids"]
        or any(
            row["album_id"] not in info["additional_context_album_ids"]
            for key, row in expanded_sources.items()
            if key not in original_sources
        )
        or final["environment"] != environment
        or final["raws"] != decision["scope"]["raws"]
    ):
        raise ValueError("expanded context differs")
    return final


def evidence(environment):
    if environment not in DATABASES:
        raise ValueError("unknown environment")
    decision = base._pin(DECISION_PATH, DECISION_SHA)
    if decision["format"] != "kifu-player-exact-anchor-top20-independent-decision-astra-v1":
        raise ValueError("top20 decision identity differs")
    inputs = {key: _pin(item) for key, item in decision["inputs"].items()}
    if (
        decision["inputs"]["exact_korean_rebase"]["file_sha256"] != REBASE_SHA
        or decision["inputs"]["source_manifest"]["file_sha256"] != SOURCE_SHA
        or inputs["source_manifest"]["sources"] != decision["source_evidence"]
    ):
        raise ValueError("top20 source/rebase pins differ")
    _pin(inputs["source_manifest"]["cwa_api_provenance"])
    for source in decision["source_evidence"]:
        for role in ("raw", "text"):
            if role + "_path" in source:
                base._pin(source[role + "_path"], source[role + "_sha256"])
        if "metadata_file" in source:
            _pin(source["metadata_file"])
    approved, held = decision["approved"], decision["held"]
    for label, rows, count in (("approved", approved, 1933), ("held", held, 1415)):
        members = [[row["album_id"], row["side"]] for row in rows]
        if (
            len(rows) != count
            or members != decision[label + "_slots"]
            or len({tuple(key) for key in members}) != count
            or base._digest(members) != decision[label + "_slot_membership_sha256"]
            or base._digest(rows) != decision[label + "_records_sha256"]
        ):
            raise ValueError("top20 exact membership differs")
    scope = sorted([[row["album_id"], row["side"], row["raw"]] for row in approved + held])
    if (
        scope != decision["scope_slots"]
        or len({tuple(row[:2]) for row in scope}) != 3348
        or len(decision["families"]) != 20
    ):
        raise ValueError("top20 exact slot partition differs")
    expected = _rebase(decision, inputs["exact_korean_rebase"], environment)
    info = decision["environments"][environment.upper()]
    if (
        info["full_preimage"]
        != inputs["exact_korean_rebase"]["environments"][environment.upper()]["final_expanded_preimage"]
    ):
        raise ValueError("top20 final preimage pin differs")
    for key, sha in info["full_guard_sha256"].items():
        if base._digest(expected[key]) != sha:
            raise ValueError(f"top20 frozen {key} SHA differs")
    if (
        any(len(expected[key]) != count for key, count in info["full_guard_counts"].items())
        or any(len(expected["catalog"][key]) != count for key, count in info["catalog_counts"].items())
        or expected["global_counts"] != info["expected_before_global_counts"]
        or [row["id"] for row in expected["albums"]] != info["scope_album_ids"]
        or [row["id"] for row in expected["existing_owner_context"]["albums"]]
        != info["existing_owner_context_album_ids"]
        or expected["existing_owner_context"]["owner_ids"] != info["existing_owner_context_ids"]
        or sorted(expected["albums"][0]) != info["all_album_columns"]
        or [[row["album_id"], row["side"], row["raw"]] for row in expected["slots"]] != scope
        or _owner_hits(decision, expected["catalog"], expected["variant_scan_inputs"]) != expected["owner_hits"]
    ):
        raise ValueError("top20 full frozen scope differs")
    albums = {row["id"]: row for row in expected["albums"]}
    players = {row["id"]: row for row in expected["catalog"]["players"]}
    associations = {}
    for row in expected["album_sources"]:
        associations.setdefault(row["album_id"], []).append(row)
    families = {row["raw"]: row for row in decision["families"]}
    targets = []
    for row in approved + held:
        album, side, guard = albums[row["album_id"]], row["side"], row["environments"][environment.upper()]
        opposite = "white" if side == "black" else "black"
        target = row["target_player_id_by_environment"][environment.upper()]
        is_approved = row["decision"] == "APPROVE_EXISTING_PLAYER_FK"
        wanted = {side + "_player_id": {"from": None, "to": target}} if is_approved else {}
        opponent = players.get(album[opposite + "_player_id"])
        if (
            side not in ("black", "white")
            or album[side + "_player_id"] is not None
            or guard["before_fk"] is not None
            or album["player_" + side] != row["raw"]
            or album["date_played"] != row["sgf_album_checks"]["date_played"]["album"]
            or album["event"] != row["event"]
            or album[side + "_rank"] != row["rank"]
            or album["player_" + opposite] != row["opponent_raw"]
            or guard["opponent_fk"] != album[opposite + "_player_id"]
            or guard["opponent_full_player_row"] != opponent
            or base._digest(opponent) != guard["opponent_player_row_sha256"]
            or base._digest(album) != guard["album_preimage_sha256"]
            or base._digest(associations.get(album["id"], [])) != guard["album_sources_preimage_sha256"]
            or base._sha(album["sgf_content"].encode()) != row["sgf_sha256"]
            or base._digest(row["root_properties"]) != row["root_properties_sha256"]
            or guard["proposed_change"] != wanted
        ):
            raise ValueError(f"top20 reviewed slot preimage differs: {album['id']}/{side}")
        if is_approved:
            if (
                target not in players
                or target != families[row["raw"]]["target_player_id_by_environment"][environment.upper()]
                or target == guard["opponent_fk"]
                or base._digest(players[target]) != guard["target_player_row_sha256"]
            ):
                raise ValueError("top20 existing target differs")
            targets.append([album["id"], side, target])
        elif row["decision"] != "HOLD":
            raise ValueError("top20 held decision differs")
    if base._digest(targets) != info["approved_targets_sha256"]:
        raise ValueError("top20 target membership differs")
    return decision, {key: expected[key] for key in GUARDS}


def _encode(value):
    if isinstance(value, dict):
        return {key: _encode(item) for key, item in value.items()}
    return value.isoformat() if hasattr(value, "isoformat") else value


def _rows(db, table, where="", **params):
    query = text("SELECT * FROM " + table + (" WHERE " + where if where else "") + " ORDER BY id")
    query = query.bindparams(*(bindparam(key, expanding=True) for key in params))
    return [_encode(dict(row)) for row in db.execute(query, params).mappings()]


def _slots(albums, raws):
    return sorted(
        [
            {
                "album_id": album["id"],
                "side": side,
                "raw": album["player_" + side],
                "current_fk": None,
                "opponent_raw": album["player_" + opposite],
                "opponent_fk": album[opposite + "_player_id"],
            }
            for album in albums
            for side, opposite in (("black", "white"), ("white", "black"))
            if album["player_" + side] in raws and album[side + "_player_id"] is None
        ],
        key=lambda row: (row["album_id"], row["side"]),
    )


def _snapshot(db, decision, expected):
    raws = decision["scope"]["raws"]
    scope = "(player_black IN :raws AND black_player_id IS NULL) OR (player_white IN :raws AND white_player_id IS NULL)"
    null_albums = _rows(db, "kifu_albums", scope, raws=raws)
    result = {
        "albums": _rows(db, "kifu_albums", "id IN :ids", ids=[row["id"] for row in expected["albums"]]),
        "slots": _slots(null_albums, raws),
        "raw_staging": _rows(db, "kifu_raw_player_values", "raw_value IN :raws", raws=raws),
        "variant_scan_inputs": expected["variant_scan_inputs"],
    }
    result["album_sources"] = _rows(
        db, "kifu_album_sources", "album_id IN :ids", ids=[row["id"] for row in result["albums"]]
    )
    catalog = {key: _rows(db, TABLES[key]) for key in ("players", "aliases", "names")}
    result["catalog"] = catalog
    result["owner_hits"] = _owner_hits(decision, catalog, expected["variant_scan_inputs"])
    owners = sorted({row["owner_id"] for hits in result["owner_hits"].values() for row in hits})
    context = _rows(
        db,
        "kifu_albums",
        "black_player_id IN :owners OR white_player_id IN :owners OR " "player_black IN :raws OR player_white IN :raws",
        owners=owners,
        raws=raws,
    )
    result["existing_owner_context"] = {
        "owner_ids": owners,
        "albums": context,
        "album_sources": _rows(db, "kifu_album_sources", "album_id IN :ids", ids=[row["id"] for row in context]),
    }
    for key in ("sources", "events", "event_editions", "event_aliases"):
        result[key] = _rows(db, TABLES[key])
    result["global_counts"] = dict(
        db.execute(
            text(
                "SELECT count(*) AS games, count(black_player_id)+"
                "count(white_player_id) AS player_links, count(event_id) AS event_links "
                "FROM kifu_albums"
            )
        )
        .mappings()
        .one()
    )
    return result


def _validate_snapshot(actual, expected):
    for key in GUARDS:
        if not safe6._equal(actual[key], expected[key]):
            raise ValueError(f"{key} preimage differs")


def _capture(db, environment, decision, expected):
    database = base._database(db, environment)
    snapshot = _snapshot(db, decision, expected)
    _validate_snapshot(snapshot, expected)
    return {
        "format": FORMAT,
        "environment": environment,
        "database": database,
        "decision_sha256": DECISION_SHA,
        "rebase_sha256": REBASE_SHA,
        "source_manifest_sha256": SOURCE_SHA,
        "snapshot": snapshot,
        "counts": dict(COUNTS),
    }


def capture(engine, environment):
    decision, expected = evidence(environment)
    with Session(engine) as db:
        if engine.dialect.name == "postgresql":
            db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        return _capture(db, environment, decision, expected)


def _after(snapshot, approved, environment):
    wanted = copy.deepcopy(snapshot)
    changes = {
        (row["album_id"], row["side"]): row["target_player_id_by_environment"][environment.upper()] for row in approved
    }
    for albums in (wanted["albums"], wanted["existing_owner_context"]["albums"]):
        for album in albums:
            for side in ("black", "white"):
                if (album["id"], side) in changes:
                    album[side + "_player_id"] = changes[(album["id"], side)]
    wanted["slots"] = _slots(wanted["albums"], list(wanted["variant_scan_inputs"]))
    wanted["global_counts"]["player_links"] += len(approved)
    return wanted


def run(engine, environment, plan, *, apply=False, plan_sha256=None, approved_plan_sha256=None):
    if apply and (not plan_sha256 or plan_sha256 != approved_plan_sha256):
        raise ValueError("separately approved plan SHA required")
    decision, expected = evidence(environment)
    if (
        plan.get("format") != FORMAT
        or plan.get("environment") != environment
        or plan.get("database") != DATABASES[environment]
        or plan.get("decision_sha256") != DECISION_SHA
        or plan.get("rebase_sha256") != REBASE_SHA
        or plan.get("source_manifest_sha256") != SOURCE_SHA
        or plan.get("counts") != COUNTS
    ):
        raise ValueError("top20 plan identity differs")
    frozen_postimage = _after(expected, decision["approved"], environment)
    dates = {row["id"]: row["date_played"] for row in expected["albums"]}
    with Session(engine) as db:
        tx = db.begin()
        try:
            if engine.dialect.name == "postgresql":
                db.execute(
                    text(
                        "LOCK TABLE kifu_albums,kifu_album_sources,kifu_sources,kifu_players,"
                        "kifu_player_aliases,kifu_player_names,kifu_raw_player_values,kifu_events,"
                        "kifu_event_editions,kifu_event_aliases IN SHARE ROW EXCLUSIVE MODE"
                    )
                )
            current = _capture(db, environment, decision, expected)
            if not safe6._equal(current, plan):
                raise ValueError("top20 captured plan preimage differs")
            for row in decision["approved"]:
                side = row["side"]
                field = KifuAlbum.black_player_id if side == "black" else KifuAlbum.white_player_id
                raw_field = KifuAlbum.player_black if side == "black" else KifuAlbum.player_white
                changed = db.execute(
                    update(KifuAlbum)
                    .where(
                        KifuAlbum.id == row["album_id"],
                        raw_field == row["raw"],
                        KifuAlbum.date_played == dates[row["album_id"]],
                        field.is_(None),
                    )
                    .values({field: row["target_player_id_by_environment"][environment.upper()]})
                )
                if changed.rowcount != 1:
                    raise ValueError(f"top20 CAS failed: {row['album_id']}/{side}")
            db.flush()
            _validate_snapshot(_snapshot(db, decision, expected), frozen_postimage)
            tx.commit() if apply else tx.rollback()
        except BaseException:
            tx.rollback()
            raise
    try:
        with Session(engine) as independent:
            if engine.dialect.name == "postgresql":
                independent.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            if base._database(independent, environment) != plan["database"]:
                raise RuntimeError("top20 independent database differs")
            _validate_snapshot(_snapshot(independent, decision, expected), frozen_postimage if apply else expected)
    except BaseException as exc:
        if apply:
            raise RuntimeError("commit succeeded; independent postcommit verification failed") from exc
        raise
    return {"committed": apply, "created_player_ids": {}, **COUNTS}
