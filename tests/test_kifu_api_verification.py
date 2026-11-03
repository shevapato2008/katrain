"""Bounded API verification uses synthetic packages and an in-process HTTP transport."""

import asyncio
from collections import Counter
from copy import deepcopy
import json

import httpx
import pytest

from katrain.core.sgf_parser import SGF
from katrain.kifu_ingest import sync
from katrain.web.kifu.name_candidates import canonical_sha256


class Clock:
    def __init__(self):
        self.now = 100.0
        self.wall = 1_000_000.0

    def monotonic(self):
        return self.now

    def time(self):
        return self.wall

    async def sleep(self, seconds):
        self.now += seconds


class AlbumAPI:
    def __init__(self, count=1):
        self.manifest = {"publication_key": "synthetic", "games": [], "decisions": []}
        self.receipt = {"status": "applied", "games": []}
        self.details = {}
        self.calls = []
        self.fault = None
        self.clock = None
        for index in range(count):
            album_id = index + 7
            black = f"Black{index}"
            sgf = f"(;PB[{black}]PW[White]EV[Event]DT[2026-10-22];B[aa])"
            game = {
                "source_key": "19x19",
                "source_item_id": str(index + 1),
                "sgf_sha256": sync.sha256(SGF.parse_sgf(sgf).sgf().encode()).hexdigest(),
                "metadata": {
                    "player_black": black,
                    "player_white": "White",
                    "event": "Event",
                    "date_played": "2026-10-22",
                },
            }
            self.manifest["games"].append(game)
            self.receipt["games"].append(
                {"source_key": "19x19", "source_item_id": str(index + 1), "album_id": album_id}
            )
            for kind, name in (("raw_player", black), ("raw_player", "White"), ("raw_event", "Event")):
                if not any(row["key"] == name for row in self.manifest["decisions"]):
                    self.manifest["decisions"].append(
                        {"kind": kind, "key": name, "displays": {lang: f"{name}/{lang}" for lang in sync.LANGUAGES}}
                    )
            for lang in sync.LANGUAGES:
                self.details[album_id, lang] = {
                    "id": album_id,
                    "sgf_content": sgf,
                    **{field: game["metadata"][field] for field in ("player_black", "player_white", "event")},
                    "sources": ["19x19"],
                    "display_player_black": f"{black}/{lang}",
                    "display_player_white": f"White/{lang}",
                    "display_event": f"Event/{lang}",
                }
        self.listing = {
            "items": [
                {
                    key: value
                    for key, value in self.details[row["album_id"], "cn"].items()
                    if key.startswith("display_") or key == "id"
                }
                for row in self.receipt["games"]
            ],
            "total": count,
        }

    async def handle(self, request):
        call = (request.url.path, tuple(request.url.params.multi_items()))
        self.calls.append(call)
        if self.clock:
            self.clock.now += 1
        if self.fault:
            response = await self.fault(request)
            if response is not None:
                return response
        if request.url.path.endswith("/albums"):
            return httpx.Response(200, json=deepcopy(self.listing))
        album_id = int(request.url.path.rsplit("/", 1)[1])
        return httpx.Response(200, json=deepcopy(self.details[album_id, request.url.params["lang"]]))

    def client(self):
        return httpx.AsyncClient(transport=httpx.MockTransport(self.handle))

    async def verify(self, **kwargs):
        async with self.client() as client:
            return await sync.verify_album_api(client, "https://example", self.manifest, self.receipt, **kwargs)

    def list_calls(self):
        return [call for call in self.calls if call[0].endswith("/albums")]


def test_v2_rejects_legacy_count_only_report_even_with_full_manifest_hash():
    api = AlbumAPI()
    api.manifest["format"] = "kifu-incremental-manifest-v2"
    digest = canonical_sha256(api.manifest)
    legacy = {
        "status": "verified",
        "manifest_sha256": digest,
        "games": 1,
        "checks": [{"album_id": 7, "lang": lang} for lang in sync.LANGUAGES],
    }
    with pytest.raises(ValueError, match="rank-aware"):
        sync.validate_test_verification(api.manifest, digest, legacy)


def rank_api(count=1, raw=None):
    from katrain.kifu_ingest.ranks import FORMAT_V2, display_rank_for_game_slot, freeze_game_ranks
    from katrain.web.kifu.player_ranks import build_source_rank_fact

    api = AlbumAPI(count)
    api.manifest.update(format=FORMAT_V2, rank_facts={})
    for index, game in enumerate(api.manifest["games"]):
        album_id = index + 7
        black = game["metadata"]["player_black"]
        sgf = SGF.parse_sgf(
            f"(;PB[{black}]PW[White]EV[Event]DT[2026-10-22]" + (f"BR[{raw}]" if raw else "") + ";B[aa])"
        ).sgf()
        game.update(
            sgf_content=sgf,
            sgf_sha256=sync.sha256(sgf.encode()).hexdigest(),
            identities={"black": {"canonical_name": black}},
        )
        game["metadata"].update(black_rank=raw, white_rank="")
        for decision in api.manifest["decisions"]:
            if decision["key"] == black:
                decision["kind"] = "player"
        fact = build_source_rank_fact(
            canonical_name=black,
            raw_rank="7p",
            sgf_content=f"(;PB[{black}]BR[7p]DT[2026-10-01])",
            slot="black",
            source_ref={"source_key": "19x19", "source_item_id": str(index + 100)},
            observed_at="2026-10-25T01:00:00+00:00",
        )
        frozen = freeze_game_ranks(game, library_facts={black: fact}, matched_at="2026-10-25T01:00:00+00:00")
        api.manifest["rank_facts"].update(frozen.pop("rank_facts"))
        game.update(frozen)
        for lang in sync.LANGUAGES:
            value = api.details[album_id, lang]
            value.update(sgf_content=sgf, black_rank=raw, white_rank="")
            for side in ("black", "white"):
                rendered = display_rank_for_game_slot(game["rank_snapshots"][side], game["metadata"][f"{side}_rank"])
                value.update(
                    {
                        f"display_{side}_rank": rendered["rank"],
                        f"{side}_rank_origin": rendered["rank_origin"],
                        f"{side}_rank_source": rendered["rank_source"],
                    }
                )
    api.listing["items"] = [deepcopy(api.details[row["album_id"], "cn"]) for row in api.receipt["games"]]
    return api


