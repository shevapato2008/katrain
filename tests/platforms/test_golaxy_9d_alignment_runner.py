import dataclasses
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from katrain.core.ladder import HUMANSL_PIKL_BASELINE
from katrain.core.ladder_calibration import GameOutcome

CALIBRATION_DIR = Path(__file__).parents[2] / "superpowers/tracks/golaxy-ai-ladder-parity/calibration"
sys.path.insert(0, str(CALIBRATION_DIR))
runner = importlib.import_module("run_golaxy_9d_alignment")


def test_alignment_search_player_uses_the_frozen_b18_pikl_recipe():
    label, rung, selection = runner.make_alignment_player("rank_9d@8")

    assert label == "rank_9d@8"
    assert rung.net == "b18"
    assert rung.mechanism == "humansl_search"
    assert rung.human_sl_profile == "rank_9d"
    assert rung.max_visits == 8
    assert rung.human_sl_params == HUMANSL_PIKL_BASELINE
    assert rung.human_sl_params is not HUMANSL_PIKL_BASELINE
    assert selection == "search"


def test_alignment_one_visit_player_uses_human_policy_argmax():
    label, rung, selection = runner.make_alignment_player("rank_9d@1s")

    assert label == "rank_9d@1s"
    assert rung.net == "humanv0"
    assert rung.mechanism == "humansl"
    assert rung.human_sl_profile == "rank_9d"
    assert rung.max_visits == 1
    assert rung.human_sl_params == {}
    assert selection == "argmax_human"


@pytest.mark.parametrize(
    "player",
    ["rank_9d@1", "rank_8d@8", "rank_9d@2", "rank_9d@7", "rank_9d@64", "b28@8", None],
)
def test_alignment_player_rejects_plain_one_and_every_non_grid_spec(player):
    with pytest.raises(ValueError, match="candidate"):
        runner.make_alignment_player(player)


def test_alignment_player_rejects_drifted_strength_spec(monkeypatch):
    original = runner.run_selfplay.make_player

    def drifted(player, **kwargs):
        label, rung, selection = original(player, **kwargs)
        return label, dataclasses.replace(rung, net="b28"), selection

    monkeypatch.setattr(runner.run_selfplay, "make_player", drifted)

    with pytest.raises(ValueError, match="strength spec"):
        runner.make_alignment_player("rank_9d@8")


def test_alignment_player_rejects_drifted_effective_query(monkeypatch):
    original = runner.run_selfplay.adapters.build_ladder_analysis_query

    def drifted(*args, **kwargs):
        query = original(*args, **kwargs)
        query["maxVisits"] += 1
        return query

    monkeypatch.setattr(runner.run_selfplay.adapters, "build_ladder_analysis_query", drifted)

    with pytest.raises(ValueError, match="effective query"):
        runner.make_alignment_player("rank_9d@8")


def test_alignment_player_rejects_unexpected_effective_query_controls(monkeypatch):
    original = runner.run_selfplay.adapters.build_ladder_analysis_query

    def drifted(*args, **kwargs):
        query = original(*args, **kwargs)
        query["maxTime"] = 1.0
        return query

    monkeypatch.setattr(runner.run_selfplay.adapters, "build_ladder_analysis_query", drifted)

    with pytest.raises(ValueError, match="effective query"):
        runner.make_alignment_player("rank_9d@8")


def test_golaxy_9d_rung_is_only_an_immutable_opponent_descriptor():
    rung = runner.golaxy_9d_opponent()

    assert rung.rung == 33
    assert rung.golaxy_api_level == 3000
    assert rung is runner.get_rung(33)
    assert rung is not runner.make_alignment_player("rank_9d@8")[1]


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8000",
        "http://127.0.0.1:8001",
        "https://127.0.0.1:8000",
        "http://user@127.0.0.1:8000",
        "http://127.0.0.1:8000/",
        "http://127.0.0.1:8000?x=1",
        "http://127.0.0.1:8000#x",
    ],
)
def test_exact_local_base_url_rejects_aliases(url):
    with pytest.raises(ValueError, match="exactly"):
        runner.validate_base_url(url)


