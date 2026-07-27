#!/usr/bin/env python3
"""Strict-serial HumanSL alignment against Golaxy 5D through 9D."""

import argparse
import asyncio
import dataclasses
import json
import os
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace

import httpx
import golaxy_9d_alignment as alignment_protocol
import run_golaxy_9d_alignment as alignment
import run_selfplay
from katrain.core.ladder import get_rung

GRID = ("1s", "4", "8", "16", "32", "64")
RESULTS = Path(__file__).resolve().parent / "results"
LEVELS = {
    5: (25, 2100, "5段"),
    6: (27, 2300, "6段"),
    7: (29, 2500, "7段"),
    8: (31, 2800, "8段"),
    9: (33, 3000, "9段"),
}
PROTOCOL = "golaxy-humansl-rank5-9-log-grid-v1"
REFINEMENT_PROTOCOL = "golaxy-humansl-rank7-rank9-refinement-v1"
REFINEMENT_TARGETS = ((7, "1s", "B"), (9, "6", "W"))


@dataclass(frozen=True)
class Action:
    player: str
    stage: str


@dataclass(frozen=True)
class Decision:
    player: str
    valid: int
    wins: int
    losses: int


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


read_jsonl = _jsonl


def _append(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def seed_results() -> list[dict]:
    seeded = []
    for rank in (7, 8):
        path = RESULTS / f"golaxy_{rank}d_rank_{rank}d_4_20260724/fixed_screen.jsonl"
        for row in _jsonl(path):
            if row.get("type") == "result" and row.get("outcome") in {"win", "loss"}:
                seeded.append(
                    {
                        "type": "carry_result",
                        "rank": rank,
                        "tier": "4",
                        "color": row["color"],
                        "outcome": row["outcome"],
                        "source": str(path.relative_to(RESULTS.parent.parent.parent.parent.parent)),
                    }
                )

    path = RESULTS / "golaxy_9d_humansl_alignment/attempts.jsonl"
    for row in _jsonl(path):
        candidate = row.get("candidate")
        outcome = row.get("outcome")
        if candidate not in {"rank_9d@4", "rank_9d@8"} or outcome not in {"win", "loss"}:
            continue
        seeded.append(
            {
                "type": "carry_result",
                "rank": 9,
                "tier": candidate.rsplit("@", 1)[1],
                "color": row["scheduled_color"],
                "outcome": outcome,
                "source": str(path.relative_to(RESULTS.parent.parent.parent.parent.parent)),
            }
        )
    return seeded


def refinement_seed_results() -> list[dict]:
    seeded = []
    alignment_path = RESULTS / "golaxy_humansl_rank5_9_alignment_20260727/alignment_v1.jsonl"
    for row in _jsonl(alignment_path):
        if (
            row.get("type") == "result"
            and row.get("rank") == 7
            and row.get("tier") == "1s"
            and row.get("outcome") in {"win", "loss"}
        ):
            seeded.append(
                {
                    "type": "carry_result",
                    "rank": 7,
                    "tier": "1s",
                    "color": row["color"],
                    "outcome": row["outcome"],
                    "source": str(alignment_path.relative_to(RESULTS.parent.parent.parent.parent.parent)),
                }
            )

    fixed_path = RESULTS / "golaxy_9d_fixed_5_6_20260724/fixed_screen.jsonl"
    for row in _jsonl(fixed_path):
        if row.get("type") == "result" and row.get("player") == "rank_9d@6" and row.get("outcome") in {"win", "loss"}:
            seeded.append(
                {
                    "type": "carry_result",
                    "rank": 9,
                    "tier": "6",
                    "color": row["color"],
                    "outcome": row["outcome"],
                    "source": str(fixed_path.relative_to(RESULTS.parent.parent.parent.parent.parent)),
                }
            )
    return seeded


def _refinement_outcomes(records: list[dict], rank: int, tier: str) -> list[str]:
    return [
        row["outcome"]
        for row in records
        if row.get("type") in {"carry_result", "result"}
        and row.get("rank") == rank
        and row.get("tier") == tier
        and row.get("outcome") in {"win", "loss"}
    ]


def next_refinement_action(records: list[dict]) -> Action | None:
    for rank, tier, _starting_color in REFINEMENT_TARGETS:
        if len(_refinement_outcomes(records, rank, tier)) < 10:
            return Action(f"rank_{rank}d@{tier}", "confirm")
    return None


def next_refinement_color(records: list[dict], rank: int, tier: str) -> str:
    starting_color = next(
        start for target_rank, target_tier, start in REFINEMENT_TARGETS if (target_rank, target_tier) == (rank, tier)
    )
    completed = len(_refinement_outcomes(records, rank, tier))
    if completed % 2 == 0:
        return starting_color
    return "W" if starting_color == "B" else "B"


def initialize_refinement(path: Path) -> None:
    if path.exists():
        records = read_jsonl(path)
        if not records or records[0].get("protocol") != REFINEMENT_PROTOCOL:
            raise RuntimeError("existing refinement ledger has an unexpected header")
        if any(row.get("type") == "stopped" for row in records):
            raise RuntimeError("refinement ledger already stopped; a remote error must not be retried automatically")
        reservations = sum(row.get("type") == "reservation" for row in records)
        results = sum(row.get("type") == "result" for row in records)
        if reservations != results:
            raise RuntimeError("refinement ledger has an unmatched reservation; automatic resume is forbidden")
        return
    _append(
        path,
        {
            "type": "header",
            "ts": time.time(),
            "protocol": REFINEMENT_PROTOCOL,
            "targets": [f"rank_{rank}d@{tier}" for rank, tier, _ in REFINEMENT_TARGETS],
            "target_valid_each": 10,
            "intergame_cooldown_seconds": 5,
            "execution": "strictly_serial_no_retry_stop_on_any_remote_error",
        },
    )
    for record in refinement_seed_results():
        _append(path, record)


def initialize(path: Path) -> None:
    if path.exists():
        records = read_jsonl(path)
        if not records or records[0].get("protocol") != PROTOCOL:
            raise RuntimeError("existing HumanSL rank alignment ledger has an unexpected header")
        if any(row.get("type") == "stopped" for row in records):
            raise RuntimeError("ledger already stopped; a remote error must not be retried automatically")
        reservations = sum(row.get("type") == "reservation" for row in records)
        results = sum(row.get("type") == "result" for row in records)
        if reservations != results:
            raise RuntimeError("ledger has an unmatched reservation; automatic resume is forbidden")
        return
    _append(
        path,
        {
            "type": "header",
            "ts": time.time(),
            "protocol": PROTOCOL,
            "grid": list(GRID),
            "screen_valid": 4,
            "screen_strong_wins": 3,
            "selected_total_valid": 10,
            "intergame_cooldown_seconds": 5,
            "execution": "strictly_serial_no_retry_stop_on_any_remote_error",
            "levels": [
                {"rank": rank, "rung": rung, "api_level": api, "name": name}
                for rank, (rung, api, name) in LEVELS.items()
            ],
        },
    )
    for record in seed_results():
        _append(path, record)


def opponent(rank: int):
    rung_number, api_level, name = LEVELS[rank]
    if rank == 5:
        return replace(
            get_rung(26), rung=rung_number, golaxy_level_name=name, golaxy_api_level=api_level, display_elo=api_level
        )
    resolved = get_rung(rung_number)
    if (resolved.golaxy_level_name, resolved.golaxy_api_level) != (name, api_level):
        raise RuntimeError(f"Golaxy {rank}D opponent descriptor drift")
    return resolved


def make_player(rank: int, tier: str):
    player = f"rank_{rank}d@{tier}"
    return run_selfplay.make_player(player, experimental_min_humansl_search_visits=2)


def next_color(records: list[dict], rank: int, tier: str) -> str:
    valid = sum(
        row.get("type") in {"carry_result", "result"}
        and row.get("rank") == rank
        and row.get("tier") == tier
        and row.get("outcome") in {"win", "loss"}
        for row in records
    )
    return "B" if valid % 2 == 0 else "W"


def next_action(records: list[dict], rank: int) -> Action | Decision:
    def outcomes(tier: str) -> list[str]:
        return [
            row["outcome"]
            for row in records
            if row.get("type") in {"carry_result", "result"}
            and row.get("rank") == rank
            and row.get("tier") == tier
            and row.get("outcome") in {"win", "loss"}
        ]

    def strength(tier: str) -> bool | None:
        sample = outcomes(tier)
        if len(sample) < 4:
            return None
        return sample[:4].count("win") >= 3

    strong = [index for index, tier in enumerate(GRID) if strength(tier) is True]
    if strong:
        candidate_index = min(strong)
        if candidate_index and strength(GRID[candidate_index - 1]) is None:
            lower = GRID[candidate_index - 1]
            return Action(f"rank_{rank}d@{lower}", "screen")
        candidate = GRID[candidate_index]
        sample = outcomes(candidate)
        if len(sample) < 10:
            return Action(f"rank_{rank}d@{candidate}", "confirm")
        wins = sample.count("win")
        return Decision(f"rank_{rank}d@{candidate}", len(sample), wins, len(sample) - wins)

    # Match the prior log-grid search: start at @8, then walk upward until
    # the first strong bound is observed. Partial screens always resume first.
    for tier in GRID:
        sample = outcomes(tier)
        if sample and len(sample) < 4:
            return Action(f"rank_{rank}d@{tier}", "screen")
    for tier in ("8", "16", "32", "64"):
        if strength(tier) is None:
            return Action(f"rank_{rank}d@{tier}", "screen")
    raise RuntimeError(f"rank_{rank}d exhausted the HumanSL grid without a strong candidate")


def _tier(player: str) -> str:
    return player.rsplit("@", 1)[1]


async def preflight(local_client, rank: int, tier: str) -> dict:
    player = f"rank_{rank}d@{tier}"
    check = await alignment.common_preflight(
        client=local_client,
        base_url=alignment_protocol.LOCAL_BASE_URL,
        action=alignment_protocol.Batch(player, 10),
        source_attestation={"protocol": PROTOCOL},
        smoke_report=alignment.DEFAULT_SMOKE_REPORT,
        player_factory=lambda _player: make_player(rank, tier),
        opponent=opponent(rank),
    )
    candidate = check["payload"]["candidate"]
    if tier == "1s":
        if candidate["selection"] != "argmax_human" or candidate["requested_main_model"] is not None:
            raise RuntimeError("@1s preflight did not attest native HumanSL argmax")
    elif (
        candidate["selection"] != "search"
        or candidate["requested_main_model"] != "b18"
        or candidate["requested_human_model"] != "humanv0"
    ):
        raise RuntimeError("HumanSL search preflight did not attest b18 + humanv0")
    return check


def summarize(records: list[dict]) -> dict:
    levels = {}
    for rank in LEVELS:
        decision = next(
            (row for row in records if row.get("type") == "level_decision" and row.get("rank") == rank), None
        )
        if decision is not None:
            levels[str(rank)] = {
                "player": decision["player"],
                "valid": decision["valid"],
                "wins": decision["wins"],
                "losses": decision["losses"],
            }
            continue
        action = next_action(records, rank)
        levels[str(rank)] = {"next": dataclasses.asdict(action), "type": type(action).__name__}
    return {
        "protocol": PROTOCOL,
        "new_reservations": sum(row.get("type") == "reservation" for row in records),
        "new_results": sum(row.get("type") == "result" for row in records),
        "stopped": sum(row.get("type") == "stopped" for row in records),
        "levels": levels,
    }


async def run_live(path: Path) -> dict:
    initialize(path)
    access_token = alignment.load_token(None)
    async with httpx.AsyncClient(follow_redirects=False, trust_env=False) as local_client:
        async with httpx.AsyncClient(follow_redirects=False, trust_env=False) as golaxy_client:
            checks = {}
            # Finish the nearly-complete inherited levels first, then fill the two absent levels.
            for rank in (9, 8, 7, 6, 5):
                while True:
                    records = read_jsonl(path)
                    action = next_action(records, rank)
                    if isinstance(action, Decision):
                        if not any(row.get("type") == "level_decision" and row.get("rank") == rank for row in records):
                            _append(
                                path,
                                {
                                    "type": "level_decision",
                                    "ts": time.time(),
                                    "rank": rank,
                                    **dataclasses.asdict(action),
                                },
                            )
                        print(
                            json.dumps(
                                {"event": "level_complete", "rank": rank, **dataclasses.asdict(action)},
                                ensure_ascii=False,
                            ),
                            flush=True,
                        )
                        break

                    tier = _tier(action.player)
                    key = (rank, tier)
                    if key not in checks:
                        checks[key] = await preflight(local_client, rank, tier)
                    color = next_color(records, rank, tier)
                    attempt = 1 + sum(row.get("type") == "reservation" for row in records)
                    reservation = {
                        "type": "reservation",
                        "ts": time.time(),
                        "attempt": attempt,
                        "rank": rank,
                        "tier": tier,
                        "player": action.player,
                        "stage": action.stage,
                        "color": color,
                        "api_level": LEVELS[rank][1],
                        "fingerprint": checks[key]["fingerprint"],
                    }
                    _append(path, reservation)
                    print(
                        json.dumps(
                            {"event": "game_start", "rank": rank, "player": action.player, "color": color},
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )
                    started = time.monotonic()
                    try:
                        outcome = await alignment.play_alignment_game(
                            local_client=local_client,
                            golaxy_client=golaxy_client,
                            base_url=alignment_protocol.LOCAL_BASE_URL,
                            token=access_token,
                            reservation=SimpleNamespace(scheduled_color=color),
                            preflight=checks[key],
                            opponent=opponent(rank),
                        )
                    except BaseException as exc:
                        _append(
                            path,
                            {
                                "type": "stopped",
                                "ts": time.time(),
                                "attempt": attempt,
                                "rank": rank,
                                "tier": tier,
                                "player": action.player,
                                "color": color,
                                "error_type": type(exc).__name__,
                                "error": str(exc),
                            },
                        )
                        print(json.dumps({"event": "stopped", "error": str(exc)}, ensure_ascii=False), flush=True)
                        raise
                    result = (
                        "win"
                        if outcome.conclusive and outcome.our_win
                        else "loss" if outcome.conclusive else "inconclusive"
                    )
                    _append(
                        path,
                        {
                            "type": "result",
                            "ts": time.time(),
                            "attempt": attempt,
                            "rank": rank,
                            "tier": tier,
                            "player": action.player,
                            "stage": action.stage,
                            "color": color,
                            "outcome": result,
                            "elapsed_seconds": time.monotonic() - started,
                            "game_outcome": dataclasses.asdict(outcome),
                        },
                    )
                    print(
                        json.dumps(
                            {"event": "game_result", "rank": rank, "player": action.player, "outcome": result},
                            ensure_ascii=False,
                        ),
                        flush=True,
                    )
                    await asyncio.sleep(5)
    return summarize(read_jsonl(path))


def summarize_refinement(records: list[dict]) -> dict:
    targets = {}
    for rank, tier, _starting_color in REFINEMENT_TARGETS:
        outcomes = _refinement_outcomes(records, rank, tier)
        targets[f"rank_{rank}d@{tier}"] = {
            "valid": len(outcomes),
            "wins": outcomes.count("win"),
            "losses": outcomes.count("loss"),
        }
    action = next_refinement_action(records)
    return {
        "protocol": REFINEMENT_PROTOCOL,
        "new_reservations": sum(row.get("type") == "reservation" for row in records),
        "new_results": sum(row.get("type") == "result" for row in records),
        "stopped": sum(row.get("type") == "stopped" for row in records),
        "targets": targets,
        "next": dataclasses.asdict(action) if action is not None else None,
    }


async def run_refinement_live(path: Path) -> dict:
    initialize_refinement(path)
    access_token = alignment.load_token(None)
    async with httpx.AsyncClient(follow_redirects=False, trust_env=False) as local_client:
        async with httpx.AsyncClient(follow_redirects=False, trust_env=False) as golaxy_client:
            checks = {}
            while True:
                records = read_jsonl(path)
                action = next_refinement_action(records)
                if action is None:
                    break
                rank = int(action.player.split("_", 1)[1].split("d", 1)[0])
                tier = _tier(action.player)
                key = (rank, tier)
                if key not in checks:
                    checks[key] = await preflight(local_client, rank, tier)
                color = next_refinement_color(records, rank, tier)
                attempt = 1 + sum(row.get("type") == "reservation" for row in records)
                reservation = {
                    "type": "reservation",
                    "ts": time.time(),
                    "attempt": attempt,
                    "rank": rank,
                    "tier": tier,
                    "player": action.player,
                    "stage": action.stage,
                    "color": color,
                    "api_level": LEVELS[rank][1],
                    "fingerprint": checks[key]["fingerprint"],
                }
                _append(path, reservation)
                print(
                    json.dumps(
                        {"event": "game_start", "rank": rank, "player": action.player, "color": color},
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                started = time.monotonic()
                try:
                    outcome = await alignment.play_alignment_game(
                        local_client=local_client,
                        golaxy_client=golaxy_client,
                        base_url=alignment_protocol.LOCAL_BASE_URL,
                        token=access_token,
                        reservation=SimpleNamespace(scheduled_color=color),
                        preflight=checks[key],
                        opponent=opponent(rank),
                    )
                except BaseException as exc:
                    _append(
                        path,
                        {
                            "type": "stopped",
                            "ts": time.time(),
                            "attempt": attempt,
                            "rank": rank,
                            "tier": tier,
                            "player": action.player,
                            "color": color,
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                        },
                    )
                    print(json.dumps({"event": "stopped", "error": str(exc)}, ensure_ascii=False), flush=True)
                    raise
                result = (
                    "win"
                    if outcome.conclusive and outcome.our_win
                    else "loss" if outcome.conclusive else "inconclusive"
                )
                _append(
                    path,
                    {
                        "type": "result",
                        "ts": time.time(),
                        "attempt": attempt,
                        "rank": rank,
                        "tier": tier,
                        "player": action.player,
                        "stage": action.stage,
                        "color": color,
                        "outcome": result,
                        "elapsed_seconds": time.monotonic() - started,
                        "game_outcome": dataclasses.asdict(outcome),
                    },
                )
                print(
                    json.dumps(
                        {"event": "game_result", "rank": rank, "player": action.player, "outcome": result},
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                await asyncio.sleep(5)
    return summarize_refinement(read_jsonl(path))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=RESULTS / "golaxy_humansl_rank5_9_alignment_20260727/alignment_v1.jsonl",
    )
    parser.add_argument("--summary", action="store_true")
    parser.add_argument(
        "--refinement-out",
        type=Path,
        help="run only the rank_7d@1s and rank_9d@6 ten-game refinements in this append-only ledger",
    )
    args = parser.parse_args(argv)
    try:
        if args.refinement_out is not None:
            initialize_refinement(args.refinement_out)
            result = (
                summarize_refinement(read_jsonl(args.refinement_out))
                if args.summary
                else asyncio.run(run_refinement_live(args.refinement_out))
            )
        else:
            initialize(args.out)
            result = summarize(read_jsonl(args.out)) if args.summary else asyncio.run(run_live(args.out))
    except Exception as exc:
        print(f"HumanSL rank alignment stopped: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
