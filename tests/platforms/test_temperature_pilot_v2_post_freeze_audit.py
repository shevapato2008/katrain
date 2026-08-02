import copy
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parents[2]
CALIBRATION_DIR = REPO_ROOT / "superpowers/tracks/golaxy-ai-ladder-parity/calibration"
AUDIT_PATH = CALIBRATION_DIR / "audit_temperature_pilot_v2.py"
MANIFEST_PATH = CALIBRATION_DIR / "temperature_pilot_v2.json"
RESULTS_DIR = CALIBRATION_DIR / "results/selfplay_temperature_pilot_v2"
sys.path.insert(0, str(CALIBRATION_DIR))

import run_selfplay as selfplay
import run_temperature_pilot as runner
import temperature_pilot as pilot


def _audit_module():
    assert AUDIT_PATH.is_file(), "the v2 post-freeze audit layer is missing"
    spec = importlib.util.spec_from_file_location("temperature_pilot_v2_post_freeze_audit", AUDIT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fixture_checkpoint():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    matchup = next(row for row in manifest["matchups"] if row["matchup_id"] == "rank_5d@1t0.4__vs__rank_5d@1t1")
    path = runner.checkpoint_path(RESULTS_DIR, matchup)
    records = selfplay._parse_strict_jsonl(path.read_bytes(), context="post-freeze audit test checkpoint")
    return manifest, matchup, records


def _append_valid_inconclusive_pair(manifest, matchup, records, *, half_pair=False):
    augmented = copy.deepcopy(records)
    attempt = augmented[-1]["pair_attempt"] + 1
    opening = manifest["opening_suite"]["allocations"][attempt]
    for source in records[-2 : -1 if half_pair else None]:
        row = copy.deepcopy(source)
        color_index = source["color_index"]
        row.update(
            index=2 * attempt + color_index,
            pair_attempt=attempt,
            opening_id=opening["id"],
            opening_moves=list(opening["moves"]),
            result="inconclusive_engine",
            conclusive=False,
            our_win=False,
            end_reason="move_cap",
            num_moves=len(opening["moves"]) + row["attested_turn_count"],
            black_score=None,
        )
        for trace in row["sampling_trace"]:
            trace["draw_u64"] = pilot.derive_draw(
                manifest_sha256=manifest["manifest_sha256"],
                canonical_matchup_id=matchup["matchup_id"],
                pair_attempt=attempt,
                color_index=color_index,
                ply=trace["ply"],
                player=trace["player"],
            )
        augmented.append(row)
    return augmented


def _assert_existing_strict_validation_accepts(records, matchup, manifest):
    snapshot = ("\n".join(json.dumps(row, sort_keys=True) for row in records) + "\n").encode("utf-8")
    header = records[0]
    validated = selfplay._validated_checkpoint_records(snapshot, header["fingerprint"], header["configuration"])
    runner._validate_exact_checkpoint_schedule(validated[1:], matchup, manifest)
    return validated


def test_post_freeze_audit_rejects_valid_inconclusive_pair_after_tenth_complete_pair():
    manifest, matchup, records = _fixture_checkpoint()
    augmented = _append_valid_inconclusive_pair(manifest, matchup, records)
    validated = _assert_existing_strict_validation_accepts(augmented, matchup, manifest)
    audit = _audit_module()

    with pytest.raises(ValueError, match="after.*10.*complete pair"):
        audit.audit_validated_checkpoint_records(validated, matchup)


def test_post_freeze_audit_rejects_eof_dangling_half_pair():
    manifest, matchup, records = _fixture_checkpoint()
    augmented = _append_valid_inconclusive_pair(manifest, matchup, records, half_pair=True)
    validated = _assert_existing_strict_validation_accepts(augmented, matchup, manifest)
    audit = _audit_module()

    with pytest.raises(ValueError, match="dangling half-pair"):
        audit.audit_validated_checkpoint_records(validated, matchup)


def test_post_freeze_audit_rejects_rows_beyond_pair_attempt_cap():
    audit = _audit_module()
    _manifest, matchup, records = _fixture_checkpoint()
    pair = copy.deepcopy(records[-2:])
    games = []
    for attempt in range(matchup["max_pair_attempts"] + 1):
        for color_index, source in enumerate(pair):
            row = copy.deepcopy(source)
            row.update(
                index=2 * attempt + color_index,
                pair_attempt=attempt,
                color_index=color_index,
                conclusive=False,
                result="inconclusive_engine",
                our_win=False,
            )
            games.append(row)

    with pytest.raises(ValueError, match="pair-attempt cap"):
        audit.audit_validated_checkpoint_records([records[0], *games], matchup)


def _copy_frozen_evidence_without_lock_sidecars(destination):
    destination.mkdir()
    for path in RESULTS_DIR.iterdir():
        if path.is_file() and not path.name.endswith(".lock"):
            shutil.copyfile(path, destination / path.name)


def _clean_cli_environment():
    return {
        name: value for name, value in os.environ.items() if not name.startswith("KIVY") and not name.startswith("KCFG")
    }


def test_post_freeze_audit_cli_outside_repo_reports_scope_and_never_creates_lock_sidecars(tmp_path):
    evidence_copy = tmp_path / "evidence"
    _copy_frozen_evidence_without_lock_sidecars(evidence_copy)
    before = {
        path.relative_to(evidence_copy): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in evidence_copy.iterdir()
        if path.is_file()
    }

    result = subprocess.run(
        [
            sys.executable,
            str(AUDIT_PATH),
            "--manifest",
            str(MANIFEST_PATH),
            "--results-dir",
            str(evidence_copy),
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        env=_clean_cli_environment(),
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip(), "post-freeze audit CLI emitted no report"
    report = json.loads(result.stdout)
    assert report["audit_scope"] == "humansl-temperature-pilot-v2-post-freeze-audit-v1"
    assert report["audit_status"] == "pass"
    assert report["frozen_gate"]["status"] == "fail"
    assert len(report["checkpoints"]) == 9
    assert all(row["complete_pairs"] == 10 for row in report["checkpoints"])
    after = {
        path.relative_to(evidence_copy): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in evidence_copy.iterdir()
        if path.is_file()
    }
    assert after == before