def test_exact_local_base_url_accepts_only_frozen_literal():
    assert runner.validate_base_url("http://127.0.0.1:8000") == "http://127.0.0.1:8000"


@pytest.mark.parametrize("reported", [1, 3, 8, 15])
def test_reported_visits_accept_pruning_and_thread_overshoot(reported):
    assert runner.validate_reported_visits(reported, 8) == reported


@pytest.mark.parametrize("reported", [True, None, "8", 0, -1, 16])
def test_reported_visits_reject_malformed_or_excessive_values(reported):
    with pytest.raises(ValueError, match="reported visits"):
        runner.validate_reported_visits(reported, 8)


def test_cli_modes_are_mutually_exclusive():
    parser = runner.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--preflight-only", "--summarize-only"])


def test_source_validation_accepts_feature_branch_and_unrelated_dirty_files(monkeypatch, tmp_path):
    revision = "f" * 40
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[1:] == ["rev-parse", "--show-toplevel"]:
            return SimpleNamespace(stdout=str(tmp_path) + "\n", returncode=0)
        if command[1:] == ["rev-parse", "HEAD"]:
            return SimpleNamespace(stdout=revision + "\n", returncode=0)
        if command[1:3] == ["merge-base", "--is-ancestor"]:
            return SimpleNamespace(stdout="", returncode=0)
        if command[1] == "diff":
            return SimpleNamespace(stdout="", returncode=0)
        if command[1] == "ls-files":
            return SimpleNamespace(stdout="", returncode=0)
        raise AssertionError(command)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    attestation = runner.validate_source_revision(revision, repo_root=tmp_path)

    assert attestation["head"] == revision
    assert attestation["scoped_clean"] is True
    assert not any("symbolic-ref" in call for call in calls)


def test_source_validation_accepts_docs_only_descendant(monkeypatch, tmp_path):
    revision = "e" * 40
    head = "f" * 40

    def fake_run(command, **kwargs):
        if command[1:] == ["rev-parse", "--show-toplevel"]:
            return SimpleNamespace(stdout=str(tmp_path) + "\n", returncode=0)
        if command[1:] == ["rev-parse", "HEAD"]:
            return SimpleNamespace(stdout=head + "\n", returncode=0)
        if command[1:4] == ["merge-base", "--is-ancestor", revision]:
            return SimpleNamespace(stdout="", returncode=0)
        if command[1] in {"diff", "ls-files"}:
            return SimpleNamespace(stdout="", returncode=0)
        raise AssertionError(command)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    attestation = runner.validate_source_revision(revision, repo_root=tmp_path)

    assert attestation["expected"] == revision
    assert attestation["head"] == head
    assert attestation["scoped_clean"] is True


def test_source_validation_rejects_runtime_change_after_frozen_revision(monkeypatch, tmp_path):
    revision = "e" * 40
    head = "f" * 40
    changed_path = "superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_9d_alignment.py"

    def fake_run(command, **kwargs):
        if command[1:] == ["rev-parse", "--show-toplevel"]:
            return SimpleNamespace(stdout=str(tmp_path) + "\n", returncode=0)
        if command[1:] == ["rev-parse", "HEAD"]:
            return SimpleNamespace(stdout=head + "\n", returncode=0)
        if command[1:3] == ["merge-base", "--is-ancestor"]:
            return SimpleNamespace(stdout="", returncode=0)
        if command[1:4] == ["diff", "--name-only", revision]:
            return SimpleNamespace(stdout=changed_path + "\n", returncode=0)
        if command[1] in {"diff", "ls-files"}:
            return SimpleNamespace(stdout="", returncode=0)
        raise AssertionError(command)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    with pytest.raises(ValueError, match="changed since expected revision"):
        runner.validate_source_revision(revision, repo_root=tmp_path)


def test_source_validation_rejects_non_ancestor_revision(monkeypatch, tmp_path):
    revision = "e" * 40
    head = "f" * 40

    def fake_run(command, **kwargs):
        if command[1:] == ["rev-parse", "--show-toplevel"]:
            return SimpleNamespace(stdout=str(tmp_path) + "\n", returncode=0)
        if command[1:] == ["rev-parse", "HEAD"]:
            return SimpleNamespace(stdout=head + "\n", returncode=0)
        if command[1:3] == ["merge-base", "--is-ancestor"]:
            return SimpleNamespace(stdout="", returncode=1)
        raise AssertionError(command)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    with pytest.raises(ValueError, match="is not an ancestor"):
        runner.validate_source_revision(revision, repo_root=tmp_path)


