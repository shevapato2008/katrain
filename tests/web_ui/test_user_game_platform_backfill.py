import copy
import json
import stat
import subprocess
import sys
from datetime import datetime

import pytest
from sqlalchemy import create_engine, event, select, update
from sqlalchemy.orm import Session

from katrain.web.core.models_db import UserGame
from scripts.backfill_user_game_platform import RepairError, apply_manifest, dry_run, main, rollback_batch


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'games.db'}")
    UserGame.__table__.create(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def add_game(db, game_id="hint", **changes):
    values = dict(
        id=game_id,
        user_id=7,
        source="play_ai",
        game_type="free",
        platform=None,
        player_white="Opponent[golaxy]",
        sgf_content="(;GM[1]PB[Me]PW[Opponent\\[golaxy\\]];B[aa])",
        sgf_hash="stored-original-hash",
        updated_at=datetime(2020, 1, 2, 3, 4, 5),
        result="B+R",
        move_count=1,
    )
    values.update(changes)
    db.execute(UserGame.__table__.insert().values(**values))
    db.commit()


def row(db, game_id="hint"):
    return dict(db.execute(select(UserGame.__table__).where(UserGame.id == game_id)).mappings().one())


def test_dry_run_requires_scope_and_never_writes(db):
    add_game(db)
    add_game(db, "explicit", sgf_content="(;GM[1]KTP[golaxy])")
    add_game(db, "unknown", player_white="Ordinary", sgf_content="(;GM[1]KTP[ogs])")
    before = [row(db, x) for x in ("hint", "explicit", "unknown")]
    statements = []
    event.listen(db.bind, "before_cursor_execute", lambda c, cu, sql, p, ctx, m: statements.append(sql))
    with pytest.raises(RepairError, match="scope"):
        dry_run(db)
    manifest = dry_run(db, user_id=7)
    assert {r["id"]: r["evidence"] for r in manifest["rows"]} == {
        "hint": "name_hint",
        "explicit": "ktp_golaxy",
        "unknown": "none",
    }
    assert manifest["database_identity_sha256"]
    assert all("sgf_content" not in candidate for candidate in manifest["rows"])
    assert all(r["sgf_content_sha256"] and r["sgf_hash"] for r in manifest["rows"])
    assert not any(sql.lstrip().upper().startswith(("UPDATE", "INSERT", "DELETE")) for sql in statements)
    assert before == [row(db, x) for x in ("hint", "explicit", "unknown")]


def test_confirmed_apply_preserves_every_other_column_and_is_idempotent(db, tmp_path):
    add_game(db)
    add_game(db, "other")
    manifest = dry_run(db, user_id=7)
    before = row(db)
    backup_path = tmp_path / "backup.json"
    result = apply_manifest(db, manifest, confirmed_game_ids=["hint"], backup_path=backup_path)
    assert result["updated_ids"] == ["hint"]
    assert stat.S_IMODE(backup_path.stat().st_mode) == 0o600
    backup_bytes = backup_path.read_bytes()
    assert row(db) == {**before, "platform": "golaxy"}
    assert row(db, "other")["platform"] is None
    result = apply_manifest(db, manifest, confirmed_game_ids=["hint"], backup_path=backup_path)
    assert result["updated_ids"] == []
    assert backup_path.read_bytes() == backup_bytes


def test_name_hint_requires_confirmation_and_unknown_has_no_evidence(db, tmp_path):
    add_game(db)
    manifest = dry_run(db, game_ids=["hint"])
    with pytest.raises(RepairError, match="confirmed"):
        apply_manifest(db, manifest, confirmed_game_ids=[], backup_path=tmp_path / "no.json")
    add_game(db, "unknown", player_white="Other", sgf_content="(;GM[1]C[KTP\\[golaxy\\]])")
    unknown = dry_run(db, game_ids=["unknown"])
    with pytest.raises(RepairError, match="evidence"):
        apply_manifest(db, unknown, confirmed_game_ids=["unknown"], backup_path=tmp_path / "unknown.json")
    assert not (tmp_path / "no.json").exists()


def test_exact_root_ktp_evidence_can_apply_without_name_confirmation(db, tmp_path):
    add_game(db, "ktp", sgf_content="(;GM[1]KTP[golaxy])", player_white="Other")
    manifest = dry_run(db, game_ids=["ktp"])
    assert apply_manifest(db, manifest, confirmed_game_ids=[], backup_path=tmp_path / "ktp.json")["updated_ids"] == [
        "ktp"
    ]


def test_imports_and_existing_platforms_are_protected_even_with_forged_manifest(db, tmp_path):
    add_game(db)
    manifest = dry_run(db, game_ids=["hint"])
    for field, value in (("source", "import"), ("platform", "ogs")):
        forged = copy.deepcopy(manifest)
        db.execute(update(UserGame.__table__).where(UserGame.id == "hint").values({field: value}))
        db.commit()
        forged["rows"][0][field] = value
        assert dry_run(db, game_ids=["hint"])["rows"] == []
        with pytest.raises(RepairError):
            apply_manifest(db, forged, confirmed_game_ids=["hint"], backup_path=tmp_path / f"{field}.json")
        db.execute(update(UserGame.__table__).where(UserGame.id == "hint").values(source="play_ai", platform=None))
        db.commit()


@pytest.mark.parametrize("change", ["owner", "database", "content", "updated_at", "source", "game_type", "stored_hash"])
def test_wrong_database_or_changed_snapshot_refuses_entire_batch(db, tmp_path, change):
    add_game(db)
    add_game(db, "second")
    manifest = dry_run(db, user_id=7)
    if change == "database":
        manifest["database_identity_sha256"] = "wrong"
    else:
        updates = {
            "owner": {"user_id": 8},
            "content": {"sgf_content": "(;GM[1];B[bb])"},
            "updated_at": {"updated_at": datetime(2024, 1, 1)},
            "source": {"source": "import"},
            "game_type": {"game_type": "rated"},
            "stored_hash": {"sgf_hash": "changed"},
        }[change]
        db.execute(update(UserGame.__table__).where(UserGame.id == "second").values(**updates))
        db.commit()
    with pytest.raises(RepairError):
        apply_manifest(db, manifest, confirmed_game_ids=["hint", "second"], backup_path=tmp_path / "backup.json")
    assert row(db)["platform"] is None
    assert row(db, "second")["platform"] is None
    assert not (tmp_path / "backup.json").exists()


def test_existing_backup_refuses_write(db, tmp_path):
    add_game(db)
    manifest = dry_run(db, user_id=7)
    backup_path = tmp_path / "backup.json"
    backup_path.write_text("keep")
    with pytest.raises(FileExistsError):
        apply_manifest(db, manifest, confirmed_game_ids=["hint"], backup_path=backup_path)
    assert row(db)["platform"] is None
    assert backup_path.read_text() == "keep"


def test_rollback_restores_only_platform_and_is_idempotent(db, tmp_path):
    add_game(db)
    before = row(db)
    path = tmp_path / "backup.json"
    apply_manifest(db, dry_run(db, user_id=7), confirmed_game_ids=["hint"], backup_path=path)
    backup = json.loads(path.read_text())
    assert rollback_batch(db, backup)["restored_ids"] == ["hint"]
    assert row(db) == before
    assert rollback_batch(db, backup)["restored_ids"] == []


def test_rollback_refuses_later_edits_and_cross_database(db, tmp_path):
    add_game(db)
    path = tmp_path / "backup.json"
    apply_manifest(db, dry_run(db, user_id=7), confirmed_game_ids=["hint"], backup_path=path)
    backup = json.loads(path.read_text())
    wrong = copy.deepcopy(backup)
    wrong["database_identity_sha256"] = "wrong"
    with pytest.raises(RepairError):
        rollback_batch(db, wrong)
    db.execute(update(UserGame.__table__).where(UserGame.id == "hint").values(result="W+R"))
    db.commit()
    with pytest.raises(RepairError):
        rollback_batch(db, backup)
    assert row(db)["platform"] == "golaxy"


def test_apply_rolls_back_all_updates_on_write_failure(db, tmp_path):
    add_game(db)
    add_game(db, "second")
    manifest = dry_run(db, user_id=7)
    updates = []

    def fail_second_update(c, cu, sql, p, ctx, m):
        if sql.lstrip().upper().startswith("UPDATE"):
            updates.append(sql)
            if len(updates) == 2:
                raise RuntimeError("injected write failure")

    event.listen(db.bind, "before_cursor_execute", fail_second_update)
    path = tmp_path / "backup.json"
    with pytest.raises(RuntimeError, match="injected"):
        apply_manifest(db, manifest, confirmed_game_ids=["hint", "second"], backup_path=path)
    assert len(updates) == 2
    assert row(db)["platform"] is None
    assert row(db, "second")["platform"] is None
    assert path.exists()  # Durable original metadata remains available after failure.


def test_null_to_empty_sgf_edit_invalidates_snapshot(db, tmp_path):
    add_game(db, sgf_content=None)
    manifest = dry_run(db, user_id=7)
    db.execute(
        update(UserGame.__table__)
        .where(UserGame.id == "hint")
        .values(sgf_content="", updated_at=datetime(2020, 1, 2, 3, 4, 5))
    )
    db.commit()
    with pytest.raises(RepairError, match="snapshot"):
        apply_manifest(db, manifest, confirmed_game_ids=["hint"], backup_path=tmp_path / "backup.json")


def test_import_has_no_runtime_database_side_effects():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import scripts.backfill_user_game_platform; "
            "assert 'katrain.web.core.db' not in sys.modules",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_cli_refuses_unscoped_or_unbacked_actions_before_opening_database():
    for arguments in ([], ["--apply", "review.json"], ["--rollback", "backup.json", "--user-id", "7"]):
        with pytest.raises(SystemExit) as exc:
            main(arguments)
        assert exc.value.code == 2
