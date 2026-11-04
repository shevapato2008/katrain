"""Audited same-row correction for PROD Numadate 5364; no undo is provided.

Only the two exact source/basis0 rows are superseded. Original repairs, names,
SGFs and native publication receipts remain immutable historical evidence.
"""

from collections.abc import Mapping
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import re
from time import monotonic

from sqlalchemy import LargeBinary, Text, cast, func, or_, select, text

from katrain.web.core import models_db as m
from katrain.web.kifu import historical_rank_repair as repair, historical_ranks as ranks, name_batch
from katrain.web.kifu.name_candidates import canonical_sha256 as digest
from katrain.web.kifu.name_evidence import registry_sha256
from katrain.web.kifu.name_first_pass import persisted_eligible
from katrain.web.kifu.identity import normalize_alias
from katrain.web.kifu.source_rank_normalization import require, snapshot_digest

FORMAT = "kifu-numadate-canonical-correction-v1"
MARKER_VERSION = "numadate-canonical-first-pass-correction-v1"
PARENT_BINDING_VERSION = "numadate-canonical-correction-parent-v1"
PLAYER_ID, ALIAS_ID = 5364, 58
OLD_NAME, NEW_NAME = "沼官沙辉哉", "沼馆沙辉哉"
PROD_DATABASE = "katrain_prod_20260725"
PROTECTED_CODE_SHA256 = "b009f59cb7160689a2ee48ebc1ac328ebbffe3fdb1ccb0217b42183e977d7300"
PROFILE_URL = "https://www.nihonkiin.or.jp/player/htm/ki000430.html"
MAX_AUTHORITY_BYTES, MAX_NAME_BYTES = 12 * 1024 * 1024, 512 * 1024
MAX_SECONDS = 45
SCOPE = (
    (124026, "black", "41442702", "2014-03-06", "二段", OLD_NAME, 2189, 186520),
    (178495, "white", "91342440", "2026-10-15", "七段", NEW_NAME, 2518, 233062),
)
ALBUM_IDS = [row[0] for row in SCOPE]
LANGUAGES = {"cn", "tw", "jp", "en", "ko"}
DISPLAYS = {"cn": NEW_NAME, "tw": "沼館沙輝哉", "jp": "沼舘沙輝哉", "en": "Sakiya Numadate", "ko": "누마다테 사키야"}
OPERATOR_FILES = (
    "katrain/web/kifu/numadate_canonical_correction.py",
    "scripts/correct_kifu_numadate.py",
    "katrain/web/kifu/name_batch.py",
    "katrain/web/kifu/player_ranks.py",
    "katrain/web/api/v1/endpoints/kifu.py",
    "katrain/kifu_ingest/catalog.py",
)
_PLAN_FIELDS = {
    "format",
    "operator_code_sha256",
    "protected_rank_code_sha256",
    "database_identity",
    "fixed_person",
    "owner_before",
    "owner_after",
    "aliases_before",
    "old_alias_create",
    "identity_review",
    "targets",
    "old_names",
    "name_package",
    "native_predecessor",
    "reference_sets",
    "approved_counts",
    "original_package",
    "matched_at",
    "identity_transition_sha256",
    "content_sha256",
    "final_approval",
}
_SHA = re.compile(r"^[a-f0-9]{64}$")


def operator_code_sha256():
    root = Path(__file__).resolve().parents[3]
    return digest([{"path": path, "sha256": sha256((root / path).read_bytes()).hexdigest()} for path in OPERATOR_FILES])


class _Budget:
    def __init__(self):
        self.deadline = monotonic() + MAX_SECONDS
        self.authority_bytes = 0

    def check(self):
        require(monotonic() < self.deadline, "canonical correction operation deadline exceeded")

    def reserve(self, size):
        self.check()
        self.authority_bytes += size
        require(self.authority_bytes <= MAX_AUTHORITY_BYTES, "canonical correction authority budget exceeded")


def _bytes(conn, expression):
    value = cast(expression, Text)
    return func.coalesce(
        func.octet_length(value) if conn.dialect.name == "postgresql" else func.length(cast(value, LargeBinary)), 0
    )


def _rows(conn, model, predicate, *, limit, budget, cap=MAX_AUTHORITY_BYTES, columns=None):
    """Count and size JSON/text before fetching a bounded exact predicate."""
    budget.check()
    table = model.__table__ if hasattr(model, "__table__") else model
    selected = list(table.c) if columns is None else list(columns)
    size = sum((_bytes(conn, col) for col in selected), 0)
    count, total = conn.execute(
        select(func.count(), func.coalesce(func.sum(size), 0)).select_from(table).where(predicate)
    ).one()
    require(count <= limit and total <= cap, "canonical correction selected material resource limit")
    budget.reserve(total)
    return [
        repair._json_image(dict(r))
        for r in conn.execute(select(*selected).where(predicate).order_by(table.c.id)).mappings()
    ]


def _one(conn, model, row_id, budget, *, cap=MAX_AUTHORITY_BYTES):
    rows = _rows(conn, model, model.__table__.c.id == row_id, limit=1, budget=budget, cap=cap)
    require(len(rows) == 1, "canonical correction exact row missing")
    return rows[0]


def _database_identity(conn):
    result = repair._database_identity(conn)
    require(
        result["dialect"] == "sqlite" or result.get("database") == PROD_DATABASE,
        "canonical correction requires the fixed PROD database",
    )
    return result


@contextmanager
def _readonly(engine):
    with engine.connect() as conn:
        if conn.dialect.name == "postgresql":
            conn = conn.execution_options(isolation_level="REPEATABLE READ")
            # This is the first SQL statement; no identity query precedes it.
            conn.exec_driver_sql("SET TRANSACTION READ ONLY")
            conn.exec_driver_sql("SET LOCAL statement_timeout = '5s'")
        else:
            require(conn.dialect.name == "sqlite", "canonical correction database unsupported")
            conn.exec_driver_sql("PRAGMA query_only=ON")
        try:
            yield conn
        finally:
            conn.rollback()
            if conn.dialect.name == "sqlite":
                conn.exec_driver_sql("PRAGMA query_only=OFF")
                conn.rollback()


def _check_codes(plan=None, *, require_current_operator=True):
    require(repair._code_sha256() == PROTECTED_CODE_SHA256, "canonical correction protected rank code changed")
    if plan is not None:
        require(
            plan["protected_rank_code_sha256"] == PROTECTED_CODE_SHA256,
            "canonical correction protected rank code changed",
        )
        require(
            _SHA.fullmatch(str(plan["operator_code_sha256"])) is not None,
            "canonical correction historical operator code pin invalid",
        )
        if require_current_operator:
            require(
                plan["operator_code_sha256"] == operator_code_sha256(), "canonical correction operator code changed"
            )


def _independent(review, *, conclusion=None):
    require(
        isinstance(review, dict)
        and all(
            isinstance(review.get(k), str) and review[k].strip()
            for k in ("producer_id", "producer_model", "reviewer_id", "reviewer_model", "reviewed_at")
        )
        and review["producer_id"] != review["reviewer_id"],
        "canonical correction independent review missing",
    )
    ranks._utc(review["reviewed_at"])
    if conclusion is not None:
        require(review.get("conclusion") == conclusion, "canonical correction identity conclusion invalid")


