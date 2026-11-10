"""Portable rank decisions freeze before names and survive profile changes."""

from copy import deepcopy
from hashlib import sha256
import importlib
import json

import pytest

from katrain.kifu_ingest.preparation import derive_metadata
from katrain.web.kifu.player_ranks import build_source_rank_fact


def ranks():
    assert importlib.util.find_spec("katrain.kifu_ingest.ranks"), "rank snapshot contract missing"
    return importlib.import_module("katrain.kifu_ingest.ranks")


def game(source_id="99999001", raw_rank="", day="2026-10-01"):
    sgf = f"(;PB[Black]PW[White]BR[{raw_rank}]EV[Match]DT[{day}];B[aa])"
    return {
        "source_key": "19x19",
        "source_item_id": source_id,
        "origin_path": f"data/kifu-album/19x19/{source_id}.sgf",
        "raw_sha256": sha256(sgf.encode()).hexdigest(),
        "sgf_sha256": sha256(sgf.encode()).hexdigest(),
        "sgf_content": sgf,
        "metadata": derive_metadata(sgf),
        "identities": {"black": {"canonical_name": "Black"}, "white": {"canonical_name": "White"}},
    }


def fact(value="7p", source_id="99999000", day="2026-09-01"):
    item = game(source_id, value, day)
    return build_source_rank_fact(
        canonical_name="Black",
        raw_rank=value,
        sgf_content=item["sgf_content"],
        slot="black",
        source_ref={"source_key": "19x19", "source_item_id": source_id},
        observed_at="2026-10-01T00:00:00Z",
    )


def frozen(item, library=None):
    module = ranks()
    decision = module.freeze_game_ranks(item, library_facts=library or {}, matched_at="2026-10-01T00:00:00Z")
    value = {
        "format": module.FORMAT_V2,
        "games": [{**item, **{k: decision[k] for k in ("rank_snapshots", "rank_observations")}}],
        "rank_facts": decision["rank_facts"],
    }
    module.validate_manifest_ranks(value)
    return value


def test_original_rank_precedes_profile_and_blank_uses_frozen_library_fact():
    source = frozen(game(raw_rank="9d"), {"Black": fact("8p")})
    snapshot = source["games"][0]["rank_snapshots"]["black"]
    assert (snapshot["display_rank"], snapshot["rank_system"], snapshot["origin"]) == ("9d", "amateur_dan", "source")
    assert source["games"][0]["rank_observations"]["black"] in source["rank_facts"]
    professional_source = frozen(game(raw_rank="9p"), {"Black": fact("8p")})
    assert professional_source["games"][0]["rank_snapshots"]["black"]["display_rank"] == "9p"
    fallback = frozen(game(), {"Black": fact()})
    snapshot = fallback["games"][0]["rank_snapshots"]["black"]
    assert (snapshot["display_rank"], snapshot["origin"]) == ("7p", "library_current")
    assert ranks().display_rank_for_game_slot(snapshot)["rank"] == "7p"
    assert fallback["games"][0]["rank_observations"]["black"] is None


def test_invalid_original_raw_rank_is_not_displayed_or_replaced_by_library():
    value = frozen(game(raw_rank="3002"), {"Black": fact()})
    snapshot = value["games"][0]["rank_snapshots"]["black"]
    assert snapshot["raw_rank"] == "3002"
    assert snapshot["display_rank"] == ""
    assert snapshot["origin"] == "source"
    assert snapshot["rank_fact_sha256"] is None
    assert ranks().display_rank_for_game_slot(snapshot)["rank"] == ""


def test_bad_library_fact_leaves_only_its_player_unknown():
    invalid = fact()
    invalid["content_sha256"] = "f" * 64
    value = frozen(game(), {"Black": invalid})
    assert value["games"][0]["rank_snapshots"]["black"]["origin"] == "unknown"
    assert value["rank_facts"] == {}


