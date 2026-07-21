#!/usr/bin/env python3
"""Calibration smoke gate (Task 9): level re-verify + ~10-game smoke + timing.

Operator-run only (NOT covered by CI; requires a live Golaxy access token + a reachable
KataGo HTTP analysis server). See `calibration/README.md` for the full runbook, INCLUDING
the MANUAL browser pass/resign sentinel capture (README Step 5b).

**Why there is no API pass/resign probe:** you cannot elicit a Golaxy pass/resign via
genmove. The `moves` history this tunnel accepts holds ONLY board coords (see
`katrain.web.platforms.golaxy.engine_client.engine_genmove`) -- there is no "play until
Golaxy passes" API path, because the pass/resign wire *encoding* (which out-of-board int(s)
mean pass vs. resign) is exactly the unknown this smoke gate needs resolved. That can only be
observed by watching the real web client's own `/genmove` traffic in a browser (README Step
5b) -- so this script never attempts it, and always writes `pass_code`/`resign_code` as
`null` for the operator (or a later run of `run_calibration.py`, once the codes are captured)
to fill in.

Usage:
    GOLAXY_TOKEN=<redacted> uv run python \\
        superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_smoke.py \\
        --base-url http://localhost:8000 \\
        --out superpowers/tracks/golaxy-ai-ladder-parity/calibration/results

Writes `results/smoke_report.json`. Never commits a live token; only commit the report AFTER
confirming it holds no token material (it never does by construction -- see the schema below).
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
from typing import Dict, List, Optional

import httpx

# katrain.core.base_katrain pulls in Kivy, which parses sys.argv on import and would hijack
# this CLI's own --base-url/--out/etc flags; KIVY_NO_ARGS=1 disables that (same pattern as
# katrain/__main__.py, katrain/vision/tools/baipu_autolabel.py, and Task 8's run_calibration.py).
os.environ.setdefault("KIVY_NO_ARGS", "1")

sys.path.insert(0, str(Path(__file__).parent))  # allow `import adapters` when run as a script
import adapters  # noqa: E402
from adapters import _assert_real_wire_level  # noqa: E402

from katrain.core.base_katrain import KaTrainBase  # noqa: E402
from katrain.core.ladder import get_rung, LadderRung  # noqa: E402
from katrain.core.ladder_calibration import play_one_game  # noqa: E402
from katrain.web.platforms.golaxy.engine_client import engine_genmove, GolaxyEngineError  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("run_smoke")

# Level re-verify set spans every part of the Golaxy-aligned Band B: 准6段, 准7段, 准8段,
# 9段, and 星阵3星 (api 2200/2400/2600/3000/3300). Native HumanSL Band A and the
# api-less rung-37 ceiling are deliberately excluded: neither has a Golaxy wire counterpart.
LEVEL_PROBE_RUNGS = [26, 28, 30, 33, 36]

# ~10-game smoke: 2 anchors, rung 26 (准6段, api 2200 -- weakest/fastest valid opponent)
# + rung 30 (准8段, api 2600 -- mid-band), 5 games each by default. Deliberately NOT the
# strongest rungs (9段/星阵3星):
# those are already timing-probed above via `probe_level`, and a full ~10-game smoke at the
# super-pro ceiling would make the "quick smoke before committing hours to P3b" gate itself
# slow. `--games-per-anchor` can widen this if the operator wants more smoke coverage.
SMOKE_ANCHORS = [(26, 5), (30, 5)]


class _MockKaTrainForConfig(KaTrainBase):
    """Config-only KaTrainBase double (mirrors run_calibration.py's helper of the same name):
    never touched by a GUI or a real engine, just used to read the SAME shipping `engine`
    config block that katrain/core/engine.py ships with."""


async def probe_level(client: httpx.AsyncClient, rung: LadderRung, token: str) -> dict:
    """Time ONE genmove at `rung.golaxy_api_level` and return a plain record -- this function
    never raises. Asserts the level is a real `GOLAXY_AI_LEVELS` wire value (via
    `adapters._assert_real_wire_level`) BEFORE calling out, so a rung misconfigured with its
    `display_elo` (rather than `golaxy_api_level`) can never be sent/paid-for as a wire level --
    that is a structural bug, not a wire condition, so it is NOT caught here (mirrors
    `adapters.golaxy_move`, which has the identical guard and identical non-catching behavior).

    Catches the full `GolaxyEngineError` taxonomy (`Retryable`/`Fatal`/`QuotaExhausted`/
    `AuthExpired`) into `record["error"]` instead of raising: one bad/unavailable level must
    not abort the rest of the level-probe sweep, nor the ~10-game smoke that follows it.
    """
    level = rung.golaxy_api_level
    _assert_real_wire_level(level)  # display_elo structurally unreachable (same guard as golaxy_move)
    record: dict = {
        "level": level,
        "level_name": rung.golaxy_level_name,
        "coord": None,
        "ok": False,
        "elapsed_s": None,
        "error": None,
    }
    t0 = time.monotonic()
    try:
        result = await engine_genmove(client, moves=[], level=level, access_token=token)
        record["coord"] = result.coord
        record["ok"] = True
    except GolaxyEngineError as e:
        record["error"] = f"{type(e).__name__}: {e}"
    finally:
        record["elapsed_s"] = time.monotonic() - t0
    return record


async def run_level_probes(client: httpx.AsyncClient, token: str) -> List[dict]:
    """Probe every rung in `LEVEL_PROBE_RUNGS` in order, logging each result. Never raises --
    `probe_level` itself is fail-closed-into-the-record."""
    records = []
    for rung_n in LEVEL_PROBE_RUNGS:
        rung = get_rung(rung_n)
        rec = await probe_level(client, rung, token)
        status = "OK" if rec["ok"] else f"ERROR: {rec['error']}"
        log.info(
            "level probe rung %d (%s, api=%s): %s coord=%s elapsed=%.2fs",
            rung_n,
            rung.golaxy_level_name,
            rung.golaxy_api_level,
            status,
            rec["coord"],
            rec["elapsed_s"],
        )
        records.append(rec)
    return records


async def run_smoke_anchor(
    rung_n: int,
    games: int,
    *,
    client: httpx.AsyncClient,
    gx_client: httpx.AsyncClient,
    base_url: str,
    token: str,
    wrn: float,
    throttle: float,
    errors: List[str],
) -> dict:
    """Play `games` games at `rung_n` (alternating our color) using the SAME fail-closed
    `play_one_game` loop the full calibration harness (`run_calibration.py`) uses. Records a
    per-move `time.monotonic()` delta for BOTH sides (`golaxy_move_timing_s`/
    `our_move_timing_s`) -- this is what the README's timing go/no-go criterion reads,
    especially for how close a strong-level reply comes to the 180s HTTP ceiling
    (`engine_client.GENMOVE_TIMEOUT_SECONDS`).

    `pass_code`/`resign_code` are always `None` here: the manual browser sentinel capture
    (README Step 5b) has not happened yet at smoke time, so EVERY Golaxy stop is an unverified
    `"terminal"` (see `adapters.golaxy_move`) -- this is exactly what sizes the per-anchor
    golaxy-terminal rate this function reports (`golaxy_terminal_rate`), which the operator
    uses to judge whether the pre-code exclusion bias is material (README Step 5c / go-no-go
    criterion 5).

    A single game raising (a Golaxy wire error, a timeout, an adjudicate failure, ...) is
    logged into `errors` and skipped -- one bad game must never abort the whole smoke run.
    """
    rung = get_rung(rung_n)
    golaxy_move_s: List[float] = []
    our_move_s: List[float] = []
    game_records: List[dict] = []
    golaxy_terminal_count = 0
    completed = 0

    for i in range(games):
        our_color = "B" if i % 2 == 0 else "W"

        async def our_move_fn(history, _rung=rung):
            t0 = time.monotonic()
            try:
                return await adapters.our_move(client, base_url, history, rung=_rung, wide_root_noise=wrn)
            finally:
                our_move_s.append(time.monotonic() - t0)

        async def golaxy_move_fn(history, _rung=rung):
            t0 = time.monotonic()
            try:
                # pass_code/resign_code intentionally omitted (None): not captured pre-smoke.
                return await adapters.golaxy_move(gx_client, history, rung=_rung, token=token)
            finally:
                golaxy_move_s.append(time.monotonic() - t0)

        adjudicate_partial = partial(adapters.adjudicate, client, base_url)

        try:
            outcome = await play_one_game(
                our_move=our_move_fn, golaxy_move=golaxy_move_fn, adjudicate=adjudicate_partial, our_color=our_color
            )
        except Exception as e:  # noqa: BLE001 -- smoke must survive ANY single bad game (network, wire, timeout)
            msg = f"rung {rung_n} game {i}: {type(e).__name__}: {e}"
            log.warning(msg)
            errors.append(msg)
            game_records.append({"rung": rung_n, "index": i, "our_color": our_color, "error": msg, "aborted": True})
            if throttle:
                await asyncio.sleep(throttle)
            continue

        completed += 1
        if outcome.end_reason == "golaxy_terminal":
            golaxy_terminal_count += 1
        game_records.append({"rung": rung_n, "index": i, **dataclasses.asdict(outcome)})
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

    rate = golaxy_terminal_count / completed if completed else None
    return {
        "rung": rung_n,
        "golaxy_level_name": rung.golaxy_level_name,
        "games_played": completed,
        "golaxy_terminal_count": golaxy_terminal_count,
        "golaxy_terminal_rate": rate,
        "golaxy_move_timing_s": golaxy_move_s,
        "our_move_timing_s": our_move_s,
        "games": game_records,
    }


def load_token(token_env: str) -> str:
    """Read the Golaxy access token from the named env var, or a redacted local file
    (~/.katrain/golaxy_token.txt, never committed -- see .gitignore) as a fallback. Never
    hard-code a token here. (Mirrors run_calibration.py's helper of the same name.)"""
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
    KataGoHttpEngine sends), never `adapters.our_move`'s hard-coded default (G2). Mirrors
    run_calibration.py's helper of the same name -- if the deployed :8000 server is known to
    run a DIFFERENT value than this checkout's katrain/config.json, pass --wide-root-noise
    explicitly and confirm it against the live server's actual config."""
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


async def main_async(args) -> int:
    token = load_token(args.token_env)
    wrn = resolve_wide_root_noise(args.wide_root_noise)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    errors: List[str] = []
    per_move_timing: Dict[str, dict] = {}
    per_anchor_rate: Dict[str, Optional[float]] = {}
    all_games: List[dict] = []

    async with httpx.AsyncClient() as client, httpx.AsyncClient() as gx_client:
        log.info("=== level probes: rungs %s ===", LEVEL_PROBE_RUNGS)
        level_probes = await run_level_probes(gx_client, token)

        for rung_n, default_games in SMOKE_ANCHORS:
            n_games = args.games_per_anchor if args.games_per_anchor else default_games
            log.info("=== smoke anchor rung %d: %d games ===", rung_n, n_games)
            anchor = await run_smoke_anchor(
                rung_n,
                n_games,
                client=client,
                gx_client=gx_client,
                base_url=args.base_url,
                token=token,
                wrn=wrn,
                throttle=args.throttle,
                errors=errors,
            )
            per_move_timing[str(rung_n)] = {
                "golaxy_move_s": anchor["golaxy_move_timing_s"],
                "our_move_s": anchor["our_move_timing_s"],
            }
            per_anchor_rate[str(rung_n)] = anchor["golaxy_terminal_rate"]
            all_games.extend(anchor["games"])
            log.info(
                "=== anchor rung %d (%s) done: %d/%d games, golaxy_terminal_rate=%s ===",
                rung_n,
                anchor["golaxy_level_name"],
                anchor["games_played"],
                n_games,
                anchor["golaxy_terminal_rate"],
            )

    report = {
        "level_probes": level_probes,
        "games": all_games,
        "per_move_timing": per_move_timing,
        "per_anchor_golaxy_terminal_rate": per_anchor_rate,
        "errors": errors,
        # Filled in by the MANUAL browser sentinel capture -- see README.md Step 5b. No API
        # probe can populate these (see the module docstring): leave null until captured.
        "pass_code": None,
        "resign_code": None,
    }
    report_path = out_dir / "smoke_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    log.info(
        "wrote smoke report to %s -- pass_code/resign_code are null; fill them in via the "
        "MANUAL browser capture (README.md Step 5b) before running run_calibration.py",
        report_path,
    )
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base-url", default="http://127.0.0.1:8000", help="our KataGo HTTP analysis server base URL")
    p.add_argument("--token-env", default="GOLAXY_TOKEN", help="env var name holding the Golaxy access token")
    p.add_argument(
        "--out",
        default=str(Path(__file__).parent / "results"),
        help="directory to write smoke_report.json into",
    )
    p.add_argument(
        "--games-per-anchor",
        type=int,
        default=5,
        help="games per smoke anchor (2 anchors -> ~2x this total games played)",
    )
    p.add_argument("--throttle", type=float, default=2.0, help="seconds to sleep between games (rate-limit Golaxy)")
    p.add_argument(
        "--wide-root-noise",
        type=float,
        default=None,
        help="override wideRootNoise; MUST match the deployed :8000 server's actual config (default: read from "
        "this checkout's katrain/config.json)",
    )
    return p


def main() -> int:
    args = build_arg_parser().parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
