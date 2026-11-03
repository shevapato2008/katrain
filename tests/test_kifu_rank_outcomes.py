"""Exact-source reuse reports verify the retained rank rather than an incoming overlay."""

from copy import deepcopy
from hashlib import sha256

import pytest

from katrain.core.sgf_parser import SGF
from katrain.kifu_ingest import ranks, sync
from katrain.web.kifu.name_candidates import canonical_sha256
from tests.test_kifu_api_verification import AlbumAPI, validate_rank_report
from tests.web_ui.test_kifu_historical_rank_native import prepared
from tests.web_ui.test_kifu_incremental_catalog import make_engine


def outcome_api(tmp_path, *, retained=False, different_bytes=False):
    engine = make_engine(tmp_path / "outcomes.db")
    manifest = prepared(engine, item="99102", raw="9p")
    game = manifest["games"][0]
    original = deepcopy(game)
    original.update(source_item_id="99101", origin_path="data/kifu-album/19x19/99101.sgf")
    if different_bytes:
        original["sgf_content"] = "\n" + original["sgf_content"]
        original["sgf_sha256"] = sha256(original["sgf_content"].encode()).hexdigest()
    old = ranks.freeze_game_ranks(original)
    outcomes = [
        dict(
            source_key=game["source_key"],
            source_item_id=game["source_item_id"],
            album_id=7,
            side=side,
            status="retained" if retained else "deferred",
            requested_snapshot_sha256=game["rank_snapshots"][side]["content_sha256"],
            original_source_ref=dict(
                source_key=original["source_key"],
                origin_path=original["origin_path"],
                sgf_sha256=original["sgf_sha256"],
                slot=side,
            ),
            retained_snapshot=old["rank_snapshots"][side] if retained else None,
            original_canonical_sgf_sha256=sha256(SGF.parse_sgf(original["sgf_content"]).sgf().encode()).hexdigest(),
        )
        for side in ("black", "white")
    ]
    api = AlbumAPI()
    api.manifest = manifest
    api.receipt = dict(
        status="applied",
        manifest_sha256=canonical_sha256(manifest),
        batch_id=9,
        games=[dict(source_key="19x19", source_item_id="99102", album_id=7, action="reused")],
        rank_outcomes=outcomes,
    )
    for lang in sync.LANGUAGES:
        value = api.details[7, lang]
        value.update(
            game["metadata"],
            sgf_content=original["sgf_content"],
            black_rank=game["metadata"].get("black_rank"),
            white_rank=game["metadata"].get("white_rank"),
        )
        for side in ("black", "white"):
            if retained:
                from katrain.web.kifu.name_parse import parse_player

                raw = parse_player(
                    game["metadata"][f"player_{side}"], game["metadata"].get(f"{side}_rank")
                ).display_rank
                expected = ranks.display_rank_for_game_slot(old["rank_snapshots"][side], raw)
            else:
                expected = dict(
                    rank="9p" if side == "black" else "",
                    rank_origin="source" if side == "black" else "unknown",
                    rank_source=None,
                )
            value.update(
                {
                    f"display_{side}_rank": expected["rank"],
                    f"{side}_rank_origin": expected["rank_origin"],
                    f"{side}_rank_source": expected["rank_source"],
                }
            )
    api.listing["items"] = [deepcopy(api.details[7, "cn"])]
    return api


@pytest.mark.asyncio
@pytest.mark.parametrize("retained,different_bytes", [(False, False), (True, False), (True, True)])
async def test_report_verifies_actual_retained_or_deferred_rank(tmp_path, retained, different_bytes):
    api = outcome_api(tmp_path, retained=retained, different_bytes=different_bytes)
    result = await api.verify()
    assert result["publication_receipt"] == api.receipt
    assert result["receipt_sha256"] == canonical_sha256(api.receipt)
    assert (
        result["checks"][0]["original_sgf_sha256"]
        == api.receipt["rank_outcomes"][0]["original_source_ref"]["sgf_sha256"]
    )
    validate_rank_report(api, result)


@pytest.mark.asyncio
@pytest.mark.parametrize("damage", ["requested", "slot", "source", "body", "display", "flag", "receipt_hash"])
async def test_report_rejects_forged_rank_outcome_or_api_evidence(tmp_path, damage):
    api = outcome_api(tmp_path, retained=True)
    result = await api.verify()
    if damage == "display":
        result["checks"][0]["ranks"]["black"]["display_rank"] = "8p"
    elif damage == "body":
        result["checks"][0]["original_sgf_sha256"] = "a" * 64
    elif damage == "receipt_hash":
        result["receipt_sha256"] = "a" * 64
    else:
        entry = result["publication_receipt"]["rank_outcomes"][0]
        if damage == "requested":
            entry["requested_snapshot_sha256"] = "a" * 64
        elif damage == "slot":
            entry["side"] = "white"
        elif damage == "source":
            entry["original_source_ref"]["origin_path"] = "data/kifu-album/19x19/99102.sgf"
        else:
            entry.update(status="deferred", retained_snapshot=None)
        result["receipt_sha256"] = canonical_sha256(result["publication_receipt"])
    with pytest.raises(ValueError):
        validate_rank_report(api, result)