def test_bad_professional_proof_keeps_original_source_observation_untyped():
    item = game(raw_rank="七段")
    decision = ranks().freeze_game_ranks(item, identity_evidence={"Black": {"bad": "proof"}})
    value = {
        "format": ranks().FORMAT_V2,
        "games": [{**item, **{key: decision[key] for key in ("rank_snapshots", "rank_observations")}}],
        "rank_facts": decision["rank_facts"],
    }
    ranks().validate_manifest_ranks(value)
    snapshot = value["games"][0]["rank_snapshots"]["black"]
    assert snapshot["display_rank"] == "七段"
    assert snapshot["rank_system"] == "dan_unspecified"
    assert value["games"][0]["rank_observations"]["black"] is not None


@pytest.mark.asyncio
async def test_manifest_oversize_is_rejected_before_paid_names(tmp_path, monkeypatch):
    from katrain.kifu_ingest import orchestration
    from katrain.kifu_ingest.staging import Stage
    from tests.test_kifu_incremental_decision_resume import ReviewedNames, _mock_catalog, _qualified_target, _stage_game

    _mock_catalog(monkeypatch)
    stage = Stage(tmp_path / "oversize")
    item = _stage_game(stage, "99999001")
    monkeypatch.setattr(ranks(), "MAX_MANIFEST_BYTES", 2000)
    names = ReviewedNames("oversize")
    with pytest.raises(ValueError, match="budget"):
        await orchestration.prepare_staged_games(
            [item], engine=object(), client=object(), names=names, check_identities=_qualified_target
        )
    assert names.calls == []


@pytest.mark.parametrize("mutation", ["hash", "slot", "owner", "raw"])
def test_corrupt_snapshot_or_fact_is_rejected(mutation):
    value = frozen(game(), {"Black": fact()})
    snapshot = value["games"][0]["rank_snapshots"]["black"]
    if mutation == "hash":
        next(iter(value["rank_facts"].values()))["rank_value"] = 9
    elif mutation == "slot":
        snapshot["source_ref"]["slot"] = "white"
    elif mutation == "owner":
        snapshot["player_ref"] = {"canonical_name": "White"}
    else:
        snapshot["raw_rank"] = "9p"
    if mutation != "hash":
        snapshot["content_sha256"] = ranks().snapshot_sha256(snapshot)
    with pytest.raises(ValueError):
        ranks().validate_manifest_ranks(value)


def test_unknown_and_library_checkpoint_are_immutable(tmp_path):
    from katrain.kifu_ingest.staging import Stage

    stage = Stage(tmp_path / "stage")
    item = game()
    value = frozen(item)["games"][0]
    payload = {
        "rank_snapshots": value["rank_snapshots"],
        "rank_observations": value["rank_observations"],
        "rank_facts": {},
    }
    assert stage.load_rank_decision(item) is None
    stage.save_rank_decision(item, payload)
    assert stage.load_rank_decision(item) == payload
    replacement = frozen(item, {"Black": fact()})
    with pytest.raises(ValueError, match="frozen"):
        stage.save_rank_decision(item, {**replacement["games"][0], "rank_facts": replacement["rank_facts"]})
    assert stage.load_rank_decision(item) == payload


