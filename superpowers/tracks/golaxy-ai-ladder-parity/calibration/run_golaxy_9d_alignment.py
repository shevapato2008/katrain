#!/usr/bin/env python3
"""Fail-closed runner for the Golaxy 9D HumanSL alignment experiment."""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Mapping, Tuple
from zoneinfo import ZoneInfo

import httpx

sys.path.insert(0, str(Path(__file__).parent))
import adapters  # noqa: E402
import golaxy_9d_alignment  # noqa: E402
import run_selfplay  # noqa: E402

from katrain.core.ladder import (  # noqa: E402
    HUMANSL_PIKL_BASELINE,
    LadderRung,
    LadderStrengthSpec,
    get_rung,
    rung_strength_spec,
)
from katrain.core.ladder_calibration import GameOutcome, play_one_game  # noqa: E402

_BOARD_SIZE = 19
_KOMI = 7.5
_RULES = "chinese"
_WIDE_ROOT_NOISE = 0.04
_REFEREE_VISITS = 200
_STABILITY_VISITS = 800
_STABILITY_DELTA = 1.0
_REPO_ROOT = Path(__file__).resolve().parents[4]
_RESULTS_DIR = Path(__file__).resolve().parent / "results"
EXPECTED_OUT_DIR = (_RESULTS_DIR / "golaxy_9d_humansl_alignment").resolve()
DEFAULT_SMOKE_REPORT = _RESULTS_DIR / "smoke_report.json"
_SCOPED_PATHS = (
    "superpowers/tracks/golaxy-ai-ladder-parity/calibration/golaxy_9d_alignment.py",
    "superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_9d_alignment.py",
    "superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py",
    "superpowers/tracks/golaxy-ai-ladder-parity/calibration/adapters.py",
    "tests/platforms/test_golaxy_9d_alignment_protocol.py",
    "tests/platforms/test_golaxy_9d_alignment_runner.py",
    "tests/platforms/test_golaxy_calibration_opponent.py",
    "tests/platforms/test_humansl_selfplay.py",
    "superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_golaxy_fixed_screen.py",
    "tests/platforms/test_golaxy_fixed_screen.py",
)


class AlignmentStop(RuntimeError):
    """A fail-closed experiment stop which must never be retried automatically."""


def _expected_strength_spec(player: str) -> LadderStrengthSpec:
    visits = int(player.removeprefix("rank_9d@").removesuffix("s"))
    overrides = {
        "reportAnalysisWinratesAs": "BLACK",
        "humanSLProfile": "rank_9d",
        "ignorePreRootHistory": False,
    }
    if visits == 1:
        return LadderStrengthSpec(visits=1, main_model=None, human_model="humanv0", override_settings=overrides)
    overrides.update(HUMANSL_PIKL_BASELINE)
    return LadderStrengthSpec(visits=visits, main_model="b18", human_model="humanv0", override_settings=overrides)


def _validate_effective_query(rung: LadderRung, expected: LadderStrengthSpec) -> None:
    query = run_selfplay.adapters.build_ladder_analysis_query([], rung, _BOARD_SIZE, _KOMI, _RULES, _WIDE_ROOT_NOISE)
    expected_overrides = dict(expected.override_settings)
    expected_overrides["wideRootNoise"] = _WIDE_ROOT_NOISE
    if expected.main_model is not None:
        expected_overrides["model"] = expected.main_model
    expected_query = {
        "rules": run_selfplay.adapters.BaseEngine.get_rules(_RULES),
        "boardXSize": _BOARD_SIZE,
        "boardYSize": _BOARD_SIZE,
        "komi": _KOMI,
        "moves": [],
        "analyzeTurns": [0],
        "maxVisits": expected.visits,
        "includePolicy": True,
        "includeOwnership": False,
        "overrideSettings": expected_overrides,
    }
    if query != expected_query:
        raise ValueError("alignment player effective query drifted from the frozen grid")


