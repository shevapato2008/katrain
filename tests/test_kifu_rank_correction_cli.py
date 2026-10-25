"""Finite correction packs use synthetic games and a temporary database only."""

from hashlib import sha256
import importlib
import json

import pytest
from sqlalchemy import create_engine, event, select

from katrain.kifu_ingest.preparation import derive_metadata
from katrain.web.core import models_db as m
from katrain.web.kifu.name_candidates import canonical_sha256
from katrain.web.kifu.player_ranks import apply_rank_fact, build_source_rank_fact


def cli():
    assert importlib.util.find_spec("scripts.kifu_rank_correction"), "finite rank correction CLI is missing"
    return importlib.import_module("scripts.kifu_rank_correction")


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    module = cli()
    engine = create_engine("sqlite:///:memory:")
    m.Base.metadata.create_all(engine)
    originals, pins, albums = [], {}, []
    registry = m.KifuNameSourceRegistry.__table__
    with engine.begin() as conn:
        conn.execute(registry.insert().values(id=1, version="test", sha256="a" * 64, registry={"sources": []}))
        conn.execute(m.KifuSource.__table__.insert().values(id=1, source_key="19x19"))
        for index, item in enumerate(("91694911", "91638738", "91637528")):
            black, white = f"棋手{index * 2 + 1}", f"棋手{index * 2 + 2}"
            ids = (index * 2 + 1, index * 2 + 2)
            conn.execute(
                m.KifuPlayer.__table__.insert(),
                [{"id": ids[0], "canonical_name": black}, {"id": ids[1], "canonical_name": white}],
            )
            content = f"(;FF[4]PB[{black}]PW[{white}]EV[测试比赛]DT[2026-10-24]SZ[19];B[aa])"
            digest = sha256(content.encode()).hexdigest()
            game = {
                "source_key": "19x19",
                "source_item_id": item,
                "origin_path": f"data/kifu-album/19x19/{item}.sgf",
                "raw_sha256": digest,
                "sgf_sha256": digest,
                "sgf_content": content,
                "metadata": derive_metadata(content),
                "source_metadata": None,
                "identities": {"black": {"canonical_name": black}, "white": {"canonical_name": white}, "event": None},
            }
            original = {
                "format": "kifu-incremental-manifest-v1",
                "publication_key": f"old-{item}",
                "games": [game],
                "decisions": [],
            }
            original_sha = canonical_sha256(original)
            pins[item] = {"sgf_sha256": digest, "manifest_sha256": original_sha}
            path = tmp_path / f"{item}.json"
            path.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")
            originals.append(path)
            album_id = 100 + index
            albums.append(album_id)
            conn.execute(
                m.KifuAlbum.__table__.insert().values(
                    id=album_id,
                    **game["metadata"],
                    sgf_content=content,
                    source_path=game["origin_path"],
                    black_player_id=ids[0],
                    white_player_id=ids[1],
                )
            )
            conn.execute(
                m.KifuAlbumSource.__table__.insert().values(
                    album_id=album_id, source_id=1, origin_path=game["origin_path"], match_method="incremental-new"
                )
            )
            source = {
                key: game[key] for key in ("source_key", "source_item_id", "origin_path", "raw_sha256", "sgf_sha256")
            }
            source.update(album_id=album_id, album_sgf_sha256=digest)
            receipt = {
                "status": "applied",
                "games": [{"source_key": "19x19", "source_item_id": item, "album_id": album_id, "action": "inserted"}],
            }
            artifact = {
                "publication_format": original["format"],
                "manifest_sha256": original_sha,
                "logical_manifest": {
                    **original,
                    "games": [{key: value for key, value in game.items() if key != "sgf_content"}],
                },
                "sources": [source],
                "receipt": receipt,
            }
            conn.execute(
                m.KifuNameBatch.__table__.insert().values(
                    bundle_sha256=original_sha,
                    inventory_sha256="b" * 64,
                    source_registry_id=1,
                    reviewed_artifact=artifact,
                    status="applied",
                )
            )
            for player_id, name in zip(ids, (black, white)):
                ranked = f"(;PB[{name}]PW[对手]BR[7p]DT[2026-10-01])"
                fact = build_source_rank_fact(
                    canonical_name=name,
                    raw_rank="7p",
                    sgf_content=ranked,
                    slot="black",
                    source_ref={"source_key": "19x19", "source_item_id": str(player_id)},
                    observed_at="2026-10-25T00:00:00+00:00",
                )
                apply_rank_fact(
                    conn,
                    player_id,
                    fact,
                    source_games=[
                        {
                            "source_key": "19x19",
                            "source_item_id": str(player_id),
                            "sgf_content": ranked,
                            "metadata": {"player_black": name, "player_white": "对手", "black_rank": "7p"},
                        }
                    ],
                )
    monkeypatch.setattr(module, "PINNED_ORIGINALS", pins)
    yield module, engine, originals, albums
    engine.dispose()