@pytest.mark.asyncio
async def test_distinct_sources_can_share_only_one_frozen_actual_album(tmp_path):
    api = outcome_api(tmp_path, retained=True)
    other = deepcopy(api.manifest["games"][0])
    other["source_item_id"] = "99103"
    other["origin_path"] = "data/kifu-album/19x19/99103.sgf"
    for snapshot in other["rank_snapshots"].values():
        snapshot["source_ref"]["origin_path"] = other["origin_path"]
        snapshot["content_sha256"] = ranks.snapshot_sha256(snapshot)
    original = ranks.freeze_game_ranks(other)
    other["rank_observations"] = original["rank_observations"]
    api.manifest["rank_facts"].update(original["rank_facts"])
    api.manifest["games"].append(other)
    api.receipt["games"].append(dict(source_key="19x19", source_item_id="99103", album_id=7, action="reused"))
    for side in ("black", "white"):
        outcome = deepcopy(api.receipt["rank_outcomes"][0 if side == "black" else 1])
        outcome.update(
            source_item_id="99103", requested_snapshot_sha256=other["rank_snapshots"][side]["content_sha256"]
        )
        api.receipt["rank_outcomes"].append(outcome)
    api.receipt["manifest_sha256"] = canonical_sha256(api.manifest)
    result = await api.verify()
    assert len(result["checks"]) == 10 and len(result["public_cards"]) == 2
    validate_rank_report(api, result)
    # A source cannot be reassigned to another original merely because the
    # target ID appears elsewhere in this same report.
    result["publication_receipt"]["rank_outcomes"][-1]["original_source_ref"][
        "origin_path"
    ] = "data/kifu-album/19x19/999.sgf"
    result["receipt_sha256"] = canonical_sha256(result["publication_receipt"])
    with pytest.raises(ValueError):
        validate_rank_report(api, result)


@pytest.mark.asyncio
async def test_receiver_passes_verified_test_outcomes_as_production_expectation(tmp_path, monkeypatch):
    from katrain.kifu_ingest import orchestration

    api = outcome_api(tmp_path, retained=True)
    report = await api.verify()
    digest = canonical_sha256(api.manifest)
    report["manifest_sha256"] = digest
    monkeypatch.setattr(
        orchestration,
        "_receive_payload",
        lambda: dict(manifest=api.manifest, manifest_sha256=digest, test_verification=report),
    )
    monkeypatch.setattr(orchestration, "_engine", lambda: object())
    captured = []

    def publish(_engine, manifest, *, expected_manifest_sha256, expected_rank_outcomes):
        assert manifest == api.manifest and expected_manifest_sha256 == digest
        captured.append(expected_rank_outcomes)
        return api.receipt

    monkeypatch.setattr(orchestration, "publish_manifest", publish)
    monkeypatch.setattr(orchestration, "_output", lambda _: None)
    assert orchestration.main(["receive"]) == 0
    assert captured == [api.receipt["rank_outcomes"]]


@pytest.mark.asyncio
async def test_applied_outcome_keeps_incoming_v3_provenance_strict(tmp_path):
    api = outcome_api(tmp_path)
    game = api.manifest["games"][0]
    for side, outcome in zip(("black", "white"), api.receipt["rank_outcomes"]):
        outcome.update(status="applied", original_source_ref=deepcopy(game["rank_snapshots"][side]["source_ref"]))
        expected = ranks.display_rank_for_game_slot(game["rank_snapshots"][side])
        for lang in sync.LANGUAGES:
            api.details[7, lang].update(
                {
                    f"display_{side}_rank": expected["rank"],
                    f"{side}_rank_origin": expected["rank_origin"],
                    f"{side}_rank_source": expected["rank_source"],
                }
            )
    api.listing["items"] = [deepcopy(api.details[7, "cn"])]
    result = await api.verify()
    validate_rank_report(api, result)
    missing = deepcopy(result)
    missing.pop("publication_receipt")
    for evidence in [*missing["checks"], *missing["public_cards"]]:
        evidence.pop("original_sgf_sha256")
    with pytest.raises(ValueError, match="actual rank outcome receipt"):
        validate_rank_report(api, missing)
    result["checks"][0]["ranks"]["black"]["source"] = None
    with pytest.raises(ValueError):
        validate_rank_report(api, result)


