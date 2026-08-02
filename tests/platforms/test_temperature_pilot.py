import hashlib
import importlib
import json
import os
import stat
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import FrozenInstanceError
from pathlib import Path

import httpx
import pytest


CALIBRATION_DIR = Path(__file__).parents[2] / "superpowers/tracks/golaxy-ai-ladder-parity/calibration"
FROZEN_V2_MANIFEST = CALIBRATION_DIR / "temperature_pilot_v2.json"
sys.path.insert(0, str(CALIBRATION_DIR))
pilot = importlib.import_module("temperature_pilot")
selfplay = importlib.import_module("run_selfplay")
runner = importlib.import_module("run_temperature_pilot")


def _valid_policy(selected_index=0):
    policy = [0.0] * 362
    policy[selected_index] = 1.0
    return policy


def _health_snapshot():
    return selfplay.adapters.retain_health_snapshot(
        {
            "capability_schema": 1,
            "katago_version": "KataGo v1.16.3",
            "default_model": "b28",
            "models": {
                "b28": {
                    "running": True,
                    "model_path": "/models/b28.bin.gz",
                    "model_sha256": "b28-sha",
                    "model_sha256_verified": True,
                    "has_human_model": True,
                    "human_model_path": "/models/human.bin.gz",
                    "human_model_sha256": "human-sha",
                    "human_model_sha256_verified": True,
                }
            },
        }
    )


def _runner_manifest():
    return {
        "schema_version": 2,
        "protocol": pilot.PROTOCOL_VERSION,
        "manifest_sha256": "ab" * 32,
        "runtime_sources": {"runtime.py": "12" * 32},
        "opening_suite": {
            "path": pilot.OPENING_SUITE_PATH,
            "file_sha256": "cd" * 32,
            "checksum": pilot.OPENING_SUITE_CHECKSUM,
            "cycle": False,
            "allocations": [
                {"attempt": attempt, "id": f"o{attempt + 1:03d}", "moves": list(range(8))} for attempt in range(20)
            ],
        },
        "matchups": [pilot._matchup_projection(matchup) for matchup in pilot.MATCHUPS],
    }


def test_dry_run_prints_exact_serial_schedule_without_network_or_result_files(tmp_path, monkeypatch, capsys):
    manifest = _runner_manifest()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("manifest fixture\n", encoding="utf-8")
    results_dir = tmp_path / "results"
    monkeypatch.setattr(runner.pilot, "validate_manifest_file", lambda path, root: manifest)

    runner.dry_run(manifest_path, results_dir, repo_root=tmp_path)

    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == f"manifest_sha256 {manifest['manifest_sha256']}"
    assert len(lines) == 1 + 9 * 22
    for matchup_index, matchup in enumerate(pilot.MATCHUPS):
        offset = 1 + matchup_index * 22
        checkpoint = results_dir / (
            f"selfplay_screen_{selfplay._fname(matchup.a.canonical_label)}"
            f"__vs__{selfplay._fname(matchup.b.canonical_label)}.jsonl"
        )
        assert lines[offset] == f"matchup {matchup_index + 1}/9 {matchup.matchup_id}"
        assert lines[offset + 1] == f"checkpoint {checkpoint}"
        assert lines[offset + 2 : offset + 22] == [
            f"attempt {attempt} opening o{attempt + 1:03d} moves 0,1,2,3,4,5,6,7" for attempt in range(20)
        ]
    assert not results_dir.exists()


def test_launch_snapshot_is_exclusive_reused_byte_for_byte_and_rejects_live_identity_drift(tmp_path):
    results_dir = tmp_path / "results"
    first = runner.ensure_launch_snapshot(results_dir, _health_snapshot(), "ab" * 32)
    snapshot_path = results_dir / "launch_snapshot.json"
    original_bytes = snapshot_path.read_bytes()

    second = runner.ensure_launch_snapshot(results_dir, _health_snapshot(), "ab" * 32)

    assert second == first
    assert snapshot_path.read_bytes() == original_bytes
    assert first["snapshot_sha256"] == pilot.canonical_digest(first, exclude="snapshot_sha256")
    drifted = json.loads(json.dumps(selfplay._json_value(_health_snapshot())))
    drifted["models"]["b28"]["human_model_sha256"] = "different-human"
    with pytest.raises(ValueError, match="live health identity.*frozen launch snapshot"):
        runner.ensure_launch_snapshot(results_dir, selfplay.adapters.retain_health_snapshot(drifted), "ab" * 32)


def test_launch_snapshot_torn_publication_leaves_no_final_or_temp_file(tmp_path, monkeypatch):
    results_dir = tmp_path / "results"

    def interrupted_link(_source, _destination):
        raise OSError("injected publication interruption")

    monkeypatch.setattr(runner.os, "link", interrupted_link)
    with pytest.raises(OSError, match="injected"):
        runner.ensure_launch_snapshot(results_dir, _health_snapshot(), "ab" * 32)

    assert not (results_dir / "launch_snapshot.json").exists()
    assert list(results_dir.iterdir()) == []


def test_launch_snapshot_concurrent_winner_is_validated_and_reused(tmp_path, monkeypatch):
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    original_link = os.link
    publications = []

    def concurrent_link(source, destination):
        publications.append(Path(source).read_bytes())
        original_link(source, destination)
        raise FileExistsError(destination)

    monkeypatch.setattr(runner.os, "link", concurrent_link)
    snapshot = runner.ensure_launch_snapshot(results_dir, _health_snapshot(), "ab" * 32)

    assert (results_dir / "launch_snapshot.json").read_bytes() == publications[0]
    assert snapshot["snapshot_sha256"] == pilot.canonical_digest(snapshot, exclude="snapshot_sha256")
    assert not any(path.name.startswith(".launch_snapshot") for path in results_dir.iterdir())


def test_checkpoint_reader_rejects_total_and_line_limits_before_json(tmp_path):
    checkpoint = tmp_path / "checkpoint.jsonl"
    with checkpoint.open("wb") as output:
        output.truncate(selfplay.PILOT_CHECKPOINT_MAX_BYTES + 1)
    with pytest.raises(ValueError, match="total byte limit"):
        selfplay._read_bounded_checkpoint(checkpoint)

    checkpoint.write_bytes(b"x" * (selfplay.PILOT_CHECKPOINT_MAX_LINE_BYTES + 1))
    with pytest.raises(ValueError, match="line byte limit"):
        selfplay._read_bounded_checkpoint(checkpoint)


def test_atomic_pilot_checkpoint_interruption_preserves_old_complete_snapshot(tmp_path, monkeypatch):
    checkpoint = tmp_path / "pilot.jsonl"
    configuration = {"temperature_pilot": {"protocol_version": pilot.PROTOCOL_VERSION}}
    fingerprint = selfplay._configuration_fingerprint(configuration)
    old_snapshot = (
        json.dumps(
            {
                "record_type": "header",
                "schema": selfplay.CHECKPOINT_SCHEMA,
                "fingerprint": fingerprint,
                "configuration": configuration,
            }
        ).encode("utf-8")
        + b"\n"
    )
    checkpoint.write_bytes(old_snapshot)

    def interrupted_replace(_source, _destination):
        raise OSError("injected checkpoint interruption")

    monkeypatch.setattr(selfplay.os, "replace", interrupted_replace)
    with pytest.raises(OSError, match="injected"):
        selfplay._atomic_replace_checkpoint(checkpoint, old_snapshot + b'{"record_type":"game"}\n')

    assert selfplay._read_bounded_checkpoint(checkpoint) == old_snapshot
    assert selfplay._already_done(checkpoint, fingerprint, configuration) == 0
    assert not any(path.name.startswith(".pilot.jsonl") for path in tmp_path.iterdir())


