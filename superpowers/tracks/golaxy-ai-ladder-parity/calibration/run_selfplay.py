#!/usr/bin/env python3
"""Self-play strength assessment (operator-run): pit two of OUR OWN KataGo configs against
each other via the local /analyze engine, adjudicated by an impartial b28 referee. NO Golaxy,
NO token, NO daily budget -- pure self-assessment of how humanSL ranks scale with search.

Reuses the TESTED calibration primitives:
  * adapters.our_move       -- builds the ladder analysis query + picks the move for ANY mechanism
  * ladder_calibration.play_one_game -- the fail-closed alternating game loop
  * adapters.adjudicate     -- b28 black-relative settled scoring (same stability contract as
                               run_calibration; neither side resigns, matching the ladder)

A "player" is a minimal LadderRung built from a spec "<profile>@<visits>":
  * rank_9d@1     -> mechanism 'humansl'        (humanv0 human policy @1 visit, weighted sample;
                     this is the vanilla HumanSL ladder config)
  * rank_9d@1s    -> mechanism 'humansl'        (humanv0 human policy @1 visit, argmax)
  * rank_9d@40    -> mechanism 'humansl_search' (b18 main model + humanv0 using the canonical
                     nonzero PIKL recipe, then select the top search move)
  * b28@20        -> mechanism 'net_search'     (pure b28 @20, no human profile)
HumanSL search is intentionally accepted only at 40 visits or more, the validated minimum for this
harness. The HTTP adapter routes b18/b28 explicitly and rejects missing or mismatched wrapper
attestation. Games end on a natural double-pass or the 400-move cap, then b28 scores.

Usage:
    KIVY_NO_ARGS=1 uv run python \
      superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py \
      --matchups "rank_9d@80:rank_9d@40:10,rank_9d@40:b28@20:10" \
      --base-url http://127.0.0.1:8000 \
      --out superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/selfplay

Each matchup is "A:B:games"; A wins are counted (from A's alternating color). Checkpoints per
matchup to selfplay_<A>__vs__<B>.jsonl (resumable -- a re-run skips finished games)."""
from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import logging
import os
import re
import sys
import time
from functools import partial
from pathlib import Path
from typing import List, Mapping, Optional, Tuple

import httpx

os.environ.setdefault("KIVY_NO_ARGS", "1")  # keep Kivy from hijacking our argv (see run_calibration)

sys.path.insert(0, str(Path(__file__).parent))
import adapters  # noqa: E402

from katrain.core.base_katrain import KaTrainBase  # noqa: E402
from katrain.core.ladder import (  # noqa: E402
    HUMANSL_PIKL_BASELINE,
    LadderMoveError,
    LadderRung,
    _valid_policy,
    colrow_to_golaxy,
    rung_strength_spec,
)
from katrain.core.ladder_calibration import play_one_game, elo_from_winrate, GameOutcome  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("run_selfplay")


class _MockKaTrainForConfig(KaTrainBase):
    """Config-only double: reads the SAME shipping engine block engine.py ships with."""


def make_player(spec: str) -> Tuple[str, LadderRung, str]:
    """'rank_9d@40' / 'rank_9d@1s' / 'b28@20' -> (label, minimal LadderRung, selection).

    selection drives HOW the move is picked from the engine reply:
      * 'search'       -- top (min-order) moveInfo. net_search uses pure b28; humansl_search uses
                          explicitly routed b18 + humanv0 with the canonical nonzero PIKL recipe.
      * 'weighted'     -- weighted RANDOM sample of humanPolicy. vanilla humansl @1 (Band A config).
      * 'argmax_human' -- ARGMAX of humanPolicy at 1 visit (deterministic "top human move"). This is
                          the faithful 'humansl_search@1': a 1-visit SEARCH returns EMPTY moveInfos
                          (only the root is evaluated), so search-move-picking is impossible at V=1;
                          argmax over the (present) humanPolicy is the real "argmax@1" the spec means.

    A trailing 's' is valid only for argmax_human at 1 visit ('rank_9d@1s'); plain 'rank_9d@1' is
    weighted vanilla HumanSL. HumanSL search requires at least 40 visits."""
    prof, sep, vs = spec.partition("@")
    force_search = vs.endswith("s")  # trailing 's' -> argmax_human @1 (see docstring)
    if force_search:
        vs = vs[:-1]
    if not sep or not vs.isdigit() or int(vs) < 1:
        raise ValueError(
            f"bad player spec {spec!r} (want '<profile>@<visits>[s]', visits>=1; a trailing 's' means "
            "argmax@1, e.g. 'rank_9d@1s' = argmax humanPolicy @1 vs 'rank_9d@1' = weighted@1)"
        )
    visits = int(vs)
    if prof == "b28":
        if force_search:
            raise ValueError("the 's' suffix is only supported by HumanSL '<profile>@1s'")
        mech, net, profile, label, selection = "net_search", "b28", None, f"b28@{visits}", "search"
    elif prof.startswith("rank_") or prof.startswith("preaz_") or prof.startswith("proyear_"):
        if visits == 1 and force_search:
            mech, selection, label = "humansl", "argmax_human", f"{prof}@1s"  # argmax humanPolicy @1
        elif visits == 1:
            mech, selection, label = "humansl", "weighted", f"{prof}@1"  # vanilla weighted humanSL
        elif force_search:
            raise ValueError("the 's' suffix is only supported by HumanSL '<profile>@1s'")
        elif visits < 40:
            raise ValueError(f"HumanSL search has a supported minimum of 40 visits, got {visits}")
        else:
            mech, selection, label = "humansl_search", "search", f"{prof}@{visits}"
        net = "humanv0" if visits == 1 else "b18"
        profile = prof
    else:
        raise ValueError(f"bad player profile {prof!r} (want 'b28' or a humanSL profile like 'rank_9d')")
    rung = LadderRung(
        rung=0,
        golaxy_level_name=None,
        golaxy_api_level=None,
        display_elo=None,
        ref_rank=prof,
        rank_name=prof,
        net=net,
        mechanism=mech,
        human_sl_profile=profile,
        max_visits=visits,
        human_sl_params=dict(HUMANSL_PIKL_BASELINE) if mech == "humansl_search" else {},
        backend_hint="server",
        root_policy_temperature=1.0,
    )
    return label, rung, selection


