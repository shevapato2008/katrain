"""Bounded duplicate-player merges preserve the catalog and undo atomically."""

from copy import deepcopy

import pytest
from sqlalchemy import create_engine, event, func, select

from katrain.web.core.models_db import (
    Base,
    KifuAlbum,
    KifuAlbumSource,
    KifuNameBatch,
    KifuNameChange,
    KifuPlayer,
    KifuPlayerAlias,
    KifuPlayerName,
    KifuRawPlayerValue,
    KifuSource,
)
from katrain.web.kifu.name_batch import BatchError
from katrain.web.kifu.name_candidates import canonical_sha256


@pytest.fixture(params=["piao", "li"])
def catalog(tmp_path, request):
    from katrain.web.kifu import player_duplicate as merge

    engine = create_engine(f"sqlite:///{tmp_path / 'duplicates.db'}")

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    pair = merge.PAIRS[request.param]
    survivor, retired = pair["ids"]["TEST"]
    moving, protected = pair["counts"]
    with engine.begin() as conn:
        conn.execute(
            KifuPlayer.__table__.insert(),
            [
                {"id": survivor, "canonical_name": pair["names"][0]},
                {"id": retired, "canonical_name": pair["names"][1]},
                {"id": 12, "canonical_name": "Opponent"},
            ],
        )
        conn.execute(KifuSource.__table__.insert().values(id=1, source_key="fixture"))
        albums = []
        for index in range(moving + protected):
            owner, raw = (retired, pair["names"][1]) if index < moving else (survivor, pair["names"][0])
            side = "black" if index % 2 == 0 else "white"
            albums.append(
                {
                    "id": index + 1,
                    "black_player_id": owner if side == "black" else 12,
                    "white_player_id": owner if side == "white" else 12,
                    "player_black": raw if side == "black" else "Opponent",
                    "player_white": raw if side == "white" else "Opponent",
                    "date_played": "1900-01-01",
                    "event": "original event",
                    "sgf_content": f"(;PB[{raw}]DT[1900-01-01])",
                    "source_path": f"{index}.sgf",
                }
            )
        conn.execute(KifuAlbum.__table__.insert(), albums)
        conn.execute(
            KifuAlbumSource.__table__.insert(),
            [
                {
                    "id": index + 1,
                    "album_id": index + 1,
                    "source_id": 1,
                    "origin_path": f"{index}.sgf",
                    "match_method": "fixture",
                }
                for index in range(moving + protected)
            ],
        )
        conn.execute(
            KifuRawPlayerValue.__table__.insert().values(
                id=pair["raw_id"],
                raw_value=pair["names"][1],
                category="readable_unlinked",
                review_status="pending",
                parsed_data={"original": True},
                review_metadata={"player_id": retired, "kind": "provisional_person_link", "extra": "keep"},
            )
        )
        if request.param == "li":
            conn.execute(
                KifuPlayerName.__table__.insert(),
                [
                    {
                        "player_id": survivor,
                        "lang": lang,
                        "display_name": display,
                        "status": "review",
                        "reference_kind": "legacy_unverified",
                    }
                    for lang, display in zip(("en", "cn", "tw", "jp", "ko"), pair["spellings"][1:6])
                ],
            )
    with engine.connect() as conn:
        before = merge.capture(conn, "TEST", request.param)
    plan = proposal(merge, before, request.param)
    approval = {
        "format": "kifu-player-duplicate-review-v1",
        "status": "independent-approved",
        "plan_sha256": canonical_sha256(plan),
        "full_preimage_canonical_sha256": canonical_sha256(before),
        "identity_review_canonical_sha256": plan["identity_review_canonical_sha256"],
        "producer_id": plan["producer_id"],
        "reviewer_id": "fixture-independent-reviewer",
        "reviewer_model": "fixture",
        "reviewed_at": "2026-10-05T16:00:00Z",
        "conclusion": "synthetic fixture",
    }
    yield merge, engine, before, plan, approval
    engine.dispose()