def make_alignment_player(player: str) -> Tuple[str, LadderRung, str]:
    """Construct and independently validate one player from the frozen alignment grid."""
    player = golaxy_9d_alignment.validate_player_spec(player)
    label, rung, selection = run_selfplay.make_player(player, experimental_min_humansl_search_visits=2)
    expected = _expected_strength_spec(player)
    try:
        actual = rung_strength_spec(rung)
    except ValueError as exc:
        raise ValueError(f"alignment player strength spec is invalid: {exc}") from exc
    expected_selection = "argmax_human" if expected.visits == 1 else "search"
    if label != player or actual != expected or selection != expected_selection:
        raise ValueError("alignment player strength spec drifted from the frozen grid")
    _validate_effective_query(rung, expected)
    return label, rung, selection


def golaxy_9d_opponent() -> LadderRung:
    """Return rung 33 solely as the immutable Golaxy level-3000 opponent descriptor."""
    rung = get_rung(33)
    if rung.golaxy_api_level != golaxy_9d_alignment.GOLAXY_API_LEVEL:
        raise ValueError("Golaxy 9D opponent descriptor drifted from API level 3000")
    return rung


player_move_strict = run_selfplay.player_move_strict


def validate_base_url(value: object) -> str:
    if value != golaxy_9d_alignment.LOCAL_BASE_URL:
        raise ValueError(f"base URL must be exactly {golaxy_9d_alignment.LOCAL_BASE_URL}")
    return value


def validate_reported_visits(reported: object, requested: int) -> int:
    if type(requested) is not int or requested <= 0:
        raise ValueError("requested visits must be a positive plain int")
    if type(reported) is not int or not 1 <= reported <= requested + 7:
        raise ValueError(f"reported visits must be a positive plain int no greater than {requested + 7}")
    return reported


def _git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo_root, check=True, text=True, capture_output=True)
    return result.stdout.strip()


def validate_source_revision(expected: object, *, repo_root: Path = _REPO_ROOT) -> dict:
    if type(expected) is not str or re.fullmatch(r"[0-9a-f]{40}", expected) is None:
        raise ValueError("expected source revision must be a full lowercase 40-hex SHA-1")
    root = Path(_git(repo_root, "rev-parse", "--show-toplevel")).resolve()
    if root != Path(repo_root).resolve():
        raise ValueError("runner must execute in the current repository")
    head = _git(root, "rev-parse", "HEAD")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", expected, head],
        cwd=root,
        check=False,
        text=True,
        capture_output=True,
    )
    if ancestor.returncode != 0:
        raise ValueError(f"expected source revision {expected} is not an ancestor of current HEAD {head}")
    committed = _git(root, "diff", "--name-only", expected, head, "--", *_SCOPED_PATHS).splitlines()
    dirty = _git(root, "diff", "--name-only", "HEAD", "--", *_SCOPED_PATHS).splitlines()
    untracked = _git(root, "ls-files", "--others", "--exclude-standard", "--", *_SCOPED_PATHS).splitlines()
    changed = sorted(set(filter(None, committed + dirty + untracked)))
    if changed:
        raise ValueError("alignment-scoped source changed since expected revision: " + ", ".join(changed))
    return {"expected": expected, "head": head, "scoped_clean": True, "scoped_paths": list(_SCOPED_PATHS)}


def validate_output_path(value: object, *, repo_root: Path = _REPO_ROOT) -> Path:
    if not isinstance(value, (str, os.PathLike)):
        raise ValueError("output path is required")
    supplied = Path(value)
    lexical = (Path.cwd() / supplied).absolute() if not supplied.is_absolute() else supplied.absolute()
    resolved = supplied.resolve(strict=False)
    expected = (Path(repo_root).resolve() / EXPECTED_OUT_DIR.relative_to(_REPO_ROOT)).resolve()
    if lexical != expected or resolved != expected or not expected.is_relative_to(Path(repo_root).resolve()):
        raise ValueError(f"output must be the exact dedicated directory {expected}")
    for parent in [supplied, *supplied.parents]:
        if parent.exists() and parent.is_symlink():
            raise ValueError("output path may not traverse a symlink")
        if parent.resolve(strict=False) == Path(repo_root).resolve():
            break
    return expected


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--preflight-only", action="store_true")
    modes.add_argument("--create-quota-only", action="store_true")
    modes.add_argument("--summarize-only", action="store_true")
    parser.add_argument("--confirm-new-quota", action="store_true")
    parser.add_argument("--quota-id")
    parser.add_argument("--token-env")
    parser.add_argument("--base-url")
    parser.add_argument("--expected-source-revision", required=True)
    parser.add_argument("--ledger-source-revision")
    parser.add_argument("--resume-legacy-fingerprint")
    parser.add_argument("--out", required=True)
    parser.add_argument("--smoke-report")
    return parser


