"""Exact, reversible merges for explicitly reviewed duplicate player pairs.

This adapter consumes the existing single-pair proposals. It does not research
identities, translate names, or extend the general name-batch undo allowlist.
"""

from copy import deepcopy
from datetime import datetime, timezone
import json
import re

from sqlalchemy import String, cast, inspect, or_, select, text
from sqlalchemy.exc import IntegrityError

from katrain.web.core.models_db import (
    KifuAlbum,
    KifuAlbumSource,
    KifuNameBatch,
    KifuNameChange,
    KifuNameResearchEvidence,
    KifuNameSourceRegistry,
    KifuPlayer,
    KifuPlayerAlias,
    KifuPlayerName,
    KifuRawPlayerName,
    KifuRawPlayerValue,
    KifuSource,
)
from katrain.web.kifu.identity import normalize_alias
from katrain.web.kifu.name_batch import (
    BatchError,
    _fail,
    _image,
    _insert,
    _locked_write,
    _record_change,
    _values_for_table,
)
from katrain.web.kifu.name_candidates import canonical_sha256


DATABASES = {"PROD": "katrain_prod_20260725", "TEST": "katrain_db"}
PAIRS = {
    "piao": {
        "ids": {"PROD": (4885, 4886), "TEST": (10670, 10671)},
        "names": ("朴文垚", "朴文尧"),
        "counts": (328, 238),
        "raw_id": 11440,
        "spellings": ("朴文垚", "朴文尧", "朴文垚五段", "朴文堯", "朴文尭", "Piao Wenyao", "Piao Wen Yao", "박문요"),
    },
    "li": {
        "ids": {"PROD": (752, 4982), "TEST": (753, 10766)},
        "names": ("李喆", "李哲"),
        "counts": (314, 247),
        "raw_id": 11601,
        "spellings": ("李喆", "李哲", "李喆", "李テツ", "Li Zhe", "리저"),
    },
    # New pairs follow this execution order: Li Jie, Park Ji, Cho Huilian,
    # Park Jin, Cho variant. Later same-survivor counts require fresh captures.
    "li_jie": {
        "ids": {"PROD": (4970, 4969), "TEST": (10755, 10754)},
        "names": ("李劼", "李劫"), "counts": (169, 30),
        "raw_ids": (11584, 11585), "spellings": ("李劼", "李劫", "李劫五段"),
    },
    "park_ji": {
        "ids": {"PROD": (4880, 4892), "TEST": (10665, 10677)},
        "names": ("朴志恩", "朴智恩"), "counts": (127, 276),
        "raw_ids": (11452,), "spellings": ("朴志恩", "朴智恩", "朴志恩九段", "朴志恩五段", "朴志恩六段"),
    },
    "park_jin": {
        "ids": {"PROD": (4880, 4924), "TEST": (10665, 10709)},
        "names": ("朴志恩", "朴鋕恩"), "counts": (1, 403),
        "raw_ids": (11506,), "spellings": ("朴志恩", "朴鋕恩", "朴志恩九段", "朴志恩五段", "朴志恩六段"),
    },
    "cho_huilian": {
        "ids": {"PROD": (5962, 5961), "TEST": (895, 11730)},
        "names": ("赵惠连", "赵惠莲"), "counts": (126, 403),
        "raw_ids": (13349, 13350), "spellings": ("赵惠连", "赵惠莲", "赵惠莲七段"),
    },
    "cho_huilian_variant": {
        "ids": {"PROD": (5962, 5963), "TEST": (895, 11731)},
        "names": ("赵惠连", "赵慧连"), "counts": (1, 529),
        "raw_ids": (13356,), "spellings": ("赵惠连", "赵慧连"),
    },
    "choi_kyubyeong": {
        "ids": {"PROD": (4537, 4558), "TEST": (10327, 10348)},
        "names": ("崔圭丙", "崔珪昞"), "counts": (88, 216),
        "raw_ids": (7346, 7412, 10853),
        "spellings": ("崔圭丙", "崔珪昞", "Ch'oeKyu-pyeong", "ChoiGyuByeong"),
    },
    "ueno_asami": {
        "ids": {"PROD": (83, 3769), "TEST": (83, 9567)},
        "names": ("上野爱咲美", "上野爱笑美"), "counts": (79, 426),
        "raw_ids": (9415,), "spellings": ("上野爱咲美", "上野爱笑美"),
    },
    "yun_junsang_jun": {
        "ids": {"PROD": (4453, 4446), "TEST": (10244, 10237)},
        "names": ("尹峻相", "尹俊相"), "counts": (79, 478),
        "raw_ids": (10650, 10651, 10652, 10653, 10654),
        "spellings": ("尹峻相", "尹俊相"),
    },
    "chinen_kaori": {
        "ids": {"PROD": (5633, 5632), "TEST": (11406, 11405)},
        "names": ("知念薰", "知念熏"), "counts": (84, 193),
        "raw_ids": (12771,), "spellings": ("知念薰", "知念熏"),
    },
    # Source-reviewed Fujisawa Hosai: retire original-name owners in this order.
    "fujisawa_kurano": {
        "ids": {"PROD": (5854, 5853), "TEST": (11623, 11622)},
        "names": ("藤泽朋斋", "藤泽库之助"), "counts": (92, 442),
        "raw_ids": (13161, 13162, 13163),
        "spellings": ("藤泽朋斋", "藤泽库之助", "藤泽库之助九段", "藤泽库之助五段"),
    },
    "fujisawa_sawa": {
        "ids": {"PROD": (5854, 5850), "TEST": (11623, 11619)},
        "names": ("藤泽朋斋", "藤沢库之助"), "counts": (1, 534),
        "raw_ids": (13155,), "spellings": ("藤泽朋斋", "藤沢库之助", "藤沢庫之助"),
    },
}
FORMAT = "kifu-player-single-duplicate-proposal-v1"
AUDIT_FORMAT = "kifu-player-duplicate-execution-v1"
REVIEW_FORMAT = "kifu-player-duplicate-review-v1"
_SHA = re.compile(r"^[0-9a-f]{64}$")
_MODELS = {
    model.__tablename__: model
    for model in (
        KifuAlbum,
        KifuAlbumSource,
        KifuNameResearchEvidence,
        KifuNameSourceRegistry,
        KifuPlayerAlias,
        KifuPlayerName,
        KifuPlayer,
        KifuRawPlayerName,
        KifuRawPlayerValue,
        KifuSource,
    )
}
_FKS = {
    ("kifu_albums", "black_player_id"),
    ("kifu_albums", "white_player_id"),
    ("kifu_name_research_evidence", "player_id"),
    ("kifu_player_aliases", "player_id"),
    ("kifu_player_names", "player_id"),
}
_PROTECTED = set(_MODELS) - {"kifu_albums", "kifu_raw_player_values", "kifu_player_aliases", "kifu_players"}
_FK_SQL = """
SELECT c.conname,ns.nspname AS table_schema,cl.relname AS table_name,
       a.attname AS column_name,c.confdeltype AS delete_action
FROM pg_constraint c JOIN pg_class cl ON cl.oid=c.conrelid
JOIN pg_namespace ns ON ns.oid=cl.relnamespace
JOIN LATERAL unnest(c.conkey) WITH ORDINALITY ck(attnum,ord) ON true
JOIN LATERAL unnest(c.confkey) WITH ORDINALITY fk(attnum,ord) ON ck.ord=fk.ord
JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=ck.attnum
WHERE c.contype='f' AND c.confrelid='kifu_players'::regclass
ORDER BY ns.nspname,cl.relname,a.attname
"""
_COLUMN_SQL = """
SELECT table_name,column_name,data_type FROM information_schema.columns
WHERE table_schema='public'
ORDER BY table_name,column_name
"""
_FUJISAWA_STUB_IDS = {"PROD": 5855, "TEST": 11624}


