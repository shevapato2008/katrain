#!/usr/bin/env python3
"""One-off fixed screening: rank_9d@5 and rank_9d@6 versus Golaxy 9D."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import httpx
import run_golaxy_9d_alignment as alignment
import run_selfplay
from katrain.core.ladder import rung_strength_spec
from katrain.core.ladder_calibration import GameOutcome

PLAYERS = ("rank_9d@5", "rank_9d@6")
CHARGED_CAP = 20
LEDGER_NAME = "fixed_screen.jsonl"
EXPECTED_OUT_DIR = (Path(__file__).resolve().parent / "results" / "golaxy_9d_fixed_5_6_20260724").resolve()


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


def make_fixed_player(player: str):
    if player not in PLAYERS:
        raise ValueError(f"fixed-screen player must be one of {PLAYERS}")
    label, rung, selection = run_selfplay.make_player(player, experimental_min_humansl_search_visits=2)
    expected = alignment._expected_strength_spec(player)
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


def next_game(records: list[dict]) -> FixedGame | None:
    starts = {"rank_9d@5": "B", "rank_9d@6": "W"}
    for player in PLAYERS:
        completed = len(_valid_results(records, player))
        if completed < 5:
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
    def __init__(self, directory: Path, quota_id: str, source_revision: str):
        self.directory = Path(directory)
        self.path = self.directory / LEDGER_NAME
        self.quota_id = quota_id
        self.source_revision = source_revision

    @classmethod
    def create(cls, directory: Path, quota_id: str, source_revision: str) -> "FixedLedger":
        ledger = cls(directory, quota_id, source_revision)
        if ledger.path.exists():
            raise ValueError("fixed-screen ledger already exists")
        _append(
            ledger.path,
            {
                "type": "header",
                "quota_id": quota_id,
                "source_revision": source_revision,
                "players": list(PLAYERS),
                "charged_cap": CHARGED_CAP,
            },
        )
        return ledger

    @classmethod
    def open(cls, directory: Path, quota_id: str, source_revision: str) -> "FixedLedger":
        ledger = cls(directory, quota_id, source_revision)
        records = ledger.records()
        if not records:
            raise ValueError("fixed-screen ledger is absent")
        expected = {
            "type": "header",
            "quota_id": quota_id,
            "source_revision": source_revision,
            "players": list(PLAYERS),
            "charged_cap": CHARGED_CAP,
        }
        if records[0] != expected:
            raise ValueError("fixed-screen ledger header mismatch")
        return ledger

    def records(self) -> list[dict]:
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines()]

    def reserve(self, game: FixedGame, fingerprint: str) -> FixedReservation:
        records = self.records()
        reservations = [record for record in records if record.get("type") == "reservation"]
        if len(reservations) >= CHARGED_CAP:
            raise ValueError("quota already has 20 charged reservations")
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
    for player in PLAYERS:
        outcomes = [record["outcome"] for record in results if record.get("player") == player]
        players[player] = {
            "wins": outcomes.count("win"),
            "losses": outcomes.count("loss"),
            "inconclusive": outcomes.count("inconclusive"),
            "valid": outcomes.count("win") + outcomes.count("loss"),
        }
    game = next_game(records)
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


def validate_output_path(value: str) -> Path:
    supplied = Path(value)
    lexical = (Path.cwd() / supplied).absolute() if not supplied.is_absolute() else supplied.absolute()
    resolved = supplied.resolve(strict=False)
    if lexical != EXPECTED_OUT_DIR or resolved != EXPECTED_OUT_DIR:
        raise ValueError(f"output must be exactly {EXPECTED_OUT_DIR}")
    return EXPECTED_OUT_DIR


async def _preflight(client, args: argparse.Namespace, source: dict, game: FixedGame) -> dict:
    smoke = Path(args.smoke_report).resolve() if args.smoke_report else alignment.DEFAULT_SMOKE_REPORT
    action = alignment.golaxy_9d_alignment.Batch(game.player, 5)
    return await alignment.common_preflight(
        client=client,
        base_url=args.base_url,
        action=action,
        source_attestation=source,
        smoke_report=smoke,
        player_factory=make_fixed_player,
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
    source = alignment.validate_source_revision(args.expected_source_revision)
    out = validate_output_path(args.out)
    first = FixedGame("rank_9d@5", "B")
    async with httpx.AsyncClient(follow_redirects=False, trust_env=False) as local_client:
        first_preflight = await _preflight(local_client, args, source, first)
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
                ledger = FixedLedger.open(out, args.quota_id, args.expected_source_revision)
            else:
                if not args.confirm_new_quota:
                    raise ValueError("new fixed-screen quota requires --confirm-new-quota")
                ledger = FixedLedger.create(out, args.quota_id, args.expected_source_revision)
            preflights = {"rank_9d@5": first_preflight}
            async with httpx.AsyncClient(follow_redirects=False, trust_env=False) as golaxy_client:
                while True:
                    records = ledger.records()
                    game = next_game(records)
                    if game is None:
                        return summarize(ledger)
                    if game.player not in preflights:
                        preflights[game.player] = await _preflight(local_client, args, source, game)
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