def validate_args(args: argparse.Namespace) -> str:
    if args.summarize_only:
        forbidden = (args.base_url, args.token_env, args.quota_id, args.smoke_report, args.resume_legacy_fingerprint)
        if any(value is not None for value in forbidden) or args.confirm_new_quota:
            raise ValueError("summarize-only rejects base URL, token, quota, smoke, and live arguments")
        return "summarize"
    if args.confirm_new_quota and not args.create_quota_only:
        raise ValueError("--confirm-new-quota is valid only with --create-quota-only")
    if args.create_quota_only and (not args.confirm_new_quota or not args.quota_id):
        raise ValueError("create-quota-only requires --confirm-new-quota and --quota-id")
    if args.create_quota_only and args.resume_legacy_fingerprint:
        raise ValueError("create-quota-only does not accept a legacy fingerprint")
    if not args.preflight_only and not args.create_quota_only and not args.quota_id:
        raise ValueError("live mode requires an explicit existing --quota-id")
    if args.preflight_only and (args.quota_id or args.token_env):
        raise ValueError("preflight-only does not accept token or quota arguments")
    if args.base_url is None:
        raise ValueError("common preflight requires --base-url")
    return "preflight" if args.preflight_only else "create" if args.create_quota_only else "live"


def load_token(token_env: str | None) -> str:
    name = token_env or "GOLAXY_ACCESS_TOKEN"
    token = os.environ.get(name, "").strip()
    if not token:
        fallback = Path.home() / ".katrain" / "golaxy_token.txt"
        if fallback.is_file():
            token = fallback.read_text(encoding="utf-8").strip()
    if not token:
        raise ValueError(f"Golaxy token is absent from ${name} and the redacted token file")
    return token


def _json_response(response: httpx.Response, endpoint: str) -> Mapping[str, object]:
    if 300 <= response.status_code < 400:
        raise ValueError(f"{endpoint} redirect is forbidden")
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, Mapping):
        raise ValueError(f"{endpoint} response must be an object")
    return payload


async def _post_probe(client, base_url: str, query: dict, endpoint: str) -> Mapping[str, object]:
    response = await client.post(f"{base_url}/analyze", json=query, timeout=httpx.Timeout(180.0, connect=10.0))
    return _json_response(response, endpoint)


async def _probe_player(client, base_url: str, player: tuple, capabilities: Mapping[str, object]) -> dict:
    label, rung, selection = player
    spec = rung_strength_spec(rung)
    identity = dict(adapters._capability_identity(capabilities, spec))
    query = adapters.build_ladder_analysis_query([], rung, _BOARD_SIZE, _KOMI, _RULES, _WIDE_ROOT_NOISE)
    if query["maxVisits"] != spec.visits:
        raise ValueError("semantic probe requested visits drift")
    analysis = await _post_probe(client, base_url, query, "candidate /analyze")
    attested_spec = (
        spec if spec.main_model is not None else dataclasses.replace(spec, main_model=identity["selected_model"])
    )
    run_selfplay.validate_analysis_attestation(analysis, attested_spec, identity)
    reported = validate_reported_visits((analysis.get("rootInfo") or {}).get("visits"), spec.visits)
    if selection == "argmax_human":
        if not run_selfplay._valid_policy(analysis.get("humanPolicy"), _BOARD_SIZE * _BOARD_SIZE + 1):
            raise ValueError("one-visit semantic probe requires a valid humanPolicy")
    elif selection == "search":
        if not isinstance(analysis.get("moveInfos"), list) or not analysis["moveInfos"]:
            raise ValueError("search semantic probe requires moveInfos")
        if (
            dict(rung.human_sl_params) != HUMANSL_PIKL_BASELINE
            or HUMANSL_PIKL_BASELINE["humanSLChosenMovePiklLambda"] <= 0
        ):
            raise ValueError("search semantic probe PIKL drift")
    else:
        raise ValueError("alignment selection may not be weighted")
    return {
        "label": label,
        "selection": selection,
        "selection_algorithm_version": run_selfplay.SELECTION_ALGORITHM_VERSION,
        "requested_visits": spec.visits,
        "reported_visits": reported,
        "requested_main_model": spec.main_model,
        "requested_human_model": spec.human_model,
        "effective_query": query,
        "identity": identity,
    }


