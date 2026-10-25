"""Portable rank decisions freeze before names and survive profile changes."""

from copy import deepcopy
from hashlib import sha256
import importlib

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
async def test_prepare_freezes_before_name_failure_and_retry_skips_today_profile(tmp_path, monkeypatch, caplog):
    from katrain.kifu_ingest import orchestration
    from katrain.kifu_ingest.staging import Stage
    from tests.test_kifu_incremental_decision_resume import ReviewedNames, _qualified_target, _stage_game

    stage = Stage(tmp_path / "prepare")
    item = _stage_game(stage, "99999001")
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
    calls = []
    monkeypatch.setattr(
        orchestration,
        "lookup_library_rank_facts",
        lambda *a, **kw: calls.append(1) or {1: {"status": "qualified", "fact": fact()}},
    )
    monkeypatch.setattr(orchestration, "_professional_identity_evidence", lambda *a: {})
    failing = ReviewedNames("first", on_translate=lambda _request: (_ for _ in ()).throw(ValueError("name outage")))
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
    monkeypatch.setattr(
        orchestration, "lookup_library_rank_facts", lambda *a, **kw: pytest.fail("cached retry queried current ranks")
    )
    result = await orchestration.prepare_staged_games(
        [item],
        engine=object(),
        client=object(),
        names=ReviewedNames("retry"),
        check_identities=_qualified_target,
        decision_store=stage,
    )
    assert len(calls) == 1
    assert result["format"] == ranks().FORMAT_V2
    assert result["games"][0]["rank_snapshots"]["black"]["display_rank"] == "7p"
    import json

    counts = json.loads(caplog.records[-1].getMessage().split(" ", 1)[1])
    assert {key: counts[key] for key in ("cached", "source", "library_current", "unknown")} == {
        "cached": 2,
        "source": 0,
        "library_current": 1,
        "unknown": 1,
    }
    assert counts["external_rank_refreshes"] == 0
    assert counts["profile_refresh_deferred"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("reverse", [False, True])
async def test_cached_and_new_games_share_fact_without_rewriting_observation_times(tmp_path, monkeypatch, reverse):
    from katrain.kifu_ingest import orchestration
    from katrain.kifu_ingest.staging import Stage
    from tests.test_kifu_incremental_decision_resume import ReviewedNames, _qualified_target, _stage_game

    stage = Stage(tmp_path / "mixed-observations")
    cached = _stage_game(stage, "99999001")
    fresh = _stage_game(stage, "99999002")
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
    monkeypatch.setattr(orchestration, "_professional_identity_evidence", lambda *a: {})
    observed = ["2026-10-01T00:00:00+00:00", "2026-10-02T00:00:00+00:00"]

    def lookup(*args, **kwargs):
        current = fact()
        current["observed_at"] = observed.pop(0)
        return {1: {"status": "qualified", "fact": current}}

    monkeypatch.setattr(orchestration, "lookup_library_rank_facts", lookup)
    names = ReviewedNames("mixed-times")

    async def prepare(items):
        return await orchestration.prepare_staged_games(
            items,
            engine=object(),
            client=object(),
            names=names,
            check_identities=_qualified_target,
            decision_store=stage,
        )

    first = await prepare([cached])
    frozen_game = deepcopy(first["games"][0])
    cached_path = stage._rank_decision_path(frozen_game)[0]
    cached_bytes = cached_path.read_bytes()
    order = [fresh, cached] if reverse else [cached, fresh]
    result = await prepare(order)
    by_source = {item["source_item_id"]: item for item in result["games"]}
    assert by_source["99999001"]["rank_snapshots"] == frozen_game["rank_snapshots"]
    assert by_source["99999002"]["rank_snapshots"]["black"]["observed_at"] == "2026-10-02T00:00:00+00:00"
    assert next(iter(result["rank_facts"].values()))["observed_at"] == "2026-10-01T00:00:00+00:00"
    assert cached_path.read_bytes() == cached_bytes
    all_paths = [stage._rank_decision_path(item)[0] for item in result["games"]]
    all_bytes = {path: path.read_bytes() for path in all_paths}
    monkeypatch.setattr(
        orchestration, "lookup_library_rank_facts", lambda *a, **kw: pytest.fail("cached retry queried ranks")
    )
    replay = await prepare(list(reversed(order)))
    assert replay["rank_facts"] == result["rank_facts"]
    assert {item["source_item_id"]: item["rank_snapshots"] for item in replay["games"]} == {
        source_id: item["rank_snapshots"] for source_id, item in by_source.items()
    }
    assert all(path.read_bytes() == content for path, content in all_bytes.items())