def proposal(merge, before, key):
    pair = merge.PAIRS[key]
    survivor, retired = pair["ids"]["TEST"]
    players = {row["id"]: row for row in before["full_rows"]["kifu_players"]}
    updates, protected = [], []
    for album in before["full_rows"]["kifu_albums"]:
        for side in ("black", "white"):
            owner = album[side + "_player_id"]
            if owner not in (survivor, retired):
                continue
            slot = {
                "album_id": album["id"],
                "side": side,
                "column": side + "_player_id",
                "raw_player_value": album["player_" + side],
                "date_played": album["date_played"],
                "before_player_id": owner,
                "after_player_id": survivor,
                "album_full_row_sha256": canonical_sha256(album),
            }
            (updates if owner == retired else protected).append(slot)
    raw = before["full_rows"]["kifu_raw_player_values"][0]
    metadata = {**raw["review_metadata"], "player_id": survivor}
    return {
        "format": "kifu-player-single-duplicate-proposal-v1",
        "status": "pending_independent_review",
        "environment": "TEST",
        "database": merge.DATABASES["TEST"],
        "captured_at": before["captured_at"],
        "producer_id": "fixture-producer",
        "producer_model": "fixture",
        "identity_review_canonical_sha256": "1" * 64,
        "full_preimage_canonical_sha256": canonical_sha256(before),
        "full_preimage_artifact": {"path": "fixture.json.gz", "sha256": "2" * 64},
        "survivor_player": players[survivor],
        "retire_player": players[retired],
        "operations": {
            "album_fk_updates": updates,
            "raw_metadata_updates": [
                {
                    "raw_id": raw["id"],
                    "raw_value": raw["raw_value"],
                    "before_full_row": raw,
                    "before_review_metadata": raw["review_metadata"],
                    "after_review_metadata": metadata,
                    "columns_allowed_to_change": ["review_metadata"],
                    "preserve_review_status": raw["review_status"],
                }
            ],
            "insert_alias_if_exact_preimage_still_absent": {
                "player_id": survivor,
                "alias": pair["names"][1],
                "normalized_alias": pair["names"][1],
            },
            "delete_empty_unreviewed_player_after_repoints": players[retired],
        },
        "protected_existing_slots": protected,
        "declared_fk_inventory": before["declared_player_fks"],
        "protected_table_full_row_hashes": {
            table: canonical_sha256(rows)
            for table, rows in before["full_rows"].items()
            if table not in {"kifu_albums", "kifu_raw_player_values", "kifu_player_aliases", "kifu_players"}
        },
        "counts": merge.expected_counts(key),
    }


def run(catalog, command="apply", **kwargs):
    merge, engine, before, plan, approval = catalog
    return merge.run(
        engine,
        plan,
        before,
        command=command,
        expected_plan_sha256=canonical_sha256(plan),
        review=approval,
        actor_id="fixture-executor",
        **kwargs,
    )


def current(catalog):
    merge, engine, _, plan, _ = catalog
    with engine.connect() as conn:
        return merge.capture(conn, "TEST", merge.pair_key(plan))


def business(snapshot):
    return {key: value for key, value in snapshot.items() if key not in {"captured_at", "transaction_read_only"}}


def test_dry_apply_verify_replay_and_atomic_undo_restore_every_field(catalog):
    merge, engine, before, plan, _ = catalog
    dry = merge.run(engine, plan, before, command="dry-run", expected_plan_sha256=canonical_sha256(plan))
    assert dry["status"] == "rolled_back"
    assert business(current(catalog)) == business(before)
    with engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(KifuNameBatch)) == 0
    receipt = run(catalog)
    assert receipt["counts"] == plan["counts"]
    assert merge.verify(engine, receipt["batch_id"])["status"] == "verified"
    assert run(catalog)["status"] == "already_applied"
    with engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(KifuNameBatch)) == 1
        assert conn.scalar(select(func.count()).select_from(KifuNameChange)) == receipt["change_count"]
    undone = merge.undo(engine, receipt["batch_id"])
    assert undone["status"] == "undone"
    assert business(current(catalog)) == business(before)


@pytest.mark.parametrize(
    "edit", ["row", "late_reference", "metadata_reference", "collision", "schema", "column_schema"]
)
def test_changed_scope_refuses_all_writes(catalog, edit):
    _, engine, before, plan, _ = catalog
    survivor = plan["survivor_player"]["id"]
    with engine.begin() as conn:
        if edit == "row":
            conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 1).values(sgf_content="later edit"))
        elif edit == "late_reference":
            conn.execute(
                KifuAlbum.__table__.insert().values(
                    id=9000,
                    black_player_id=survivor,
                    player_black="new spelling",
                    player_white="Opponent",
                    sgf_content="original",
                    source_path="new.sgf",
                )
            )
        elif edit == "metadata_reference":
            conn.execute(
                KifuRawPlayerValue.__table__.insert().values(
                    id=9000,
                    raw_value="late metadata",
                    category="readable_unlinked",
                    review_metadata={"player_id": str(survivor)},
                )
            )
        elif edit == "collision":
            conn.execute(
                KifuPlayerAlias.__table__.insert().values(
                    player_id=12, alias="collision", normalized_alias=plan["retire_player"]["canonical_name"]
                )
            )
        elif edit == "schema":
            conn.exec_driver_sql(
                "CREATE TABLE late_reference (id INTEGER PRIMARY KEY, player_id INTEGER REFERENCES kifu_players(id))"
            )
        else:
            conn.exec_driver_sql("ALTER TABLE kifu_players ADD COLUMN future_identity TEXT")
    changed = business(current(catalog)) if edit not in {"schema", "column_schema"} else None
    with pytest.raises(BatchError):
        run(catalog)
    if changed is not None:
        assert business(current(catalog)) == changed
    with engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(KifuNameBatch)) == 0
        assert conn.scalar(select(func.count()).select_from(KifuNameChange)) == 0