def _health():
    return {
        "capability_schema": 1,
        "katago_version": "KataGo v1.16.3",
        "default_model": "b28",
        "models": {
            name: {
                "running": True,
                "model_path": f"/models/{name}.bin.gz",
                "model_sha256": f"{name}-sha",
                "model_sha256_verified": True,
                "has_human_model": True,
                "human_model_path": "/models/human.bin.gz",
                "human_model_sha256": "human-sha",
                "human_model_sha256_verified": True,
            }
            for name in ("b18", "b28")
        },
    }


def _wrapper(model):
    return {
        "selected_model": model,
        "model_path": f"/models/{model}.bin.gz",
        "model_sha256": f"{model}-sha",
        "human_model_path": "/models/human.bin.gz",
        "human_model_sha256": "human-sha",
        "katago_version": "KataGo v1.16.3",
    }


@pytest.mark.asyncio
async def test_common_preflight_attests_candidate_referees_and_smoke_without_golaxy(tmp_path):
    requested = []

    def handler(request):
        if request.url.path == "/health":
            return httpx.Response(200, json=_health())
        query = json.loads(request.content)
        requested.append((query["overrideSettings"]["model"], query["maxVisits"]))
        model = query["overrideSettings"]["model"]
        return httpx.Response(
            200,
            json={
                "rootInfo": {"visits": max(1, query["maxVisits"] - 1)},
                "moveInfos": [{"move": "Q16", "order": 0}],
                "_wrapper": _wrapper(model),
            },
        )

    smoke = tmp_path / "smoke.json"
    smoke.write_text(
        json.dumps(
            {
                "pass_code": -1,
                "resign_code": -3,
                "level_probes": [{"level": 3000, "ok": True}],
                "errors": [],
            }
        )
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False) as client:
        result = await runner.common_preflight(
            client=client,
            base_url="http://127.0.0.1:8000",
            action=runner.golaxy_9d_alignment.Batch("rank_9d@8", 5),
            source_attestation={"head": "f" * 40, "scoped_clean": True},
            smoke_report=smoke,
        )

    assert requested == [("b18", 8), ("b28", 200), ("b28", 800)]
    assert result["payload"]["candidate"]["requested_visits"] == 8
    assert result["payload"]["candidate"]["reported_visits"] == 7
    assert len(result["fingerprint"]) == 64