def _identity_review(review):
    _independent(review, conclusion="same_existing_player_canonical_typo")
    require(
        set(review)
        == {
            "producer_id",
            "producer_model",
            "reviewer_id",
            "reviewer_model",
            "reviewed_at",
            "conclusion",
            "official_profile",
            "official_name",
            "latin_name",
            "career",
            "source_items",
            "same_player_id",
            "capture",
            "corroboration",
        },
        "canonical correction identity review shape invalid",
    )
    require(
        review["official_profile"] == "ki000430"
        and review["official_name"] == "沼舘沙輝哉"
        and review["latin_name"] == "NUMADATE, Sakiya"
        and review["same_player_id"] == PLAYER_ID
        and review["source_items"] == ["41442702", "91342440"]
        and review["career"] == {"professional_since": 2010, "second_dan": 2013, "seventh_dan": 2021}
        and isinstance(review["corroboration"], str)
        and len(review["corroboration"]) >= 40,
        "canonical correction source identity corroboration incomplete",
    )
    capture = review["capture"]
    require(
        isinstance(capture, dict)
        and set(capture) == {"url", "body_excerpt", "body_sha256"}
        and capture["url"] == PROFILE_URL
        and _SHA.fullmatch(str(capture["body_sha256"]))
        and "沼舘沙輝哉" in capture["body_excerpt"]
        and "NUMADATE" in capture["body_excerpt"]
        and ranks._json_size(review) <= MAX_NAME_BYTES,
        "canonical correction official capture invalid",
    )


def _owner_and_aliases(conn, budget, *, before):
    owner = _one(conn, m.KifuPlayer, PLAYER_ID, budget, cap=MAX_NAME_BYTES)
    require(
        owner["canonical_name"] == (OLD_NAME if before else NEW_NAME), "canonical correction player preimage changed"
    )
    p, a = m.KifuPlayer.__table__, m.KifuPlayerAlias.__table__
    names = [OLD_NAME, NEW_NAME]
    collisions = _rows(conn, p, p.c.canonical_name.in_(names), limit=1, budget=budget, cap=MAX_NAME_BYTES)
    require(len(collisions) == 1 and collisions[0]["id"] == PLAYER_ID, "canonical correction canonical collision")
    aliases = _rows(
        conn,
        a,
        or_(a.c.player_id == PLAYER_ID, a.c.normalized_alias.in_(names), a.c.alias.in_(names)),
        limit=64,
        budget=budget,
        cap=MAX_NAME_BYTES,
    )
    require(all(r["player_id"] == PLAYER_ID for r in aliases), "canonical correction alias collision")
    alias58 = [r for r in aliases if r["id"] == ALIAS_ID]
    require(
        len(alias58) == 1
        and alias58[0]["alias"] == NEW_NAME
        and alias58[0]["normalized_alias"] == normalize_alias(NEW_NAME),
        "canonical correction alias58 changed",
    )
    old = [r for r in aliases if r["normalized_alias"] == normalize_alias(OLD_NAME)]
    require(
        (not old) if before else (len(old) == 1 and old[0]["alias"] == OLD_NAME),
        "canonical correction old spelling alias changed",
    )
    return owner, aliases


def _live_targets(conn, budget, *, resource=None):
    a = m.KifuAlbum.__table__
    lengths = dict(
        conn.execute(select(a.c.id, ranks._body_length(conn, a.c.sgf_content)).where(a.c.id.in_(ALBUM_IDS))).all()
    )
    require(
        set(lengths) == set(ALBUM_IDS)
        and all(0 < n <= 256 * 1024 for n in lengths.values())
        and sum(lengths.values()) <= 512 * 1024,
        "canonical correction source body resource limit",
    )
    # Scalar/JSON budget is checked before fetching either exact original body.
    resource = resource if resource is not None else ranks.EvidenceBudget(max_bytes=512 * 1024)
    scalars = _rows(
        conn,
        a,
        a.c.id.in_(ALBUM_IDS),
        limit=2,
        budget=budget,
        cap=MAX_NAME_BYTES,
        columns=[c for c in a.c if c.name != "sgf_content"],
    )
    albums = {}
    for row in scalars:
        album = dict(row, sgf_bytes=lengths[row["id"]])
        album["sgf_content"] = ranks.load_rank_body(conn, album, resource=resource)
        albums[row["id"]] = album
    link_rows = _rows(
        conn, m.KifuAlbumSource, m.KifuAlbumSource.album_id.in_(ALBUM_IDS), limit=8, budget=budget, cap=MAX_NAME_BYTES
    )
    source_ids = {row["source_id"] for row in link_rows}
    sources = _rows(conn, m.KifuSource, m.KifuSource.id.in_(source_ids), limit=8, budget=budget, cap=MAX_NAME_BYTES)
    source_keys = {r["id"]: r["source_key"] for r in sources}
    links = {
        ident: [dict(row, source_key=source_keys[row["source_id"]]) for row in link_rows if row["album_id"] == ident]
        for ident in ALBUM_IDS
    }
    result = []
    for ident, side, item, day, raw_rank, raw_name, _, _ in SCOPE:
        album = albums[ident]
        require(
            album["source_path"] == f"data/kifu-album/19x19/{item}.sgf"
            and album[f"{side}_player_id"] == PLAYER_ID
            and album[f"player_{side}"] == raw_name
            and album[f"{side}_rank"] == raw_rank
            and album["date_played"] == day
            and repair._public(album),
            "canonical correction fixed source/FK/raw scope changed",
        )
        target = {"album": album, "side": side, "source_links": links[ident]}
        require(
            len(links[ident]) == 1 and links[ident][0]["source_key"] == "19x19",
            "canonical correction exact source link changed",
        )
        result.append((target, repair._album_image(album, links[ident]), sources))
    budget.check()
    return result


def _old_repair(conn, scope, budget, *, current=None):
    ident, side, _, _, _, _, batch_id, row_id = scope
    batch = _one(conn, m.KifuNameBatch, batch_id, budget, cap=repair.MAX_PART_BYTES + 16384)
    artifact = batch["reviewed_artifact"]
    require(
        batch["status"] == "applied" and isinstance(artifact, dict) and artifact.get("format") == repair.FORMAT,
        "canonical correction old repair authority missing",
    )
    part = repair._validate_part(artifact.get("part"))
    require(
        part["database_identity"] == _database_identity(conn)
        and batch["bundle_sha256"] == digest(part)
        and artifact == repair._artifact(part),
        "canonical correction old repair artifact changed",
    )
    selected = [c for c in part["changes"] if (c["album_id"], c["side"]) == (ident, side)]
    require(
        len(selected) == 1 and selected[0]["snapshot_before"] is None,
        "canonical correction old repair predecessor is not null",
    )
    changes = _rows(
        conn,
        m.KifuNameChange,
        (m.KifuNameChange.batch_id == batch_id)
        & (m.KifuNameChange.target_table == m.KifuAlbumRankSnapshot.__tablename__)
        & (m.KifuNameChange.target_row_id == row_id),
        limit=1,
        budget=budget,
        cap=MAX_NAME_BYTES,
    )
    require(
        len(changes) == 1 and changes[0]["before_image"] is None,
        "canonical correction old repair journal predecessor invalid",
    )
    journal, change = changes[0], selected[0]
    require(
        journal["sequence"] == part["changes"].index(change) + 1,
        "canonical correction old selected journal sequence changed",
    )
    old = journal["after_image"]
    require(
        isinstance(old, dict)
        and old["id"] == row_id
        and old["album_id"] == ident
        and old["side"] == side
        and old["native_batch_id"] == batch_id
        and old["publication_key"] == "historical-rank:" + batch["bundle_sha256"]
        and old["snapshot"] == change["snapshot_after"]
        and old["snapshot_sha256"] == old["snapshot"]["content_sha256"]
        and old["rank_fact_id"] is None,
        "canonical correction old repair selected afterimage changed",
    )
    ranks.validate_rank_decision(old["snapshot"])
    require(
        old["snapshot"]["origin"] == "source"
        and old["snapshot"]["basis"] == []
        and old["snapshot"]["player_ref"] == {"canonical_name": OLD_NAME}
        and change["basis_binding"]["target"]["player_id"] == PLAYER_ID
        and change["basis_binding"]["basis"] == [],
        "canonical correction old rank is not fixed source/basis0",
    )
    if current is not None:
        require(current == old, "canonical correction current old snapshot changed")
    return {"batch": batch, "part": part, "journal": journal, "selected_change": change}