def expected_counts(key):
    moving, protected = PAIRS[key]["counts"]
    raw_ids = PAIRS[key]["raw_ids"] if "raw_ids" in PAIRS[key] else (PAIRS[key]["raw_id"],)
    return {
        "album_fk_updates": moving,
        "protected_existing_slots": protected,
        "survivor_slots_after": moving + protected,
        "raw_metadata_updates": len(raw_ids),
        "aliases_to_insert": 1,
        "unreviewed_duplicate_rows_to_delete": 1,
        "name_writes": 0,
        "new_players": 0,
        "source_page_writes": 0,
    }


def pair_key(plan):
    environment = plan.get("environment")
    _fail(environment in DATABASES, "unknown environment")
    for key, pair in PAIRS.items():
        if (plan.get("survivor_player", {}).get("id"), plan.get("retire_player", {}).get("id")) == pair["ids"][
            environment
        ]:
            return key
    raise BatchError("only explicitly pinned duplicate-player pairs are supported")


def _schema(conn):
    table_columns = {}
    if conn.dialect.name == "postgresql":
        fks = [dict(row) for row in conn.execute(text(_FK_SQL)).mappings()]
        columns = [dict(row) for row in conn.execute(text(_COLUMN_SQL)).mappings()]
        references = [row for row in columns if "player_id" in row["column_name"]]
        for row in columns:
            table_columns.setdefault(row["table_name"], set()).add(row["column_name"])
    elif conn.dialect.name == "sqlite":
        inspector = inspect(conn)
        fks, references = [], []
        for table in sorted(inspector.get_table_names()):
            for fk in inspector.get_foreign_keys(table):
                if fk["referred_table"] == "kifu_players":
                    _fail(fk["referred_columns"] == ["id"], "unexpected player foreign key")
                    for column in fk["constrained_columns"]:
                        fks.append(
                            {
                                "conname": fk["name"],
                                "table_schema": "main",
                                "table_name": table,
                                "column_name": column,
                                "delete_action": (
                                    "a"
                                    if fk.get("options", {}).get("ondelete", "NO ACTION") == "NO ACTION"
                                    else fk["options"]["ondelete"]
                                ),
                            }
                        )
            for column in inspector.get_columns(table):
                table_columns.setdefault(table, set()).add(column["name"])
                if "player_id" in column["name"]:
                    references.append(
                        {"table_name": table, "column_name": column["name"], "data_type": str(column["type"]).lower()}
                    )
        fks.sort(key=lambda row: (row["table_schema"], row["table_name"], row["column_name"]))
        references.sort(key=lambda row: (row["table_name"], row["column_name"]))
    else:
        raise BatchError("only PostgreSQL and SQLite are supported")
    _fail(
        {(row["table_name"], row["column_name"]) for row in fks} == _FKS and len(fks) == 5,
        "declared player foreign-key set changed",
    )
    _fail(
        all(table_columns.get(table) == set(model.__table__.columns.keys()) for table, model in _MODELS.items()),
        "bounded full-row column schema changed",
    )
    return fks, references