def test_atomic_pilot_checkpoint_refuses_unresumable_oversized_row(tmp_path):
    checkpoint = tmp_path / "pilot.jsonl"
    old_snapshot = b'{"record_type":"header"}\n'
    checkpoint.write_bytes(old_snapshot)

    with pytest.raises(ValueError, match="line byte limit"):
        selfplay._atomic_replace_checkpoint(
            checkpoint,
            old_snapshot + b"x" * (selfplay.PILOT_CHECKPOINT_MAX_LINE_BYTES + 1),
        )

    assert checkpoint.read_bytes() == old_snapshot


def test_legacy_checkpoint_header_keeps_non_atomic_creation_path(tmp_path, monkeypatch):
    checkpoint = tmp_path / "legacy.jsonl"
    configuration = {"legacy": True}
    fingerprint = selfplay._configuration_fingerprint(configuration)
    monkeypatch.setattr(
        selfplay,
        "_atomic_replace_checkpoint",
        lambda *_args: (_ for _ in ()).throw(AssertionError("legacy checkpoint used pilot persistence")),
    )

    selfplay._prepare_checkpoint(checkpoint, fingerprint, configuration)

    assert checkpoint.read_text(encoding="utf-8").endswith("\n")


def test_pilot_checkpoint_exclusive_header_creation_never_overwrites_unbound_evidence(tmp_path, monkeypatch):
    checkpoint = tmp_path / "pilot.jsonl"
    configuration = {"temperature_pilot": {"protocol_version": pilot.PROTOCOL_VERSION}}
    fingerprint = selfplay._configuration_fingerprint(configuration)
    unbound = b'{"unbound":"evidence"}\n'

    def concurrent_link(_source, destination):
        Path(destination).write_bytes(unbound)
        raise FileExistsError(destination)

    monkeypatch.setattr(selfplay.os, "link", concurrent_link)
    with pytest.raises(ValueError, match="schema-3 header"):
        selfplay._prepare_checkpoint(checkpoint, fingerprint, configuration, atomic=True)

    assert checkpoint.read_bytes() == unbound
    assert not any(path.name.startswith(".pilot.jsonl") for path in tmp_path.iterdir())


@pytest.mark.parametrize("occupant", ["fifo", "broken_symlink"])
def test_pilot_checkpoint_rejects_nonregular_unbound_occupants(tmp_path, occupant):
    checkpoint = tmp_path / "pilot.jsonl"
    if occupant == "fifo":
        os.mkfifo(checkpoint)
    else:
        checkpoint.symlink_to(tmp_path / "missing-target")
    configuration = {"temperature_pilot": {"protocol_version": pilot.PROTOCOL_VERSION}}
    fingerprint = selfplay._configuration_fingerprint(configuration)

    with pytest.raises(ValueError, match="regular file"):
        selfplay._prepare_checkpoint(checkpoint, fingerprint, configuration, atomic=True)

    assert checkpoint.is_symlink() if occupant == "broken_symlink" else stat.S_ISFIFO(checkpoint.lstat().st_mode)


def test_legacy_checkpoint_read_error_keeps_value_error_contract(tmp_path, monkeypatch):
    checkpoint = tmp_path / "legacy.jsonl"
    checkpoint.write_text("{}\n", encoding="utf-8")

    def unreadable(path):
        if path == checkpoint:
            raise PermissionError("injected unreadable checkpoint")
        return original_read_bytes(path)

    original_read_bytes = Path.read_bytes
    monkeypatch.setattr(Path, "read_bytes", unreadable)
    with pytest.raises(ValueError, match="cannot read self-play checkpoint"):
        selfplay._already_done(checkpoint, "unused", {"legacy": True})