@pytest.mark.asyncio
async def test_common_preflight_rejects_health_redirect_before_analyze_or_golaxy(tmp_path):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(307, headers={"location": "http://127.0.0.1:8001/health"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False) as client:
        with pytest.raises(ValueError, match="redirect"):
            await runner.common_preflight(
                client=client,
                base_url="http://127.0.0.1:8000",
                action=runner.golaxy_9d_alignment.Batch("rank_9d@8", 5),
                source_attestation={"head": "f" * 40, "scoped_clean": True},
                smoke_report=tmp_path / "never-read.json",
            )

    assert calls == ["/health"]


def _game_preflight():
    return {
        "player": runner.make_alignment_player("rank_9d@8"),
        "capabilities": runner.adapters.retain_health_snapshot(_health()),
        "smoke": {"pass_code": -1, "resign_code": -3},
    }


@pytest.mark.asyncio
async def test_live_game_uses_level_3000_once_and_never_retries_service_errors(monkeypatch):
    calls = []

    class ServiceError(Exception):
        pass

    async def golaxy_move(_client, _history, *, rung, **_kwargs):
        calls.append(rung.golaxy_api_level)
        raise ServiceError("429")

    async def invoke_opponent(**kwargs):
        return await kwargs["golaxy_move"]([])

    monkeypatch.setattr(runner.adapters, "golaxy_move", golaxy_move)
    monkeypatch.setattr(runner, "play_one_game", invoke_opponent)

    with pytest.raises(ServiceError, match="429"):
        await runner.play_alignment_game(
            local_client=object(),
            golaxy_client=object(),
            base_url="http://127.0.0.1:8000",
            token="secret",
            reservation=SimpleNamespace(scheduled_color="B"),
            preflight=_game_preflight(),
        )

    assert calls == [3000]


@pytest.mark.asyncio
async def test_runtime_player_drift_is_a_non_replenishable_stop(monkeypatch):
    async def drift(*_args, **_kwargs):
        raise runner.run_selfplay.LadderMoveError("identity drift")

    async def invoke_player(**kwargs):
        return await kwargs["our_move"]([])

    monkeypatch.setattr(runner, "player_move_strict", drift)
    monkeypatch.setattr(runner, "play_one_game", invoke_player)

    with pytest.raises(runner.run_selfplay.LadderMoveError, match="identity drift"):
        await runner.play_alignment_game(
            local_client=object(),
            golaxy_client=object(),
            base_url="http://127.0.0.1:8000",
            token="secret",
            reservation=SimpleNamespace(scheduled_color="B"),
            preflight=_game_preflight(),
        )


@pytest.mark.asyncio
async def test_genuine_stability_ambiguity_is_the_only_replenishable_runtime_result(monkeypatch):
    visits = []

    async def conclusive(**kwargs):
        await kwargs["our_move"]([])
        return GameOutcome("B", "our_win", True, 0, 10.0, True, "move_cap")

    async def stable_check(*_args, **kwargs):
        visits.append(kwargs["visits"])
        return 10.0, False

    async def pass_move(*_args, **_kwargs):
        return "pass"

    monkeypatch.setattr(runner, "player_move_strict", pass_move)
    monkeypatch.setattr(runner, "play_one_game", conclusive)
    monkeypatch.setattr(runner.adapters, "adjudicate", stable_check)

    outcome = await runner.play_alignment_game(
        local_client=object(),
        golaxy_client=object(),
        base_url="http://127.0.0.1:8000",
        token="secret",
        reservation=SimpleNamespace(scheduled_color="B"),
        preflight=_game_preflight(),
    )

    assert visits == [800]
    assert (outcome.result, outcome.conclusive) == ("inconclusive_unstable", False)


@pytest.mark.asyncio
async def test_stability_recheck_uses_the_exact_post_move_cap_history(monkeypatch):
    rechecked = []

    async def move_cap(**kwargs):
        history = []
        move = await kwargs["our_move"](history)
        history.append(move)
        return GameOutcome("B", "our_win", True, 1, 10.0, True, "move_cap")

    async def chosen_move(*_args, **_kwargs):
        return 42

    async def stability(_client, _base_url, history, **_kwargs):
        rechecked.append(list(history))
        return 10.0, True

    monkeypatch.setattr(runner, "player_move_strict", chosen_move)
    monkeypatch.setattr(runner, "play_one_game", move_cap)
    monkeypatch.setattr(runner.adapters, "adjudicate", stability)

    await runner.play_alignment_game(
        local_client=object(),
        golaxy_client=object(),
        base_url="http://127.0.0.1:8000",
        token="secret",
        reservation=SimpleNamespace(scheduled_color="B"),
        preflight=_game_preflight(),
    )

    assert rechecked == [[42]]


class _NoopAsyncClient:
    def __init__(self, **_kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False


@pytest.mark.asyncio
async def test_preflight_rejects_persisted_fingerprint_drift_before_token_or_quota(monkeypatch, tmp_path):
    revision = "f" * 40
    with runner.golaxy_9d_alignment.experiment_session(tmp_path, revision) as session:
        runner.golaxy_9d_alignment.create_or_resume_quota(
            session, "quota", confirm_new=True, operator_date="2026-07-23"
        )
        runner.golaxy_9d_alignment.reserve_next_attempt(
            session, "quota", runner.golaxy_9d_alignment.Batch("rank_9d@8", 5), "old-fingerprint"
        )

    async def preflight(**_kwargs):
        return {"fingerprint": "new-fingerprint"}

    monkeypatch.setattr(runner, "validate_source_revision", lambda _revision: {"head": revision})
    monkeypatch.setattr(runner, "validate_output_path", lambda _out: tmp_path)
    monkeypatch.setattr(runner, "common_preflight", preflight)
    monkeypatch.setattr(runner.httpx, "AsyncClient", _NoopAsyncClient)
    monkeypatch.setattr(runner, "load_token", lambda *_args: pytest.fail("token must not be loaded"))
    args = runner.build_parser().parse_args(
        [
            "--preflight-only",
            "--base-url",
            "http://127.0.0.1:8000",
            "--expected-source-revision",
            revision,
            "--out",
            str(tmp_path),
        ]
    )

    with pytest.raises(ValueError, match="fingerprint drift"):
        await runner._run_async(args)


@pytest.mark.asyncio
async def test_summarize_is_offline_and_does_not_mutate_ledgers(monkeypatch, tmp_path):
    revision = "f" * 40
    with runner.golaxy_9d_alignment.experiment_session(tmp_path, revision):
        pass
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}
    monkeypatch.setattr(runner, "validate_source_revision", lambda _revision: {"head": revision})
    monkeypatch.setattr(runner, "validate_output_path", lambda _out: tmp_path)
    monkeypatch.setattr(runner, "common_preflight", lambda **_kwargs: pytest.fail("no local engine"))
    monkeypatch.setattr(runner, "load_token", lambda *_args: pytest.fail("no token"))
    args = runner.build_parser().parse_args(
        ["--summarize-only", "--expected-source-revision", revision, "--out", str(tmp_path)]
    )

    summary = await runner._run_async(args)

    after = {path.name: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}
    assert before == after
    assert summary["charged_attempts"] == 0
    assert summary["next_action"] == {"type": "Batch", "player": "rank_9d@8", "target_conclusive": 5}


@pytest.mark.asyncio
async def test_live_resumes_cumulative_target_holds_lock_and_exits_after_one_batch(monkeypatch, tmp_path):
    revision = "f" * 40
    batch = runner.golaxy_9d_alignment.Batch("rank_9d@8", 5)
    with runner.golaxy_9d_alignment.experiment_session(tmp_path, revision) as session:
        runner.golaxy_9d_alignment.create_or_resume_quota(
            session, "quota", confirm_new=True, operator_date="2026-07-23"
        )
        for outcome in ("win", "loss"):
            reservation = runner.golaxy_9d_alignment.reserve_next_attempt(session, "quota", batch, "fingerprint")
            runner.golaxy_9d_alignment.append_attempt_result(session, reservation, outcome, "fingerprint")

    async def preflight(**_kwargs):
        return {"fingerprint": "fingerprint"}

    colors = []

    async def game(**kwargs):
        colors.append(kwargs["reservation"].scheduled_color)
        records = [json.loads(line) for line in (tmp_path / "attempts.jsonl").read_text().splitlines()]
        assert records[-1]["type"] == "attempt_reserved"
        with pytest.raises(RuntimeError, match="already held"):
            with runner.golaxy_9d_alignment.experiment_session(tmp_path, revision):
                pass
        return GameOutcome(kwargs["reservation"].scheduled_color, "our_win", True, 1, 3.5, True, "golaxy_resign")

    monkeypatch.setattr(runner, "validate_source_revision", lambda _revision: {"head": revision})
    monkeypatch.setattr(runner, "validate_output_path", lambda _out: tmp_path)
    monkeypatch.setattr(runner, "common_preflight", preflight)
    monkeypatch.setattr(runner, "play_alignment_game", game)
    monkeypatch.setattr(runner, "load_token", lambda *_args: "secret")
    monkeypatch.setattr(runner.httpx, "AsyncClient", _NoopAsyncClient)
    args = runner.build_parser().parse_args(
        [
            "--quota-id",
            "quota",
            "--base-url",
            "http://127.0.0.1:8000",
            "--expected-source-revision",
            revision,
            "--out",
            str(tmp_path),
        ]
    )

    summary = await runner._run_async(args)

    assert colors == ["B", "W", "B"]
    assert summary["charged_attempts"] == 5
    assert summary["completed_batch"] == {"player": "rank_9d@8", "target_conclusive": 5}
    assert summary["next_action"] == {"type": "Batch", "player": "rank_9d@4", "target_conclusive": 5}