def _pick_argmax_human(hp: list, board_size: Tuple[int, int]) -> object:
    """ARGMAX of a humanPolicy vector -> (col,row0) bottom-origin, or 'pass'. Same index layout as
    ladder._weighted_policy_pick (idx = (by-y-1)*bx + x; last entry = pass)."""
    bx, by = board_size
    best_val, best = -1.0, None
    for x in range(bx):
        for y in range(by):
            idx = (by - y - 1) * bx + x
            if idx < len(hp) and hp[idx] > best_val:
                best_val, best = hp[idx], (x, y)
    if len(hp) > bx * by and hp[bx * by] > best_val:
        best = "pass"
    return best if best is not None else "pass"


async def _player_move(
    client,
    base_url,
    history,
    *,
    rung: LadderRung,
    selection: str,
    wrn: float,
    capabilities: Mapping[str, object],
):
    """Dispatch a self-play move by selection. 'search'/'weighted' reuse the TESTED adapters.our_move
    (pick_ladder_move). 'argmax_human' issues the same maxVisits=1 humanSL query but picks argmax of
    humanPolicy directly (moveInfos are empty at 1 visit, so the search picker cannot be used)."""
    if selection != "argmax_human":
        return await adapters.our_move(
            client,
            base_url,
            history,
            rung=rung,
            wide_root_noise=wrn,
            capabilities=capabilities,
        )
    try:
        adapters._capability_identity(capabilities, rung_strength_spec(rung))
    except LadderMoveError:
        return "unavailable"
    q = adapters.build_ladder_analysis_query(history, rung, 19, 7.5, "chinese", wrn)
    r = await client.post(f"{base_url}/analyze", json=q, timeout=httpx.Timeout(180.0, connect=10.0))
    r.raise_for_status()
    hp = r.json().get("humanPolicy")
    if not _valid_policy(hp, 19 * 19 + 1):
        return "unavailable"  # -> harness marks inconclusive_engine (never a fabricated move)
    picked = _pick_argmax_human(hp, (19, 19))
    return "pass" if picked == "pass" else colrow_to_golaxy(picked[0], picked[1], 19)


def _fname(label: str) -> str:
    return re.sub(r"[^0-9A-Za-z]+", "-", label)


def parse_matchups(spec: str) -> List[Tuple[str, str, int]]:
    """'rank_9d@80:rank_9d@40:10,rank_9d@40:b28@20:10' -> [(A,B,games), ...]."""
    out = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        bits = part.split(":")
        if len(bits) != 3:
            raise ValueError(f"matchup {part!r}: want 'A:B:games'")
        a, b, g = bits[0].strip(), bits[1].strip(), int(bits[2])
        make_player(a)  # validate
        make_player(b)
        if g <= 0:
            raise ValueError(f"matchup {part!r}: games must be > 0")
        out.append((a, b, g))
    if not out:
        raise ValueError(f"no matchups parsed from {spec!r}")
    return out


def _already_done(path: Path) -> int:
    if not path.is_file():
        return 0
    with path.open() as f:
        return sum(1 for line in f if line.strip())