def validate_rank_report(api, result):
    digest = canonical_sha256(api.manifest)
    sync.validate_test_verification(api.manifest, digest, {**result, "manifest_sha256": digest})


def supersession_snapshot(api):
    game = api.manifest["games"][0]
    snapshot = {
        "version": "kifu-rank-snapshot-v3",
        "policy_version": "historical-rank-as-of-v1",
        "source_ref": {
            "source_key": game["source_key"],
            "origin_path": "data/kifu-album/19x19/1.sgf",
            "sgf_sha256": game["sgf_sha256"],
            "slot": "black",
        },
        "player_ref": game["identities"]["black"],
        "raw_rank": "9段",
        "raw_name": game["metadata"]["player_black"],
        "display_rank": "9段",
        "rank_value": 9,
        "rank_system": "dan_unspecified",
        "origin": "source",
        "target_date": "2026-10-22",
        "basis": [],
        "qualification": None,
        "refusal_reason": "unusable_identity",
        "matched_at": "2026-11-03T00:00:00+00:00",
    }
    snapshot["content_sha256"] = canonical_sha256(snapshot)
    return snapshot


def supersession_context(api):
    """A real v3 source decision; only the DB loader may supply its authority."""
    from katrain.kifu_ingest.ranks import display_rank_for_game_slot

    game, snapshot = api.manifest["games"][0], supersession_snapshot(api)
    expected = display_rank_for_game_slot(snapshot)
    context = {
        "version": "kifu-rank-publication-context-v1",
        "manifest_sha256": canonical_sha256(api.manifest),
        "receipt_sha256": canonical_sha256(api.receipt),
        "database_identity": {"dialect": "sqlite", "database_sha256": "d" * 64},
        "source_mapping_sha256": canonical_sha256(api.receipt["games"]),
        "slots": [
            {
                **api.receipt["games"][0],
                "side": "black",
                "snapshot_id": 11,
                "original_snapshot_sha256": game["rank_snapshots"]["black"]["content_sha256"],
                "current_snapshot_sha256": snapshot["content_sha256"],
                "repair_part_sha256": "a" * 64,
                "repair_batch_id": 21,
                "predecessor_after_sha256": "b" * 64,
                "successor_before_sha256": "b" * 64,
                "successor_after_sha256": "c" * 64,
                "expected": expected,
            }
        ],
    }
    context["content_sha256"] = canonical_sha256(context)
    return context


def show_current_rank(api, context):
    expected = context["slots"][0]["expected"]
    for lang in sync.LANGUAGES:
        api.details[7, lang].update(
            display_black_rank=expected["rank"],
            black_rank_origin=expected["rank_origin"],
            black_rank_source=deepcopy(expected["rank_source"]),
        )
    api.listing["items"][0] = deepcopy(api.details[7, "cn"])


@pytest.mark.asyncio
async def test_supersession_keeps_original_report_and_uses_fresh_context_checkpoint(tmp_path):
    api = rank_api(raw="9段")
    original = await api.verify(checkpoint_dir=tmp_path)
    original_copy, manifest, receipt = deepcopy(original), deepcopy(api.manifest), deepcopy(api.receipt)
    context = supersession_context(api)
    show_current_rank(api, context)
    loads = []

    async def loader(manifest_sha, receipt_sha, *, timeout):
        loads.append((manifest_sha, receipt_sha, timeout))
        return deepcopy(context)

    api.calls.clear()
    current = await api.verify(checkpoint_dir=tmp_path, rank_context_loader=loader)
    assert len(api.calls) == 6  # Original checkpoint is not current API evidence.
    assert current["status"] == "current_rank_verified"
    assert current["algorithm"] == sync.CURRENT_RANK_ALGORITHM
    assert current["rank_context_sha256"] == context["content_sha256"]
    assert current["rank_publication_context"] == context
    assert current["target"] == "https://example"
    assert current["database_identity"] == context["database_identity"]
    assert len(current["checks"]) == 5 and len(current["public_cards"]) == 1
    sync.validate_current_rank_verification(api.manifest, api.receipt, current, context, "https://example")
    with pytest.raises(ValueError, match="test verification"):
        validate_rank_report(api, current)
    assert (original, api.manifest, api.receipt) == (original_copy, manifest, receipt)
    validate_rank_report(api, original)
    api.calls.clear()
    assert await api.verify(checkpoint_dir=tmp_path, rank_context_loader=loader) == current
    assert api.calls == [] and len(loads) == 2  # Authority is refreshed even on resume.
    assert loads[0] == (canonical_sha256(api.manifest), canonical_sha256(api.receipt), 30)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,value",
    [
        ("rank_system", "professional_dan"),
        ("source_as_of", "2026-10-21"),
        ("policy_version", "other-policy"),
        ("refusal_reason", None),
        ("snapshot_sha256", "e" * 64),
        ("source_sha256", "e" * 64),
    ],
)
async def test_supersession_rejects_equal_visible_rank_with_changed_machine_provenance(field, value):
    api = rank_api(raw="9段")
    context = supersession_context(api)
    show_current_rank(api, context)
    source = api.details[7, "en"]["black_rank_source"]
    if field == "source_sha256":
        source["source_ref"]["sgf_sha256"] = value
    else:
        source[field] = value
    with pytest.raises(ValueError, match="rank"):
        await api.verify(rank_context_loader=lambda *a, **kw: deepcopy(context))


