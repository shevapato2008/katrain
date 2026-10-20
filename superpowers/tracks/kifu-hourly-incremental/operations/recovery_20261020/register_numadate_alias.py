"""One reviewed PROD alias only. Default dry-run; no automatic undo or publication."""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

sys.path.insert(0, "/app")

from sqlalchemy import create_engine, insert, or_, select, text
from sqlalchemy.orm import Session

from katrain.kifu_ingest.catalog import _identity_indexes, _resolve_identity
from katrain.web.core.models_db import KifuAlbum, KifuPlayer, KifuPlayerAlias, KifuPlayerName
from katrain.web.kifu.identity import PRIMARY_NAME_LANGUAGES, _approved_names, _qualified_name_rows, normalize_alias
from katrain.web.kifu.name_batch import _image, _locked_write

APPROVAL_SHA = "b75326ee8a80eca93cbbfe2ff5c847d46698c4cd4ec87afa9d325711fc0d8585"
DATABASE = "katrain_prod_20260725"
OWNER = 5364
CANONICAL = "沼官沙辉哉"
ALIAS = "沼馆沙辉哉"
SGF_SHA = "9f3a8395b9bab863c88ca109f5e301e536acff02054a176b11811b6651bc1679"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def image(obj):
    return {
        c.name: value.isoformat() if hasattr(value, "isoformat") else value
        for c in obj.__table__.columns
        for value in [getattr(obj, c.name)]
    }


def qualified_snapshot(conn):
    owner = _image(conn, KifuPlayer.__table__, OWNER)
    require(
        owner and owner["canonical_name"] == CANONICAL and owner["authoritative_pages"] == [],
        "exact owner preimage differs",
    )
    with Session(bind=conn) as db:
        query = _approved_names(db, KifuPlayerName, "player_id", ids={OWNER})
        rows = _qualified_name_rows(db, query, KifuPlayerName, "player_id")
        require(
            len(rows) == 5 and {n.lang for n, *_ in rows} == PRIMARY_NAME_LANGUAGES,
            "owner does not have five current native-qualified primary names",
        )
        proofs = sorted(
            ({"name": image(name), "evidence": image(evidence)} for name, evidence, *_ in rows),
            key=lambda row: row["name"]["lang"],
        )
    return {"owner": owner, "qualified_names": proofs}


def old_game_proof(conn, approval):
    row = conn.execute(select(KifuAlbum.__table__).where(KifuAlbum.id == 124026)).mappings().one()
    expected = approval["old_sgf_proof"]
    actual = {k: row[k] for k in ("source_path", "player_black", "player_white", "date_played", "event")}
    actual.update(album_id=row["id"], black_player_id=row["black_player_id"])
    actual["sgf_sha256"] = sha256(row["sgf_content"].encode("utf-8")).hexdigest()
    require(
        row["black_player_id"] == OWNER
        and actual["sgf_sha256"] == SGF_SHA
        and all(
            actual[k] == expected[k] for k in ("source_path", "player_black", "player_white", "date_played", "event")
        ),
        "exact old source SGF/slot/opponent proof differs",
    )
    return actual


def checked_alias(conn):
    key = normalize_alias(ALIAS)
    indexes = _identity_indexes(conn)
    require(indexes["player"].get(key, set()) <= {OWNER}, "alias/canonical collision names another owner")
    table = KifuPlayerAlias.__table__
    rows = (
        conn.execute(select(table).where(or_(table.c.normalized_alias == key, table.c.alias == ALIAS))).mappings().all()
    )
    require(len(rows) <= 1, "alias identity has multiple rows")
    if rows:
        require(
            rows[0]["player_id"] == OWNER and rows[0]["alias"] == ALIAS and rows[0]["normalized_alias"] == key,
            "existing alias is not the exact approved row",
        )
    owner_aliases = conn.execute(select(table).where(table.c.player_id == OWNER)).mappings().all()
    require(len(owner_aliases) == len(rows), "owner gained an unexpected alias")
    return _image(conn, table, rows[0]["id"]) if rows else None


def write_receipt(path, value):
    temporary = path.with_name("." + path.name + "." + str(uuid4()))
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            os.chmod(temporary, 0o600)
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary.exists():
            temporary.unlink()


def operate(engine, approval, receipt_path, *, apply=False):
    require(engine.dialect.name == "postgresql", "PROD PostgreSQL required")
    # Refuse even catalog locking on an unexpected database.
    with engine.connect() as conn:
        require(conn.scalar(text("SELECT current_database()")) == DATABASE, "unexpected database")
    receipt = {
        "format": "kifu-numadate-alias-receipt-v1",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "database": DATABASE,
        "apply": apply,
        "approval_sha256": APPROVAL_SHA,
        "approval": approval,
    }
    with _locked_write(engine, lock_timeout_ms=15000) as conn:
        conn.execute(text("SET LOCAL statement_timeout = '120s'"))
        require(conn.scalar(text("SELECT current_database()")) == DATABASE, "unexpected locked database")
        before = qualified_snapshot(conn)
        proof = old_game_proof(conn, approval)
        prior_alias = checked_alias(conn)
        receipt.update(before=before, old_sgf_proof=proof, alias_before=prior_alias, status="preflight_passed")
        # Persist the actual preimage before the sole possible INSERT.
        write_receipt(receipt_path, receipt)
        inserted = False
        if apply and prior_alias is None:
            result = conn.execute(
                insert(KifuPlayerAlias.__table__).values(
                    player_id=OWNER, alias=ALIAS, normalized_alias=normalize_alias(ALIAS)
                )
            )
            require(result.rowcount == 1, "expected exactly one inserted alias")
            inserted = True
        actual_alias = checked_alias(conn)
        after = qualified_snapshot(conn)
        require(after == before, "owner or five native-qualified name/evidence preimages changed")
        resolved = None
        if actual_alias is not None:
            resolved = _resolve_identity("player", ALIAS, {"canonical_name": ALIAS}, _identity_indexes(conn))
            require(resolved == OWNER, "native resolver does not return the exact owner")
        require(not apply or actual_alias is not None, "applied alias row missing")
        receipt.update(
            after=after,
            alias_after=actual_alias,
            inserted=inserted,
            native_resolved_owner=resolved,
            status="validated_uncommitted" if apply else "dry_run",
            committed=False,
        )
        # A lost commit acknowledgement leaves an honest, durable uncertain
        # checkpoint. A later explicit run reads the actual alias; it never undoes.
        write_receipt(receipt_path, receipt)
    receipt.update(
        status=("applied" if inserted else "already_present") if apply else "dry_run",
        committed=apply,
        finished_at=datetime.now(timezone.utc).isoformat(),
    )
    write_receipt(receipt_path, receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval", type=Path, default=Path(__file__).with_name("numadate-alias-approval.json"))
    parser.add_argument("--receipt", type=Path, required=True, help="new file in an existing private 0700 directory")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    raw = args.approval.read_bytes()
    require(sha256(raw).hexdigest() == APPROVAL_SHA, "pinned independent approval differs")
    approval = json.loads(raw)
    path = args.receipt
    require(
        path.is_absolute()
        and path.parent.is_dir()
        and path.parent.resolve() == path.parent
        and path.parent.stat().st_mode & 0o077 == 0
        and path.parent.stat().st_uid == os.getuid()
        and not path.exists()
        and not path.is_symlink(),
        "receipt must be a new file in an owned private directory without symlinks",
    )
    engine = create_engine(os.environ["KATRAIN_DATABASE_URL"], pool_pre_ping=True)
    try:
        receipt = operate(engine, approval, path, apply=args.apply)
    finally:
        engine.dispose()
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