async def run_matchup(
    specA: str,
    specB: str,
    games: int,
    *,
    client: httpx.AsyncClient,
    base_url: str,
    wrn: float,
    out_dir: Path,
    capabilities: Mapping[str, object],
) -> dict:
    labelA, rungA, selA = make_player(specA)
    labelB, rungB, selB = make_player(specB)
    out_dir.mkdir(parents=True, exist_ok=True)
    ckpt = out_dir / f"selfplay_{_fname(labelA)}__vs__{_fname(labelB)}.jsonl"
    start = _already_done(ckpt)
    winsA = conclusive = 0
    reason_counts: dict = {}
    if ckpt.is_file():  # fold prior games into the running totals (resume)
        with ckpt.open() as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                if rec["conclusive"]:
                    conclusive += 1
                    winsA += 1 if rec["our_win"] else 0
                reason_counts[rec["result"]] = reason_counts.get(rec["result"], 0) + 1
    if start >= games:
        log.info("matchup %s vs %s: already have %d/%d, skipping", labelA, labelB, start, games)
    else:
        log.info("matchup %s vs %s: resuming at game %d/%d", labelA, labelB, start, games)

    adj = partial(adapters.adjudicate, client, base_url, capabilities=capabilities)
    with ckpt.open("a") as f:
        for i in range(start, games):
            a_color = "B" if i % 2 == 0 else "W"  # alternate A's color for a fair B/W split

            async def a_move(history):
                return await _player_move(
                    client,
                    base_url,
                    history,
                    rung=rungA,
                    selection=selA,
                    wrn=wrn,
                    capabilities=capabilities,
                )

            async def b_move(history):
                return await _player_move(
                    client,
                    base_url,
                    history,
                    rung=rungB,
                    selection=selB,
                    wrn=wrn,
                    capabilities=capabilities,
                )

            # A occupies play_one_game's "our" slot, B the "golaxy" slot; both return int|'pass'|
            # 'unavailable' only (never resign/terminal/illegal), so the loop scores them normally.
            outcome: GameOutcome = await play_one_game(
                our_move=a_move, golaxy_move=b_move, adjudicate=adj, our_color=a_color
            )
            if outcome.conclusive:
                conclusive += 1
                winsA += 1 if outcome.our_win else 0
            reason_counts[outcome.result] = reason_counts.get(outcome.result, 0) + 1
            rec = {
                "index": i,
                "player_a": labelA,
                "player_b": labelB,
                "a_color": a_color,
                **dataclasses.asdict(outcome),  # result/our_win(=A won)/num_moves/black_score/conclusive/end_reason
                "ts": time.time(),
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            log.info(
                "  %s vs %s game %d/%d: A_%s (%s, end=%s, conclusive=%s, moves=%d, score=%s)",
                labelA,
                labelB,
                i + 1,
                games,
                "win" if (outcome.conclusive and outcome.our_win) else ("loss" if outcome.conclusive else "?"),
                outcome.result,
                outcome.end_reason,
                outcome.conclusive,
                outcome.num_moves,
                outcome.black_score,
            )

    elo, lo, hi = elo_from_winrate(winsA, conclusive)
    summary = {
        "player_a": labelA,
        "player_b": labelB,
        "games": games,
        "conclusive": conclusive,
        "a_wins": winsA,
        "a_winrate": (winsA / conclusive if conclusive else None),
        "a_elo_vs_b": elo,
        "a_elo_ci95": [lo, hi],
        "reason_counts": reason_counts,
    }
    log.info(
        "=== %s vs %s: A %d/%d (%.0f%%) Elo %+.0f [%.0f,%.0f] ===",
        labelA,
        labelB,
        winsA,
        conclusive,
        100 * (winsA / conclusive) if conclusive else 0.0,
        elo,
        lo,
        hi,
    )
    return summary


async def main_async(args) -> int:
    matchups = parse_matchups(args.matchups)
    if args.wide_root_noise is None:
        wrn = adapters.load_engine_wide_root_noise(
            dict(_MockKaTrainForConfig(force_package_config=True).config("engine"))
        )
        log.info("wide_root_noise = %.4f (from this checkout's config.json engine block)", wrn)
    else:
        wrn = args.wide_root_noise
        log.info("wide_root_noise = %.4f (override)", wrn)
    out_dir = Path(args.out)
    summaries = []
    async with httpx.AsyncClient() as client:
        capabilities = await adapters.fetch_health_snapshot(client, args.base_url)
        for a, b, g in matchups:
            summaries.append(
                await run_matchup(
                    a,
                    b,
                    g,
                    client=client,
                    base_url=args.base_url,
                    wrn=wrn,
                    out_dir=out_dir,
                    capabilities=capabilities,
                )
            )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "selfplay_summary.json").write_text(
        json.dumps({"matchups": summaries, "wide_root_noise": wrn}, indent=2, ensure_ascii=False)
    )
    log.info("wrote %s", out_dir / "selfplay_summary.json")
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--matchups", required=True, help="'A:B:games,...' e.g. 'rank_9d@80:rank_9d@40:10'")
    p.add_argument("--base-url", default="http://127.0.0.1:8000", help="our KataGo HTTP analysis server")
    p.add_argument("--out", default=str(Path(__file__).parent / "results" / "selfplay"), help="checkpoint dir")
    p.add_argument(
        "--wide-root-noise", type=float, default=None, help="override wideRootNoise (default: shipping config)"
    )
    return p


def main() -> int:
    return asyncio.run(main_async(build_arg_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
