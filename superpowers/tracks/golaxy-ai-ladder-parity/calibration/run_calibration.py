#!/usr/bin/env python3
"""Full empirical calibration CLI (Phase P3b, operator-run — NOT covered by CI; requires a
live Golaxy access token + a reachable KataGo HTTP analysis server).

For each `rung:games` anchor, plays `games` games (alternating our color so each anchor is
split as evenly as possible between B/W) of `our engine (via /analyze)` vs `Golaxy (via the
genmove tunnel)` using the SAME fail-closed loop as the unit-tested harness
(`katrain.core.ladder_calibration.play_one_game`), checkpoints every game to
`results/rung_<n>.jsonl` (so a crashed/interrupted run resumes instead of re-playing finished
games), and prints an Elo-with-CI summary per anchor plus the golaxy-terminal rate (the
fraction of games ended by an UNVERIFIED out-of-board Golaxy reply — see adapters.golaxy_move
docstring; this is the pre-smoke-code selection bias the operator must judge before trusting
the numbers, per Task 9 / plan.md Phase P3a note).

Usage:
    GOLAXY_TOKEN=<redacted> uv run python \\
        superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_calibration.py \\
        --anchors "26:20,30:20,36:10" --base-url http://127.0.0.1:8000 \\
        --token-env GOLAXY_TOKEN --out superpowers/tracks/golaxy-ai-ladder-parity/calibration/results

Never commit a live token: --token-env only names the env var to read (default GOLAXY_TOKEN);
nothing here ever writes the token to disk.
"""
from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import logging
import os
import sys
import time
from functools import partial
from pathlib import Path
from typing import List, Optional, Tuple

import httpx

# katrain.core.base_katrain pulls in Kivy, which parses sys.argv on import and would hijack
# this CLI's own --anchors/--out/etc flags; KIVY_NO_ARGS=1 disables that (same pattern as
# katrain/__main__.py and katrain/vision/tools/baipu_autolabel.py).
os.environ.setdefault("KIVY_NO_ARGS", "1")

sys.path.insert(0, str(Path(__file__).parent))  # allow `import adapters` when run as a script
import adapters  # noqa: E402

from katrain.core.base_katrain import KaTrainBase  # noqa: E402
from katrain.core.ladder import get_rung  # noqa: E402
from katrain.core.ladder_calibration import play_one_game, elo_from_winrate, GameOutcome  # noqa: E402
from katrain.web.platforms.golaxy.engine_client import AuthExpired  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("run_calibration")

# end_reasons that did NOT stop via a verified two-pass -- re-check score stability before
# trusting them as conclusive (G5). `our_pass` is included until a two-pass encoding is
# confirmed against the live server (see adjudicate's docstring / Task 9 smoke notes).
_NEEDS_STABILITY_RECHECK = {"move_cap", "golaxy_terminal", "our_pass"}
_STABILITY_VISITS_MULTIPLIER = 4
_STABILITY_MAX_VISITS = 800
_STABILITY_DELTA_TOLERANCE = 1.0


class _MockKaTrainForConfig(KaTrainBase):
    """Config-only KaTrainBase double: never touched by a GUI or a real engine, just used to
    read the SAME shipping `engine` config block that katrain/core/engine.py ships with."""


def parse_anchors(spec: str) -> List[Tuple[int, int]]:
    """'26:20,30:20,36:10' -> valid Golaxy-aligned anchors. Validates counterpart + games."""
    anchors = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        rung_s, _, games_s = part.partition(":")
        rung_n, games = int(rung_s), int(games_s)
        rung = get_rung(rung_n)  # raises ValueError if out of range 1..37
        if rung.golaxy_api_level is None:
            raise ValueError(f"anchor rung {rung_n} has no Golaxy counterpart")
        if games <= 0:
            raise ValueError(f"anchor {part!r}: games must be > 0")
        anchors.append((rung_n, games))
    if not anchors:
        raise ValueError(f"no anchors parsed from --anchors {spec!r}")
    return anchors