@pytest.mark.asyncio
@pytest.mark.parametrize("damage", ["manifest", "receipt", "mapping", "original", "duplicate", "extra", "oversized"])
async def test_current_rank_context_rejects_invalid_authority_before_get(damage):
    api = rank_api(raw="9段")
    context = supersession_context(api)
    if damage in {"manifest", "receipt"}:
        context[f"{damage}_sha256"] = "f" * 64
    elif damage == "mapping":
        context["source_mapping_sha256"] = "f" * 64
    elif damage == "original":
        context["slots"][0]["original_snapshot_sha256"] = "f" * 64
    elif damage == "duplicate":
        context["slots"].append(deepcopy(context["slots"][0]))
    elif damage == "extra":
        context["rank_override"] = "9段"
    else:
        context["slots"][0]["expected"]["rank"] = "x" * (1024 * 1024)
    context["content_sha256"] = canonical_sha256({k: v for k, v in context.items() if k != "content_sha256"})
    with pytest.raises(ValueError, match="context"):
        await api.verify(rank_context_loader=lambda *a, **kw: context)
    assert api.calls == []


@pytest.mark.asyncio
async def test_current_rank_context_empty_preserves_legacy_output_and_deadline_clamps_loader():
    api, clock = rank_api(raw="9段"), Clock()
    original = await api.verify()
    context = supersession_context(api)
    context["slots"] = []
    context["content_sha256"] = canonical_sha256({k: v for k, v in context.items() if k != "content_sha256"})
    calls = []

    def loader(*args, timeout):
        calls.append(timeout)
        return context

    assert await api.verify(rank_context_loader=loader, clock=clock.monotonic, deadline=clock.now + 7) == original
    assert calls == [7]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "damage", ["target", "database", "context", "missing_slot", "rank", "missing_check", "duplicate", "budget"]
)
async def test_current_rank_context_saved_report_requires_fresh_authority_and_all_evidence(damage):
    api = rank_api(raw="9段")
    context = supersession_context(api)
    show_current_rank(api, context)
    result = await api.verify(rank_context_loader=lambda *a, **kw: context)
    report = deepcopy(result)
    if damage == "target":
        report["target"] = "https://other"
    elif damage == "database":
        report["database_identity"]["database_sha256"] = "f" * 64
    elif damage == "context":
        report["rank_publication_context"]["slots"][0]["expected"]["rank"] = "9p"
    elif damage == "missing_slot":
        report["rank_publication_context"]["slots"] = []
    elif damage == "rank":
        report["checks"][-1]["ranks"]["black"]["source"]["rank_system"] = "professional_dan"
    elif damage == "missing_check":
        report["checks"].pop()
    elif damage == "duplicate":
        report["checks"][-1] = deepcopy(report["checks"][0])
    else:
        report["checks"][-1]["ranks"]["black"]["source"]["refusal_reason"] = "x" * (4 * 1024 * 1024)
    with pytest.raises(ValueError):
        sync.validate_current_rank_verification(api.manifest, api.receipt, report, context, "https://example")
    # The original validator also cannot accept a supplement with a forged status.
    report["status"] = "verified"
    with pytest.raises(ValueError):
        validate_rank_report(api, report)


@pytest.mark.asyncio
async def test_current_rank_context_markers_cannot_masquerade_as_original_test_authorization():
    api = rank_api(raw="9段")
    original = await api.verify()
    original.update(rank_publication_context=supersession_context(api))
    with pytest.raises(ValueError, match="original|current"):
        validate_rank_report(api, original)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,value",
    [
        ("sgf_content", "(;PB[changed];B[bb])"),
        ("player_black", "changed"),
        ("black_rank", "9p"),
        ("sources", []),
        ("display_player_black", "changed"),
    ],
)
async def test_supersession_still_checks_original_metadata_names_source_and_sgf(field, value):
    api = rank_api(raw="9段")
    context = supersession_context(api)
    show_current_rank(api, context)
    api.details[7, "en"][field] = value
    with pytest.raises(ValueError):
        await api.verify(rank_context_loader=lambda *a, **kw: context)


@pytest.mark.asyncio
async def test_current_rank_context_new_v3_never_loads_compatibility_context():
    from katrain.kifu_ingest.ranks import display_rank_for_game_slot

    api = rank_api(raw="9段")
    game = api.manifest["games"][0]
    game["origin_path"] = "data/kifu-album/19x19/1.sgf"
    black = supersession_snapshot(api)
    white = deepcopy(black)
    white.update(
        player_ref=None,
        raw_name="White",
        raw_rank="",
        display_rank="",
        rank_value=None,
        rank_system=None,
        origin="unknown",
    )
    white["source_ref"]["slot"] = "white"
    white["content_sha256"] = canonical_sha256({k: v for k, v in white.items() if k != "content_sha256"})
    game["rank_snapshots"] = {"black": black, "white": white}
    for side, snapshot in game["rank_snapshots"].items():
        expected = display_rank_for_game_slot(snapshot)
        for lang in sync.LANGUAGES:
            api.details[7, lang].update(
                {
                    f"display_{side}_rank": expected["rank"],
                    f"{side}_rank_origin": expected["rank_origin"],
                    f"{side}_rank_source": expected["rank_source"],
                }
            )
    api.listing["items"][0] = deepcopy(api.details[7, "cn"])
    # A new native V3 publication keeps its ordinary applied-outcome contract.
    api.receipt["manifest_sha256"] = canonical_sha256(api.manifest)
    api.receipt["rank_outcomes"] = [
        {
            **api.receipt["games"][0],
            "side": side,
            "status": "applied",
            "requested_snapshot_sha256": snapshot["content_sha256"],
            "original_source_ref": snapshot["source_ref"],
            "retained_snapshot": None,
            "original_canonical_sgf_sha256": game["sgf_sha256"],
        }
        for side, snapshot in game["rank_snapshots"].items()
    ]

    def forbidden(*args, **kwargs):
        raise AssertionError("new V3 must not load legacy authority")

    result = await api.verify(rank_context_loader=forbidden)
    assert result["status"] == "verified" and result["algorithm"] == sync.RANK_ALGORITHM_VERSION
    assert len(api.calls) == 6