@pytest.mark.asyncio
async def test_legacy_second_checkpoint_read_error_keeps_value_error_contract(tmp_path, monkeypatch):
    checkpoint = tmp_path / "legacy.jsonl"
    configuration = {"legacy": True}
    fingerprint = selfplay._configuration_fingerprint(configuration)
    checkpoint.write_text(
        json.dumps(
            {
                "record_type": "header",
                "schema": selfplay.CHECKPOINT_SCHEMA,
                "fingerprint": fingerprint,
                "configuration": configuration,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    original_read_bytes = Path.read_bytes
    reads = 0

    def fail_second_read(path):
        nonlocal reads
        if path == checkpoint:
            reads += 1
            if reads == 2:
                raise PermissionError("injected second-read failure")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", fail_second_read)
    with pytest.raises(ValueError, match="cannot read self-play checkpoint"):
        await selfplay._run_matchup_checkpoint(
            labelA="A",
            rungA=None,
            selA=None,
            labelB="B",
            rungB=None,
            selB=None,
            target_pairs=1,
            max_pair_attempts=1,
            phase="screen",
            experiment4=False,
            openings=[{"id": "o001", "moves": [0]}],
            cycle_openings=False,
            client=None,
            base_url="http://unused",
            wrn=0.04,
            capabilities={},
            configuration=configuration,
            fingerprint=fingerprint,
            ckpt=checkpoint,
        )

    assert reads == 2


def test_runner_locks_and_validates_one_bounded_immutable_checkpoint_snapshot(tmp_path, monkeypatch):
    manifest = _runner_manifest()
    matchup = manifest["matchups"][0]
    checkpoint = runner.checkpoint_path(tmp_path, matchup)
    checkpoint.write_bytes(b"immutable checkpoint snapshot\n")
    launch = runner.ensure_launch_snapshot(tmp_path, _health_snapshot(), manifest["manifest_sha256"])
    snapshot = checkpoint.read_bytes()
    calls = {"locks": 0, "reads": 0, "validations": 0}
    original_lock = selfplay._checkpoint_lock

    @contextmanager
    def recording_lock(path):
        calls["locks"] += 1
        with original_lock(path):
            yield

    def bounded_read(path):
        calls["reads"] += 1
        assert path == checkpoint
        return snapshot

    def validated_records(data, fingerprint, configuration):
        calls["validations"] += 1
        assert data is snapshot
        return [{"record_type": "header"}]

    monkeypatch.setattr(selfplay, "_checkpoint_lock", recording_lock)
    monkeypatch.setattr(selfplay, "_read_bounded_checkpoint", bounded_read)
    monkeypatch.setattr(selfplay, "_validated_checkpoint_records", validated_records)
    monkeypatch.setattr(runner, "_validate_exact_checkpoint_schedule", lambda records, *_args: None)
    monkeypatch.setattr(
        selfplay,
        "complete_pair_sample",
        lambda records, phase: {"a_wins": 0, "complete_pairs": 0, "games": 0, "inconclusive_pairs": 0},
    )

    evidence = runner._validated_checkpoint_evidence(checkpoint, matchup, manifest, launch, tmp_path / "manifest.json")

    assert calls == {"locks": 1, "reads": 1, "validations": 1}
    assert evidence["checkpoint_sha256"] == hashlib.sha256(snapshot).hexdigest()


def test_runner_decides_missing_checkpoint_only_after_acquiring_its_lock(tmp_path, monkeypatch):
    manifest = _runner_manifest()
    matchup = manifest["matchups"][0]
    checkpoint = runner.checkpoint_path(tmp_path, matchup)
    launch = runner.ensure_launch_snapshot(tmp_path, _health_snapshot(), manifest["manifest_sha256"])
    snapshot = b"published while waiting for checkpoint lock\n"
    calls = {"locks": 0, "reads": 0}

    @contextmanager
    def publishing_lock(path):
        calls["locks"] += 1
        path.write_bytes(snapshot)
        yield

    monkeypatch.setattr(selfplay, "_checkpoint_lock", publishing_lock)
    monkeypatch.setattr(
        selfplay,
        "_read_bounded_checkpoint",
        lambda path: calls.__setitem__("reads", calls["reads"] + 1) or snapshot,
    )
    monkeypatch.setattr(
        selfplay,
        "_validated_checkpoint_records",
        lambda data, fingerprint, configuration: [{"record_type": "header"}],
    )
    monkeypatch.setattr(runner, "_validate_exact_checkpoint_schedule", lambda records, *_args: None)
    monkeypatch.setattr(
        selfplay,
        "complete_pair_sample",
        lambda records, phase: {"a_wins": 0, "complete_pairs": 0, "games": 0, "inconclusive_pairs": 0},
    )

    evidence = runner._validated_checkpoint_evidence(checkpoint, matchup, manifest, launch, tmp_path / "manifest.json")

    assert calls == {"locks": 1, "reads": 1}
    assert evidence["checkpoint_sha256"] == hashlib.sha256(snapshot).hexdigest()


@pytest.mark.asyncio
async def test_live_runner_is_strictly_serial_runs_all_completed_inversions_and_binds_launch_digest(
    tmp_path, monkeypatch
):
    manifest = _runner_manifest()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("fixture\n", encoding="utf-8")
    monkeypatch.setattr(runner.pilot, "validate_manifest_file", lambda path, root: manifest)
    monkeypatch.setattr(
        runner.adapters, "fetch_health_snapshot", lambda client, base_url: _async_value(_health_snapshot())
    )
    active = 0
    calls = []

    async def fake_run_matchup(spec_a, spec_b, target_pairs, **kwargs):
        nonlocal active
        assert active == 0
        active += 1
        calls.append((spec_a, spec_b, target_pairs, kwargs))
        await _async_value(None)
        active -= 1
        # Every matchup is complete; these include both point and persuasive inversions.
        score = 5 if len(calls) == 1 else 9 if len(calls) == 2 else 11
        return {"complete_pairs": 10, "a_wins": score, "decision_games": 20}

    monkeypatch.setattr(runner.run_selfplay, "run_matchup", fake_run_matchup)
    summary = await runner.run_pilot(manifest_path, "http://engine", tmp_path / "results", repo_root=tmp_path)

    assert len(calls) == 9
    assert summary["status"] == "fail"
    launch = json.loads((tmp_path / "results/launch_snapshot.json").read_text(encoding="utf-8"))
    for matchup, (spec_a, spec_b, target_pairs, kwargs) in zip(pilot.MATCHUPS, calls):
        assert (spec_a, spec_b, target_pairs, kwargs["max_pair_attempts"], kwargs["phase"]) == (
            matchup.a.canonical_label,
            matchup.b.canonical_label,
            10,
            20,
            "screen",
        )
        assert kwargs["pilot_context"]["launch_snapshot_sha256"] == launch["snapshot_sha256"]
        assert kwargs["pilot_context"]["canonical_matchup_id"] == matchup.matchup_id
        assert kwargs["exact_openings"] == [
            {"id": allocation["id"], "moves": allocation["moves"]}
            for allocation in manifest["opening_suite"]["allocations"]
        ]


@pytest.mark.asyncio
async def test_live_runner_stops_on_first_incomplete_matchup(tmp_path, monkeypatch):
    manifest = _runner_manifest()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("fixture\n", encoding="utf-8")
    monkeypatch.setattr(runner.pilot, "validate_manifest_file", lambda path, root: manifest)
    monkeypatch.setattr(
        runner.adapters, "fetch_health_snapshot", lambda client, base_url: _async_value(_health_snapshot())
    )
    calls = []

    async def fake_run_matchup(*args, **kwargs):
        calls.append(args)
        complete_pairs = 9 if len(calls) == 3 else 10
        return {"complete_pairs": complete_pairs, "a_wins": 11, "decision_games": 2 * complete_pairs}

    monkeypatch.setattr(runner.run_selfplay, "run_matchup", fake_run_matchup)
    summary = await runner.run_pilot(manifest_path, "http://engine", tmp_path / "results", repo_root=tmp_path)

    assert len(calls) == 3
    assert summary["status"] == "incomplete"


async def _async_value(value):
    return value


def test_summarize_and_check_use_all_nine_validated_checkpoints_and_report_gate(tmp_path, monkeypatch):
    manifest = _runner_manifest()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("fixture\n", encoding="utf-8")
    results_dir = tmp_path / "results"
    runner.ensure_launch_snapshot(results_dir, _health_snapshot(), manifest["manifest_sha256"])
    monkeypatch.setattr(runner.pilot, "validate_manifest_file", lambda path, root: manifest)
    calls = []

    def validated(path, matchup, manifest_arg, launch, manifest_path_arg):
        calls.append(path)
        return {
            "matchup_id": matchup["matchup_id"],
            "a_wins": 11,
            "complete_pairs": 10,
            "identity_valid": True,
            "decision_games": 20,
            "inconclusive_pairs": 0,
            "checkpoint": str(path),
            "checkpoint_sha256": "34" * 32,
        }

    monkeypatch.setattr(runner, "_validated_checkpoint_evidence", validated)
    checked = runner.check_pilot(manifest_path, results_dir, repo_root=tmp_path)
    assert checked["status"] == "pass"
    assert calls == [runner.checkpoint_path(results_dir, matchup) for matchup in manifest["matchups"]]

    calls.clear()
    summarized = runner.summarize_pilot(manifest_path, results_dir, repo_root=tmp_path)
    assert summarized["status"] == "pass"
    frozen_summary = json.loads((results_dir / "summary.json").read_text(encoding="utf-8"))
    assert frozen_summary["status"] == "pass"
    assert frozen_summary["runtime_sources"] == manifest["runtime_sources"]
    assert frozen_summary["launch_snapshot_sha256"]
    assert frozen_summary["model_identities"]
    assert frozen_summary["evidence"][0]["checkpoint_sha256"] == "34" * 32
    assert frozen_summary["evidence"][0]["a_losses"] == 9
    assert frozen_summary["evidence"][0]["target_games"] == 20
    assert frozen_summary["evidence"][0]["classification"] == "direction_supported"
    report = (results_dir / "report.md").read_text(encoding="utf-8")
    assert all(
        token in report
        for token in (
            "overall: pass",
            "launch_snapshot_sha256",
            "runtime.py",
            "11-9/20",
            "direction_supported",
            "checkpoint_sha256",
        )
    )
    assert not list(results_dir.glob("*.tmp"))
    generation = json.loads((results_dir / "summary_generation.json").read_text(encoding="utf-8"))
    assert generation["summary_sha256"] == hashlib.sha256((results_dir / "summary.json").read_bytes()).hexdigest()
    assert generation["report_sha256"] == hashlib.sha256((results_dir / "report.md").read_bytes()).hexdigest()
    assert generation["generation"] in report
    assert runner._validate_summary_generation(results_dir) == generation


def test_atomic_write_fsyncs_file_and_containing_directory(tmp_path, monkeypatch):
    fsynced_modes = []
    original_fsync = runner.os.fsync

    def recording_fsync(fd):
        fsynced_modes.append(stat.S_IFMT(os.fstat(fd).st_mode))
        return original_fsync(fd)

    monkeypatch.setattr(runner.os, "fsync", recording_fsync)
    runner._atomic_write(tmp_path / "artifact.json", b"{}\n")

    assert stat.S_IFREG in fsynced_modes
    assert stat.S_IFDIR in fsynced_modes


def test_interrupted_summary_generation_is_detected_and_can_be_regenerated(tmp_path, monkeypatch):
    manifest = _runner_manifest()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("fixture\n", encoding="utf-8")
    results_dir = tmp_path / "results"
    runner.ensure_launch_snapshot(results_dir, _health_snapshot(), manifest["manifest_sha256"])
    monkeypatch.setattr(runner.pilot, "validate_manifest_file", lambda path, root: manifest)
    score = {"wins": 11}

    def validated(path, matchup, manifest_arg, launch, manifest_path_arg):
        return {
            "matchup_id": matchup["matchup_id"],
            "a_wins": score["wins"],
            "complete_pairs": 10,
            "identity_valid": True,
            "decision_games": 20,
            "inconclusive_pairs": 0,
            "checkpoint": str(path),
            "checkpoint_sha256": "34" * 32,
        }

    monkeypatch.setattr(runner, "_validated_checkpoint_evidence", validated)
    runner.summarize_pilot(manifest_path, results_dir, repo_root=tmp_path)
    score["wins"] = 12
    with pytest.raises(ValueError, match="checkpoint evidence"):
        runner.check_pilot(manifest_path, results_dir, repo_root=tmp_path)
    original_atomic_write = runner._atomic_write

    def interrupt_report(path, data):
        if Path(path).name == "report.md":
            raise OSError("injected summary interruption")
        return original_atomic_write(path, data)

    monkeypatch.setattr(runner, "_atomic_write", interrupt_report)
    with pytest.raises(OSError, match="injected"):
        runner.summarize_pilot(manifest_path, results_dir, repo_root=tmp_path)
    with pytest.raises(ValueError, match="summary generation"):
        runner.check_pilot(manifest_path, results_dir, repo_root=tmp_path)

    monkeypatch.setattr(runner, "_atomic_write", original_atomic_write)
    regenerated = runner.summarize_pilot(manifest_path, results_dir, repo_root=tmp_path)
    assert regenerated["evidence"][0]["a_wins"] == 12
    assert runner.check_pilot(manifest_path, results_dir, repo_root=tmp_path)["status"] in {"pass", "fail"}


def test_check_without_results_only_validates_manifest_and_missing_results_are_incomplete(tmp_path, monkeypatch):
    manifest = _runner_manifest()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("fixture\n", encoding="utf-8")
    monkeypatch.setattr(runner.pilot, "validate_manifest_file", lambda path, root: manifest)

    assert runner.check_pilot(manifest_path, repo_root=tmp_path) == {
        "status": "valid",
        "manifest_sha256": manifest["manifest_sha256"],
        "matchups": 9,
        "planned_games": 180,
    }
    result = runner.check_pilot(manifest_path, tmp_path / "missing", repo_root=tmp_path)
    assert result["status"] == "incomplete"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda row: row.update(pair_attempt=20, index=40),
        lambda row: row.update(opening_id="wrong"),
        lambda row: row.update(opening_moves=[99]),
    ],
)
def test_standalone_checkpoint_validation_rejects_attempt_or_frozen_opening_drift(mutation):
    manifest = _runner_manifest()
    matchup = manifest["matchups"][0]
    record = {
        "phase": "screen",
        "pair_attempt": 0,
        "color_index": 0,
        "index": 0,
        "opening_id": "o001",
        "opening_moves": list(range(8)),
    }
    mutation(record)
    with pytest.raises(ValueError, match="attempt|opening"):
        runner._validate_exact_checkpoint_schedule([record], matchup, manifest)


@pytest.mark.parametrize(
    "argv",
    [
        ["create-manifest", "--implementation-base", "a" * 40, "--out", "manifest.json"],
        ["check", "--manifest", "manifest.json"],
        ["check", "--manifest", "manifest.json", "--results-dir", "results"],
        ["dry-run", "--manifest", "manifest.json", "--results-dir", "results"],
        ["run", "--manifest", "manifest.json", "--base-url", "http://engine", "--results-dir", "results"],
        ["summarize", "--manifest", "manifest.json", "--results-dir", "results"],
    ],
)
def test_cli_exposes_only_the_narrow_temperature_pilot_commands(argv):
    args = runner.build_arg_parser().parse_args(argv)
    assert args.command == argv[0]


def test_executable_disables_kivy_argument_interception():
    environment = dict(os.environ)
    environment.pop("KIVY_NO_ARGS", None)
    result = subprocess.run(
        [sys.executable, str(CALIBRATION_DIR / "run_temperature_pilot.py"), "--help"],
        text=True,
        capture_output=True,
        env=environment,
        check=True,
    )
    assert "{create-manifest,check,dry-run,run,summarize}" in result.stdout
    assert "KIVY OPTION" not in result.stdout


@pytest.mark.parametrize("command", ["check", "dry-run"])
def test_non_running_cli_startup_is_silent_and_home_side_effect_free(tmp_path, command):
    home = tmp_path / "home"
    home.mkdir()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("fixture\n", encoding="utf-8")
    results_dir = tmp_path / "results"
    manifest = _runner_manifest()
    script = f"""
import json
import socket
import sys
sys.path.insert(0, {str(CALIBRATION_DIR)!r})
socket.socket.connect = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network access"))
import run_temperature_pilot as runner
runner.pilot.validate_manifest_file = lambda path, root: json.loads({json.dumps(manifest)!r})
sys.argv = ["run_temperature_pilot.py", {command!r}, "--manifest", {str(manifest_path)!r}]
if {command!r} == "dry-run":
    sys.argv += ["--results-dir", {str(results_dir)!r}]
exit_code = runner.main()
assert "run_selfplay" not in sys.modules
assert "adapters" not in sys.modules
raise SystemExit(exit_code)
"""
    environment = dict(os.environ)
    environment["HOME"] = str(home)
    for name in ("KIVY_NO_ARGS", "KIVY_NO_CONFIG", "KIVY_NO_FILELOG", "KIVY_NO_CONSOLELOG"):
        environment.pop(name, None)

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        env=environment,
    )

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert list(home.iterdir()) == []
    assert not results_dir.exists()