def load_token(token_env: str) -> str:
    """Read the Golaxy access token from the named env var, or a redacted local file
    (~/.katrain/golaxy_token.txt, never committed -- see .gitignore) as a fallback. Never
    hard-code a token here."""
    tok = os.environ.get(token_env)
    if tok:
        return tok.strip()
    fallback = Path.home() / ".katrain" / "golaxy_token.txt"
    if fallback.is_file():
        tok = fallback.read_text().strip()
        if tok:
            return tok
    raise SystemExit(
        f"No Golaxy token found: set ${token_env} or write one (single line) to {fallback}. "
        f"Never commit a token to the repo."
    )


def resolve_wide_root_noise(cli_value: Optional[float]) -> float:
    """wide_root_noise MUST come from the shipping engine config (the SAME value the runtime
    KataGoHttpEngine sends), never the adapters.our_move hard-coded default (G2). If the
    deployed :8000 server is known to run a DIFFERENT value than this checkout's
    katrain/config.json, pass --wide-root-noise explicitly to override -- and confirm that
    value against the live server's actual config, since a silent mismatch would calibrate
    against a different strength curve than production serves."""
    shipping = adapters.load_engine_wide_root_noise(
        dict(_MockKaTrainForConfig(force_package_config=True).config("engine"))
    )
    if cli_value is None:
        log.info("wide_root_noise = %.4f (from this checkout's katrain/config.json engine block)", shipping)
        return shipping
    if abs(cli_value - shipping) > 1e-9:
        log.warning(
            "wide_root_noise override %.4f differs from this checkout's shipping config (%.4f) -- "
            "make sure this matches the DEPLOYED :8000 server's actual config, not a stale local one",
            cli_value,
            shipping,
        )
    else:
        log.info("wide_root_noise = %.4f (matches this checkout's shipping config)", cli_value)
    return cli_value


def load_smoke_codes(smoke_report_path: Path) -> Tuple[Optional[int], Optional[int], dict]:
    """Read pass_code/resign_code from Task 9's results/smoke_report.json. If the file is
    absent or the codes were never captured (both null), Golaxy resigns/passes cannot be
    verified: golaxy_move degrades every such reply to 'terminal', which the harness treats as
    inconclusive -- a directional bias that UNDER-counts our wins (a real resign/pass Golaxy
    reply is thrown away instead of counted). We log a prominent warning so the operator can
    judge whether the resulting golaxy-terminal rate (recorded per anchor below) is material
    before trusting the numbers."""
    if not smoke_report_path.is_file():
        log.warning(
            "=" * 78 + "\nNo smoke report at %s -- running WITHOUT verified Golaxy pass/resign codes.\n"
            "Every Golaxy pass/resign will be recorded as an UNVERIFIED 'terminal' "
            "(inconclusive_terminal), which UNDER-counts our wins. Run run_smoke.py (Task 9) "
            "and its manual browser sentinel capture first, or accept this known bias.\n" + "=" * 78,
            smoke_report_path,
        )
        return None, None, {}
    report = json.loads(smoke_report_path.read_text())
    pass_code, resign_code = report.get("pass_code"), report.get("resign_code")
    if pass_code is None and resign_code is None:
        log.warning(
            "=" * 78 + "\nsmoke_report.json found but pass_code/resign_code are both null (Step 5b manual "
            "capture not done yet) -- running WITHOUT verified Golaxy pass/resign codes; see "
            "above bias note.\n" + "=" * 78
        )
    return pass_code, resign_code, report


def _checkpoint_path(out_dir: Path, rung_n: int) -> Path:
    return out_dir / f"rung_{rung_n}.jsonl"


def _already_done(path: Path) -> int:
    """Resume support: count completed games already checkpointed for this anchor. Anchors
    replay the SAME deterministic our_color sequence (alternating by index) on every run, so
    skipping the first N games reproduces the same half/half split."""
    if not path.is_file():
        return 0
    with path.open() as f:
        return sum(1 for line in f if line.strip())