@pytest.mark.asyncio
async def test_legacy_checkpoint_survives_name_failure_and_retry_without_current_lookup(tmp_path, monkeypatch, caplog):
    from katrain.kifu_ingest import orchestration
    from katrain.kifu_ingest.staging import Stage
    from tests.test_kifu_incremental_decision_resume import ReviewedNames, _qualified_target, _stage_game

    stage = Stage(tmp_path / "prepare")
    item = _stage_game(stage, "99999001")
    game = await orchestration.derive_staged_record(item)
    game["identities"] = {"black": {"canonical_name": "Black"}, "white": {"canonical_name": "White"}}
    legacy = ranks().freeze_game_ranks(game, library_facts={"Black": fact()})
    stage.save_rank_decision(game, legacy)
    checkpoint = stage._rank_decision_path(game)[0]
    frozen_bytes = checkpoint.read_bytes()
    monkeypatch.setattr(
        orchestration,
        "lookup_qualified_identities",
        lambda *a, **kw: {
            "player": {
                name: {"id": i, "canonical_name": name, "status": "qualified"}
                for i, name in enumerate(("Black", "White"), 1)
            },
            "event": {"Match": {"status": "unresolved"}},
        },
    )
    monkeypatch.setattr(orchestration, "qualified_raw_event_templates", lambda *a, **kw: {"templates": {}})
    monkeypatch.setattr(
        orchestration, "_historical_rank_decisions", lambda *a: pytest.fail("legacy checkpoint was refrozen")
    )
    monkeypatch.setattr(orchestration, "lookup_library_rank_facts", lambda *a, **kw: pytest.fail("current lookup"))
    failing = ReviewedNames("first", on_translate=lambda _: (_ for _ in ()).throw(ValueError("name outage")))
    caplog.set_level("INFO", logger=orchestration.__name__)
    with pytest.raises(ValueError, match="name outage"):
        await orchestration.prepare_staged_games(
            [item],
            engine=object(),
            client=object(),
            names=failing,
            check_identities=_qualified_target,
            decision_store=stage,
        )
    result = await orchestration.prepare_staged_games(
        [item],
        engine=object(),
        client=object(),
        names=ReviewedNames("retry"),
        check_identities=_qualified_target,
        decision_store=stage,
    )
    assert result["games"][0]["rank_snapshots"] == legacy["rank_snapshots"]
    assert checkpoint.read_bytes() == frozen_bytes
    counts = json.loads(caplog.records[-1].getMessage().split(" ", 1)[1])
    assert counts["cached"] == 2 and counts["library_current"] == 1
    assert counts["external_rank_refreshes"] == 0 and counts["profile_refresh_deferred"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True])
async def test_mixed_old_checkpoint_and_new_v3_keep_old_bytes_and_observation(tmp_path, monkeypatch, reverse):
    from katrain.kifu_ingest import orchestration
    from katrain.kifu_ingest.staging import Stage
    from tests.test_kifu_incremental_decision_resume import ReviewedNames, _qualified_target, _stage_game
    from tests.web_ui.test_kifu_incremental_catalog import make_engine

    engine = make_engine(tmp_path / "mixed.db")
    stage = Stage(tmp_path / "mixed-stage")
    cached, fresh = [
        _stage_game(stage, item, black="Black Alias", white="White Alias", event="Summer Cup")
        for item in ("99999001", "99999002")
    ]
    game = await orchestration.derive_staged_record(cached)
    game["identities"] = {"black": {"canonical_name": "Black"}, "white": {"canonical_name": "White"}}
    legacy = ranks().freeze_game_ranks(game, library_facts={"Black": fact()}, matched_at="2026-10-01T00:00:00Z")
    stage.save_rank_decision(game, legacy)
    path = stage._rank_decision_path(game)[0]
    frozen_bytes = path.read_bytes()
    order = [fresh, cached] if reverse else [cached, fresh]

    async def prepare(items):
        return await orchestration.prepare_staged_games(
            items,
            engine=engine,
            client=object(),
            names=ReviewedNames("mixed"),
            check_identities=_qualified_target,
            decision_store=stage,
        )

    result = await prepare(order)
    by_source = {game["source_item_id"]: game for game in result["games"]}
    assert by_source["99999001"]["rank_snapshots"] == legacy["rank_snapshots"]
    assert by_source["99999002"]["rank_snapshots"]["black"]["version"] == "kifu-rank-snapshot-v3"
    assert result["rank_facts"] == legacy["rank_facts"]
    assert path.read_bytes() == frozen_bytes
    monkeypatch.setattr(
        orchestration, "_historical_rank_decisions", lambda *a: pytest.fail("cached retry reread history")
    )
    replay = await prepare(list(reversed(order)))
    assert replay["rank_facts"] == result["rank_facts"]
    assert {game["source_item_id"]: game["rank_snapshots"] for game in replay["games"]} == {
        source: game["rank_snapshots"] for source, game in by_source.items()
    }
    assert path.read_bytes() == frozen_bytes