def _rows(conn, model, condition):
    return [
        {key: value.isoformat() if isinstance(value, datetime) else value for key, value in row.items()}
        for row in conn.execute(select(model.__table__).where(condition).order_by(model.id)).mappings()
    ]


def capture(conn, environment, key):
    """Read this pair's complete current reference/raw/source/collision scope."""
    _fail(environment in DATABASES and key in PAIRS, "unknown bounded pair/environment")
    database = (
        conn.scalar(text("SELECT current_database()")) if conn.dialect.name == "postgresql" else DATABASES[environment]
    )
    _fail(database == DATABASES[environment], "database/environment mismatch")
    ids = PAIRS[key]["ids"][environment]
    fks, references = _schema(conn)
    full = {"kifu_players": _rows(conn, KifuPlayer, KifuPlayer.id.in_(ids))}
    for model in (KifuAlbum, KifuPlayerAlias, KifuPlayerName, KifuNameResearchEvidence):
        columns = [model.__table__.c[row["column_name"]] for row in fks if row["table_name"] == model.__tablename__]
        full[model.__tablename__] = _rows(conn, model, or_(*(column.in_(ids) for column in columns)))
    spellings = sorted(
        set(PAIRS[key]["spellings"])
        | {
            row["player_" + side]
            for row in full["kifu_albums"]
            for side in ("black", "white")
            if row[side + "_player_id"] in ids and row["player_" + side]
        }
    )
    exact = _rows(conn, KifuAlbum, or_(KifuAlbum.player_black.in_(spellings), KifuAlbum.player_white.in_(spellings)))
    raw = _rows(
        conn,
        KifuRawPlayerValue,
        or_(
            KifuRawPlayerValue.raw_value.in_(spellings),
            cast(KifuRawPlayerValue.review_metadata["player_id"].as_string(), String).in_(
                [str(owner) for owner in ids]
            ),
        ),
    )
    full["kifu_raw_player_values"] = raw
    rawids = [row["id"] for row in raw]
    full["kifu_raw_player_names"] = _rows(conn, KifuRawPlayerName, KifuRawPlayerName.raw_player_id.in_(rawids))
    raw_evidence = _rows(conn, KifuNameResearchEvidence, KifuNameResearchEvidence.raw_player_id.in_(rawids))
    regids = {row["source_registry_id"] for row in full["kifu_name_research_evidence"] + raw_evidence}
    full["kifu_name_source_registry"] = _rows(conn, KifuNameSourceRegistry, KifuNameSourceRegistry.id.in_(regids))
    albumids = [row["id"] for row in full["kifu_albums"]]
    full["kifu_album_sources"] = _rows(conn, KifuAlbumSource, KifuAlbumSource.album_id.in_(albumids))
    sourceids = {row["source_id"] for row in full["kifu_album_sources"]}
    full["kifu_sources"] = _rows(conn, KifuSource, KifuSource.id.in_(sourceids))
    result = {
        "environment": environment,
        "database": database,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "transaction_read_only": (
            conn.scalar(text("SHOW transaction_read_only")) if conn.dialect.name == "postgresql" else "local"
        ),
        "target_ids": list(ids),
        "declared_player_fks": fks,
        "player_reference_columns": references,
        "full_rows": full,
        "exact_raw_album_scope": exact,
        "raw_owned_evidence": raw_evidence,
        "collision_preimages": {
            "players": _rows(conn, KifuPlayer, KifuPlayer.canonical_name.in_(spellings)),
            "aliases": _rows(
                conn,
                KifuPlayerAlias,
                or_(
                    KifuPlayerAlias.alias.in_(spellings),
                    KifuPlayerAlias.normalized_alias.in_(
                        {value.casefold() for value in spellings} | {normalize_alias(value) for value in spellings}
                    ),
                ),
            ),
            "names": _rows(conn, KifuPlayerName, KifuPlayerName.display_name.in_(spellings)),
        },
    }
    if key in {"fujisawa_kurano", "fujisawa_sawa"}:
        stub_id = _FUJISAWA_STUB_IDS[environment]
        stub_refs = {}
        for table, column in sorted(_FKS):
            model = _MODELS[table]
            stub_refs[f"{table}.{column}"] = _rows(conn, model, model.__table__.c[column] == stub_id)
        result["protected_stub"] = {
            "owner": _rows(conn, KifuPlayer, KifuPlayer.id == stub_id),
            "declared_fk_rows": stub_refs,
            "raw_metadata_refs": _rows(
                conn, KifuRawPlayerValue,
                cast(KifuRawPlayerValue.review_metadata["player_id"].as_string(), String) == str(stub_id),
            ),
            "retained_raw_13167": _rows(conn, KifuRawPlayerValue, KifuRawPlayerValue.id == 13167),
        }
    return result