@pytest.mark.parametrize("edit", ["album", "names", "source", "late_reference", "ledger"])
def test_undo_and_replay_refuse_later_edits_atomically(catalog, edit):
    merge, engine, _, plan, _ = catalog
    receipt = run(catalog)
    with engine.begin() as conn:
        if edit == "album":
            conn.execute(KifuAlbum.__table__.update().where(KifuAlbum.id == 1).values(event="later event"))
        elif edit == "names":
            conn.execute(
                KifuPlayerName.__table__.insert().values(
                    player_id=plan["survivor_player"]["id"], lang="fr", display_name="later name", status="review"
                )
            )
        elif edit == "source":
            conn.execute(KifuSource.__table__.update().where(KifuSource.id == 1).values(display_name="later source"))
        elif edit == "late_reference":
            conn.execute(
                KifuAlbum.__table__.insert().values(
                    id=9000,
                    black_player_id=plan["survivor_player"]["id"],
                    player_black="new spelling",
                    player_white="Opponent",
                    sgf_content="original",
                    source_path="new.sgf",
                )
            )
        else:
            conn.execute(KifuNameChange.__table__.delete().where(KifuNameChange.batch_id == receipt["batch_id"]))
    changed = business(current(catalog))
    with pytest.raises(BatchError):
        merge.undo(engine, receipt["batch_id"])
    with pytest.raises(BatchError):
        run(catalog)
    assert business(current(catalog)) == changed
    with engine.connect() as conn:
        assert conn.scalar(select(KifuNameBatch.status).where(KifuNameBatch.id == receipt["batch_id"])) == "applied"


@pytest.mark.parametrize("review_edit", ["pending", "self", "sha"])
def test_apply_requires_independent_exact_plan_approval(catalog, review_edit):
    merge, engine, before, plan, approval = catalog
    approval = deepcopy(approval)
    if review_edit == "pending":
        approval["status"] = "pending"
    elif review_edit == "self":
        approval["reviewer_id"] = approval["producer_id"]
    else:
        approval["plan_sha256"] = "3" * 64
    with pytest.raises(BatchError):
        merge.run(
            engine,
            plan,
            before,
            command="apply",
            expected_plan_sha256=canonical_sha256(plan),
            review=approval,
            actor_id="fixture-executor",
        )
    assert business(current(catalog)) == business(before)


def test_database_rejection_after_album_writes_rolls_back_all_data_and_audit(catalog):
    _, engine, before, _, _ = catalog
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TRIGGER reject_metadata BEFORE UPDATE OF review_metadata ON kifu_raw_player_values "
            "BEGIN SELECT RAISE(ABORT, 'fixture rejection'); END"
        )
    with pytest.raises(BatchError, match="atomic duplicate merge"):
        run(catalog)
    assert business(current(catalog)) == business(before)
    with engine.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(KifuNameBatch)) == 0
        assert conn.scalar(select(func.count()).select_from(KifuNameChange)) == 0


def test_database_rejection_during_undo_rolls_back_restored_owner_and_references(catalog):
    merge, engine, _, _, _ = catalog
    receipt = run(catalog)
    after = business(current(catalog))
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TRIGGER reject_album BEFORE UPDATE OF black_player_id ON kifu_albums "
            "WHEN OLD.id=1 BEGIN SELECT RAISE(ABORT, 'fixture rejection'); END"
        )
    with pytest.raises(BatchError, match="atomic duplicate undo"):
        merge.undo(engine, receipt["batch_id"])
    assert business(current(catalog)) == after
    with engine.connect() as conn:
        assert conn.scalar(select(KifuNameBatch.status).where(KifuNameBatch.id == receipt["batch_id"])) == "applied"


def test_applying_actor_can_be_the_independent_reviewer(catalog):
    merge, engine, before, plan, approval = catalog
    receipt = merge.run(
        engine,
        plan,
        before,
        command="apply",
        expected_plan_sha256=canonical_sha256(plan),
        review=approval,
        actor_id=approval["reviewer_id"],
    )
    assert merge.verify(engine, receipt["batch_id"])["status"] == "verified"