def _json_selected(conn, batch_id, path, owner_id, lang, budget):
    """Fetch exactly one selected member from an old large name bundle."""
    require(path in {"bundle.candidates", "bundle.members"}, "canonical correction JSON path invalid")
    if conn.dialect.name == "postgresql":
        path_sql = "'{" + path.replace(".", ",") + "}'"
        source = f"jsonb_array_elements(b.reviewed_artifact::jsonb #> {path_sql}) AS s(value)"
        owner = "(s.value #>> '{owner,id}')::integer"
        lang_sql, value = "s.value->>'lang'", "s.value"
        size = "octet_length(s.value::text)"
    else:
        source = f"json_each(b.reviewed_artifact, '$.{path}') AS s"
        owner, lang_sql, value = "json_extract(s.value, '$.owner.id')", "json_extract(s.value, '$.lang')", "s.value"
        size = "length(cast(s.value AS blob))"
    base = f"FROM kifu_name_batches b, {source} WHERE b.id=:batch AND {owner}=:owner AND {lang_sql}=:lang"
    params = {"batch": batch_id, "owner": owner_id, "lang": lang}
    count, total = conn.execute(text(f"SELECT count(*),coalesce(sum({size}),0) {base}"), params).one()
    require(count == 1 and total <= MAX_NAME_BYTES, "canonical correction old name bundle membership ambiguous")
    budget.reserve(total)
    result = conn.execute(text(f"SELECT {value} {base}"), params).scalar_one()
    return json.loads(result) if isinstance(result, str) else result


def _old_names(conn, owner_before, budget, *, frozen=None):
    names = (
        _rows(
            conn, m.KifuPlayerName, m.KifuPlayerName.player_id == PLAYER_ID, limit=5, budget=budget, cap=MAX_NAME_BYTES
        )
        if frozen is None
        else [cell["name"] for cell in frozen]
    )
    require(
        len(names) == 5 and {n["lang"] for n in names} == LANGUAGES, "canonical correction old five names scope changed"
    )
    result = []
    for name in names:
        evidence = _one(conn, m.KifuNameResearchEvidence, name["evidence_id"], budget, cap=MAX_NAME_BYTES)
        payload = evidence["research_payload"]
        require(
            isinstance(payload, dict) and isinstance(payload.get("first_pass"), dict),
            "canonical correction old name first-pass proof missing",
        )
        batch_id = payload["first_pass"]["batch_id"]
        bt = m.KifuNameBatch.__table__
        meta = _rows(
            conn,
            bt,
            bt.c.id == batch_id,
            limit=1,
            budget=budget,
            cap=MAX_NAME_BYTES,
            columns=[c for c in bt.c if c.name != "reviewed_artifact"],
        )
        require(len(meta) == 1 and meta[0]["status"] == "applied", "canonical correction old name batch missing")
        candidate = _json_selected(conn, batch_id, "bundle.candidates", PLAYER_ID, name["lang"], budget)
        member = _json_selected(conn, batch_id, "bundle.members", PLAYER_ID, name["lang"], budget)
        require(
            candidate == payload.get("candidate")
            and member == {"owner": {"kind": "player", "id": PLAYER_ID}, "lang": name["lang"]},
            "canonical correction old name membership changed",
        )
        # Verify the research hash against the actual selected artifact hash list.
        if conn.dialect.name == "postgresql":
            membership = "SELECT count(*) FROM kifu_name_batches b,jsonb_array_elements_text(b.reviewed_artifact::jsonb->'research_hashes') AS h(value) WHERE b.id=:batch AND h.value=:sha"
        else:
            membership = "SELECT count(*) FROM kifu_name_batches b,json_each(b.reviewed_artifact,'$.research_hashes') AS h WHERE b.id=:batch AND h.value=:sha"
        require(
            conn.scalar(text(membership), {"batch": batch_id, "sha": digest(payload.get("research"))}) == 1,
            "canonical correction old name research membership changed",
        )
        predicate = (m.KifuNameChange.batch_id == batch_id) & or_(
            (m.KifuNameChange.target_table == m.KifuPlayerName.__tablename__)
            & (m.KifuNameChange.target_row_id == name["id"]),
            (m.KifuNameChange.target_table == m.KifuNameResearchEvidence.__tablename__)
            & (m.KifuNameChange.target_row_id == evidence["id"]),
        )
        changes = _rows(conn, m.KifuNameChange, predicate, limit=2, budget=budget, cap=MAX_NAME_BYTES)
        mapped = {(r["target_table"], r["target_row_id"]): r for r in changes}
        batch = {**meta[0], "reviewed_artifact": {}}
        compiled = ({digest(candidate)}, {digest(payload["research"])}, [])
        require(
            len(changes) == 2
            and persisted_eligible(name, evidence, "player", owner_before, batch, mapped, compiled=compiled),
            "canonical correction old name creation authority changed",
        )
        cell = {
            "name": name,
            "evidence": evidence,
            "batch": meta[0],
            "candidate": candidate,
            "member": member,
            "journals": changes,
        }
        result.append(cell)
    require(ranks._json_size(result) <= MAX_NAME_BYTES, "canonical correction old name evidence budget exceeded")
    return result