@pytest.mark.asyncio
async def test_current_rank_context_is_not_accepted_as_caller_data_or_unbounded_loader():
    api = rank_api(raw="9段")
    context = supersession_context(api)
    show_current_rank(api, context)
    api.receipt["rank_publication_context"] = context
    with pytest.raises(ValueError, match="rank"):
        await api.verify()
    with pytest.raises(TypeError, match="rank_context"):
        await api.verify(rank_context=context)
    api.receipt.pop("rank_publication_context")
    calls = len(api.calls)

    async def slow(*args, **kwargs):
        await asyncio.sleep(60)

    with pytest.raises(TimeoutError):
        await api.verify(rank_context_loader=slow, deadline=sync.time.monotonic() + 0.01)
    assert len(api.calls) == calls


def test_current_rank_context_ssh_uses_exact_fixed_command_and_request(monkeypatch):
    import subprocess
    import sys

    api = rank_api(raw="9段")
    context = supersession_context(api)
    response = {"status": "resolved", "context": context}
    actual_popen, calls = subprocess.Popen, []
    request = {
        "operation": "read-rank-publication-context-v1",
        "manifest_sha256": context["manifest_sha256"],
        "receipt_sha256": context["receipt_sha256"],
    }
    script = (
        "import json,sys; raw=sys.stdin.buffer.read(); assert len(raw)<=1024; "
        "assert json.loads(raw)==" + repr(request) + "; print(json.dumps(" + repr(response) + "))"
    )

    def popen(command, **kwargs):
        calls.append((command, kwargs))
        return actual_popen([sys.executable, "-c", script], **kwargs)

    monkeypatch.setattr(sync.subprocess, "Popen", popen)
    got = sync.read_rank_publication_context(
        host="prod",
        key_path="/private/key",
        known_hosts="/private/known_hosts",
        manifest_sha256=context["manifest_sha256"],
        receipt_sha256=context["receipt_sha256"],
        timeout=30,
    )
    assert got == context
    assert calls[0][0] == sync._receiver_command("prod", "/private/key", "/private/known_hosts")
    assert calls[0][1]["stderr"] == subprocess.DEVNULL