def test_exact_three_pack_is_portable_rank_only_and_build_is_read_only(fixture):
    module, engine, originals, _ = fixture
    writes = []

    @event.listens_for(engine, "before_cursor_execute")
    def record(_conn, _cursor, statement, *_args):
        if statement.lstrip().split()[0].upper() in {"INSERT", "UPDATE", "DELETE", "CREATE", "ALTER"}:
            writes.append(statement)

    manifest = module.build_correction(engine, originals, matched_at="2026-10-25T01:00:00+00:00")
    assert manifest["mode"] == "rank_only" and manifest["decisions"] == []
    assert {game["source_item_id"] for game in manifest["games"]} == set(module.PINNED_ORIGINALS)
    assert len(manifest["rank_facts"]) == 6
    for game in manifest["games"]:
        assert "album_id" not in game
        assert game["metadata"].get("black_rank") is None
        assert game["rank_snapshots"]["black"]["display_rank"] == "7p"
        assert game["rank_correction"]["expected_snapshots"] == {"black": None, "white": None}
    assert writes == []


@pytest.mark.parametrize("change", ["extra", "missing", "sgf", "source", "raw_rank", "identity", "prior_overlay"])
def test_invalid_preimage_rejects_before_any_publication(fixture, change):
    module, engine, originals, albums = fixture
    if change == "extra":
        originals.append(originals[0])
    elif change == "missing":
        originals.pop()
    elif change in {"sgf", "source", "raw_rank"}:
        pack = json.loads(originals[0].read_text())
        game = pack["games"][0]
        if change == "sgf":
            game["sgf_content"] += " "
        elif change == "source":
            game["source_item_id"] = "999"
        else:
            game["metadata"]["black_rank"] = "7p"
        originals[0].write_text(json.dumps(pack))
    elif change == "identity":
        with engine.begin() as conn:
            conn.execute(m.KifuAlbum.__table__.update().where(m.KifuAlbum.id == albums[0]).values(black_player_id=2))
    else:
        with engine.begin() as conn:
            conn.execute(
                m.KifuAlbumRankSnapshot.__table__.insert().values(
                    album_id=albums[0],
                    side="black",
                    snapshot={"content_sha256": "c" * 64},
                    snapshot_sha256="d" * 64,
                    publication_key="old-rank",
                    native_batch_id=1,
                )
            )
    writes = []

    @event.listens_for(engine, "before_cursor_execute")
    def record(_conn, _cursor, statement, *_args):
        if statement.lstrip().split()[0].upper() in {"INSERT", "UPDATE", "DELETE", "CREATE", "ALTER"}:
            writes.append(statement)

    with pytest.raises(ValueError):
        module.build_correction(engine, originals)
    assert writes == []