def _native_predecessor(conn, budget):
    """Exact-source queries in the existing native binding registry, no bodies."""
    registry = _one(conn, m.KifuNameSourceRegistry, 385, budget, cap=MAX_NAME_BYTES)
    require(registry["version"] == "kifu-incremental-binding-v1", "canonical correction native registry changed")
    if conn.dialect.name == "postgresql":
        arr = "jsonb_array_elements(b.reviewed_artifact::jsonb->'sources') AS s(value)"
        item, key, value = "s.value->>'source_item_id'", "s.value->>'source_key'", "s.value"
        fmt = "b.reviewed_artifact->>'publication_format'"
    else:
        arr = "json_each(b.reviewed_artifact,'$.sources') AS s"
        item, key, value = "json_extract(s.value,'$.source_item_id')", "json_extract(s.value,'$.source_key')", "s.value"
        fmt = "json_extract(b.reviewed_artifact,'$.publication_format')"
    base = f"FROM kifu_name_batches b, {arr} WHERE b.source_registry_id=385 AND b.status='applied' AND {fmt} IN ('kifu-incremental-manifest-v1','kifu-incremental-manifest-v2') AND {key}='19x19' AND {item} IN ('41442702','91342440')"
    count = conn.scalar(text("SELECT count(*) " + base))
    require(count == 1, "canonical correction new native predecessor/dependency")
    source_size = (
        f"octet_length({value}::text)" if conn.dialect.name == "postgresql" else f"length(cast({value} AS blob))"
    )
    size = conn.scalar(text(f"SELECT coalesce(sum({source_size}),0) {base}"))
    require(size <= MAX_NAME_BYTES, "canonical correction native selected source resource limit")
    budget.reserve(size)
    rows = conn.execute(text(f"SELECT b.id,{value} AS source {base}")).mappings().all()
    require(rows[0]["id"] == 876, "canonical correction native876 missing")
    source = rows[0]["source"]
    source = json.loads(source) if isinstance(source, str) else source
    require(
        source["source_item_id"] == "91342440" and source["album_id"] == 178495,
        "canonical correction native exact source changed",
    )
    bt = m.KifuNameBatch.__table__
    expressions = {
        "publication_format": bt.c.reviewed_artifact["publication_format"],
        "publication_key": bt.c.reviewed_artifact["publication_key"],
        "manifest_sha256": bt.c.reviewed_artifact["manifest_sha256"],
        "receipt": bt.c.reviewed_artifact["receipt"],
        "rank_bindings": bt.c.reviewed_artifact["rank_bindings"],
    }
    size = conn.scalar(select(sum((_bytes(conn, e) for e in expressions.values()), 0)).where(bt.c.id == 876))
    require(
        size is not None and size <= MAX_NAME_BYTES, "canonical correction native selected evidence budget exceeded"
    )
    budget.reserve(size)
    selected = dict(
        conn.execute(
            select(bt.c.bundle_sha256, bt.c.status, *[v.label(k) for k, v in expressions.items()]).where(bt.c.id == 876)
        )
        .mappings()
        .one()
    )
    presence_sql = (
        "SELECT reviewed_artifact::jsonb ? 'rank_bindings' FROM kifu_name_batches WHERE id=876"
        if conn.dialect.name == "postgresql"
        else "SELECT json_type(reviewed_artifact,'$.rank_bindings') IS NOT NULL FROM kifu_name_batches WHERE id=876"
    )
    selected["rank_bindings_present"] = bool(conn.scalar(text(presence_sql)))
    require(
        selected["publication_format"] == "kifu-incremental-manifest-v1"
        and not selected["rank_bindings_present"]
        and selected["rank_bindings"] is None
        and selected["manifest_sha256"] == selected["bundle_sha256"]
        and isinstance(selected["receipt"], dict),
        "canonical correction native rank predecessor forbidden",
    )
    # Select the exact logical game, never game zero or the whole manifest.
    if conn.dialect.name == "postgresql":
        arrg = "jsonb_array_elements(b.reviewed_artifact::jsonb #> '{logical_manifest,games}') AS g(value)"
        pred = "g.value->>'source_item_id'='91342440' AND g.value->>'source_key'='19x19'"
        gv = "g.value"
    else:
        arrg = "json_each(b.reviewed_artifact,'$.logical_manifest.games') AS g"
        pred = "json_extract(g.value,'$.source_item_id')='91342440' AND json_extract(g.value,'$.source_key')='19x19'"
        gv = "g.value"
    game_base = f"FROM kifu_name_batches b,{arrg} WHERE b.id=876 AND {pred}"
    game_size = f"octet_length({gv}::text)" if conn.dialect.name == "postgresql" else f"length(cast({gv} AS blob))"
    count, size = conn.execute(text(f"SELECT count(*),coalesce(sum({game_size}),0) {game_base}")).one()
    require(count == 1 and size <= MAX_NAME_BYTES, "canonical correction native selected logical game resource limit")
    budget.reserve(size)
    game_rows = conn.execute(text(f"SELECT {gv} {game_base}")).scalars().all()
    require(len(game_rows) == 1, "canonical correction native exact logical game missing")
    game = json.loads(game_rows[0]) if isinstance(game_rows[0], str) else game_rows[0]
    require(
        ranks._json_size(game) <= MAX_NAME_BYTES
        and not any(k in game for k in ("rank_snapshots", "rank_observations")),
        "canonical correction native rank payload predecessor forbidden",
    )
    require(
        all(
            game.get(k) == source.get(k)
            for k in ("source_key", "source_item_id", "origin_path", "raw_sha256", "sgf_sha256")
        ),
        "canonical correction native source/logical game changed",
    )
    journal_count = conn.scalar(
        select(func.count())
        .select_from(m.KifuNameChange)
        .where(m.KifuNameChange.batch_id == 876, m.KifuNameChange.target_table == m.KifuAlbumRankSnapshot.__tablename__)
    )
    require(journal_count == 0, "canonical correction native snapshot predecessor forbidden")
    if conn.dialect.name == "postgresql":
        require(
            selected["bundle_sha256"] == "0f64c2b366a0d9ba59b452d4aac4148dc5609d19c57c6befa1deacde06459e67"
            and selected["publication_key"] == "19x19-event-recovery-870a06d9f6b3f234b354a5f4"
            and digest(selected["receipt"]) == "674c34b37294cca5929bdf8ba6aaa528c3214c50ad630712ddc999ba5def5f0f",
            "canonical correction original native876 pins changed",
        )
    return {
        "registry": registry,
        "batch_id": 876,
        "source": source,
        "selected": selected,
        "logical_game": game,
        "snapshot_journal_count": journal_count,
    }


def _references(conn, budget):
    a, s, f = m.KifuAlbum.__table__, m.KifuAlbumRankSnapshot.__table__, m.KifuPlayerRankHistory.__table__
    slots = []
    for side in ("black", "white"):
        ids = list(conn.scalars(select(a.c.id).where(a.c[f"{side}_player_id"] == PLAYER_ID).order_by(a.c.id).limit(4)))
        slots.extend({"album_id": i, "side": side} for i in ids)
    facts = list(conn.scalars(select(f.c.id).where(f.c.player_id == PLAYER_ID).order_by(f.c.id).limit(2)))
    snapshots = list(
        conn.scalars(
            select(s.c.id)
            .where(or_(*[(s.c.album_id == row[0]) & (s.c.side == row[1]) for row in SCOPE]))
            .order_by(s.c.id)
            .limit(3)
        )
    )
    require(
        sorted(slots, key=lambda r: (r["album_id"], r["side"])) == [{"album_id": r[0], "side": r[1]} for r in SCOPE]
        and not facts
        and snapshots == [186520, 233062],
        "canonical correction requires exactly two slots and zero facts",
    )
    budget.check()
    return {"slots": slots, "fact_ids": facts, "snapshot_ids": snapshots}


def _transition(plan):
    return digest(
        {
            key: plan[key]
            for key in (
                "fixed_person",
                "database_identity",
                "owner_before",
                "owner_after",
                "aliases_before",
                "old_alias_create",
                "identity_review",
                "old_names",
            )
        }
        | {
            "sources": [
                {k: t[k] for k in ("album_before", "sources", "snapshot_before", "old_authority")}
                for t in plan["targets"]
            ]
        }
    )


def _marker(plan, cell, research):
    name, evidence, prior = cell["name"], cell["evidence"], cell["candidate"]
    return {
        "version": MARKER_VERSION,
        "identity_transition_sha256": plan["identity_transition_sha256"],
        "player_id": PLAYER_ID,
        "lang": name["lang"],
        "name_preimage_sha256": digest(name),
        "prior_evidence_id": evidence["id"],
        "prior_evidence_sha256": digest(evidence),
        "prior_candidate_sha256": digest(prior),
        "prior_batch_id": cell["batch"]["id"],
        "prior_bundle_sha256": cell["batch"]["bundle_sha256"],
        "prior_revision": name["revision"],
        "owner_before_sha256": digest(plan["owner_before"]),
        "owner_after_sha256": digest(plan["owner_after"]),
        "source_input_sha256": digest(research["source_input"]),
    }