@pytest.mark.parametrize(
    "damage", ["extra_envelope", "wrong_manifest", "invalid_json", "oversized", "exit", "timeout", "bad_hash"]
)
def test_current_rank_context_ssh_fails_closed_with_fixed_safe_error(monkeypatch, damage):
    import subprocess
    import sys

    api = rank_api(raw="9段")
    context = supersession_context(api)
    request_sha = context["manifest_sha256"]
    response = {"status": "resolved", "context": context}
    if damage == "extra_envelope":
        response["secret"] = "never-forward-this"
    elif damage == "wrong_manifest":
        context["manifest_sha256"] = "f" * 64
    elif damage == "bad_hash":
        request_sha = "not-a-hash"
    script = "import sys; sys.stdin.read(); print(" + repr(json.dumps(response)) + ")"
    if damage == "invalid_json":
        script = "print('never-forward-this')"
    elif damage == "oversized":
        script = "import sys; sys.stdout.write('x' * (1024 * 1024 + 1)); sys.stdout.flush()"
    elif damage == "exit":
        script = "import sys; print('never-forward-this'); sys.exit(2)"
    elif damage == "timeout":
        script = "import time; time.sleep(60)"
    actual_popen, calls = subprocess.Popen, []

    def popen(command, **kwargs):
        calls.append(command)
        return actual_popen([sys.executable, "-c", script], **kwargs)

    monkeypatch.setattr(sync.subprocess, "Popen", popen)
    with pytest.raises(sync.RankPublicationContextUnavailable, match="^rank publication context unavailable$"):
        sync.read_rank_publication_context(
            host="prod",
            key_path="/private/key",
            known_hosts="/private/known_hosts",
            manifest_sha256=request_sha,
            receipt_sha256=context["receipt_sha256"],
            timeout=0.01 if damage == "timeout" else 30,
        )
    assert len(calls) == (0 if damage == "bad_hash" else 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("raw", [None, "9p", "6d", "6k"])
async def test_v2_keeps_complete_rank_evidence_for_every_language_and_public_card(raw):
    from katrain.kifu_ingest.verification import RANK_ALGORITHM_VERSION

    api = rank_api(2, raw)
    result = await api.verify()
    assert result["algorithm"] == RANK_ALGORITHM_VERSION
    assert len(result["checks"]) == 10 and len(result["public_cards"]) == 2
    for checked in result["checks"]:
        assert checked["source_item_id"] in {"1", "2"}
        assert checked["metadata"]["black_rank"] == raw
        assert checked["ranks"]["black"]["display_rank"] == (raw or "7p")
        assert checked["ranks"]["white"]["display_rank"] == ""
        assert checked["ranks"]["white"]["source"]["source_ref"]["slot"] == "white"
    validate_rank_report(api, result)
    assert len(api.list_calls()) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,damage",
    [
        ("black_rank", "8p"),
        ("display_black_rank", "8p"),
        ("black_rank_origin", "source"),
        ("black_rank_source", None),
        ("white_rank_source", None),
        ("snapshot_sha256", "a" * 64),
        ("origin", "unknown"),
        ("rank_fact_sha256", "b" * 64),
        ("source_item_id", "999"),
        ("slot", "white"),
        ("sgf_sha256", "c" * 64),
    ],
)
async def test_v2_rejects_raw_display_and_snapshot_disagreement_in_last_language(field, damage):
    api = rank_api()
    value = api.details[7, "en"]
    if field in {"source_item_id", "slot", "sgf_sha256"}:
        value["black_rank_source"]["source_ref"][field] = damage
    elif field in {"snapshot_sha256", "origin", "rank_fact_sha256"}:
        value["black_rank_source"][field] = damage
    else:
        value[field] = damage
    with pytest.raises(ValueError, match="rank"):
        await api.verify()


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["black_rank", "display_black_rank", "black_rank_origin", "black_rank_source"])
async def test_v2_public_card_must_match_raw_rank_and_snapshot_provenance(field):
    api = rank_api()
    api.listing["items"][0][field] = None if field.endswith("source") else "wrong"
    with pytest.raises(ValueError, match="public list card"):
        await api.verify()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "damage",
    [
        "count_only",
        "language",
        "duplicate",
        "public",
        "source_id",
        "album_id",
        "slot",
        "origin",
        "source_hash",
        "raw",
        "display",
        "manifest_hash",
        "mapping",
        "duplicate_mapping",
        "receipt",
        "oversized",
    ],
)
async def test_v2_report_validation_rechecks_exact_finite_coverage_and_rank_assertions(damage):
    api = rank_api(2)
    result = await api.verify()
    if damage == "count_only":
        result["checks"] = [{"album_id": row["album_id"], "lang": row["lang"]} for row in result["checks"]]
    elif damage == "language":
        result["checks"].pop()
    elif damage == "duplicate":
        result["checks"][-1] = deepcopy(result["checks"][0])
    elif damage == "public":
        result["public_cards"].pop()
    elif damage in {"source_id", "album_id"}:
        result["checks"][0]["source_item_id" if damage == "source_id" else "album_id"] = (
            "999" if damage == "source_id" else 999
        )
    elif damage == "slot":
        result["checks"][0]["ranks"].pop("white")
    elif damage == "origin":
        result["checks"][0]["ranks"]["black"]["origin"] = "source"
    elif damage == "source_hash":
        result["checks"][0]["ranks"]["black"]["source"]["source_ref"]["sgf_sha256"] = "a" * 64
    elif damage == "raw":
        result["checks"][0]["metadata"]["black_rank"] = "8p"
    elif damage == "display":
        result["checks"][0]["ranks"]["black"]["display_rank"] = "8p"
    elif damage == "mapping":
        result["album_mappings"][0]["album_id"] = 999
    elif damage == "duplicate_mapping":
        result["album_mappings"][1]["album_id"] = result["album_mappings"][0]["album_id"]
    elif damage == "receipt":
        result.pop("receipt_sha256")
    elif damage == "oversized":
        result["padding"] = "x" * (4 * 1024 * 1024)
    else:
        api.manifest["publication_key"] = "changed"
        with pytest.raises(ValueError):
            sync.validate_test_verification(api.manifest, "a" * 64, {**result, "manifest_sha256": "a" * 64})
        return
    with pytest.raises(ValueError):
        validate_rank_report(api, result)


@pytest.mark.asyncio
async def test_v2_checkpoint_uses_new_algorithm_and_revalidates_rank_evidence(tmp_path):
    from katrain.kifu_ingest.verification import RANK_ALGORITHM_VERSION

    api = rank_api()
    result = await api.verify(checkpoint_dir=tmp_path)
    path = next(tmp_path.glob("*.json"))
    record = json.loads(path.read_text())
    assert record["binding"]["algorithm"] == RANK_ALGORITHM_VERSION
    api.calls.clear()
    assert await api.verify(checkpoint_dir=tmp_path) == result
    assert api.calls == []
    completed = next(iter(record["completed"].values()))
    completed["details"][0]["ranks"]["black"]["origin"] = "source"
    record["content_sha256"] = canonical_sha256(
        {key: value for key, value in record.items() if key != "content_sha256"}
    )
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="checkpoint"):
        await api.verify(checkpoint_dir=tmp_path)
    assert api.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("old_algorithm", [True, False])
async def test_v2_never_reuses_legacy_algorithm_or_names_only_completed_object(tmp_path, old_algorithm):
    from katrain.kifu_ingest.verification import RANK_ALGORITHM_VERSION

    legacy, api = AlbumAPI(), rank_api()
    await legacy.verify(checkpoint_dir=tmp_path)
    original_path = next(tmp_path.glob("*.json"))
    record = json.loads(original_path.read_text())
    record["binding"]["manifest_sha256"] = canonical_sha256(api.manifest)
    if not old_algorithm:
        record["binding"]["algorithm"] = RANK_ALGORITHM_VERSION
    record["content_sha256"] = canonical_sha256(
        {key: value for key, value in record.items() if key != "content_sha256"}
    )
    path = tmp_path / f"{canonical_sha256(record['binding'])}.json"
    path.write_text(json.dumps(record))
    if old_algorithm:
        assert (await api.verify(checkpoint_dir=tmp_path))["status"] == "verified"
        assert len(api.calls) == 6
    else:
        with pytest.raises(ValueError, match="checkpoint"):
            await api.verify(checkpoint_dir=tmp_path)
        assert api.calls == []


