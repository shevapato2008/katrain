#!/usr/bin/env python3
"""Fail-closed fixed HumanSL screenings against an exact Golaxy level."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import httpx
import run_golaxy_9d_alignment as alignment
import run_selfplay
from katrain.core.ladder import HUMANSL_PIKL_BASELINE, LadderStrengthSpec, get_rung, rung_strength_spec
from katrain.core.ladder_calibration import GameOutcome

LEDGER_NAME = "fixed_screen.jsonl"
_RESULTS_DIR = Path(__file__).resolve().parent / "results"


@dataclass(frozen=True)
class ScreenSpec:
    name: str
    players: tuple[str, ...]
    starting_colors: tuple[tuple[str, str], ...]
    valid_per_player: int
    charged_cap: int
    golaxy_rung: int
    golaxy_level_name: str
    golaxy_api_level: int
    expected_out_dir: Path
    legacy_header: bool = False


LEGACY_PRESET = ScreenSpec(
    name="golaxy9d-fixed56-20260724",
    players=("rank_9d@5", "rank_9d@6"),
    starting_colors=(("rank_9d@5", "B"), ("rank_9d@6", "W")),
    valid_per_player=5,
    charged_cap=20,
    golaxy_rung=33,
    golaxy_level_name="9段",
    golaxy_api_level=3000,
    expected_out_dir=(_RESULTS_DIR / "golaxy_9d_fixed_5_6_20260724").resolve(),
    legacy_header=True,
)
GOLAXY_8D_PRESET = ScreenSpec(
    name="golaxy8d-rank8d4-20260724",
    players=("rank_8d@4",),
    starting_colors=(("rank_8d@4", "B"),),
    valid_per_player=5,
    charged_cap=9,
    golaxy_rung=31,
    golaxy_level_name="8段",
    golaxy_api_level=2800,
    expected_out_dir=(_RESULTS_DIR / "golaxy_8d_rank_8d_4_20260724").resolve(),
)
GOLAXY_7D_PRESET = ScreenSpec(
    name="golaxy7d-rank7d4-20260724",
    players=("rank_7d@4",),
    starting_colors=(("rank_7d@4", "B"),),
    valid_per_player=5,
    charged_cap=9,
    golaxy_rung=29,
    golaxy_level_name="7段",
    golaxy_api_level=2500,
    expected_out_dir=(_RESULTS_DIR / "golaxy_7d_rank_7d_4_20260724").resolve(),
)
GOLAXY_3STAR_PRESET = ScreenSpec(
    name="golaxy3star-rank9d-conditional-20260725",
    players=("rank_9d@8", "rank_9d@16", "rank_9d@32", "rank_9d@64", "rank_9d@4", "rank_9d@2"),
    starting_colors=(
        ("rank_9d@8", "B"),
        ("rank_9d@16", "B"),
        ("rank_9d@32", "B"),
        ("rank_9d@64", "B"),
        ("rank_9d@4", "B"),
        ("rank_9d@2", "B"),
    ),
    valid_per_player=5,
    charged_cap=32,
    golaxy_rung=36,
    golaxy_level_name="星阵3星",
    golaxy_api_level=3300,
    expected_out_dir=(_RESULTS_DIR / "golaxy_3star_rank_9d_conditional_20260725").resolve(),
)
PRESETS = {spec.name: spec for spec in (LEGACY_PRESET, GOLAXY_8D_PRESET, GOLAXY_7D_PRESET, GOLAXY_3STAR_PRESET)}

# Backward-compatible names for the completed 9D preset and its tests.
PLAYERS = LEGACY_PRESET.players
CHARGED_CAP = LEGACY_PRESET.charged_cap
EXPECTED_OUT_DIR = LEGACY_PRESET.expected_out_dir


@dataclass(frozen=True)
class FixedGame:
    player: str
    color: str


@dataclass(frozen=True)
class FixedReservation:
    attempt_id: int
    player: str
    color: str
    fingerprint: str

    @property
    def scheduled_color(self) -> str:
        return self.color


def _expected_fixed_strength_spec(player: str) -> LadderStrengthSpec:
    match = re.fullmatch(r"rank_([1-9])d@([2-9]|[1-9][0-9]*)", player)
    if match is None:
        raise ValueError("fixed-screen player must be a dan-rank HumanSL search spec with at least 2 visits")
    profile = f"rank_{match.group(1)}d"
    overrides = {
        "reportAnalysisWinratesAs": "BLACK",
        "humanSLProfile": profile,
        "ignorePreRootHistory": False,
        **HUMANSL_PIKL_BASELINE,
    }
    return LadderStrengthSpec(
        visits=int(match.group(2)), main_model="b18", human_model="humanv0", override_settings=overrides
    )


def make_fixed_player(player: str, spec: ScreenSpec = LEGACY_PRESET):
    if player not in spec.players:
        raise ValueError(f"fixed-screen player must be one of {spec.players}")
    label, rung, selection = run_selfplay.make_player(player, experimental_min_humansl_search_visits=2)
    expected = _expected_fixed_strength_spec(player)
    if label != player or rung_strength_spec(rung) != expected or selection != "search":
        raise ValueError("fixed-screen player strength drift")
    alignment._validate_effective_query(rung, expected)
    return label, rung, selection


def _valid_results(records: list[dict], player: str) -> list[dict]:
    return [
        record
        for record in records
        if record.get("type") == "result"
        and record.get("player") == player
        and record.get("outcome") in ("win", "loss")
    ]


def next_game(records: list[dict], spec: ScreenSpec = LEGACY_PRESET) -> FixedGame | None:
    starts = dict(spec.starting_colors)
    if spec.name == GOLAXY_3STAR_PRESET.name:
        eight_results = _valid_results(records, "rank_9d@8")
        if len(eight_results) < spec.valid_per_player:
            color = "B" if len(eight_results) % 2 == 0 else "W"
            return FixedGame("rank_9d@8", color)

        if all(record["outcome"] == "win" for record in eight_results):
            branch = ("rank_9d@4",)
            four_results = _valid_results(records, "rank_9d@4")
            if len(four_results) == spec.valid_per_player and all(
                record["outcome"] == "win" for record in four_results
            ):
                branch += ("rank_9d@2",)
        else:
            branch = ("rank_9d@16", "rank_9d@32", "rank_9d@64")

        for player in branch:
            completed = len(_valid_results(records, player))
            if completed < spec.valid_per_player:
                color = starts[player] if completed % 2 == 0 else "W"
                return FixedGame(player, color)
        return None

    for player in spec.players:
        completed = len(_valid_results(records, player))
        if completed < spec.valid_per_player:
            start = starts[player]
            color = start if completed % 2 == 0 else ("W" if start == "B" else "B")
            return FixedGame(player, color)
    return None


def _append(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


class FixedLedger:
    def __init__(self, directory: Path, quota_id: str, source_revision: str, spec: ScreenSpec = LEGACY_PRESET):
        self.directory = Path(directory)
        self.path = self.directory / LEDGER_NAME
        self.quota_id = quota_id
        self.source_revision = source_revision
        self.spec = spec

    def _header(self) -> dict:
        header = {
            "type": "header",
            "quota_id": self.quota_id,
            "source_revision": self.source_revision,
            "players": list(self.spec.players),
            "charged_cap": self.spec.charged_cap,
        }
        if not self.spec.legacy_header:
            header.update(
                {
                    "preset": self.spec.name,
                    "golaxy": {
                        "rung": self.spec.golaxy_rung,
                        "level_name": self.spec.golaxy_level_name,
                        "api_level": self.spec.golaxy_api_level,
                    },
                }
            )
        return header

    @classmethod
    def create(
        cls, directory: Path, quota_id: str, source_revision: str, spec: ScreenSpec = LEGACY_PRESET
    ) -> "FixedLedger":
        ledger = cls(directory, quota_id, source_revision, spec)
        if ledger.path.exists():
            raise ValueError("fixed-screen ledger already exists")
        _append(ledger.path, ledger._header())
        return ledger

    @classmethod
    def open(
        cls, directory: Path, quota_id: str, source_revision: str, spec: ScreenSpec = LEGACY_PRESET
    ) -> "FixedLedger":
        ledger = cls(directory, quota_id, source_revision, spec)
        records = ledger.records()
        if not records:
            raise ValueError("fixed-screen ledger is absent")
        if records[0] != ledger._header():
            raise ValueError("fixed-screen ledger header mismatch")
        return ledger

    def records(self) -> list[dict]:
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines()]

    def reserve(self, game: FixedGame, fingerprint: str) -> FixedReservation:
        records = self.records()
        reservations = [record for record in records if record.get("type") == "reservation"]
        if len(reservations) >= self.spec.charged_cap:
            raise ValueError(f"quota already has {self.spec.charged_cap} charged reservations")
        reservation = FixedReservation(len(reservations) + 1, game.player, game.color, fingerprint)
        _append(
            self.path,
            {
                "type": "reservation",
                "attempt_id": reservation.attempt_id,
                "player": reservation.player,
                "color": reservation.color,
                "fingerprint": reservation.fingerprint,
                "quota_id": self.quota_id,
                "source_revision": self.source_revision,
            },
        )
        return reservation

    def append_result(self, reservation: FixedReservation, outcome: str, fingerprint: str) -> None:
        if outcome not in ("win", "loss", "inconclusive"):
            raise ValueError("invalid fixed-screen outcome")
        records = self.records()
        stored = next(
            (
                record
                for record in records
                if record.get("type") == "reservation" and record.get("attempt_id") == reservation.attempt_id
            ),
            None,
        )
        if stored is None:
            raise ValueError("result reservation is absent")
        if any(
            record.get("type") == "result" and record.get("attempt_id") == reservation.attempt_id for record in records
        ):
            raise ValueError("duplicate result")
        if (
            stored.get("player") != reservation.player
            or stored.get("color") != reservation.color
            or stored.get("fingerprint") != fingerprint
            or reservation.fingerprint != fingerprint
        ):
            raise ValueError("result reservation mismatch")
        _append(
            self.path,
            {
                "type": "result",
                "attempt_id": reservation.attempt_id,
                "player": reservation.player,
                "color": reservation.color,
                "outcome": outcome,
                "fingerprint": fingerprint,
                "quota_id": self.quota_id,
                "source_revision": self.source_revision,
            },
        )


def summarize(ledger: FixedLedger) -> dict:
    records = ledger.records()
    reservations = [record for record in records if record.get("type") == "reservation"]
    results = [record for record in records if record.get("type") == "result"]
    players = {}
    for player in ledger.spec.players:
        outcomes = [record["outcome"] for record in results if record.get("player") == player]
        players[player] = {
            "wins": outcomes.count("win"),
            "losses": outcomes.count("loss"),
            "inconclusive": outcomes.count("inconclusive"),
            "valid": outcomes.count("win") + outcomes.count("loss"),
        }
    game = next_game(records, ledger.spec)
    return {
        "quota_id": ledger.quota_id,
        "charged_attempts": len(reservations),
        "results": len(results),
        "players": players,
        "next_game": None if game is None else {"player": game.player, "color": game.color},
    }


def classify_outcome(outcome: GameOutcome) -> str:
    if outcome.conclusive:
        return "win" if outcome.our_win else "loss"
    if outcome.result in {"inconclusive_score", "inconclusive_unsettled", "inconclusive_unstable"}:
        return "inconclusive"
    raise ValueError(f"unexpected fixed-screen outcome: {outcome.result}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", choices=tuple(PRESETS), default=LEGACY_PRESET.name)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--confirm-new-quota", action="store_true")
    parser.add_argument("--quota-id")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--expected-source-revision", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--smoke-report")
    parser.add_argument("--token-env")
    return parser


def validate_args(args: argparse.Namespace) -> None:
    alignment.validate_base_url(args.base_url)
    if args.preflight_only:
        if args.quota_id or args.confirm_new_quota or args.token_env:
            raise ValueError("preflight-only rejects quota and token arguments")
    elif not args.quota_id:
        raise ValueError("live fixed-screen mode requires --quota-id")


def resolve_preset(name: str) -> ScreenSpec:
    try:
        return PRESETS[name]
    except KeyError as exc:
        raise ValueError(f"unknown fixed-screen preset: {name!r}") from exc


def validate_output_path(value: str, spec: ScreenSpec = LEGACY_PRESET) -> Path:
    supplied = Path(value)
    lexical = (Path.cwd() / supplied).absolute() if not supplied.is_absolute() else supplied.absolute()
    resolved = supplied.resolve(strict=False)
    if lexical != spec.expected_out_dir or resolved != spec.expected_out_dir:
        raise ValueError(f"output must be exactly {spec.expected_out_dir}")
    return spec.expected_out_dir


def fixed_opponent(spec: ScreenSpec):
    opponent = get_rung(spec.golaxy_rung)
    actual = (opponent.golaxy_level_name, opponent.golaxy_api_level)
    expected = (spec.golaxy_level_name, spec.golaxy_api_level)
    if actual != expected:
        raise ValueError(f"Golaxy opponent descriptor drift: expected {expected}, got {actual}")
    return opponent


async def _preflight(
    client, args: argparse.Namespace, source: dict, game: FixedGame, spec: ScreenSpec = LEGACY_PRESET
) -> dict:
    smoke = Path(args.smoke_report).resolve() if args.smoke_report else alignment.DEFAULT_SMOKE_REPORT
    action = alignment.golaxy_9d_alignment.Batch(game.player, spec.valid_per_player)
    return await alignment.common_preflight(
        client=client,
        base_url=args.base_url,
        action=action,
        source_attestation=source,
        smoke_report=smoke,
        player_factory=lambda player: make_fixed_player(player, spec),
        opponent=fixed_opponent(spec),
    )


def _persisted_fingerprint(records: list[dict], player: str) -> str | None:
    values = {
        record["fingerprint"]
        for record in records
        if record.get("player") == player and record.get("type") in {"reservation", "result"}
    }
    if len(values) > 1:
        raise ValueError(f"fingerprint drift in persisted fixed-screen records for {player}")
    return next(iter(values), None)


async def _run_async(args: argparse.Namespace) -> dict:
    validate_args(args)
    spec = resolve_preset(args.preset)
    source = alignment.validate_source_revision(args.expected_source_revision)
    out = validate_output_path(args.out, spec)
    first = next_game([], spec)
    if first is None:
        raise ValueError("fixed-screen preset has no scheduled game")
    async with httpx.AsyncClient(follow_redirects=False, trust_env=False) as local_client:
        first_preflight = await _preflight(local_client, args, source, first, spec)
        if args.preflight_only:
            return {
                "mode": "preflight",
                "configuration_fingerprint": first_preflight["fingerprint"],
                "next_game": {"player": first.player, "color": first.color},
            }
        token = alignment.load_token(args.token_env)
        ledger_path = out / LEDGER_NAME
        with alignment.golaxy_9d_alignment.experiment_session(out, args.expected_source_revision):
            if ledger_path.exists():
                if args.confirm_new_quota:
                    raise ValueError("existing fixed-screen quota may not be recreated")
                ledger = FixedLedger.open(out, args.quota_id, args.expected_source_revision, spec)
            else:
                if not args.confirm_new_quota:
                    raise ValueError("new fixed-screen quota requires --confirm-new-quota")
                ledger = FixedLedger.create(out, args.quota_id, args.expected_source_revision, spec)
            preflights = {first.player: first_preflight}
            async with httpx.AsyncClient(follow_redirects=False, trust_env=False) as golaxy_client:
                while True:
                    records = ledger.records()
                    game = next_game(records, spec)
                    if game is None:
                        return summarize(ledger)
                    if game.player not in preflights:
                        preflights[game.player] = await _preflight(local_client, args, source, game, spec)
                    preflight = preflights[game.player]
                    persisted = _persisted_fingerprint(records, game.player)
                    if persisted is not None and persisted != preflight["fingerprint"]:
                        raise ValueError(f"fixed-screen fingerprint drift for {game.player}")
                    reservation = ledger.reserve(game, preflight["fingerprint"])
                    outcome = await alignment.play_alignment_game(
                        local_client=local_client,
                        golaxy_client=golaxy_client,
                        base_url=args.base_url,
                        token=token,
                        reservation=reservation,
                        preflight=preflight,
                        opponent=fixed_opponent(spec),
                    )
                    ledger.append_result(reservation, classify_outcome(outcome), preflight["fingerprint"])


def main(argv=None) -> int:
    try:
        result = asyncio.run(_run_async(build_parser().parse_args(argv)))
    except Exception as exc:
        print(f"fixed-screen runner stopped: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