async def _golaxy_move_with_reauth(
    history,
    *,
    gx_client: httpx.AsyncClient,
    rung,
    pass_code: Optional[int],
    resign_code: Optional[int],
    token_holder: dict,
    token_env: str,
    throttle: float,
):
    """Call `adapters.golaxy_move` with the CURRENT token in `token_holder` (shared across an
    anchor's games), retrying ONCE on AuthExpired after re-reading the token env var -- e.g.
    an operator who noticed the failure and exported a freshly-captured token while the run
    was paused. No programmatic Golaxy login exists here (the real login is an SMS-OTP
    browser flow); this is a manual-refresh retry, not an automatic one. On success after
    retry, `token_holder` is updated so later games in this anchor reuse the fresh token."""
    try:
        return await adapters.golaxy_move(
            gx_client, history, rung=rung, token=token_holder["token"], pass_code=pass_code, resign_code=resign_code
        )
    except AuthExpired:
        log.warning(
            "Golaxy token expired/invalid (AuthExpired). Re-reading $%s and retrying ONCE in %.1fs -- "
            "if it is still stale, export a freshly captured token now.",
            token_env,
            throttle,
        )
        await asyncio.sleep(throttle)
        token_holder["token"] = load_token(token_env)
        return await adapters.golaxy_move(
            gx_client, history, rung=rung, token=token_holder["token"], pass_code=pass_code, resign_code=resign_code
        )


async def _stability_recheck(
    adjudicate_partial, history: List[int], prior_score: Optional[float]
) -> Tuple[bool, Optional[float]]:
    """G5: re-run adjudicate at higher visits and require |delta scoreLead| < tolerance before
    trusting a non-two-pass conclusive game. Returns (stable, recheck_score)."""
    if prior_score is None:
        return False, None
    visits = min(
        _STABILITY_MAX_VISITS, int(adjudicate_partial.keywords.get("visits", 200)) * _STABILITY_VISITS_MULTIPLIER
    )
    recheck_score, recheck_settled = await adjudicate_partial(history, visits=visits)
    if recheck_score is None or not recheck_settled:
        return False, recheck_score
    return abs(recheck_score - prior_score) < _STABILITY_DELTA_TOLERANCE, recheck_score


async def run_anchor(
    rung_n: int,
    games: int,
    *,
    client: httpx.AsyncClient,
    gx_client: httpx.AsyncClient,
    base_url: str,
    token_env: str,
    token: str,
    wrn: float,
    pass_code: Optional[int],
    resign_code: Optional[int],
    throttle: float,
    out_dir: Path,
) -> dict:
    rung = get_rung(rung_n)
    token_holder = {"token": token}  # mutable so a mid-anchor re-auth persists across games
    ckpt_path = _checkpoint_path(out_dir, rung_n)
    out_dir.mkdir(parents=True, exist_ok=True)
    start_index = _already_done(ckpt_path)
    if start_index >= games:
        log.info("rung %d: already have %d/%d games checkpointed, skipping", rung_n, start_index, games)
    else:
        log.info("rung %d (%s): resuming at game %d/%d", rung_n, rung.golaxy_level_name, start_index, games)

    wins = 0
    conclusive = 0
    reason_counts: dict = {}
    golaxy_terminal_count = 0

    # Tally prior checkpointed games into the running totals so the summary reflects the
    # FULL anchor, not just this process's newly-played games.
    if ckpt_path.is_file():
        with ckpt_path.open() as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                if rec["conclusive"]:
                    conclusive += 1
                    if rec["our_win"]:
                        wins += 1
                reason_counts[rec["result"]] = reason_counts.get(rec["result"], 0) + 1
                if rec["end_reason"] == "golaxy_terminal":
                    golaxy_terminal_count += 1

    with ckpt_path.open("a") as ckpt:
        for i in range(start_index, games):
            our_color = "B" if i % 2 == 0 else "W"
            history_holder: dict = {"history": None}

            async def our_move_fn(history, _holder=history_holder):
                _holder["history"] = history
                return await adapters.our_move(client, base_url, history, rung=rung, wide_root_noise=wrn)

            async def golaxy_move_fn(history, _holder=history_holder):
                _holder["history"] = history
                return await _golaxy_move_with_reauth(
                    history,
                    gx_client=gx_client,
                    rung=rung,
                    pass_code=pass_code,
                    resign_code=resign_code,
                    token_holder=token_holder,
                    token_env=token_env,
                    throttle=throttle,
                )

            adjudicate_partial = partial(adapters.adjudicate, client, base_url)

            outcome: GameOutcome = await play_one_game(
                our_move=our_move_fn, golaxy_move=golaxy_move_fn, adjudicate=adjudicate_partial, our_color=our_color
            )

            stability_checked = False
            stability_delta_ok = None
            if (
                outcome.conclusive
                and outcome.end_reason in _NEEDS_STABILITY_RECHECK
                and history_holder["history"] is not None
            ):
                stability_checked = True
                stable, recheck_score = await _stability_recheck(
                    adjudicate_partial, history_holder["history"], outcome.black_score
                )
                stability_delta_ok = stable
                if not stable:
                    outcome = dataclasses.replace(
                        outcome, result="inconclusive_unstable", our_win=False, conclusive=False
                    )

            if outcome.conclusive:
                conclusive += 1
                if outcome.our_win:
                    wins += 1
            reason_counts[outcome.result] = reason_counts.get(outcome.result, 0) + 1
            if outcome.end_reason == "golaxy_terminal":
                golaxy_terminal_count += 1

            record = {
                "index": i,
                "rung": rung_n,
                **dataclasses.asdict(outcome),
                "stability_checked": stability_checked,
                "stability_delta_ok": stability_delta_ok,
                "history": history_holder["history"],
                "ts": time.time(),
            }
            ckpt.write(json.dumps(record) + "\n")
            ckpt.flush()
            log.info(
                "rung %d game %d/%d: %s (end=%s, conclusive=%s)",
                rung_n,
                i + 1,
                games,
                outcome.result,
                outcome.end_reason,
                outcome.conclusive,
            )
            if throttle:
                await asyncio.sleep(throttle)

    total_games = start_index + max(0, games - start_index)
    elo, lo, hi = elo_from_winrate(wins, conclusive)
    golaxy_terminal_rate = golaxy_terminal_count / total_games if total_games else 0.0
    return {
        "rung": rung_n,
        "golaxy_level_name": rung.golaxy_level_name,
        "games_played": total_games,
        "conclusive": conclusive,
        "wins": wins,
        "elo_vs_opponent": elo,
        "elo_ci95": [lo, hi],
        "golaxy_terminal_rate": golaxy_terminal_rate,
        "reason_counts": reason_counts,
    }