def _business(snapshot):
    return {key: value for key, value in snapshot.items() if key not in {"captured_at", "transaction_read_only"}}


def _slot(album, side, survivor):
    return {
        "album_id": album["id"],
        "side": side,
        "column": side + "_player_id",
        "raw_player_value": album["player_" + side],
        "date_played": album["date_played"],
        "before_player_id": album[side + "_player_id"],
        "after_player_id": survivor,
        "album_full_row_sha256": canonical_sha256(album),
    }


def _validate(plan, preimage, expected_sha):
    key = pair_key(plan)
    pair = PAIRS[key]
    _fail(
        isinstance(expected_sha, str) and _SHA.fullmatch(expected_sha) and canonical_sha256(plan) == expected_sha,
        "exact canonical plan SHA-256 required",
    )
    _fail(
        plan.get("format") == FORMAT and plan.get("status") == "pending_independent_review",
        "unsupported proposal format/status",
    )
    _fail(plan.get("database") == DATABASES[plan["environment"]], "proposal database mismatch")
    _fail(isinstance(plan.get("producer_id"), str) and plan["producer_id"].strip(), "proposal producer required")
    _fail(_SHA.fullmatch(plan.get("identity_review_canonical_sha256", "")) is not None, "identity review SHA required")
    _fail(canonical_sha256(preimage) == plan.get("full_preimage_canonical_sha256"), "full preimage SHA changed")
    _fail(
        preimage.get("environment") == plan["environment"]
        and preimage.get("database") == plan["database"]
        and preimage.get("target_ids") == list(pair["ids"][plan["environment"]]),
        "preimage target changed",
    )
    full = preimage["full_rows"]
    _fail(set(full) == set(_MODELS), "full preimage table set changed")
    for table, rows in full.items():
        _fail(
            rows == sorted(rows, key=lambda row: row["id"]) and len({row["id"] for row in rows}) == len(rows),
            f"unordered or duplicate preimage rows: {table}",
        )
        _fail(
            all(set(row) == set(_MODELS[table].__table__.columns.keys()) for row in rows),
            f"incomplete preimage row: {table}",
        )
    survivor, retired = pair["ids"][plan["environment"]]
    protected_stub_id = None
    if key in {"fujisawa_kurano", "fujisawa_sawa"}:
        protected_stub_id = _FUJISAWA_STUB_IDS[plan["environment"]]
        protected_stub = preimage.get("protected_stub")
        _fail(isinstance(protected_stub, dict)
              and set(protected_stub) == {"owner", "declared_fk_rows", "raw_metadata_refs", "retained_raw_13167"},
              "Fujisawa protected stub preimage missing")
        _fail(len(protected_stub["owner"]) == 1
              and protected_stub["owner"][0]["id"] == protected_stub_id
              and protected_stub["owner"][0]["canonical_name"] == "藤泽朋斎"
              and set(protected_stub["owner"][0]) == set(KifuPlayer.__table__.columns.keys()),
              "Fujisawa protected stub owner changed")
        _fail(set(protected_stub["declared_fk_rows"]) == {f"{table}.{column}" for table, column in _FKS}
              and all(not rows for rows in protected_stub["declared_fk_rows"].values())
              and protected_stub["raw_metadata_refs"] == [],
              "Fujisawa protected stub acquired a reference")
        retained_raw = protected_stub["retained_raw_13167"]
        _fail(len(retained_raw) == 1 and retained_raw[0]["id"] == 13167
              and set(retained_raw[0]) == set(KifuRawPlayerValue.__table__.columns.keys())
              and retained_raw[0]["raw_value"] == "藤泽朋斎"
              and isinstance(retained_raw[0]["review_metadata"], dict)
              and retained_raw[0]["review_metadata"].get("player_id") == survivor,
              "Fujisawa retained raw 13167 changed ownership")
    else:
        _fail("protected_stub" not in preimage, "unexpected protected stub scope")
    _fail(
        full["kifu_players"] == sorted([plan["survivor_player"], plan["retire_player"]], key=lambda row: row["id"]),
        "owner preimage differs from proposal",
    )
    _fail(
        (plan["survivor_player"]["canonical_name"], plan["retire_player"]["canonical_name"]) == pair["names"],
        "pinned canonical names changed",
    )
    _fail(not plan["retire_player"]["authoritative_pages"], "retired owner has authoritative pages")
    for table in ("kifu_player_names", "kifu_player_aliases", "kifu_name_research_evidence"):
        _fail(all(row["player_id"] != retired for row in full[table]), "retired owner has review/name/alias history")
    _fail(
        all(
            row["player_id"] in (survivor, retired)
            for rows in preimage["collision_preimages"].values()
            for row in rows
            if "player_id" in row
        )
        and all(row["id"] in (survivor, retired, protected_stub_id)
                for row in preimage["collision_preimages"]["players"]),
        "external identity collision",
    )
    _fail(plan.get("counts") == expected_counts(key), "pinned operation counts changed")
    updates, protected = [], []
    for row in full["kifu_albums"]:
        _fail(
            not (row["black_player_id"] in (survivor, retired) and row["white_player_id"] in (survivor, retired)),
            "self/opponent identity conflict",
        )
        for side in ("black", "white"):
            if row[side + "_player_id"] in (survivor, retired):
                (updates if row[side + "_player_id"] == retired else protected).append(_slot(row, side, survivor))
    operations = plan["operations"]
    _fail(
        set(operations)
        == {
            "album_fk_updates",
            "raw_metadata_updates",
            "insert_alias_if_exact_preimage_still_absent",
            "delete_empty_unreviewed_player_after_repoints",
        },
        "unexpected operation",
    )
    _fail(
        operations["album_fk_updates"] == updates
        and plan["protected_existing_slots"] == protected
        and (len(updates), len(protected)) == pair["counts"],
        "exact album slot set changed",
    )
    _fail(operations["delete_empty_unreviewed_player_after_repoints"] == plan["retire_player"], "deleted owner changed")
    alias = {"player_id": survivor, "alias": pair["names"][1], "normalized_alias": normalize_alias(pair["names"][1])}
    _fail(operations["insert_alias_if_exact_preimage_still_absent"] == alias, "alias insertion changed")
    _fail(
        not any(
            row["normalized_alias"] == alias["normalized_alias"]
            for row in full["kifu_player_aliases"] + preimage["collision_preimages"]["aliases"]
        ),
        "alias already exists",
    )
    raw_updates = operations["raw_metadata_updates"]
    raw_ids = pair["raw_ids"] if "raw_ids" in pair else (pair["raw_id"],)
    expected_raw = []
    for raw_id in raw_ids:
        raw = next((row for row in full["kifu_raw_player_values"] if row["id"] == raw_id), None)
        _fail(
            raw is not None
            and isinstance(raw["review_metadata"], dict)
            and raw["review_metadata"].get("player_id") == retired,
            "old raw metadata reference changed",
        )
        expected_raw.append({
            "raw_id": raw["id"], "raw_value": raw["raw_value"], "before_full_row": raw,
            "before_review_metadata": raw["review_metadata"],
            "after_review_metadata": {**raw["review_metadata"], "player_id": survivor},
            "columns_allowed_to_change": ["review_metadata"],
            "preserve_review_status": raw["review_status"],
        })
    _fail(raw_updates == expected_raw, "only pinned raw metadata.player_id values may change")
    _fail(
        [
            row["id"]
            for row in full["kifu_raw_player_values"]
            if isinstance(row["review_metadata"], dict) and str(row["review_metadata"].get("player_id")) == str(retired)
        ]
        == list(raw_ids),
        "unexpected retired metadata references",
    )
    _fail(plan["declared_fk_inventory"] == preimage["declared_player_fks"], "proposal FK inventory changed")
    _fail(
        plan["protected_table_full_row_hashes"] == {table: canonical_sha256(full[table]) for table in _PROTECTED},
        "protected full-row hashes changed",
    )
    return key