def test_frozen_output_retry_does_not_recompute_after_promotion(fixture, tmp_path, monkeypatch):
    module, engine, originals, _ = fixture
    output = tmp_path / "correction.json"
    manifest = module.build_correction(engine, originals, matched_at="2026-10-25T01:00:00+00:00")
    module.freeze_output(output, manifest)
    raw = output.read_bytes()
    promoted = "(;PB[棋手1]PW[对手]BR[8p]DT[2026-10-26])"
    fact = build_source_rank_fact(
        canonical_name="棋手1",
        raw_rank="8p",
        sgf_content=promoted,
        slot="black",
        source_ref={"source_key": "19x19", "source_item_id": "999"},
        observed_at="2026-10-26T01:00:00+00:00",
    )
    with engine.begin() as conn:
        apply_rank_fact(
            conn,
            1,
            fact,
            source_games=[
                {
                    "source_key": "19x19",
                    "source_item_id": "999",
                    "sgf_content": promoted,
                    "metadata": {"player_black": "棋手1", "player_white": "对手", "black_rank": "8p"},
                }
            ],
        )
    with pytest.raises(ValueError, match="already exists"):
        module.freeze_output(output, manifest)
    monkeypatch.setattr(module, "build_correction", lambda *_a, **_k: pytest.fail("recomputed frozen pack"))
    monkeypatch.setattr(module, "_engine", lambda *_a: pytest.fail("opened database on frozen retry"))
    assert module.main(["build", "--output", str(output)]) == 0
    assert output.read_bytes() == raw


@pytest.mark.parametrize("fact_link", ["valid", "missing", "wrong_owner"])
def test_current_complete_snapshot_hash_is_frozen_as_cas(fixture, fact_link):
    module, engine, originals, albums = fixture
    first = module.build_correction(engine, originals)
    game = next(game for game in first["games"] if game["source_item_id"] == "91694911")
    snapshot = game["rank_snapshots"]["black"]
    with engine.begin() as conn:
        fact_id = conn.scalar(select(m.KifuPlayerRankHistory.id).where(m.KifuPlayerRankHistory.player_id == 1))
        if fact_link == "missing":
            fact_id = None
        elif fact_link == "wrong_owner":
            fact_id = conn.scalar(select(m.KifuPlayerRankHistory.id).where(m.KifuPlayerRankHistory.player_id == 2))
        conn.execute(
            m.KifuAlbumRankSnapshot.__table__.insert().values(
                album_id=albums[0],
                side="black",
                snapshot=snapshot,
                snapshot_sha256=snapshot["content_sha256"],
                rank_fact_id=fact_id,
                publication_key="prior",
                native_batch_id=1,
            )
        )
    if fact_link != "valid":
        with pytest.raises(ValueError, match="fact"):
            module.build_correction(engine, originals)
        return
    second = module.build_correction(engine, originals)
    game = next(game for game in second["games"] if game["source_item_id"] == "91694911")
    assert game["rank_correction"]["expected_snapshots"] == {
        "black": snapshot["content_sha256"],
        "white": None,
    }


def test_forbidden_album_path_is_rejected_before_open(monkeypatch):
    module = cli()
    monkeypatch.setattr(module.os, "open", lambda *_a, **_k: pytest.fail("opened forbidden filesystem path"))
    with pytest.raises(ValueError, match="album filesystem access"):
        module._read_json("/app/data/kifu-album/19x19/91694911.sgf")