@pytest.mark.asyncio
async def test_v2_transient_list_failure_recovers_once_with_same_finite_budget():
    api = rank_api()

    async def fault(request):
        assert set(request.extensions["timeout"].values()) == {30}
        if request.url.path.endswith("/albums") and len(api.list_calls()) == 1:
            raise httpx.ReadTimeout("temporary", request=request)

    api.fault = fault
    result = await api.verify(sleep=Clock().sleep)
    validate_rank_report(api, result)
    assert len(api.list_calls()) == 2


@pytest.mark.asyncio
async def test_v2_unknown_display_allows_null_without_inventing_a_grade():
    api = rank_api()
    for value in (*api.details.values(), *api.listing["items"]):
        value["display_white_rank"] = None
    result = await api.verify()
    assert all(row["ranks"]["white"]["display_rank"] is None for row in result["checks"])
    validate_rank_report(api, result)


def test_sender_rejects_oversized_encoded_envelope_before_ssh(monkeypatch):
    api = AlbumAPI()
    api.manifest["padding"] = "x" * (16 * 1024 * 1024)
    digest = canonical_sha256(api.manifest)
    report = {
        "status": "verified",
        "manifest_sha256": digest,
        "games": 1,
        "checks": [{"album_id": 7, "lang": lang} for lang in sync.LANGUAGES],
    }

    def forbidden(*args, **kwargs):
        pytest.fail("oversized payload must be rejected before SSH")

    monkeypatch.setattr(sync.subprocess, "run", forbidden)
    with pytest.raises(ValueError, match="payload budget"):
        sync.send_verified_manifest(
            api.manifest, digest, report, host="synthetic", key_path="/key", known_hosts="/known"
        )


@pytest.mark.asyncio
async def test_transient_list_timeout_retries_once_and_uses_finite_default():
    api = AlbumAPI()
    timeouts = []

    async def fault(request):
        timeouts.append(request.extensions["timeout"])
        if request.url.path.endswith("/albums") and len(api.list_calls()) == 1:
            raise httpx.ReadTimeout("temporary", request=request)

    api.fault = fault
    result = await api.verify(sleep=Clock().sleep)
    assert result["status"] == "verified"
    assert len(api.list_calls()) == 2
    assert all(set(timeout.values()) == {30} for timeout in timeouts)


@pytest.mark.asyncio
@pytest.mark.parametrize("exception", [httpx.ReadTimeout, httpx.ConnectError])
async def test_persistent_transport_failure_is_not_verified_after_two_attempts(exception):
    api = AlbumAPI()

    async def fault(request):
        if request.url.path.endswith("/albums"):
            raise exception("persistent", request=request)

    api.fault = fault
    with pytest.raises(exception):
        await api.verify(sleep=Clock().sleep)
    assert len(api.list_calls()) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [429, 503, "malformed"])
async def test_non200_and_semantic_failures_are_not_retried(failure):
    api = AlbumAPI()

    async def fault(request):
        if request.url.path.endswith("/albums"):
            return (
                httpx.Response(200, json={"items": "bad", "total": 1})
                if failure == "malformed"
                else httpx.Response(failure)
            )

    api.fault = fault
    with pytest.raises(ValueError):
        await api.verify()
    assert len(api.list_calls()) == 1


@pytest.mark.asyncio
async def test_list_cache_reuses_exact_page_but_checks_each_albums_card():
    api = AlbumAPI(2)
    result = await api.verify()
    assert len(result["checks"]) == 10
    assert len(api.list_calls()) == 1
    api.calls.clear()
    api.listing["items"][1]["display_event"] = "wrong"
    with pytest.raises(ValueError, match="public list card"):
        await api.verify()
    assert len(api.list_calls()) == 1


@pytest.mark.asyncio
async def test_cache_does_not_cross_invocations_or_targets():
    api = AlbumAPI()
    await api.verify()
    async with api.client() as client:
        await sync.verify_album_api(client, "https://other", api.manifest, api.receipt)
    await api.verify()
    assert len(api.list_calls()) == 3


@pytest.mark.asyncio
async def test_date_query_keeps_twenty_page_cap_before_player_fallback():
    api = AlbumAPI()

    async def fault(request):
        if request.url.path.endswith("/albums") and request.url.params["q"] == "2026-10-22":
            return httpx.Response(200, json={"items": [], "total": 5000})

    api.fault = fault
    await api.verify()
    queries = [dict(params) for _, params in api.list_calls()]
    assert [int(query["page"]) for query in queries[:-1]] == list(range(1, 21))
    assert queries[-1] == {"q": "Black0", "lang": "cn", "page": "1", "page_size": "100"}


@pytest.mark.asyncio
async def test_list_cache_keeps_different_pages_separate():
    api = AlbumAPI(2)

    async def fault(request):
        if request.url.path.endswith("/albums") and request.url.params["page"] == "1":
            return httpx.Response(200, json={"items": [], "total": 101})

    api.fault = fault
    await api.verify()
    assert [dict(params)["page"] for _, params in api.list_calls()] == ["1", "2"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,value,error",
    [
        ("sgf_content", "(;PB[Wrong])", "SGF hash"),
        ("sgf_content", None, "SGF is invalid"),
        ("player_black", "other", "player_black mismatch"),
        ("player_white", "other", "player_white mismatch"),
        ("event", "other", "event mismatch"),
        ("sources", [], "source link"),
        ("display_event", "wrong", "display_event mismatch"),
        ("display_player_black", "", "display_player_black missing"),
    ],
)
async def test_last_language_still_requires_sgf_original_names_source_and_reviewed_displays(field, value, error):
    api = AlbumAPI()
    api.details[7, "en"][field] = value
    with pytest.raises(ValueError, match=error):
        await api.verify()
    assert len(api.calls) == 5