def _name_package(plan, package):
    package = deepcopy(package)
    require(
        set(package) == {"bundle", "registry", "inventory", "evidence_records"}
        and ranks._json_size(package) <= MAX_NAME_BYTES,
        "canonical correction name package shape/resource invalid",
    )
    bundle, registry, inventory, records = (package[k] for k in ("bundle", "registry", "inventory", "evidence_records"))
    require(
        bundle.get("bundle_format") == 2
        and bundle.get("album_links") == []
        and bundle.get("owners") == [{"owner": {"kind": "player", "id": PLAYER_ID}, "preimage": plan["owner_after"]}]
        and len(bundle["candidates"]) == len(records) == 5
        and {c["lang"] for c in bundle["candidates"]} == LANGUAGES,
        "canonical correction five names owner/scope invalid",
    )
    by_hash = {digest(r): r for r in records}
    old = {c["name"]["lang"]: c for c in plan["old_names"]}
    for candidate in bundle["candidates"]:
        lang = candidate["lang"]
        require(
            candidate["owner"] == {"kind": "player", "id": PLAYER_ID}
            and candidate["display_name"] == DISPLAYS[lang]
            and candidate.get("name_preimage_sha256") == digest(old[lang]["name"]),
            "canonical correction reviewed name differs",
        )
        research = by_hash.get(candidate["research_sha256"])
        require(isinstance(research, dict), "canonical correction new name research missing")
        if lang == "jp":
            require(
                candidate.get("decision_kind") == "conventional"
                and candidate.get("generation_rule_version") == "none"
                and "first_pass_correction" not in candidate
                and any(
                    c.get("url") == PROFILE_URL
                    and c.get("candidate_name") == DISPLAYS[lang]
                    and c.get("status") == "found"
                    and "沼舘沙輝哉" in c.get("body_excerpt", "")
                    for c in research.get("source_checks", [])
                ),
                "canonical correction Japanese official source missing",
            )
        else:
            require(
                candidate.get("decision_kind") == "generated"
                and candidate.get("generation_rule_version") == "user_authorized_first_pass_v1"
                and research.get("source_input")
                == {
                    "kind": "catalog_canonical",
                    "owner": {"kind": "player", "id": PLAYER_ID},
                    "text": NEW_NAME,
                    "owner_preimage_sha256": digest(plan["owner_after"]),
                },
                "canonical correction generated source is not corrected owner",
            )
            expected = _marker(plan, old[lang], research)
            require(
                candidate.get("first_pass_correction", expected) == expected, "canonical correction forged name marker"
            )
            candidate["first_pass_correction"] = expected
    name_batch._prevalidate(bundle, registry, inventory, records)
    return package


def _identity_neutral(decision):
    result = deepcopy(decision)
    for key in ("player_ref", "matched_at", "content_sha256"):
        result.pop(key)
    if result.get("qualification") is not None:
        result["qualification"].pop("player_ref")
    return result


def _content_sha(plan):
    return digest({k: v for k, v in plan.items() if k not in {"content_sha256", "final_approval"}})


def prepare_in_transaction(conn, *, matched_at, identity_review, name_package, original_package):
    """Read a fixed snapshot; public preparation supplies the readonly transaction."""
    if conn.dialect.name == "postgresql":
        require(
            conn.get_isolation_level() == "REPEATABLE READ", "canonical correction preparation requires REPEATABLE READ"
        )
        require(
            conn.exec_driver_sql("SHOW transaction_read_only").scalar_one() == "on",
            "canonical correction preparation requires READ ONLY",
        )
    _check_codes()
    budget = _Budget()
    _identity_review(identity_review)
    owner, aliases = _owner_and_aliases(conn, budget, before=True)
    targets = []
    resource = ranks.EvidenceBudget(max_bytes=512 * 1024)
    for scope, (live, album, sources) in zip(SCOPE, _live_targets(conn, budget, resource=resource)):
        current = _one(conn, m.KifuAlbumRankSnapshot, scope[7], budget, cap=MAX_NAME_BYTES)
        authority = _old_repair(conn, scope, budget, current=current)
        require(authority["selected_change"]["album_before"] == album, "canonical correction old repair source changed")
        old_binding = ranks.bind_rank_decision(conn, live, current["snapshot"], lock=False, resource=resource)
        require(
            old_binding == authority["selected_change"]["basis_binding"],
            "canonical correction old live binding changed",
        )
        new = deepcopy(current["snapshot"])
        new.update(player_ref={"canonical_name": NEW_NAME}, matched_at=ranks._utc(matched_at))
        if new.get("qualification") is not None:
            new["qualification"]["player_ref"] = {"canonical_name": NEW_NAME}
        new["content_sha256"] = snapshot_digest(new)
        ranks.validate_rank_decision(new)
        targets.append(
            {
                "album_before": album,
                "sources": sources,
                "snapshot_before": current,
                "old_authority": authority,
                "expected_snapshot": new,
            }
        )
    plan = {
        "format": FORMAT,
        "operator_code_sha256": operator_code_sha256(),
        "protected_rank_code_sha256": PROTECTED_CODE_SHA256,
        "database_identity": _database_identity(conn),
        "fixed_person": {"official_profile": "ki000430", "player_id": PLAYER_ID},
        "owner_before": owner,
        "owner_after": dict(owner, canonical_name=NEW_NAME),
        "aliases_before": aliases,
        "old_alias_create": {"player_id": PLAYER_ID, "alias": OLD_NAME, "normalized_alias": normalize_alias(OLD_NAME)},
        "identity_review": deepcopy(identity_review),
        "targets": targets,
        "old_names": _old_names(conn, owner, budget),
        "native_predecessor": _native_predecessor(conn, budget),
        "reference_sets": _references(conn, budget),
        "approved_counts": {
            "player_updates": 1,
            "alias_creates": 1,
            "snapshot_updates": 2,
            "name_updates": 5,
            "evidence_creates": 5,
            "facts": 0,
            "parent_journals": 4,
            "child_journals": 10,
        },
        "original_package": deepcopy(original_package),
        "matched_at": ranks._utc(matched_at),
        "final_approval": None,
    }
    plan["identity_transition_sha256"] = _transition(plan)
    plan["name_package"] = _name_package(plan, name_package)
    plan["content_sha256"] = _content_sha(plan)
    _validate_plan(plan, approved=False)
    return plan


def prepare_correction(engine, **kwargs):
    with _readonly(engine) as conn:
        return prepare_in_transaction(conn, **kwargs)