def test_runner_overrides_conflicting_kivy_suppression_environment():
    environment = dict(os.environ)
    names = ("KIVY_NO_ARGS", "KIVY_NO_CONFIG", "KIVY_NO_FILELOG", "KIVY_NO_CONSOLELOG")
    environment.update({name: "0" for name in names})
    script = f"""
import os
import sys
sys.path.insert(0, {str(CALIBRATION_DIR)!r})
import run_temperature_pilot
print(" ".join(os.environ[name] for name in {names!r}))
"""

    result = subprocess.run([sys.executable, "-c", script], text=True, capture_output=True, env=environment, check=True)

    assert result.stdout == "1 1 1 1\n"
    assert result.stderr == ""


@pytest.mark.parametrize("command", ["check", "dry-run"])
def test_frozen_v2_manifest_cli_is_silent_and_side_effect_free(tmp_path, command):
    if not FROZEN_V2_MANIFEST.is_file():
        pytest.skip("temperature_pilot_v2.json has not been frozen yet")
    home = tmp_path / "home"
    home.mkdir()
    results_dir = tmp_path / "results"
    environment = dict(os.environ)
    environment["HOME"] = str(home)
    for name in ("KIVY_NO_ARGS", "KIVY_NO_CONFIG", "KIVY_NO_FILELOG", "KIVY_NO_CONSOLELOG"):
        environment.pop(name, None)
    argv = [
        sys.executable,
        str(CALIBRATION_DIR / "run_temperature_pilot.py"),
        command,
        "--manifest",
        str(FROZEN_V2_MANIFEST),
    ]
    if command == "dry-run":
        argv += ["--results-dir", str(results_dir)]

    result = subprocess.run(argv, cwd=tmp_path, text=True, capture_output=True, env=environment)

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert list(home.iterdir()) == []
    assert not results_dir.exists()
    assert set(tmp_path.iterdir()) == {home}