@pytest.mark.asyncio
async def test_deadline_cancels_slow_transport_and_does_not_retry():
    api = AlbumAPI()
    cancelled = []

    async def fault(request):
        try:
            await asyncio.sleep(0.2)
        except asyncio.CancelledError:
            cancelled.append(True)
            raise

    api.fault = fault
    with pytest.raises(TimeoutError):
        await api.verify(deadline=asyncio.get_running_loop().time() + 0.025)
    assert cancelled == [True]
    assert len(api.calls) == 1


@pytest.mark.asyncio
async def test_per_attempt_timeout_is_a_wall_cap_without_caller_deadline():
    api = AlbumAPI()
    cancelled = []

    async def fault(request):
        try:
            await asyncio.sleep(0.2)
        except asyncio.CancelledError:
            cancelled.append(True)
            raise

    api.fault = fault
    with pytest.raises(TimeoutError, match="wall-clock timeout"):
        await api.verify(timeout=0.025, sleep=Clock().sleep)
    assert len(api.calls) == 2
    assert cancelled == [True, True]


@pytest.mark.asyncio
async def test_per_attempt_wall_timeout_recovers_once_with_remaining_overall_deadline():
    api = AlbumAPI()
    cancelled = []

    async def fault(request):
        if len(api.calls) == 1:
            try:
                await asyncio.sleep(0.2)
            except asyncio.CancelledError:
                cancelled.append(True)
                raise

    api.fault = fault
    result = await api.verify(timeout=0.025, deadline=asyncio.get_running_loop().time() + 1, sleep=Clock().sleep)
    assert result["status"] == "verified"
    assert len(result["checks"]) == 5
    assert len(api.calls) == 7
    assert cancelled == [True]


@pytest.mark.asyncio
async def test_deadline_exhausted_during_timeout_retry_delay_does_not_make_another_request():
    from katrain.kifu_ingest.verification import VerificationDeadlineExceeded

    api = AlbumAPI()

    async def fault(request):
        await asyncio.sleep(0.2)

    api.fault = fault
    with pytest.raises(VerificationDeadlineExceeded):
        await api.verify(timeout=0.025, deadline=asyncio.get_running_loop().time() + 0.04)
    assert len(api.calls) == 1


@pytest.mark.asyncio
async def test_exhausted_deadline_never_requests_or_returns_checkpoint_success(tmp_path):
    api = AlbumAPI()
    clock = Clock()
    await api.verify(checkpoint_dir=tmp_path, wall_clock=clock.time)
    api.calls.clear()
    with pytest.raises(TimeoutError):
        await api.verify(checkpoint_dir=tmp_path, deadline=clock.now, clock=clock.monotonic, wall_clock=clock.time)
    assert api.calls == []


@pytest.mark.asyncio
async def test_remaining_deadline_clamps_timeout_and_prevents_retry():
    api = AlbumAPI()
    clock = Clock()

    async def fault(request):
        assert set(request.extensions["timeout"].values()) == {2}
        clock.now += 2
        raise httpx.ReadTimeout("budget exhausted", request=request)

    api.fault = fault
    with pytest.raises(TimeoutError):
        await api.verify(deadline=102, clock=clock.monotonic, sleep=clock.sleep)
    assert len(api.calls) == 1


@pytest.mark.asyncio
async def test_final_coverage_check_cannot_return_success_after_deadline(monkeypatch):
    api = AlbumAPI()
    clock = Clock()
    validate = sync.validate_test_verification

    def expire_after_coverage(*args):
        validate(*args)
        clock.now = 200

    monkeypatch.setattr(sync, "validate_test_verification", expire_after_coverage)
    with pytest.raises(TimeoutError):
        await api.verify(deadline=200, clock=clock.monotonic)


@pytest.mark.asyncio
async def test_complete_albums_resume_across_two_bounded_calls(tmp_path):
    api = AlbumAPI(2)
    clock = Clock()
    api.clock = clock
    options = {"checkpoint_dir": tmp_path, "clock": clock.monotonic, "wall_clock": clock.time, "sleep": clock.sleep}
    with pytest.raises(TimeoutError):
        await api.verify(deadline=106.5, **options)
    checkpoint = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert len(checkpoint["completed"]) == 1
    api.calls.clear()
    result = await api.verify(deadline=clock.now + 7, **options)
    assert result["status"] == "verified"
    assert len(result["checks"]) == 10
    assert Counter(check["album_id"] for check in result["checks"]) == {7: 5, 8: 5}
    assert all(not path.endswith("/7") for path, _ in api.calls)
    sync.validate_test_verification(api.manifest, "digest", {**result, "manifest_sha256": "digest"})


@pytest.mark.asyncio
async def test_half_album_has_no_checkpoint_credit(tmp_path):
    api = AlbumAPI()
    clock = Clock()
    api.clock = clock
    options = {"checkpoint_dir": tmp_path, "clock": clock.monotonic, "wall_clock": clock.time}
    with pytest.raises(TimeoutError):
        await api.verify(deadline=102.5, **options)
    api.calls.clear()
    await api.verify(deadline=clock.now + 7, **options)
    assert len(api.calls) == 6


@pytest.mark.asyncio
async def test_completed_at_is_not_refreshed_when_another_album_completes(tmp_path):
    api = AlbumAPI(2)
    clock = Clock()
    api.clock = clock
    options = {"checkpoint_dir": tmp_path, "clock": clock.monotonic, "wall_clock": clock.time}
    with pytest.raises(TimeoutError):
        await api.verify(deadline=106.5, **options)
    path = next(tmp_path.glob("*.json"))
    before = json.loads(path.read_text())["completed"]
    first = next(iter(before))
    clock.wall += 86_399
    await api.verify(**options)
    after = json.loads(path.read_text())["completed"]
    assert after[first]["completed_at"] == before[first]["completed_at"]
    clock.wall += 2
    api.calls.clear()
    await api.verify(**options)
    assert [path for path, _ in api.calls if not path.endswith("/albums")] == ["/api/v1/kifu/albums/7"] * 5