def _validate_plan(plan, *, approved=True, require_current_operator=True):
    require(
        isinstance(plan, dict)
        and set(plan) == _PLAN_FIELDS
        and plan["format"] == FORMAT
        and ranks._json_size(plan) <= MAX_AUTHORITY_BYTES,
        "canonical correction plan shape/resource invalid",
    )
    _check_codes(plan, require_current_operator=require_current_operator)
    require(
        ranks._json_size({k: plan[k] for k in ("identity_review", "old_names", "name_package")}) <= MAX_NAME_BYTES,
        "canonical correction combined names/captures resource limit",
    )
    _identity_review(plan["identity_review"])
    require(
        plan["fixed_person"] == {"official_profile": "ki000430", "player_id": PLAYER_ID}
        and plan["owner_before"]["id"] == PLAYER_ID
        and plan["owner_before"]["canonical_name"] == OLD_NAME
        and plan["owner_after"] == dict(plan["owner_before"], canonical_name=NEW_NAME)
        and plan["identity_transition_sha256"] == _transition(plan)
        and plan["content_sha256"] == _content_sha(plan),
        "canonical correction identity/content binding changed",
    )
    require(
        plan["old_alias_create"]
        == {"player_id": PLAYER_ID, "alias": OLD_NAME, "normalized_alias": normalize_alias(OLD_NAME)}
        and plan["approved_counts"]
        == {
            "player_updates": 1,
            "alias_creates": 1,
            "snapshot_updates": 2,
            "name_updates": 5,
            "evidence_creates": 5,
            "facts": 0,
            "parent_journals": 4,
            "child_journals": 10,
        },
        "canonical correction mutation counts changed",
    )
    original = plan["original_package"]
    require(
        isinstance(original, dict)
        and set(original)
        == {
            "publication_key",
            "manifest_sha256",
            "home_batch_id",
            "home_receipt_sha256",
            "home_report_sha256",
            "queue_phase",
        }
        and original["publication_key"] == "19x19-0ef14d803cd49221b37f4648"
        and original["home_batch_id"] == 1438
        and all(
            _SHA.fullmatch(str(original[k])) for k in ("manifest_sha256", "home_receipt_sha256", "home_report_sha256")
        )
        and isinstance(original["queue_phase"], str)
        and original["queue_phase"],
        "canonical correction original frozen publication pins missing",
    )
    require(len(plan["targets"]) == 2, "canonical correction exact target count changed")
    require(
        plan["native_predecessor"]["source"].get("album_sgf_sha256")
        == plan["targets"][1]["album_before"]["sgf_sha256"],
        "canonical correction native original source SHA changed",
    )
    for scope, target in zip(SCOPE, plan["targets"]):
        require(
            set(target) == {"album_before", "sources", "snapshot_before", "old_authority", "expected_snapshot"}
            and target["snapshot_before"]["id"] == scope[7],
            "canonical correction target schema/scope changed",
        )
        require(
            target["old_authority"]["journal"]["after_image"] == target["snapshot_before"]
            and target["old_authority"]["selected_change"]["album_before"] == target["album_before"]
            and target["old_authority"]["selected_change"]["snapshot_after"] == target["snapshot_before"]["snapshot"],
            "canonical correction predecessor-to-owner transition chain changed",
        )
        old, new = target["snapshot_before"]["snapshot"], target["expected_snapshot"]
        ranks.validate_rank_decision(new)
        require(
            old["origin"] == new["origin"] == "source"
            and old["basis"] == new["basis"] == []
            and new["player_ref"] == {"canonical_name": NEW_NAME}
            and new["matched_at"] == plan["matched_at"]
            and _identity_neutral(old) == _identity_neutral(new),
            "canonical correction candidate changed source/numeric/system/qualification fields",
        )
    require(
        _name_package(plan, plan["name_package"]) == plan["name_package"], "canonical correction name package changed"
    )
    if approved:
        approval = plan["final_approval"]
        _independent(approval)
        require(
            set(approval)
            == {
                "producer_id",
                "producer_model",
                "reviewer_id",
                "reviewer_model",
                "reviewed_at",
                "decision",
                "content_sha256",
            }
            and approval["decision"] == "approve_exact_canonical_correction"
            and approval["content_sha256"] == plan["content_sha256"],
            "canonical correction exact final approval missing",
        )
    return plan


class _NameCorrectionContext:
    __slots__ = ("connection", "plan", "candidate_hashes")

    def __init__(self, conn, plan):
        self.connection, self.plan = conn, plan
        self.candidate_hashes = {digest(c) for c in plan["name_package"]["bundle"]["candidates"] if c["lang"] != "jp"}


def _validate_name_correction_context(conn, prior_proofs, candidate):
    context = prior_proofs.get("_numadate_canonical_correction") if isinstance(prior_proofs, dict) else None
    require(
        type(context) is _NameCorrectionContext
        and context.connection is conn
        and digest(candidate) in context.candidate_hashes,
        "canonical correction requires the trusted operation-local context",
    )
    plan = context.plan
    lang = candidate["lang"]
    cell = next(c for c in plan["old_names"] if c["name"]["lang"] == lang)
    research = next(r for r in plan["name_package"]["evidence_records"] if digest(r) == candidate["research_sha256"])
    expected = _marker(plan, cell, research)
    require(
        candidate.get("first_pass_correction") == expected
        and name_batch._image(conn, m.KifuPlayer.__table__, PLAYER_ID) == plan["owner_after"]
        and name_batch._image(conn, m.KifuPlayerName.__table__, cell["name"]["id"]) == cell["name"]
        and name_batch._image(conn, m.KifuNameResearchEvidence.__table__, cell["evidence"]["id"]) == cell["evidence"],
        "canonical correction trusted name preimages changed",
    )
    for frozen in cell["journals"]:
        require(
            name_batch._image(conn, m.KifuNameChange.__table__, frozen["id"]) == frozen,
            "canonical correction trusted old creation journal changed",
        )
    return expected


def _before(conn, plan, budget, resource):
    require(_database_identity(conn) == plan["database_identity"], "canonical correction database identity changed")
    owner, aliases = _owner_and_aliases(conn, budget, before=True)
    require(
        owner == plan["owner_before"] and aliases == plan["aliases_before"],
        "canonical correction owner/alias beforeimage changed",
    )
    require(_references(conn, budget) == plan["reference_sets"], "canonical correction reference census changed")
    require(
        _native_predecessor(conn, budget) == plan["native_predecessor"],
        "canonical correction native predecessor changed",
    )
    require(_old_names(conn, owner, budget) == plan["old_names"], "canonical correction old names changed")
    live = _live_targets(conn, budget, resource=resource)
    for scope, target, (entry, album, sources) in zip(SCOPE, plan["targets"], live):
        current = _one(conn, m.KifuAlbumRankSnapshot, scope[7], budget, cap=MAX_NAME_BYTES)
        require(
            current == target["snapshot_before"] and album == target["album_before"] and sources == target["sources"],
            "canonical correction complete source/snapshot preimage changed",
        )
        authority = _old_repair(conn, scope, budget, current=current)
        require(
            authority == target["old_authority"]
            and ranks.bind_rank_decision(conn, entry, current["snapshot"], lock=False, resource=resource)
            == authority["selected_change"]["basis_binding"],
            "canonical correction old rank authority/binding changed",
        )
    return [entry for entry, _, _ in live]


def _parent_binding(batch_id, plan_sha, plan):
    return {
        "version": PARENT_BINDING_VERSION,
        "parent_id": batch_id,
        "plan_sha256": plan_sha,
        "identity_transition_sha256": plan["identity_transition_sha256"],
        "player_id": PLAYER_ID,
        "affected_album_ids": ALBUM_IDS,
    }