async def _probe_referee(client, base_url: str, capabilities: Mapping[str, object], visits: int) -> dict:
    _label, rung, selection = run_selfplay.make_player(f"b28@{visits}")
    if selection != "search" or rung.net != "b28" or rung.max_visits != visits:
        raise ValueError("referee construction drift")
    spec = rung_strength_spec(rung)
    identity = dict(adapters._capability_identity(capabilities, spec))
    query = adapters.build_ladder_analysis_query([], rung, _BOARD_SIZE, _KOMI, _RULES, 0.0)
    analysis = await _post_probe(client, base_url, query, f"referee b28@{visits} /analyze")
    run_selfplay.validate_analysis_attestation(analysis, spec, identity)
    reported = validate_reported_visits((analysis.get("rootInfo") or {}).get("visits"), visits)
    if not isinstance(analysis.get("moveInfos"), list) or not analysis["moveInfos"]:
        raise ValueError("referee semantic probe requires moveInfos")
    return {"requested_visits": visits, "reported_visits": reported, "identity": identity}


def load_verified_smoke_codes(path: Path) -> dict:
    try:
        raw_report = path.read_bytes()
        report = json.loads(raw_report)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"verified smoke report is unavailable: {exc}") from exc
    if type(report) is not dict:
        raise ValueError("smoke report must be an object")
    pass_code, resign_code = adapters._valid_sentinels(report.get("pass_code"), report.get("resign_code"), _BOARD_SIZE)
    level_verified = any(
        type(item) is dict and item.get("level") == golaxy_9d_alignment.GOLAXY_API_LEVEL and item.get("ok") is True
        for item in report.get("level_probes", [])
    )
    if pass_code is None or resign_code is None or not level_verified or report.get("errors") != []:
        raise ValueError("smoke pass/resign codes must be verified, distinct, and out of board")
    return {
        "pass_code": pass_code,
        "resign_code": resign_code,
        "report_sha256": hashlib.sha256(raw_report).hexdigest(),
    }