def test_pilot_configuration_records_argmax_identity_without_temperature_entries():
    matchup = pilot.MATCHUPS[2]
    players = {
        "A": selfplay.make_player(matchup.a.canonical_label),
        "B": selfplay.make_player(matchup.b.canonical_label),
    }
    capabilities = _health_snapshot()
    configuration = selfplay._matchup_configuration(
        players,
        selfplay._preflight_capabilities(capabilities, players),
        capabilities=capabilities,
        wide_root_noise=0.04,
        target_pairs=10,
        max_pair_attempts=20,
        phase="screen",
        exact_openings=[{"id": f"o{index + 1:03d}", "moves": list(range(8))} for index in range(20)],
        pilot_context={
            "protocol_version": pilot.PROTOCOL_VERSION,
            "manifest_path": "manifest.json",
            "manifest_sha256": "ab" * 32,
            "canonical_matchup_id": matchup.matchup_id,
            "launch_snapshot_sha256": "ef" * 32,
        },
    )

    assert configuration["players"]["A"]["selection_algorithm_version"] == (pilot.ARGMAX_SELECTION_ALGORITHM_VERSION)
    assert "temperature" not in configuration["players"]["A"]
    assert configuration["players"]["B"]["selection_algorithm_version"] == pilot.SELECTION_ALGORITHM_VERSION
    assert configuration["players"]["B"]["temperature"] == "0.4"


@pytest.mark.asyncio
async def test_pilot_matchup_persists_and_resume_validates_sampling_traces(tmp_path, monkeypatch):
    calls = []
    atomic_writes = []
    opening = {"id": "o001", "moves": list(range(8))}
    context = {
        "protocol_version": pilot.PROTOCOL_VERSION,
        "manifest_path": "calibration/temperature_pilot_v2.json",
        "manifest_sha256": "ab" * 32,
        "canonical_matchup_id": pilot.MATCHUPS[0].matchup_id,
        "launch_snapshot_sha256": "ef" * 32,
    }

    async def fake_game(*, our_move, golaxy_move, our_color, initial_history, **_kwargs):
        calls.append((our_color, list(initial_history)))
        first, second = (our_move, golaxy_move) if our_color == "B" else (golaxy_move, our_move)
        assert await first(initial_history) in range(362)
        assert await second(initial_history + [20]) in range(362)
        return selfplay.GameOutcome(our_color, "our_win", True, len(initial_history) + 2, 1.0, True, "move_cap")

    def handler(_request):
        return httpx.Response(200, json={"humanPolicy": _valid_policy(), "_wrapper": _attestation()})

    monkeypatch.setattr(selfplay, "play_one_game", fake_game)
    monkeypatch.setattr(selfplay, "required_conclusive_pairs", lambda *_args, **_kwargs: 1)
    original_atomic_replace = selfplay._atomic_replace_checkpoint

    def recording_atomic_replace(path, data):
        atomic_writes.append(bytes(data))
        return original_atomic_replace(path, data)

    monkeypatch.setattr(selfplay, "_atomic_replace_checkpoint", recording_atomic_replace)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        kwargs = dict(
            client=client,
            base_url="http://engine",
            wrn=0.04,
            out_dir=tmp_path,
            capabilities=_health_snapshot(),
            phase="screen",
            max_pair_attempts=1,
            exact_openings=[opening],
            pilot_context=context,
        )
        await selfplay.run_matchup("rank_1d@1t1", "rank_1d@1t2", 1, **kwargs)
        checkpoint = next(tmp_path.glob("*.jsonl"))
        checkpoint.write_text(
            "\n".join(checkpoint.read_text(encoding="utf-8").splitlines()[:2]) + "\n", encoding="utf-8"
        )
        calls.clear()
        await selfplay.run_matchup("rank_1d@1t1", "rank_1d@1t2", 1, **kwargs)
        await selfplay.run_matchup("rank_1d@1t1", "rank_1d@1t2", 1, **kwargs)

    assert calls == [("W", opening["moves"])]
    assert len(atomic_writes) == 3  # two initial games, then the resumed missing color
    assert all(write.endswith(b"\n") for write in atomic_writes)
    records = [json.loads(line) for line in checkpoint.read_text(encoding="utf-8").splitlines()]
    assert records[0]["configuration"]["temperature_pilot"] == context
    assert records[0]["configuration"]["players"]["A"]["selection_algorithm_version"] == (
        pilot.SELECTION_ALGORITHM_VERSION
    )
    assert records[0]["configuration"]["players"]["A"]["temperature"] == "1"
    assert records[0]["configuration"]["players"]["B"]["selection_algorithm_version"] == (
        pilot.SELECTION_ALGORITHM_VERSION
    )
    assert records[0]["configuration"]["players"]["B"]["temperature"] == "2"
    assert [trace["player"] for trace in records[1]["sampling_trace"]] == ["A", "B"]
    assert [trace["ply"] for trace in records[1]["sampling_trace"]] == [8, 9]

    records[1]["sampling_trace"][0]["draw_u64"] = 0
    checkpoint.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="sampling trace"):
            await selfplay.run_matchup(
                "rank_1d@1t1",
                "rank_1d@1t2",
                1,
                client=client,
                base_url="http://engine",
                wrn=0.04,
                out_dir=tmp_path,
                capabilities=_health_snapshot(),
                phase="screen",
                max_pair_attempts=1,
                exact_openings=[opening],
                pilot_context=context,
            )


def _attestation():
    return {
        "selected_model": "b28",
        "model_path": "/models/b28.bin.gz",
        "model_sha256": "b28-sha",
        "human_model_path": "/models/human.bin.gz",
        "human_model_sha256": "human-sha",
        "katago_version": "KataGo v1.16.3",
    }


def test_temperature_evidence_identity_is_canonical_and_complete():
    identity = pilot.temperature_player_identity("rank_1d", "002.000")

    assert identity.canonical_label == "rank_1d@1t2"
    assert identity.profile == "rank_1d"
    assert identity.selection == "temperature_weighted"
    assert identity.selection_algorithm == "temperature-inverse-cdf-v1"
    assert identity.temperature == "2"


def test_temperature_identity_preserves_more_than_decimal_context_precision():
    raw = "0009.9999999999999999999999999999100"
    identity = pilot.temperature_player_identity("rank_1d", raw)

    assert identity.temperature == "9.99999999999999999999999999991"
    assert identity.canonical_label == "rank_1d@1t9.99999999999999999999999999991"


def test_distinct_long_temperature_decimals_have_distinct_evidence_identities():
    first = pilot.temperature_player_identity("rank_1d", "9.99999999999999999999999999991")
    second = pilot.temperature_player_identity("rank_1d", "9.99999999999999999999999999992")

    assert first.temperature != second.temperature
    assert first.canonical_label != second.canonical_label