def apply_correction(engine, plan, *, expected_sha256):
    _validate_plan(plan)
    require(
        isinstance(expected_sha256, str) and _SHA.fullmatch(expected_sha256) and digest(plan) == expected_sha256,
        "canonical correction reviewed plan SHA mismatch",
    )
    child_sha = digest(plan["name_package"]["bundle"])
    with name_batch._locked_write(engine, search_operation=("name_apply", {"bundle_sha256": child_sha})) as conn:
        if conn.dialect.name == "postgresql":
            conn.exec_driver_sql("SET LOCAL statement_timeout = '5s'")
            conn.exec_driver_sql(
                "LOCK TABLE kifu_album_rank_snapshots, kifu_player_rank_history IN SHARE ROW EXCLUSIVE MODE"
            )
        existing = conn.execute(
            select(m.KifuNameBatch.id).where(m.KifuNameBatch.bundle_sha256 == expected_sha256)
        ).scalar_one_or_none()
        if existing is not None:
            verify_correction(conn, existing)
            batch = name_batch._image(conn, m.KifuNameBatch.__table__, existing)
            return batch["reviewed_artifact"]["receipt"]
        budget = _Budget()
        resource = ranks.EvidenceBudget(max_bytes=512 * 1024)
        targets = _before(conn, plan, budget, resource)
        package = plan["name_package"]
        registry_id, _ = name_batch._source_registry_for_batch(conn, package["registry"], package["bundle"])
        parent_id, _ = name_batch._insert(
            conn,
            m.KifuNameBatch,
            {
                "bundle_sha256": expected_sha256,
                "inventory_sha256": digest(plan["reference_sets"]),
                "source_registry_id": registry_id,
                "reviewed_artifact": {"format": FORMAT, "plan": plan},
                "status": "pending",
            },
        )
        before = plan["owner_before"]
        conn.execute(
            m.KifuPlayer.__table__.update().where(m.KifuPlayer.id == PLAYER_ID).values(canonical_name=NEW_NAME)
        )
        after = name_batch._image(conn, m.KifuPlayer.__table__, PLAYER_ID)
        require(after == plan["owner_after"], "canonical correction same-row canonical postimage invalid")
        name_batch._record_change(conn, parent_id, 1, m.KifuPlayer, PLAYER_ID, before, after)
        alias_id, alias_after = name_batch._insert(conn, m.KifuPlayerAlias, plan["old_alias_create"])
        name_batch._record_change(conn, parent_id, 2, m.KifuPlayerAlias, alias_id, None, alias_after)
        fresh = ranks.prepare_rank_decisions(conn, targets, matched_at=plan["matched_at"], resource=resource)[
            "decisions"
        ]
        require(
            fresh == [t["expected_snapshot"] for t in plan["targets"]],
            "canonical correction fresh b009 resolver differs from frozen candidates",
        )
        ranks.verify_initial_rank_decisions(conn, targets, fresh, resource=resource)
        bindings = [
            ranks.bind_rank_decision(conn, target, decision, resource=resource)
            for target, decision in zip(targets, fresh)
        ]
        for sequence, (target, decision) in enumerate(zip(plan["targets"], fresh), 3):
            old = target["snapshot_before"]
            conn.execute(
                m.KifuAlbumRankSnapshot.__table__.update()
                .where(m.KifuAlbumRankSnapshot.id == old["id"])
                .values(
                    snapshot=decision,
                    snapshot_sha256=decision["content_sha256"],
                    publication_key="canonical-correction:" + expected_sha256,
                    native_batch_id=parent_id,
                )
            )
            name_batch._record_change(
                conn,
                parent_id,
                sequence,
                m.KifuAlbumRankSnapshot,
                old["id"],
                old,
                name_batch._image(conn, m.KifuAlbumRankSnapshot.__table__, old["id"]),
            )
        child_artifact = {
            "bundle": package["bundle"],
            "research_hashes": sorted(digest(r) for r in package["evidence_records"]),
            "resolved_refs": {"player:5364": PLAYER_ID},
            "affected_album_ids": ALBUM_IDS,
            "canonical_correction_parent": _parent_binding(parent_id, expected_sha256, plan),
        }
        child_id, _ = name_batch._insert(
            conn,
            m.KifuNameBatch,
            {
                "bundle_sha256": child_sha,
                "inventory_sha256": package["inventory"]["sha256"],
                "source_registry_id": registry_id,
                "reviewed_artifact": child_artifact,
                "status": "pending",
            },
        )
        prior_proofs = {"_numadate_canonical_correction": _NameCorrectionContext(conn, plan)}
        by_hash = {digest(r): r for r in package["evidence_records"]}
        name_batch._check_name_preimages(conn, package["bundle"]["candidates"], package["registry"], prior_proofs)
        name_batch._check_first_pass_sources(
            conn, package["bundle"]["candidates"], by_hash, package["bundle"]["owners"]
        )
        name_batch._check_cross_bundle_collisions(
            conn, package["bundle"]["candidates"], owners=package["bundle"]["owners"], research_by_hash=by_hash
        )
        sequence = 1
        for candidate in package["bundle"]["candidates"]:
            sequence = name_batch._apply_candidate(
                conn,
                candidate,
                by_hash,
                registry_id,
                child_id,
                sequence,
                registry=package["registry"],
                prior_proofs=prior_proofs,
            )
        require(sequence == 11, "canonical correction name ledger count changed")
        receipt = {
            "status": "applied",
            "batch_id": parent_id,
            "child_batch_id": child_id,
            "plan_sha256": expected_sha256,
            "child_bundle_sha256": child_sha,
            "identity_transition_sha256": plan["identity_transition_sha256"],
            "snapshot_ids": [r[7] for r in SCOPE],
            "publication_key": "canonical-correction:" + expected_sha256,
            "search_operation": {"operation_type": "name_apply", "operation_ref": {"bundle_sha256": child_sha}},
        }
        conn.execute(
            m.KifuNameBatch.__table__.update()
            .where(m.KifuNameBatch.id == parent_id)
            .values(
                status="applied",
                applied_at=datetime.now(timezone.utc),
                reviewed_artifact={
                    "format": FORMAT,
                    "manifest_sha256": expected_sha256,
                    "plan": plan,
                    "basis_bindings": bindings,
                    "receipt": receipt,
                },
            )
        )
        conn.execute(
            m.KifuNameBatch.__table__.update()
            .where(m.KifuNameBatch.id == child_id)
            .values(status="applied", applied_at=datetime.now(timezone.utc))
        )
        verify_correction(conn, parent_id, resource=resource)
    return receipt


def _guard_current_name_material(conn, plan, child_changes, budget):
    """Bound every live name/evidence column before the normal qualifier reads it."""
    names, evidence = m.KifuPlayerName.__table__, m.KifuNameResearchEvidence.__table__
    name_ids = {cell["name"]["id"] for cell in plan["old_names"]}
    name_changes = {
        row["target_row_id"]: row["after_image"] for row in child_changes if row["target_table"] == names.name
    }
    require(set(name_changes) == name_ids, "canonical correction current name ledger membership changed")
    predicate = (names.c.player_id == PLAYER_ID) & names.c.lang.in_(LANGUAGES)
    size = sum((_bytes(conn, column) for column in names.c), 0)
    count, name_bytes = conn.execute(
        select(func.count(), func.coalesce(func.sum(size), 0)).select_from(names).where(predicate)
    ).one()
    require(count == 5 and name_bytes <= MAX_NAME_BYTES, "canonical correction current name material resource limit")
    pointers = (
        conn.execute(select(names.c.id, names.c.player_id, names.c.lang, names.c.evidence_id).where(predicate))
        .mappings()
        .all()
    )
    require(
        len(pointers) == 5
        and {row["id"] for row in pointers} == name_ids
        and all(
            all(row[key] == name_changes[row["id"]][key] for key in ("id", "player_id", "lang", "evidence_id"))
            for row in pointers
        ),
        "canonical correction current name/evidence pointer changed",
    )
    evidence_ids = {row["evidence_id"] for row in pointers}
    require(len(evidence_ids) == 5, "canonical correction current evidence membership changed")
    size = sum((_bytes(conn, column) for column in evidence.c), 0)
    count, evidence_bytes = conn.execute(
        select(func.count(), func.coalesce(func.sum(size), 0))
        .select_from(evidence)
        .where(evidence.c.id.in_(evidence_ids))
    ).one()
    require(
        count == 5 and name_bytes + evidence_bytes <= MAX_NAME_BYTES,
        "canonical correction current name/evidence material resource limit",
    )
    budget.reserve(name_bytes + evidence_bytes)