def _canonical(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _canonical(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    return value


def _fingerprint(payload: Mapping[str, object]) -> str:
    data = json.dumps(_canonical(payload), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def configuration_fingerprint(payload: Mapping[str, object]) -> str:
    """Hash requested configuration and identities, excluding observational probe statistics."""
    stable = _canonical(payload)
    source = stable.get("source")
    if isinstance(source, dict):
        source.pop("head", None)
    candidate = stable.get("candidate")
    if isinstance(candidate, dict):
        candidate.pop("reported_visits", None)
    referee = stable.get("referee")
    if isinstance(referee, dict):
        for probe in referee.values():
            if isinstance(probe, dict):
                probe.pop("reported_visits", None)
    return _fingerprint(stable)


def resolve_ledger_fingerprint(current: str, persisted: str | None, explicit_legacy: str | None) -> str:
    if persisted is None:
        if explicit_legacy is not None:
            raise ValueError("legacy fingerprint is valid only for an existing candidate checkpoint")
        return current
    if persisted == current:
        if explicit_legacy not in (None, persisted):
            raise ValueError("legacy fingerprint does not match the persisted candidate checkpoint")
        return current
    if explicit_legacy != persisted:
        if explicit_legacy is None:
            raise ValueError("selection fingerprint drift; exact legacy fingerprint is required for audited resume")
        raise ValueError("legacy fingerprint does not match the persisted candidate checkpoint")
    return persisted


async def common_preflight(
    *, client, base_url: str, action, source_attestation: dict, smoke_report: Path, player_factory=make_alignment_player
) -> dict:
    validate_base_url(base_url)
    if not isinstance(action, golaxy_9d_alignment.Batch):
        raise ValueError(f"protocol is terminal; no live batch is available: {action!r}")
    player = player_factory(action.player)
    response = await client.get(f"{base_url}/health", timeout=httpx.Timeout(30.0, connect=10.0))
    capabilities = adapters.retain_health_snapshot(dict(_json_response(response, "/health")))
    candidate = await _probe_player(client, base_url, player, capabilities)
    referee = {
        "adjudication": await _probe_referee(client, base_url, capabilities, _REFEREE_VISITS),
        "stability": await _probe_referee(client, base_url, capabilities, _STABILITY_VISITS),
    }
    smoke = load_verified_smoke_codes(smoke_report)
    if golaxy_9d_opponent().golaxy_api_level != 3000:
        raise ValueError("Golaxy opponent must remain level 3000")
    payload = {
        "protocol_version": golaxy_9d_alignment.PROTOCOL_VERSION,
        "source": source_attestation,
        "candidate": candidate,
        "capability_snapshot": capabilities,
        "golaxy": {"rung": 33, "api_level": 3000},
        "game": {"board_size": _BOARD_SIZE, "rules": _RULES, "komi": _KOMI},
        "referee": referee,
        "smoke": smoke,
    }
    return {
        "player": player,
        "capabilities": capabilities,
        "smoke": smoke,
        "payload": payload,
        "fingerprint": configuration_fingerprint(payload),
    }


async def play_alignment_game(
    *, local_client, golaxy_client, base_url: str, token: str, reservation, preflight: dict
) -> GameOutcome:
    _label, rung, selection = preflight["player"]
    capabilities = preflight["capabilities"]
    smoke = preflight["smoke"]
    opponent = golaxy_9d_opponent()
    history_holder = {"history": None}

    async def our_move(history):
        history_holder["history"] = history
        return await player_move_strict(
            local_client,
            base_url,
            history,
            rung=rung,
            selection=selection,
            wrn=_WIDE_ROOT_NOISE,
            capabilities=capabilities,
        )

    async def opponent_move(history):
        history_holder["history"] = history
        return await adapters.golaxy_move(
            golaxy_client,
            history,
            rung=opponent,
            token=token,
            pass_code=smoke["pass_code"],
            resign_code=smoke["resign_code"],
        )

    adjudicate = partial(
        adapters.adjudicate,
        local_client,
        base_url,
        visits=_REFEREE_VISITS,
        capabilities=capabilities,
        strict_identity=True,
    )
    outcome = await play_one_game(
        our_move=our_move, golaxy_move=opponent_move, adjudicate=adjudicate, our_color=reservation.scheduled_color
    )
    if outcome.result in {"inconclusive_engine", "inconclusive_terminal"}:
        raise AlignmentStop(f"non-replenishable runtime drift: {outcome.result}")
    if outcome.conclusive and outcome.end_reason != "golaxy_resign":
        history = history_holder["history"]
        score, settled = await adapters.adjudicate(
            local_client,
            base_url,
            history,
            visits=_STABILITY_VISITS,
            capabilities=capabilities,
            strict_identity=True,
        )
        if (
            outcome.black_score is None
            or score is None
            or not settled
            or abs(score - outcome.black_score) >= _STABILITY_DELTA
        ):
            outcome = dataclasses.replace(outcome, result="inconclusive_unstable", our_win=False, conclusive=False)
    return outcome


def _summary_from_session(session) -> dict:
    # The protocol snapshot is backed by its single strict replay implementation, so summarize
    # mode stays offline and never grows a second ledger parser.
    snapshot = golaxy_9d_alignment.load_experiment_snapshot(session)
    evidence = golaxy_9d_alignment.load_evidence(session, dict(snapshot.fingerprints))
    action = golaxy_9d_alignment.next_batch(evidence)
    return {
        "charged_attempts": snapshot.charged_attempts,
        "quotas": [dataclasses.asdict(quota) for quota in snapshot.quotas],
        "fingerprints": dict(snapshot.fingerprints),
        "reservations": snapshot.reservations,
        "results": snapshot.results,
        "wins": snapshot.wins,
        "losses": snapshot.losses,
        "inconclusive": snapshot.inconclusive,
        "colors": snapshot.colors,
        "evidence": [dataclasses.asdict(batch) for batch in evidence.batches],
        "next_action": {"type": type(action).__name__, **dataclasses.asdict(action)},
    }


async def _run_async(args: argparse.Namespace) -> dict:
    mode = validate_args(args)
    source = validate_source_revision(args.expected_source_revision)
    ledger_revision = args.ledger_source_revision or args.expected_source_revision
    if re.fullmatch(r"[0-9a-f]{40}", ledger_revision) is None:
        raise ValueError("ledger source revision must be a full lowercase 40-hex SHA-1")
    if ledger_revision != args.expected_source_revision:
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", ledger_revision, args.expected_source_revision],
            cwd=_REPO_ROOT,
            check=False,
            text=True,
            capture_output=True,
        )
        if ancestor.returncode != 0:
            raise ValueError("ledger source revision must be an ancestor of the current implementation revision")
    out = validate_output_path(args.out)
    smoke_report = Path(args.smoke_report).resolve() if args.smoke_report else DEFAULT_SMOKE_REPORT
    if mode == "summarize" and not out.is_dir():
        raise ValueError("summarize-only requires an existing experiment directory")
    with golaxy_9d_alignment.experiment_session(out, ledger_revision) as session:
        if mode == "summarize":
            return _summary_from_session(session)
        evidence = golaxy_9d_alignment.load_evidence(session, {})
        action = golaxy_9d_alignment.next_batch(evidence)
        persisted_fingerprint = dict(golaxy_9d_alignment.load_experiment_snapshot(session).fingerprints).get(
            action.player
        )
        async with httpx.AsyncClient(follow_redirects=False, trust_env=False) as local_client:
            preflight = await common_preflight(
                client=local_client,
                base_url=args.base_url,
                action=action,
                source_attestation=source,
                smoke_report=smoke_report,
            )
            ledger_fingerprint = resolve_ledger_fingerprint(
                preflight["fingerprint"], persisted_fingerprint, args.resume_legacy_fingerprint
            )
            golaxy_9d_alignment.load_evidence(session, {action.player: ledger_fingerprint})
            if mode == "preflight":
                return {
                    "mode": mode,
                    "configuration_fingerprint": preflight["fingerprint"],
                    "ledger_fingerprint": ledger_fingerprint,
                    "next_action": repr(action),
                }
            token = load_token(args.token_env)
            operator_date = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
            quota = golaxy_9d_alignment.create_or_resume_quota(
                session,
                args.quota_id,
                confirm_new=mode == "create" and args.confirm_new_quota,
                operator_date=operator_date,
            )
            if mode == "create":
                return {
                    "mode": mode,
                    "quota_id": quota.quota_id,
                    "charged_attempts": quota.charged_attempts,
                    "next_action": repr(action),
                }

            batch_started = action
            async with httpx.AsyncClient(follow_redirects=False, trust_env=False) as golaxy_client:
                while True:
                    evidence = golaxy_9d_alignment.load_evidence(session, {})
                    current = golaxy_9d_alignment.next_batch(evidence)
                    if current != batch_started:
                        break
                    conclusive = next(
                        (
                            item.wins + item.losses
                            for item in reversed(evidence.batches)
                            if item.player == current.player and item.target_conclusive == current.target_conclusive
                        ),
                        0,
                    )
                    if conclusive >= current.target_conclusive:
                        break
                    reservation = golaxy_9d_alignment.reserve_next_attempt(
                        session, args.quota_id, current, ledger_fingerprint
                    )
                    outcome = await play_alignment_game(
                        local_client=local_client,
                        golaxy_client=golaxy_client,
                        base_url=args.base_url,
                        token=token,
                        reservation=reservation,
                        preflight=preflight,
                    )
                    if outcome.conclusive:
                        result = "win" if outcome.our_win else "loss"
                    elif outcome.result in {"inconclusive_score", "inconclusive_unsettled", "inconclusive_unstable"}:
                        result = "inconclusive"
                    else:
                        raise AlignmentStop(f"unexpected non-replenishable result: {outcome.result}")
                    golaxy_9d_alignment.append_attempt_result(session, reservation, result, ledger_fingerprint)
            summary = _summary_from_session(session)
            summary["mode"] = "live"
            summary["completed_batch"] = dataclasses.asdict(batch_started)
            return summary


def main(argv=None) -> int:
    parser = build_parser()
    try:
        result = asyncio.run(_run_async(parser.parse_args(argv)))
    except Exception as exc:  # every service/transport/identity failure is a one-shot protocol stop
        print(f"alignment runner stopped: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