async def main_async(args) -> int:
    anchors = parse_anchors(args.anchors)
    token = load_token(args.token_env)
    wrn = resolve_wide_root_noise(args.wide_root_noise)
    out_dir = Path(args.out)
    smoke_report_path = Path(args.smoke_report) if args.smoke_report else out_dir / "smoke_report.json"
    pass_code, resign_code, smoke_report = load_smoke_codes(smoke_report_path)

    summaries = []
    async with httpx.AsyncClient() as client, httpx.AsyncClient() as gx_client:
        for rung_n, games in anchors:
            summary = await run_anchor(
                rung_n,
                games,
                client=client,
                gx_client=gx_client,
                base_url=args.base_url,
                token_env=args.token_env,
                token=token,
                wrn=wrn,
                pass_code=pass_code,
                resign_code=resign_code,
                throttle=args.throttle,
                out_dir=out_dir,
            )
            summaries.append(summary)
            log.info("=== anchor summary: %s ===", json.dumps(summary, ensure_ascii=False))

    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps({"anchors": summaries, "wide_root_noise": wrn}, indent=2, ensure_ascii=False))
    log.info("wrote summary to %s", summary_path)
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--anchors", required=True, help="'rung:games,rung:games,...' e.g. '26:20,30:20,36:10'")
    p.add_argument("--throttle", type=float, default=2.0, help="seconds to sleep between games (rate-limit Golaxy)")
    p.add_argument("--base-url", default="http://127.0.0.1:8000", help="our KataGo HTTP analysis server base URL")
    p.add_argument("--token-env", default="GOLAXY_TOKEN", help="env var name holding the Golaxy access token")
    p.add_argument("--out", default=str(Path(__file__).parent / "results"), help="checkpoint/results directory")
    p.add_argument(
        "--wide-root-noise",
        type=float,
        default=None,
        help="override wideRootNoise; MUST match the deployed :8000 server's actual config (default: read from "
        "this checkout's katrain/config.json)",
    )
    p.add_argument("--smoke-report", default=None, help="path to smoke_report.json (default: <out>/smoke_report.json)")
    return p


def main() -> int:
    args = build_arg_parser().parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