def _verify_correction(conn, batch_id, *, expected_rows=None, resource=None):
    """Independently prove exact current rows using bounded reads.

    The two-slot/zero-fact census is deliberately only an apply admission gate.
    Later strict publications may add legitimate slots/facts without revoking
    this immutable correction authority. Protected rank helpers may use local
    timeout/savepoint controls; this verifier performs no business writes.
    """
    budget = _Budget()
    batch = _one(conn, m.KifuNameBatch, batch_id, budget)
    artifact = batch["reviewed_artifact"]
    require(
        batch["status"] == "applied" and isinstance(artifact, dict) and artifact.get("format") == FORMAT,
        "canonical correction applied authority missing",
    )
    require(
        set(artifact) == {"format", "manifest_sha256", "plan", "basis_bindings", "receipt"},
        "canonical correction applied artifact shape changed",
    )
    # The applied plan/approval retains its historical operator pin; future
    # unrelated hook-file edits do not revoke this fully rechecked DB chain.
    plan = _validate_plan(artifact["plan"], require_current_operator=False)
    plan_sha = digest(plan)
    require(
        batch["bundle_sha256"] == artifact["manifest_sha256"] == plan_sha
        and _database_identity(conn) == plan["database_identity"],
        "canonical correction applied plan/database binding changed",
    )
    owner, aliases = _owner_and_aliases(conn, budget, before=False)
    require(owner == plan["owner_after"], "canonical correction current owner changed")
    require(all(row in aliases for row in plan["aliases_before"]), "canonical correction original aliases changed")
    old_alias = [row for row in aliases if row["normalized_alias"] == normalize_alias(OLD_NAME)]
    require(
        len(aliases) == len(plan["aliases_before"]) + 1
        and len(old_alias) == 1
        and all(old_alias[0][k] == v for k, v in plan["old_alias_create"].items()),
        "canonical correction exact alias transition changed",
    )
    journals = _rows(
        conn, m.KifuNameChange, m.KifuNameChange.batch_id == batch_id, limit=4, budget=budget, cap=MAX_NAME_BYTES
    )
    require(
        len(journals) == 4 and [r["sequence"] for r in journals] == [1, 2, 3, 4],
        "canonical correction parent ledger count/order changed",
    )
    require(
        journals[0]["target_table"] == m.KifuPlayer.__tablename__
        and journals[0]["target_row_id"] == PLAYER_ID
        and journals[0]["before_image"] == plan["owner_before"]
        and journals[0]["after_image"] == owner
        and journals[1]["target_table"] == m.KifuPlayerAlias.__tablename__
        and journals[1]["target_row_id"] == old_alias[0]["id"]
        and journals[1]["before_image"] is None
        and journals[1]["after_image"] == old_alias[0],
        "canonical correction exact owner/alias journal changed",
    )
    require(
        _native_predecessor(conn, budget) == plan["native_predecessor"],
        "canonical correction old native receipt/predecessor changed",
    )
    require(
        _old_names(conn, plan["owner_before"], budget, frozen=plan["old_names"]) == plan["old_names"],
        "canonical correction old name historical evidence changed",
    )
    resource = resource if resource is not None else ranks.EvidenceBudget(max_bytes=512 * 1024)
    live = _live_targets(conn, budget, resource=resource)
    rows, bindings, current_rows = {}, [], {}
    for scope, target, (entry, album, sources), journal in zip(SCOPE, plan["targets"], live, journals[2:]):
        require(
            album == target["album_before"] and sources == target["sources"],
            "canonical correction original source/body/FK changed",
        )
        require(
            _old_repair(conn, scope, budget) == target["old_authority"],
            "canonical correction old repair historical authority changed",
        )
        current = _one(conn, m.KifuAlbumRankSnapshot, scope[7], budget, cap=MAX_NAME_BYTES)
        current_rows[current["id"]] = current
        expected = dict(
            target["snapshot_before"],
            snapshot=target["expected_snapshot"],
            snapshot_sha256=target["expected_snapshot"]["content_sha256"],
            publication_key="canonical-correction:" + plan_sha,
            native_batch_id=batch_id,
        )
        require(
            current == expected
            and journal["target_table"] == m.KifuAlbumRankSnapshot.__tablename__
            and journal["target_row_id"] == current["id"]
            and journal["before_image"] == target["snapshot_before"]
            and journal["after_image"] == current,
            "canonical correction current rank/journal afterimage changed",
        )
        binding = ranks.bind_rank_decision(conn, entry, current["snapshot"], lock=False, resource=resource)
        old_binding = deepcopy(target["old_authority"]["selected_change"]["basis_binding"])
        old_binding["target"]["snapshot_sha256"] = current["snapshot_sha256"]
        old_binding["content_sha256"] = snapshot_digest(old_binding)
        require(
            binding == old_binding and binding["basis"] == [],
            "canonical correction local old/new basis0 binding changed",
        )
        bindings.append(binding)
        rows[current["id"]] = {
            "row_id": current["id"],
            "album_id": current["album_id"],
            "side": current["side"],
            "snapshot_sha256": current["snapshot_sha256"],
            "batch_id": batch_id,
            "batch_sha256": plan_sha,
        }
    require(bindings == artifact["basis_bindings"], "canonical correction new b009 private binding changed")
    receipt = artifact["receipt"]
    child = _one(conn, m.KifuNameBatch, receipt["child_batch_id"], budget, cap=MAX_NAME_BYTES)
    package = plan["name_package"]
    child_sha = digest(package["bundle"])
    expected_child = {
        "bundle": package["bundle"],
        "research_hashes": sorted(digest(r) for r in package["evidence_records"]),
        "resolved_refs": {"player:5364": PLAYER_ID},
        "affected_album_ids": ALBUM_IDS,
        "canonical_correction_parent": _parent_binding(batch_id, plan_sha, plan),
    }
    require(
        child["status"] == "applied"
        and child["bundle_sha256"] == child_sha
        and child["reviewed_artifact"] == expected_child
        and child["source_registry_id"] == batch["source_registry_id"],
        "canonical correction reciprocal name child binding changed",
    )
    registry = _one(conn, m.KifuNameSourceRegistry, batch["source_registry_id"], budget, cap=MAX_NAME_BYTES)
    require(
        registry["registry"] == package["registry"] and registry["sha256"] == registry_sha256(package["registry"]),
        "canonical correction child source registry changed",
    )
    child_changes = _rows(
        conn, m.KifuNameChange, m.KifuNameChange.batch_id == child["id"], limit=10, budget=budget, cap=MAX_NAME_BYTES
    )
    require(len(child_changes) == 10, "canonical correction child ledger count changed")
    _guard_current_name_material(conn, plan, child_changes, budget)
    # Existing standard name verifier validates complete signed candidates,
    # research, real evidence rows and all ten exact current afterimages.
    name_batch._check_applied_v4(conn, child, package["bundle"])
    name_batch._check_first_pass_sources(
        conn,
        package["bundle"]["candidates"],
        {digest(r): r for r in package["evidence_records"]},
        package["bundle"]["owners"],
    )
    expected_receipt = {
        "status": "applied",
        "batch_id": batch_id,
        "child_batch_id": child["id"],
        "plan_sha256": plan_sha,
        "child_bundle_sha256": child_sha,
        "identity_transition_sha256": plan["identity_transition_sha256"],
        "snapshot_ids": [r[7] for r in SCOPE],
        "publication_key": "canonical-correction:" + plan_sha,
        "search_operation": {"operation_type": "name_apply", "operation_ref": {"bundle_sha256": child_sha}},
    }
    require(receipt == expected_receipt, "canonical correction receipt changed")
    if expected_rows is not None:
        supplied = list(expected_rows.values()) if isinstance(expected_rows, dict) else list(expected_rows)
        base_fields = set(m.KifuAlbumRankSnapshot.__table__.c.keys())
        require(
            all(
                isinstance(row, Mapping)
                and base_fields.issubset(row)
                and row["id"] in current_rows
                and digest(repair._json_image({key: row[key] for key in base_fields}))
                == digest(current_rows[row["id"]])
                for row in supplied
            ),
            "canonical correction supplied current rows changed",
        )
    budget.check()
    return {"batch_id": batch_id, "batch_sha256": plan_sha, "rows": rows, "receipt": receipt}


def verify_correction(conn, batch_id, *, expected_rows=None, resource=None):
    try:
        with ranks._bounded_queries(conn):
            return _verify_correction(conn, batch_id, expected_rows=expected_rows, resource=resource)
    except (KeyError, TypeError, IndexError, AttributeError) as exc:
        raise ValueError("canonical correction malformed authority") from exc


def verify_correction_readonly(engine, batch_id):
    with _readonly(engine) as conn:
        return verify_correction(conn, batch_id)