def test_default_cli_build_does_not_create_stage_or_output(fixture, tmp_path, monkeypatch, capsys):
    module, engine, originals, _ = fixture
    monkeypatch.setattr(module, "_engine", lambda *_a: engine)
    before = {path.name for path in tmp_path.iterdir()}
    args = ["build"]
    for path in originals:
        args.extend(["--original", str(path)])
    assert module.main(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "dry_run" and result["games"] == 3
    assert {path.name for path in tmp_path.iterdir()} == before


def test_apply_requires_digest_explicit_apply_and_test_target(fixture, tmp_path, monkeypatch):
    module, engine, originals, _ = fixture
    manifest = module.build_correction(engine, originals)
    output = tmp_path / "correction.json"
    module.freeze_output(output, manifest)
    digest = canonical_sha256(manifest)
    calls = []
    monkeypatch.setattr(module, "_engine", lambda *_a: engine)
    monkeypatch.setattr(
        module, "publish_manifest", lambda db, pack, **kw: calls.append((db, pack, kw)) or {"status": "applied"}
    )
    assert module.main(["apply-existing", "--manifest", str(output), "--expected-sha256", digest]) == 2
    assert (
        module.main(
            ["apply-existing", "--manifest", str(output), "--expected-sha256", "0" * 64, "--apply", "--target", "test"]
        )
        == 2
    )
    assert calls == []
    args = ["apply-existing", "--manifest", str(output), "--expected-sha256", digest, "--apply", "--target", "test"]
    assert module.main(args) == 0
    assert calls == [(engine, manifest, {"expected_manifest_sha256": digest})]


def test_public_whitelist_is_exact():
    module = cli()
    assert set(module.PINNED_ORIGINALS) == {"91694911", "91638738", "91637528"}
    assert (
        module.PINNED_ORIGINALS["91694911"]["sgf_sha256"]
        == "b044277aaac3223d3304fee2b958358418a83624d8c817fedb850c1994d845c2"
    )


def test_frozen_cli_pack_applies_and_replays_through_actual_native_publisher(tmp_path, monkeypatch, capsys):
    from katrain.kifu_ingest import catalog
    from tests.web_ui.test_kifu_incremental_catalog import make_engine, manifest, publish, state
    from tests.web_ui.test_kifu_rank_publication import ranked

    module = cli()
    engine = make_engine(tmp_path / "native.db")
    originals, pins = [], {}
    for item in ("91694911", "91638738", "91637528"):
        original = manifest(item, black="Black")
        game = original["games"][0]
        content = game["sgf_content"].replace("whole original", f"synthetic {item}")
        game.update(
            sgf_content=content,
            sgf_sha256=sha256(content.encode()).hexdigest(),
            raw_sha256=sha256(content.encode()).hexdigest(),
            metadata=derive_metadata(content),
            origin_path=f"data/kifu-album/19x19/{item}.sgf",
            identities={"black": {"canonical_name": "Black"}, "white": {"canonical_name": "White"}},
        )
        publish(engine, original)
        pins[item] = {"manifest_sha256": canonical_sha256(original), "sgf_sha256": game["sgf_sha256"]}
        path = tmp_path / f"original-{item}.json"
        path.write_text(json.dumps(original), encoding="utf-8")
        originals.append(path)
    publish(engine, ranked("99999099", "7p", "2026-03-01"))
    monkeypatch.setattr(module, "PINNED_ORIGINALS", pins)
    value = module.build_correction(engine, originals)
    frozen = tmp_path / "frozen.json"
    module.freeze_output(frozen, value)
    before = state(engine)
    monkeypatch.setattr(module, "_engine", lambda *_a: engine)
    for name in ("warm_sgf_cache", "_identity_indexes", "_source_records", "_apply_decisions"):
        monkeypatch.setattr(catalog, name, lambda *_a, **_kw: pytest.fail("correction entered name/global path"))
    args = [
        "apply-existing",
        "--manifest",
        str(frozen),
        "--expected-sha256",
        canonical_sha256(value),
        "--apply",
        "--target",
        "test",
    ]
    assert module.main(args) == 0
    first = json.loads(capsys.readouterr().out)
    after = state(engine)
    assert after[m.KifuAlbum.__table__] == before[m.KifuAlbum.__table__]
    assert after[m.KifuAlbumSource.__table__] == before[m.KifuAlbumSource.__table__]
    assert after[m.KifuNameBatch.__table__][:-1] == before[m.KifuNameBatch.__table__]
    assert module.main(args) == 0
    assert json.loads(capsys.readouterr().out) == first
    assert state(engine) == after
    engine.dispose()