@pytest.mark.asyncio
async def test_retained_v2_keeps_original_signed_bytes_and_raw_body_sha(tmp_path):
    from katrain.web.kifu.source_rank_normalization import build_source_snapshot

    api = outcome_api(tmp_path, retained=True, different_bytes=True)
    game = api.manifest["games"][0]
    ref = api.receipt["rank_outcomes"][0]["original_source_ref"]
    album = dict(
        game["metadata"],
        id=7,
        source_path=ref["origin_path"],
        sgf_content=api.details[7, "cn"]["sgf_content"],
        black_player_id=17,
        white_player_id=18,
    )
    link = dict(album_id=7, id=41, source_id=4, origin_path=ref["origin_path"], source_key="19x19")
    snapshot = build_source_snapshot(album, "black", link)
    api.receipt["rank_outcomes"][0]["retained_snapshot"] = snapshot
    expected = dict(
        policy_version=snapshot["policy_version"],
        snapshot_sha256=snapshot["content_sha256"],
        rank_system=snapshot["rank_system"],
        source_ref=snapshot["source_ref"],
        source_kind=snapshot["evidence"]["kind"],
    )
    for lang in sync.LANGUAGES:
        api.details[7, lang]["black_rank_source"] = deepcopy(expected)
    api.listing["items"] = [deepcopy(api.details[7, "cn"])]
    result = await api.verify()
    assert result["publication_receipt"]["rank_outcomes"][0]["retained_snapshot"] == snapshot
    assert result["checks"][0]["ranks"]["black"]["source"] == expected
    validate_rank_report(api, result)
    changed = deepcopy(api.receipt["rank_outcomes"])
    changed[0]["retained_snapshot"]["source_ref"]["source_id"] = 5
    changed[0]["retained_snapshot"]["content_sha256"] = ranks.snapshot_sha256(changed[0]["retained_snapshot"])
    assert ranks.portable_rank_outcomes(changed) != ranks.portable_rank_outcomes(api.receipt["rank_outcomes"])


@pytest.mark.asyncio
@pytest.mark.parametrize("retained,different_bytes", [(False, False), (True, False), (True, True)])
async def test_native_reuse_runs_real_detail_list_verification_and_frozen_replay(tmp_path, retained, different_bytes):
    from types import SimpleNamespace
    from sqlalchemy.orm import Session
    from katrain.web.api.v1.endpoints import kifu
    from tests.web_ui.test_kifu_incremental_catalog import publish

    engine = make_engine(tmp_path / "native-outcomes.db")
    old = prepared(engine, item="99101", raw="9p")
    original = old["games"][0]
    if different_bytes:
        original["sgf_content"] = "\n" + original["sgf_content"]
        original["sgf_sha256"] = sha256(original["sgf_content"].encode()).hexdigest()
        original["raw_sha256"] = original["sgf_sha256"]
    if retained:
        legacy = ranks.freeze_game_ranks(original)
        original.update({key: legacy[key] for key in ("rank_snapshots", "rank_observations")})
        old["rank_facts"] = legacy["rank_facts"]
    else:
        old["format"] = "kifu-incremental-manifest-v1"
        old.pop("rank_facts")
        original.pop("rank_snapshots")
        original.pop("rank_observations")
    first = publish(engine, old)
    incoming = prepared(engine, item="99102", raw="9p")
    receipt = publish(engine, incoming)
    assert receipt["games"][0]["album_id"] == first["games"][0]["album_id"]
    assert {outcome["status"] for outcome in receipt["rank_outcomes"]} == ({"retained"} if retained else {"deferred"})
    api = AlbumAPI()
    api.manifest = incoming
    api.receipt = receipt
    api.details = {}
    album_id = receipt["games"][0]["album_id"]
    with Session(engine) as db:
        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
        for lang in sync.LANGUAGES:
            api.details[album_id, lang] = (await kifu.get_kifu_album(request, album_id, lang=lang, db=db)).model_dump()
        page = kifu.read_album_page(db, q=None, page=1, page_size=100, lang="cn")
        api.listing = dict(total=page.total, items=[item.model_dump() for item in page.items])
    result = await api.verify()
    validate_rank_report(api, result)
    assert publish(engine, incoming) == receipt


def test_outcome_sides_cannot_claim_different_original_source_owners(tmp_path):
    api = outcome_api(tmp_path)
    api.receipt["rank_outcomes"][0]["original_source_ref"].update(
        source_key="CWI", origin_path="data/kifu-album/Go_Seigen/99101.sgf"
    )
    with pytest.raises(ValueError, match="different original"):
        ranks.validate_rank_outcomes(api.manifest, api.receipt)