@pytest.mark.asyncio
async def test_temperature_player_move_uses_audited_draw_and_appends_valid_trace(monkeypatch):
    label, rung, selection = selfplay.make_player("rank_1d@1t2.0")
    matchup_id = "rank_1d@1t1__vs__rank_1d@1t2"
    context = {
        "protocol_version": pilot.PROTOCOL_VERSION,
        "manifest_sha256": "ab" * 32,
        "canonical_matchup_id": matchup_id,
        "pair_attempt": 3,
        "color_index": 1,
        "player": "B",
    }
    history = [0, 1, 2]
    policy = [0.0] * 362
    policy[0] = 0.25
    policy[342] = 0.75
    expected_draw = pilot.derive_draw(
        manifest_sha256=context["manifest_sha256"],
        canonical_matchup_id=matchup_id,
        pair_attempt=3,
        color_index=1,
        ply=len(history),
        player="B",
    )
    expected_pick = selfplay.pick_temperature_policy(policy, (19, 19), 2.0, expected_draw)
    assert expected_draw == 9451441004411297038
    assert expected_pick == ((0, 0), 342)
    calls = []
    original_pick = selfplay.pick_temperature_policy

    def recording_pick(*args):
        calls.append(args)
        return original_pick(*args)

    monkeypatch.setattr(selfplay, "pick_temperature_policy", recording_pick)

    def handler(request):
        body = json.loads(request.content)
        assert label == "rank_1d@1t2"
        assert body["maxVisits"] == 1
        assert body["overrideSettings"].get("model") is None
        assert "human_policy_temperature" not in body["overrideSettings"]
        assert "rootPolicyTemperature" not in body["overrideSettings"]
        return httpx.Response(200, json={"humanPolicy": policy, "_wrapper": _attestation()})

    traces = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        move = await selfplay._player_move(
            client,
            "http://engine",
            history,
            rung=rung,
            selection=selection,
            wrn=0.04,
            capabilities=_health_snapshot(),
            temperature_context=context,
            sampling_trace=traces,
            player="B",
        )

    assert calls == [(policy, (19, 19), 2.0, expected_draw)]
    assert move == 342
    assert traces == [
        pilot.build_sampling_trace(
            manifest_sha256=context["manifest_sha256"],
            canonical_matchup_id=matchup_id,
            pair_attempt=3,
            color_index=1,
            ply=len(history),
            player="B",
            temperature="2",
            draw_u64=expected_draw,
            selected_index=expected_pick[1],
            policy=policy,
        )
    ]
    assert pilot.validate_sampling_trace(
        traces[0], **{k: context[k] for k in context if k not in ("protocol_version", "player")}
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "context_mutation",
    [
        lambda context: context.pop("protocol_version"),
        lambda context: context.update(protocol_version="wrong"),
        lambda context: context.pop("manifest_sha256"),
        lambda context: context.update(canonical_matchup_id="not-frozen"),
        lambda context: context.update(pair_attempt=-1),
        lambda context: context.update(color_index=2),
        lambda context: context.update(player="C"),
    ],
)
async def test_temperature_player_move_fails_closed_for_incomplete_or_invalid_context(context_mutation):
    _, rung, selection = selfplay.make_player("rank_1d@1t1")
    context = {
        "protocol_version": pilot.PROTOCOL_VERSION,
        "manifest_sha256": "ab" * 32,
        "canonical_matchup_id": "rank_1d@1t1__vs__rank_1d@1t2",
        "pair_attempt": 0,
        "color_index": 0,
        "player": "A",
    }
    context_mutation(context)

    def handler(_request):
        raise AssertionError("invalid static temperature context must fail before /analyze")

    traces = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        move = await selfplay._player_move(
            client,
            "http://engine",
            [],
            rung=rung,
            selection=selection,
            wrn=0.04,
            capabilities=_health_snapshot(),
            temperature_context=context,
            sampling_trace=traces,
        )

    assert move == "unavailable"
    assert traces == []


@pytest.mark.asyncio
async def test_temperature_player_move_rejects_cross_profile_context_before_analyze():
    _, rung, selection = selfplay.make_player("rank_1d@1t1")
    context = {
        "protocol_version": pilot.PROTOCOL_VERSION,
        "manifest_sha256": "ab" * 32,
        "canonical_matchup_id": "rank_5d@1t1__vs__rank_5d@1t2",
        "pair_attempt": 0,
        "color_index": 0,
        "player": "A",
    }

    def handler(_request):
        raise AssertionError("cross-profile context must fail before /analyze")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        move = await selfplay._player_move(
            client,
            "http://engine",
            [],
            rung=rung,
            selection=selection,
            wrn=0.04,
            capabilities=_health_snapshot(),
            temperature_context=context,
            sampling_trace=[],
            player="A",
        )

    assert move == "unavailable"


@pytest.mark.asyncio
async def test_temperature_player_move_fails_closed_for_malformed_policy():
    _, rung, selection = selfplay.make_player("rank_1d@1t1")
    context = {
        "protocol_version": pilot.PROTOCOL_VERSION,
        "manifest_sha256": "ab" * 32,
        "canonical_matchup_id": "rank_1d@1t1__vs__rank_1d@1t2",
        "pair_attempt": 0,
        "color_index": 0,
        "player": "A",
    }

    def handler(_request):
        return httpx.Response(200, json={"humanPolicy": [1.0], "_wrapper": _attestation()})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        move = await selfplay._player_move(
            client,
            "http://engine",
            [],
            rung=rung,
            selection=selection,
            wrn=0.04,
            capabilities=_health_snapshot(),
            temperature_context=context,
            sampling_trace=[],
        )

    assert move == "unavailable"


def test_draw_has_frozen_canonical_json_sha256_and_u64_vector():
    context = {
        "manifest_sha256": "ab" * 32,
        "canonical_matchup_id": "rank_1d@1t1__vs__rank_1d@1t2",
        "pair_attempt": 3,
        "color_index": 1,
    }
    encoded, digest, draw = pilot.derive_draw(**context, ply=27, player="A", include_audit=True)
    assert encoded.decode() == (
        '["humansl-temperature-pilot-v1","abababababababababababababababababababababababababababababababab",'
        '"rank_1d@1t1__vs__rank_1d@1t2",3,1,27,"A"]'
    )
    assert digest == "088d856d73d010b92d926e94e9a1a6e6bb0f7192e0410807ff56a99e1b449b9e"
    assert draw == 616295429160571065


def test_draw_rejects_matchup_ids_outside_the_exact_frozen_nine():
    with pytest.raises(ValueError, match="frozen matchup"):
        pilot.derive_draw(
            manifest_sha256="ab" * 32,
            canonical_matchup_id="rank_2d@1t1__vs__rank_2d@1t2",
            pair_attempt=0,
            color_index=0,
            ply=8,
            player="A",
        )


def test_policy_digest_has_frozen_count_and_binary64_vector_with_final_pass_entry():
    policy = [0.0] * 361 + [0.25]
    assert pilot.policy_digest(policy) == "ba08745956e76568164c75022ed57da172c75366e0607eb4a73abeddd9f0a69b"


@pytest.mark.parametrize(("index", "gtp"), [(0, "A19"), (18, "T19"), (342, "A1"), (360, "T1"), (361, "pass")])
def test_trace_uses_exact_policy_index_gtp_mapping(index, gtp):
    context = {
        "manifest_sha256": "ab" * 32,
        "canonical_matchup_id": "rank_1d@1t1__vs__rank_1d@1t2",
        "pair_attempt": 3,
        "color_index": 1,
    }
    policy = _valid_policy(index)
    trace = pilot.build_sampling_trace(
        **context,
        ply=27,
        player="A",
        temperature="1",
        draw_u64=pilot.derive_draw(**context, ply=27, player="A"),
        selected_index=index,
        policy=policy,
    )
    assert trace == {
        "ply": 27,
        "player": "A",
        "temperature": "1",
        "draw_u64": 616295429160571065,
        "selected_index": index,
        "selected_move": gtp,
        "policy_sha256": pilot.policy_digest(policy),
    }
    assert pilot.validate_sampling_trace(trace, **context) == trace


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        (lambda row: row.pop("ply"), "shape"),
        (lambda row: row.update(draw_u64=0), "draw"),
        (lambda row: row.update(selected_index=362), "index"),
        (lambda row: row.update(selected_move="a19"), "move"),
        (lambda row: row.update(policy_sha256="xyz"), "digest"),
    ],
)
def test_trace_validation_fails_closed_on_shape_draw_bounds_mapping_and_digest(mutation, match):
    context = {
        "manifest_sha256": "ab" * 32,
        "canonical_matchup_id": "rank_1d@1t1__vs__rank_1d@1t2",
        "pair_attempt": 3,
        "color_index": 1,
    }
    trace = pilot.build_sampling_trace(
        **context,
        ply=27,
        player="A",
        temperature="1",
        draw_u64=pilot.derive_draw(**context, ply=27, player="A"),
        selected_index=0,
        policy=_valid_policy(),
    )
    mutation(trace)
    with pytest.raises(ValueError, match=match):
        pilot.validate_sampling_trace(trace, **context)