def _check_review(plan, review):
    _fail(
        isinstance(review, dict)
        and review.get("format") == REVIEW_FORMAT
        and review.get("status") == "independent-approved",
        "independent-approved review required",
    )
    _fail(
        review.get("plan_sha256") == canonical_sha256(plan)
        and review.get("full_preimage_canonical_sha256") == plan["full_preimage_canonical_sha256"]
        and review.get("identity_review_canonical_sha256") == plan["identity_review_canonical_sha256"],
        "review does not bind the exact plan/preimage/identity evidence",
    )
    _fail(
        review.get("producer_id") == plan["producer_id"]
        and isinstance(review.get("reviewer_id"), str)
        and review["reviewer_id"].strip()
        and review["reviewer_id"] != plan["producer_id"],
        "independent reviewer required",
    )
    _fail(
        all(
            isinstance(review.get(field), str) and review[field].strip()
            for field in ("reviewer_model", "reviewed_at", "conclusion")
        ),
        "complete review attribution required",
    )
    try:
        reviewed_at = datetime.fromisoformat(review["reviewed_at"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise BatchError("invalid review timestamp") from exc
    _fail(reviewed_at.tzinfo is not None, "review timestamp timezone required")


def _capture_match(conn, plan, expected):
    actual = capture(conn, plan["environment"], pair_key(plan))
    _fail(_business(actual) == _business(expected), "complete bounded preimage/after-image changed")
    return actual


def _check_before(conn, plan, preimage):
    _capture_match(conn, plan, preimage)
    retired = plan["retire_player"]["id"]
    history = conn.scalar(
        select(KifuNameChange.id)
        .where(KifuNameChange.target_table == KifuPlayer.__tablename__, KifuNameChange.target_row_id == retired)
        .limit(1)
    )
    _fail(history is None, "retired owner has earlier audit history")


def _readonly(engine):
    conn = engine.connect()
    if engine.dialect.name == "postgresql":
        conn = conn.execution_options(isolation_level="REPEATABLE READ", postgresql_readonly=True)
    return conn


def check(engine, plan, preimage, *, expected_plan_sha256):
    _validate(plan, preimage, expected_plan_sha256)
    with _readonly(engine) as conn, conn.begin():
        _check_before(conn, plan, preimage)
    return {"status": "checked", "plan_sha256": expected_plan_sha256, "counts": plan["counts"]}


def _changes(plan, preimage, alias_image):
    changes = []
    albums = {row["id"]: row for row in preimage["full_rows"]["kifu_albums"]}
    after_albums = {}
    for slot in plan["operations"]["album_fk_updates"]:
        row_id = slot["album_id"]
        after_albums.setdefault(row_id, deepcopy(albums[row_id]))[slot["column"]] = slot["after_player_id"]
    for row_id in sorted(after_albums):
        changes.append((KifuAlbum, row_id, albums[row_id], after_albums[row_id]))
    for raw in plan["operations"]["raw_metadata_updates"]:
        changes.append(
            (
                KifuRawPlayerValue,
                raw["raw_id"],
                raw["before_full_row"],
                {**raw["before_full_row"], "review_metadata": raw["after_review_metadata"]},
            )
        )
    changes.append((KifuPlayerAlias, alias_image["id"], None, alias_image))
    changes.append((KifuPlayer, plan["retire_player"]["id"], plan["retire_player"], None))
    return changes


def _postimage(plan, preimage, alias_image):
    result = deepcopy(preimage)
    for model, row_id, _before, after in _changes(plan, preimage, alias_image):
        rows = [row for row in result["full_rows"][model.__tablename__] if row["id"] != row_id]
        if after is not None:
            rows.append(after)
        result["full_rows"][model.__tablename__] = sorted(rows, key=lambda row: row["id"])
    albums = {row["id"]: row for row in result["full_rows"]["kifu_albums"]}
    result["exact_raw_album_scope"] = [albums.get(row["id"], row) for row in result["exact_raw_album_scope"]]
    result["collision_preimages"]["players"] = [
        row for row in result["collision_preimages"]["players"] if row["id"] != plan["retire_player"]["id"]
    ]
    result["collision_preimages"]["aliases"] = sorted(
        result["collision_preimages"]["aliases"] + [alias_image], key=lambda row: row["id"]
    )
    return result


def _cas(conn, model, row_id, before, after):
    table = model.__table__
    _fail(_image(conn, table, row_id) == before, f"full row compare-and-swap failed: {table.name}:{row_id}")
    if before is None:
        _fail(after is not None, "invalid empty change")
        conn.execute(table.insert().values(**_values_for_table(table, after)))
    elif after is None:
        _fail(conn.execute(table.delete().where(table.c.id == row_id)).rowcount == 1, "delete CAS failed")
    else:
        changed = {field: value for field, value in after.items() if before[field] != value}
        clause = table.c.id == row_id
        # Every write is under table locks, with a complete preceding image check.
        # Scalar FK writes also compare the previous value in the UPDATE itself.
        for field in changed:
            if field in {"black_player_id", "white_player_id"}:
                clause = clause & (table.c[field] == before[field])
        _fail(
            conn.execute(table.update().where(clause).values(**_values_for_table(table, changed))).rowcount == 1,
            "update CAS failed",
        )
    _fail(_image(conn, table, row_id) == after, "written full after-image differs")


def _audit_registry(conn):
    registry = {
        "format": AUDIT_FORMAT,
        "purpose": "bounded duplicate identity merge audit",
        "pairs": json.loads(json.dumps(PAIRS)),
    }
    sha = canonical_sha256(registry)
    table = KifuNameSourceRegistry.__table__
    row_id = conn.scalar(select(table.c.id).where(table.c.version == "player-duplicate-v1", table.c.sha256 == sha))
    if row_id is None:
        row_id, image = _insert(
            conn, KifuNameSourceRegistry, {"version": "player-duplicate-v1", "sha256": sha, "registry": registry}
        )
    else:
        image = _image(conn, table, row_id)
        _fail(image["registry"] == registry, "audit registry changed")
    return row_id, image


def _lock_audit(conn):
    if conn.dialect.name == "postgresql":
        conn.exec_driver_sql("LOCK TABLE kifu_name_batches, kifu_name_changes IN SHARE ROW EXCLUSIVE MODE")


def _assert_retired_empty(conn, plan):
    retired = plan["retire_player"]["id"]
    for table, column in _FKS:
        model = _MODELS[table]
        _fail(
            conn.scalar(select(model.id).where(model.__table__.c[column] == retired).limit(1)) is None,
            "retired owner still has a declared reference",
        )
    _fail(
        conn.scalar(
            select(KifuRawPlayerValue.id)
            .where(cast(KifuRawPlayerValue.review_metadata["player_id"].as_string(), String) == str(retired))
            .limit(1)
        )
        is None,
        "retired owner still has metadata references",
    )
    _fail(_image(conn, KifuPlayer.__table__, retired) == plan["retire_player"], "retired owner changed before deletion")


def _check_applied(conn, batch, *, require_review=True):
    artifact = batch["reviewed_artifact"]
    _fail(isinstance(artifact, dict) and artifact.get("format") == AUDIT_FORMAT, "not a bounded duplicate batch")
    plan, preimage = artifact["plan"], artifact["preimage"]
    _validate(plan, preimage, batch["bundle_sha256"])
    if require_review:
        _check_review(plan, artifact["review"])
    _fail(
        batch["status"] == "applied" and batch["inventory_sha256"] == plan["full_preimage_canonical_sha256"],
        "batch status/preimage changed",
    )
    registry = artifact["audit_registry"]
    _fail(
        batch["source_registry_id"] == registry["id"]
        and _image(conn, KifuNameSourceRegistry.__table__, registry["id"]) == registry,
        "audit registry image changed",
    )
    alias = artifact["alias_image"]
    values = plan["operations"]["insert_alias_if_exact_preimage_still_absent"]
    _fail(
        set(alias) == set(KifuPlayerAlias.__table__.columns.keys())
        and all(alias.get(field) == value for field, value in values.items())
        and type(alias["id"]) is int
        and alias["id"] > 0,
        "receipt alias changed",
    )
    expected = _changes(plan, preimage, alias)
    ledger = (
        conn.execute(
            select(KifuNameChange.__table__)
            .where(KifuNameChange.batch_id == batch["id"])
            .order_by(KifuNameChange.sequence)
        )
        .mappings()
        .all()
    )
    _fail(len(ledger) == len(expected), "incomplete duplicate change ledger")
    for sequence, (row, (model, row_id, before, after)) in enumerate(zip(ledger, expected), 1):
        _fail(
            row["sequence"] == sequence
            and row["target_table"] == model.__tablename__
            and row["target_row_id"] == row_id
            and row["before_image"] == before
            and row["after_image"] == after,
            "duplicate change ledger differs from signed plan/receipt",
        )
        _fail(_image(conn, model.__table__, row_id) == after, "complete current after-image changed")
    postimage = _postimage(plan, preimage, alias)
    _fail(artifact["postimage_sha256"] == canonical_sha256(_business(postimage)), "receipt postimage hash changed")
    _capture_match(conn, plan, postimage)
    return expected


def run(engine, plan, preimage, *, command, expected_plan_sha256, review=None, actor_id=None):
    """Run a real rollback-only dry transaction or one independently approved apply."""
    _fail(command in {"dry-run", "apply"}, "unsupported execution command")
    _validate(plan, preimage, expected_plan_sha256)
    if command == "apply" or review is not None:
        _check_review(plan, review)
    if command == "apply":
        _fail(isinstance(actor_id, str) and actor_id.strip(), "apply actor attribution required")
    try:
        with _locked_write(engine) as conn:
            _lock_audit(conn)
            previous = (
                conn.execute(select(KifuNameBatch.__table__).where(KifuNameBatch.bundle_sha256 == expected_plan_sha256))
                .mappings()
                .one_or_none()
            )
            if previous is not None:
                _fail(
                    previous["reviewed_artifact"].get("plan") == plan
                    and previous["reviewed_artifact"].get("preimage") == preimage
                    and (review is None or previous["reviewed_artifact"].get("review") == review),
                    "applied reviewed artifact differs",
                )
                _check_applied(conn, previous)
                return {
                    "status": "already_applied",
                    "batch_id": previous["id"],
                    "change_count": 0,
                    "alias_id": previous["reviewed_artifact"]["alias_image"]["id"],
                    "counts": plan["counts"],
                }
            _check_before(conn, plan, preimage)
            registry_id, registry = _audit_registry(conn)
            artifact = {
                "format": AUDIT_FORMAT,
                "plan": plan,
                "preimage": preimage,
                "review": review,
                "actor_id": actor_id,
                "audit_registry": registry,
            }
            batch_id, _ = _insert(
                conn,
                KifuNameBatch,
                {
                    "bundle_sha256": expected_plan_sha256,
                    "inventory_sha256": plan["full_preimage_canonical_sha256"],
                    "source_registry_id": registry_id,
                    "reviewed_artifact": artifact,
                    "status": "pending",
                },
            )
            # The alias is installed after all original rows are checked, and before
            # retiring the old owner. Its generated ID and timestamp are receipted.
            alias_id, alias = _insert(
                conn, KifuPlayerAlias, plan["operations"]["insert_alias_if_exact_preimage_still_absent"]
            )
            changes = _changes(plan, preimage, alias)
            for sequence, (model, row_id, before, after) in enumerate(changes, 1):
                if model is KifuPlayerAlias:
                    _fail(_image(conn, model.__table__, row_id) == after, "new alias image changed")
                else:
                    if model is KifuPlayer:
                        _assert_retired_empty(conn, plan)
                    _cas(conn, model, row_id, before, after)
                _record_change(conn, batch_id, sequence, model, row_id, before, after)
            artifact = {
                **artifact,
                "alias_image": alias,
                "postimage_sha256": canonical_sha256(_business(_postimage(plan, preimage, alias))),
            }
            conn.execute(
                KifuNameBatch.__table__.update()
                .where(KifuNameBatch.id == batch_id)
                .values(reviewed_artifact=artifact, status="applied", applied_at=datetime.now(timezone.utc))
            )
            batch = conn.execute(select(KifuNameBatch.__table__).where(KifuNameBatch.id == batch_id)).mappings().one()
            # Dry runs may use pending data; they verify every data/ledger image with
            # the same checks, but cannot persist any approval or batch.
            _check_applied(conn, batch, require_review=command == "apply" or review is not None)
            receipt = {
                "status": "applied" if command == "apply" else "rolled_back",
                "batch_id": batch_id,
                "alias_id": alias_id,
                "change_count": len(changes),
                "counts": plan["counts"],
                "plan_sha256": expected_plan_sha256,
                "postimage_sha256": artifact["postimage_sha256"],
            }
            if command == "dry-run":
                conn.rollback()
    except IntegrityError as exc:
        raise BatchError("dependent row or collision blocks atomic duplicate merge") from exc
    if command == "dry-run":
        with _readonly(engine) as conn, conn.begin():
            _check_before(conn, plan, preimage)
            _fail(
                conn.scalar(select(KifuNameBatch.id).where(KifuNameBatch.bundle_sha256 == expected_plan_sha256))
                is None,
                "dry batch did not roll back",
            )
    return receipt


def verify(engine, batch_id):
    """Read-only verification of signed inputs, exact ledger and complete scope."""
    with _readonly(engine) as conn, conn.begin():
        batch = (
            conn.execute(select(KifuNameBatch.__table__).where(KifuNameBatch.id == batch_id)).mappings().one_or_none()
        )
        _fail(batch is not None, "duplicate batch not found")
        changes = _check_applied(conn, batch)
        return {
            "status": "verified",
            "batch_id": batch_id,
            "change_count": len(changes),
            "alias_id": batch["reviewed_artifact"]["alias_image"]["id"],
            "counts": batch["reviewed_artifact"]["plan"]["counts"],
        }


def undo(engine, batch_id):
    """Restore the deleted owner first; reject any later change before writing."""
    try:
        with _locked_write(engine) as conn:
            _lock_audit(conn)
            batch = (
                conn.execute(select(KifuNameBatch.__table__).where(KifuNameBatch.id == batch_id))
                .mappings()
                .one_or_none()
            )
            _fail(batch is not None, "duplicate batch not found")
            changes = _check_applied(conn, batch)
            artifact = batch["reviewed_artifact"]
            undo_changes = [changes[-1], *reversed(changes[:-2]), changes[-2]]
            for model, row_id, before, after in undo_changes:
                _cas(conn, model, row_id, after, before)
            _capture_match(conn, artifact["plan"], artifact["preimage"])
            conn.execute(KifuNameBatch.__table__.update().where(KifuNameBatch.id == batch_id).values(status="undone"))
            return {"status": "undone", "batch_id": batch_id, "reverted": len(changes), "skipped": 0}
    except IntegrityError as exc:
        raise BatchError("dependent row blocks atomic duplicate undo") from exc