@pytest.mark.asyncio
@pytest.mark.parametrize("changed", ["manifest", "receipt", "target", "algorithm", "languages"])
async def test_checkpoint_binding_changes_cannot_skip_verification(tmp_path, monkeypatch, changed):
    api = AlbumAPI()
    await api.verify(checkpoint_dir=tmp_path)
    api.calls.clear()
    target = "https://example"
    if changed == "manifest":
        api.manifest["publication_key"] = "different"
    elif changed == "receipt":
        api.receipt["native_receipt_extra"] = "changed"
    elif changed == "target":
        target = "https://other"
    elif changed == "algorithm":
        from katrain.kifu_ingest import verification

        monkeypatch.setattr(verification, "ALGORITHM_VERSION", "future-test-version")
    elif changed == "languages":
        monkeypatch.setattr(sync, "LANGUAGES", tuple(reversed(sync.LANGUAGES)))
    async with api.client() as client:
        await sync.verify_album_api(client, target, api.manifest, api.receipt, checkpoint_dir=tmp_path)
    assert len(api.calls) == 6
    assert len(list(tmp_path.glob("*.json"))) == 2


@pytest.mark.asyncio
async def test_normalized_target_reuses_same_bound_checkpoint(tmp_path):
    api = AlbumAPI()
    await api.verify(checkpoint_dir=tmp_path)
    api.calls.clear()
    async with api.client() as client:
        result = await sync.verify_album_api(
            client, "HTTPS://EXAMPLE:443/", api.manifest, api.receipt, checkpoint_dir=tmp_path
        )
    assert result["status"] == "verified"
    assert api.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("damage", ["json", "digest", "binding", "partial", "future", "card", "details"])
async def test_corrupt_or_inconsistent_checkpoint_fails_closed(tmp_path, damage):
    api = AlbumAPI()
    clock = Clock()
    await api.verify(checkpoint_dir=tmp_path, wall_clock=clock.time)
    path = next(tmp_path.glob("*.json"))
    record = json.loads(path.read_text())
    if damage == "json":
        path.write_text("{broken")
    else:
        album = next(iter(record["completed"].values()))
        if damage == "digest":
            record["content_sha256"] = "0" * 64
        elif damage == "binding":
            record["binding"]["target"] = "https://other"
        elif damage == "partial":
            album["details"].pop()
        elif damage == "future":
            album["completed_at"] = clock.wall + 100
        elif damage == "card":
            album["public_card"]["displays"]["display_event"] = "wrong"
        elif damage == "details":
            album["details"][0]["sgf_sha256"] = "0" * 64
        if damage != "digest":
            record["content_sha256"] = canonical_sha256(
                {key: value for key, value in record.items() if key != "content_sha256"}
            )
        path.write_text(json.dumps(record))
    api.calls.clear()
    with pytest.raises(ValueError, match="checkpoint"):
        await api.verify(checkpoint_dir=tmp_path, wall_clock=clock.time)
    assert api.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("link", ["file", "directory", "parent"])
async def test_checkpoint_symlinks_are_rejected(tmp_path, link):
    api = AlbumAPI()
    directory = tmp_path / "checkpoints"
    await api.verify(checkpoint_dir=directory)
    if link == "file":
        path = next(directory.glob("*.json"))
        moved = tmp_path / "moved.json"
        path.rename(moved)
        path.symlink_to(moved)
    elif link == "directory":
        directory.rename(tmp_path / "real")
        directory.symlink_to(tmp_path / "real", target_is_directory=True)
    else:
        (tmp_path / "parent").symlink_to(tmp_path, target_is_directory=True)
        directory = tmp_path / "parent" / "checkpoints"
    api.calls.clear()
    with pytest.raises(ValueError, match="checkpoint"):
        await api.verify(checkpoint_dir=directory)
    assert api.calls == []


@pytest.mark.asyncio
async def test_prod_published_receipt_resumes_only_verification_and_failure_does_not_advance(tmp_path):
    from katrain.cron.jobs.kifu_ingest import resume_batch

    api = AlbumAPI()

    class Store:
        row = {"status": "prod_published", "prod_receipt": api.receipt}

        def get_batch(self, key):
            return self.row

        def advance_batch(self, key, status, *, expected_status, receipt):
            assert expected_status == "prod_published"
            self.row.update(status=status, prod_verification=receipt)
            return self.row

    async def forbidden(*args):
        pytest.fail("native prod receipt must not repeat publication or translation")

    async def verify(manifest, receipt):
        return await api.verify(checkpoint_dir=tmp_path)

    store = Store()
    api.listing["items"][0]["display_event"] = "wrong"
    with pytest.raises(ValueError, match="public list card"):
        await resume_batch(
            store,
            api.manifest,
            "digest",
            test_publish=forbidden,
            test_verify=forbidden,
            sync=forbidden,
            prod_verify=verify,
        )
    assert store.row["status"] == "prod_published"
    api.listing["items"][0]["display_event"] = "Event/cn"
    await resume_batch(
        store, api.manifest, "digest", test_publish=forbidden, test_verify=forbidden, sync=forbidden, prod_verify=verify
    )
    assert store.row["status"] == "prod_synced"
    assert len(store.row["prod_verification"]["checks"]) == 5
    assert len([path for path, _ in api.calls if not path.endswith("/albums")]) == 10