@pytest.mark.parametrize("temperature", ["1.0", "01", "0.04", "10.01"])
def test_trace_rejects_noncanonical_or_out_of_range_temperature(temperature):
    context = {
        "manifest_sha256": "ab" * 32,
        "canonical_matchup_id": "rank_1d@1t1__vs__rank_1d@1t2",
        "pair_attempt": 0,
        "color_index": 0,
    }
    with pytest.raises(ValueError, match="temperature"):
        pilot.build_sampling_trace(
            **context,
            ply=8,
            player="A",
            temperature=temperature,
            draw_u64=pilot.derive_draw(**context, ply=8, player="A"),
            selected_index=0,
            policy=_valid_policy(),
        )


@pytest.mark.parametrize(
    ("matchup_id", "player", "temperature"),
    [
        ("rank_1d@1t1__vs__rank_1d@1t2", "A", "2"),
        ("rank_1d@1t1__vs__rank_1d@1t2", "B", "1"),
        ("rank_1d@1s__vs__rank_1d@1t0.4", "A", "0.4"),
    ],
)
def test_trace_temperature_must_match_the_temperature_player_on_that_side(matchup_id, player, temperature):
    context = {
        "manifest_sha256": "ab" * 32,
        "canonical_matchup_id": matchup_id,
        "pair_attempt": 0,
        "color_index": 0,
    }
    with pytest.raises(ValueError, match="temperature player"):
        pilot.build_sampling_trace(
            **context,
            ply=8,
            player=player,
            temperature=temperature,
            draw_u64=pilot.derive_draw(**context, ply=8, player=player),
            selected_index=0,
            policy=_valid_policy(),
        )


def test_trace_validation_rechecks_the_temperature_side_binding():
    context = {
        "manifest_sha256": "ab" * 32,
        "canonical_matchup_id": "rank_1d@1t1__vs__rank_1d@1t2",
        "pair_attempt": 0,
        "color_index": 0,
    }
    trace = pilot.build_sampling_trace(
        **context,
        ply=8,
        player="A",
        temperature="1",
        draw_u64=pilot.derive_draw(**context, ply=8, player="A"),
        selected_index=0,
        policy=_valid_policy(),
    )
    trace["temperature"] = "2"
    with pytest.raises(ValueError, match="temperature player"):
        pilot.validate_sampling_trace(trace, **context)


@pytest.mark.parametrize(
    ("policy", "selected_index", "match"),
    [
        ([], 0, "362"),
        ([1.0] * 361, 0, "362"),
        ([1.0] + [float("nan")] + [0.0] * 360, 0, "finite"),
        ([1.0] + [float("inf")] + [0.0] * 360, 0, "finite"),
        ([0.0] * 362, 0, "positive"),
        ([0.0, 1.0] + [0.0] * 360, 0, "selected.*positive"),
    ],
)
def test_trace_builder_rejects_malformed_or_unusable_policy(policy, selected_index, match):
    context = {
        "manifest_sha256": "ab" * 32,
        "canonical_matchup_id": "rank_1d@1t1__vs__rank_1d@1t2",
        "pair_attempt": 0,
        "color_index": 0,
    }
    with pytest.raises(ValueError, match=match):
        pilot.build_sampling_trace(
            **context,
            ply=8,
            player="A",
            temperature="1",
            draw_u64=pilot.derive_draw(**context, ply=8, player="A"),
            selected_index=selected_index,
            policy=policy,
        )


def test_protocol_helpers_do_not_import_selfplay():
    script = (
        "import importlib,sys; "
        f"sys.path.insert(0,{str(CALIBRATION_DIR)!r}); "
        "importlib.import_module('temperature_pilot'); "
        "print('run_selfplay' in sys.modules)"
    )
    result = subprocess.run([sys.executable, "-c", script], check=True, text=True, capture_output=True)
    assert result.stdout.strip() == "False"


def test_ordered_matchups_and_evidence_identities_are_frozen():
    expected = []
    for profile in ("rank_1d", "rank_5d", "rank_9d"):
        expected.extend(
            [
                f"{profile}@1t1__vs__{profile}@1t2",
                f"{profile}@1t0.4__vs__{profile}@1t1",
                f"{profile}@1s__vs__{profile}@1t0.4",
            ]
        )
    assert [matchup.matchup_id for matchup in pilot.MATCHUPS] == expected
    assert all(
        (m.phase, m.target_complete_pairs, m.max_pair_attempts, m.expected_stronger) == ("screen", 10, 20, "A")
        for m in pilot.MATCHUPS
    )
    first = pilot.MATCHUPS[0]
    assert (first.a.canonical_label, first.a.profile, first.a.selection_algorithm, first.a.temperature) == (
        "rank_1d@1t1",
        "rank_1d",
        "temperature-inverse-cdf-v1",
        "1",
    )
    assert first.b.temperature == "2"
    assert (
        pilot.MATCHUPS[2].a.canonical_label,
        pilot.MATCHUPS[2].a.profile,
        pilot.MATCHUPS[2].a.selection_algorithm,
        pilot.MATCHUPS[2].a.temperature,
    ) == ("rank_1d@1s", "rank_1d", "policy-argmax-v1", None)


def test_canonical_matchup_protocol_is_deeply_immutable():
    with pytest.raises(FrozenInstanceError):
        pilot.MATCHUPS[0].matchup_id = "mutated"
    with pytest.raises(FrozenInstanceError):
        pilot.MATCHUPS[0].a.canonical_label = "mutated"


def _git(root, *args):
    return subprocess.run(["git", *args], cwd=root, check=True, text=True, capture_output=True).stdout.strip()


def _fixture_repository(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    for relative in pilot.RUNTIME_SOURCE_PATHS:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"fixture for {relative}\n")
    suite_path = root / pilot.OPENING_SUITE_PATH
    suite_path.parent.mkdir(parents=True, exist_ok=True)
    suite = json.loads((CALIBRATION_DIR / "opening_suite_v1.json").read_text(encoding="utf-8"))
    suite_path.write_text(json.dumps(suite))
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "Protocol Test")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "implementation")
    base = _git(root, "rev-parse", "HEAD")
    (root / "README").write_text("descendant\n")
    _git(root, "add", "README")
    _git(root, "commit", "-qm", "manifest parent")
    return root, base, suite


def test_manifest_binds_exact_sources_ancestry_opening_allocation_and_self_digest(tmp_path):
    root, base, suite = _fixture_repository(tmp_path)
    manifest = pilot.build_manifest(root, base)
    assert manifest["schema_version"] == 2
    assert manifest["protocol"] == "humansl-temperature-pilot-v1"
    assert manifest["implementation_base_revision"] == base
    assert manifest["manifest_digest_contract"] == {
        "algorithm": "sha256",
        "excluded_top_level_field": "manifest_sha256",
        "encoding": "utf-8",
        "sort_keys": True,
        "item_separator": ",",
        "key_separator": ":",
        "ensure_ascii": False,
        "allow_nan": False,
        "file_byte_digest": False,
    }
    assert tuple(manifest["runtime_sources"]) == pilot.RUNTIME_SOURCE_PATHS
    assert manifest["opening_suite"] == {
        "path": pilot.OPENING_SUITE_PATH,
        "file_sha256": hashlib.sha256((root / pilot.OPENING_SUITE_PATH).read_bytes()).hexdigest(),
        "checksum": suite["checksum"],
        "allocations": [{"attempt": i, **suite["openings"][i]} for i in range(20)],
        "cycle": False,
    }
    assert manifest["versions"] == {
        "selection": "temperature-inverse-cdf-v1",
        "draw": "temperature-draw-sha256-u64-v1",
        "referee": "b28@200",
        "adjudication": "b28-settled-score-v1",
        "symmetry": {"mode": "katago-default", "requested_symmetry": None},
        "rules": "chinese",
        "komi": "7.5",
        "move_cap": 400,
        "checkpoint_schema": 3,
    }
    assert manifest["manifest_sha256"] == pilot.canonical_digest(manifest, exclude="manifest_sha256")
    serialized = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    assert manifest["manifest_sha256"] != hashlib.sha256(serialized).hexdigest()
    pilot.validate_manifest(manifest, root)


def test_manifest_rejects_altered_suite_even_with_a_recalculated_internal_checksum(tmp_path):
    root, base, _ = _fixture_repository(tmp_path)
    suite_path = root / pilot.OPENING_SUITE_PATH
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    suite["openings"][0]["moves"][0] += 1
    suite["checksum"] = pilot.canonical_digest(suite, exclude="checksum")
    suite_path.write_text(json.dumps(suite))
    with pytest.raises(ValueError, match="frozen opening suite"):
        pilot.build_manifest(root, base)


def test_manifest_matchups_do_not_alias_mutable_global_protocol_state(tmp_path):
    root, base, _ = _fixture_repository(tmp_path)
    original_label = pilot.MATCHUPS[0].a.canonical_label
    first = pilot.build_manifest(root, base)
    first["matchups"][0]["a"]["canonical_label"] = "mutated"
    assert pilot.MATCHUPS[0].a.canonical_label == original_label
    second = pilot.build_manifest(root, base)
    assert second["matchups"][0]["a"]["canonical_label"] == original_label
    assert pilot.classify_pilot(_results([11] * 9))["status"] == "pass"


def test_manifest_creation_is_exclusive_and_validation_rejects_bound_file_drift(tmp_path):
    root, base, _ = _fixture_repository(tmp_path)
    path = root / "manifest.json"
    created = pilot.create_manifest(path, root, base)
    assert json.loads(path.read_text(encoding="utf-8")) == created
    with pytest.raises(FileExistsError):
        pilot.create_manifest(path, root, base)
    (root / pilot.RUNTIME_SOURCE_PATHS[0]).write_text("drift\n")
    with pytest.raises(ValueError, match="source drift"):
        pilot.validate_manifest_file(path, root)


def test_manifest_validation_rejects_nonancestor_base_and_bad_self_digest(tmp_path):
    root, base, _ = _fixture_repository(tmp_path)
    manifest = pilot.build_manifest(root, base)
    manifest["manifest_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="self-digest"):
        pilot.validate_manifest(manifest, root)

    unrelated = _git(root, "commit-tree", _git(root, "write-tree"), "-m", "unrelated")
    with pytest.raises(ValueError, match="not an ancestor"):
        pilot.build_manifest(root, unrelated)


def test_manifest_rejects_staged_only_bound_source_drift(tmp_path):
    root, base, _ = _fixture_repository(tmp_path)
    relative = pilot.RUNTIME_SOURCE_PATHS[0]
    path = root / relative
    original = path.read_text()
    path.write_text("staged drift\n")
    _git(root, "add", relative)
    path.write_text(original)
    with pytest.raises(ValueError, match="source drift"):
        pilot.build_manifest(root, base)


def test_manifest_rejects_bound_source_mode_change_and_deletion(tmp_path):
    root, base, _ = _fixture_repository(tmp_path)
    mode_path = root / pilot.RUNTIME_SOURCE_PATHS[0]
    mode_path.chmod(mode_path.stat().st_mode | stat.S_IXUSR)
    with pytest.raises(ValueError, match="source drift"):
        pilot.build_manifest(root, base)

    deletion_root = tmp_path / "deletion"
    deletion_root.mkdir()
    root, base, _ = _fixture_repository(deletion_root)
    (root / pilot.RUNTIME_SOURCE_PATHS[0]).unlink()
    with pytest.raises(ValueError, match="source.*missing"):
        pilot.build_manifest(root, base)


def test_manifest_rejects_committed_descendant_bound_source_drift(tmp_path):
    root, base, _ = _fixture_repository(tmp_path)
    relative = pilot.RUNTIME_SOURCE_PATHS[0]
    (root / relative).write_text("committed descendant drift\n")
    _git(root, "add", relative)
    _git(root, "commit", "-qm", "change bound source")
    with pytest.raises(ValueError, match="source drift"):
        pilot.build_manifest(root, base)


def test_protocol_json_reads_are_explicit_utf8(tmp_path, monkeypatch):
    root, base, _ = _fixture_repository(tmp_path)
    manifest_path = root / "manifest.json"
    pilot.create_manifest(manifest_path, root, base)
    original_read_text = Path.read_text
    encodings = []

    def recording_read_text(path, *args, **kwargs):
        if path.suffix == ".json":
            encodings.append(kwargs.get("encoding"))
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", recording_read_text)
    pilot.validate_manifest_file(manifest_path, root)
    assert encodings and set(encodings) == {"utf-8"}


@pytest.mark.parametrize(
    ("wins", "expected"),
    [
        (15, "persuasive_direction"),
        (11, "direction_supported"),
        (10, "point_tie"),
        (9, "point_inversion"),
        (5, "persuasive_inversion"),
    ],
)
def test_per_match_classification_covers_every_category(wins, expected):
    assert pilot.classify_matchup(wins, complete_pairs=10, identity_valid=True)["classification"] == expected


def _results(wins):
    return [
        {"matchup_id": matchup.matchup_id, "a_wins": score, "complete_pairs": 10, "identity_valid": True}
        for matchup, score in zip(pilot.MATCHUPS, wins)
    ]


def test_overall_pass_accepts_exactly_eight_direction_wins_with_all_profile_totals_above_30():
    summary = pilot.classify_pilot(_results([11, 11, 11, 11, 11, 11, 11, 11, 10]))
    assert summary["status"] == "pass"
    assert summary["direction_matchups"] == 8
    assert summary["profile_a_wins"] == {"rank_1d": 33, "rank_5d": 33, "rank_9d": 32}


@pytest.mark.parametrize(
    ("wins", "reason"),
    [
        ([11, 11, 11, 11, 11, 11, 11, 10, 10], "fewer_than_8_direction_matchups"),
        ([11, 11, 8, 11, 11, 11, 11, 11, 11], "profile_aggregate_not_above_30"),
        ([5, 15, 15, 15, 15, 15, 15, 15, 15], "persuasive_inversion"),
    ],
)
def test_overall_failure_branches(wins, reason):
    summary = pilot.classify_pilot(_results(wins))
    assert summary["status"] == "fail"
    assert reason in summary["reasons"]


@pytest.mark.parametrize("field,value", [("complete_pairs", 9), ("complete_pairs", 11), ("identity_valid", False)])
def test_overall_is_incomplete_for_nonexact_pair_count_or_invalid_identity(field, value):
    results = _results([11] * 9)
    results[0][field] = value
    summary = pilot.classify_pilot(results)
    assert summary["status"] == "incomplete"


def test_overall_is_incomplete_for_missing_or_noncanonical_evidence():
    assert pilot.classify_pilot(_results([11] * 8))["status"] == "incomplete"
    changed = _results([11] * 9)
    changed[0]["matchup_id"] = "swapped"
    assert pilot.classify_pilot(changed)["status"] == "incomplete"
