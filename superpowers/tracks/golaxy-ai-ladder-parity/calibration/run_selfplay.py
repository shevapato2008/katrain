#!/usr/bin/env python3
"""Self-play strength assessment (operator-run): pit two of OUR OWN KataGo configs against
each other via the local /analyze engine, adjudicated by an impartial b28 referee. NO Golaxy,
NO token, NO daily budget -- pure self-assessment of how humanSL ranks scale with search.

Reuses the TESTED calibration primitives:
  * adapters query/identity -- builds the canonical ladder query and verifies the executed model
  * ladder_calibration.play_one_game -- the fail-closed alternating game loop
  * adapters.adjudicate     -- one b28@200 black-relative settled score; unlike calibration,
                               self-play does not run a second stability recheck

A "player" is a minimal LadderRung built from a spec "<profile>@<visits>":
  * rank_9d@1     -> mechanism 'humansl'        (humanv0 human policy @1 visit, weighted sample;
                     this is the vanilla HumanSL ladder config)
  * rank_9d@1s    -> mechanism 'humansl'        (humanv0 human policy @1 visit, argmax)
  * rank_9d@40    -> mechanism 'humansl_search' (b18 main model + humanv0 using the canonical
                     nonzero PIKL recipe, then select the top search move)
  * b28@20        -> mechanism 'net_search'     (pure b28 @20, no human profile)
HumanSL search defaults to a 40-visit minimum. Lower visits require the explicit operator-only
experimental floor option. The HTTP adapter routes b18/b28 explicitly and rejects missing or
mismatched wrapper attestation. Games end on the first pass or the 400-move cap, then b28 scores.

Usage:
    KIVY_NO_ARGS=1 uv run python \
      superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_selfplay.py \
      --matchups "rank_9d@80:rank_9d@40:20,rank_9d@40:b28@20:40" \
      --phase confirm \
      --base-url http://127.0.0.1:8000 \
      --out superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/selfplay_v2_pikl

Each matchup is "A:B:fully-conclusive-pairs". Every frozen opening is played with A as Black and
White; a pair with either game inconclusive contributes zero decision games. Checkpoints are
phase-isolated and resumable, including completion of an interrupted color pair."""
from __future__ import annotations

import argparse
import asyncio
import dataclasses
import hashlib
import json
import logging
import math
import os
import re
import sys
import time
from contextlib import contextmanager
from functools import partial
from pathlib import Path
from typing import List, Mapping, Optional, Tuple

import httpx

try:  # POSIX (macOS/Linux)
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - exercised by backend-selection tests
    _fcntl = None

try:  # Windows
    import msvcrt as _msvcrt
except ImportError:  # pragma: no cover - exercised by backend-selection tests
    _msvcrt = None

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
    golaxy_to_colrow,
    pick_ladder_move,
    rung_strength_spec,
    validate_analysis_attestation,
)
from katrain.core.ladder_calibration import play_one_game, elo_from_winrate, GameOutcome  # noqa: E402
from katrain.core.game import BaseGame, IllegalMoveException  # noqa: E402
from katrain.core.sgf_parser import Move  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("run_selfplay")

_RESULTS_DIR = Path(__file__).parent / "results"
DEFAULT_OUT_DIR = _RESULTS_DIR / "selfplay_v2_pikl"
LEGACY_OUT_DIR = _RESULTS_DIR / "selfplay"
_RANK_TOKEN = r"(?:[1-9]d|(?:[1-9]|1[0-9]|20)k)"
_RANK_PROFILE_RE = re.compile(rf"(?:rank|preaz)_{_RANK_TOKEN}(?:_{_RANK_TOKEN})?\Z")
_PROYEAR_PROFILE_RE = re.compile(r"proyear_([0-9]{4})\Z")
CHECKPOINT_SCHEMA = 3
SELECTION_ALGORITHM_VERSION = "selfplay-selection-v1"
SYMMETRY_SETTINGS = {"mode": "katago-default", "requested_symmetry": None}
OPENING_SUITE_PATH = Path(__file__).parent / "opening_suite_v1.json"
OPENING_SUITE_ID = "humansl-opening-suite-v1"
OPENING_SUITE_SEED = 20260721
BOARD_SIZE = 19
KOMI = 7.5
RULES = "chinese"
MOVE_CAP = 400
REFEREE_VISITS = 200
ADJUDICATION_ALGORITHM_VERSION = "b28-settled-score-v1"
_IDENTITY_FIELDS = (
    "selected_model",
    "model_path",
    "model_sha256",
    "human_model_path",
    "human_model_sha256",
    "katago_version",
)
WILSON_Z95 = 1.959963984540054


def wilson_interval(wins: int, n: int) -> Tuple[float, float]:
    """Return the two-sided 95% Wilson score interval for a binomial sample."""
    if type(wins) is not int or type(n) is not int or n <= 0 or not 0 <= wins <= n:
        raise ValueError("Wilson inputs require integer 0 <= wins <= n and n > 0")
    p = wins / n
    z2 = WILSON_Z95 * WILSON_Z95
    denominator = 1 + z2 / n
    center = (p + z2 / (2 * n)) / denominator
    radius = WILSON_Z95 * math.sqrt((p * (1 - p) + z2 / (4 * n)) / n) / denominator
    return max(0.0, center - radius), min(1.0, center + radius)


def required_conclusive_pairs(phase: str, *, experiment4: bool = False) -> int:
    if phase not in {"screen", "confirm"}:
        raise ValueError("phase must be 'screen' or 'confirm'")
    if experiment4 and phase != "confirm":
        raise ValueError("experiment-4 requires confirm phase")
    return 40 if experiment4 else (10 if phase == "screen" else 20)


def classify_seam(wins: int, n: int, *, experiment4: bool = False) -> str:
    minimum_games = 2 * required_conclusive_pairs("confirm", experiment4=experiment4)
    if n < minimum_games or n % 2:
        return "insufficient_pairs"
    low, high = wilson_interval(wins, n)
    if low > 0.5:
        return "a_stronger"
    if high < 0.5:
        return "a_weaker"
    return "inconclusive"


def opening_suite_checksum(payload: Mapping[str, object]) -> str:
    canonical = {key: value for key, value in payload.items() if key != "checksum"}
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class _OpeningBoardConfig:
    @staticmethod
    def config(key):
        return 0 if key == "game/handicap" else "chinese"


def _validate_opening_legality(moves: List[int], board_size: int) -> None:
    game = BaseGame(
        _OpeningBoardConfig(),
        game_properties={"SZ": board_size, "KM": KOMI, "RU": RULES},
        bypass_config=True,
    )
    for ply, wire in enumerate(moves):
        colrow = golaxy_to_colrow(wire, board_size)
        if colrow == "pass":
            raise ValueError("opening moves must not contain pass")
        try:
            game.play(Move(colrow, player="B" if ply % 2 == 0 else "W"))
        except IllegalMoveException as exc:
            raise ValueError(f"opening is not legal at ply {ply}: {exc}") from exc


def load_opening_suite(path: Path = OPENING_SUITE_PATH) -> dict:
    try:
        payload = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load opening suite: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("suite_id") != OPENING_SUITE_ID:
        raise ValueError(f"opening suite ID must be {OPENING_SUITE_ID!r}")
    if type(payload.get("seed")) is not int or payload["seed"] != OPENING_SUITE_SEED:
        raise ValueError(f"opening suite seed must be documented as {OPENING_SUITE_SEED}")
    if payload.get("board_size") != BOARD_SIZE:
        raise ValueError(f"opening suite board size must be {BOARD_SIZE}")
    openings = payload.get("openings")
    if not isinstance(openings, list) or len(openings) < 20:
        raise ValueError("opening suite requires at least 20 openings")
    seen_ids, seen_prefixes = set(), set()
    for opening in openings:
        if not isinstance(opening, dict) or not isinstance(opening.get("id"), str) or not opening["id"]:
            raise ValueError("opening suite entry has invalid ID")
        if opening["id"] in seen_ids:
            raise ValueError("opening IDs must be unique")
        seen_ids.add(opening["id"])
        moves = opening.get("moves")
        if not isinstance(moves, list) or not moves:
            raise ValueError("opening moves must be a nonempty list")
        if any(type(move) is not int or not 0 <= move < BOARD_SIZE * BOARD_SIZE for move in moves):
            raise ValueError("opening move is outside coordinate bounds")
        prefix = tuple(moves)
        if prefix in seen_prefixes:
            raise ValueError("opening prefixes must be unique")
        seen_prefixes.add(prefix)
        _validate_opening_legality(moves, BOARD_SIZE)
    actual_checksum = payload.get("checksum")
    expected_checksum = opening_suite_checksum(payload)
    if not isinstance(actual_checksum, str) or actual_checksum != expected_checksum:
        raise ValueError(f"opening suite checksum mismatch: expected {expected_checksum}")
    return payload


def complete_pair_sample(records: List[Mapping[str, object]], *, phase: str) -> dict:
    grouped = {}
    for record in records:
        if record.get("phase") != phase:
            raise ValueError("checkpoint phase does not match this run")
        key = (record.get("pair_attempt"), record.get("opening_id"))
        color_index = record.get("color_index")
        if type(key[0]) is not int or type(color_index) is not int or color_index not in {0, 1}:
            raise ValueError("checkpoint pair key is malformed")
        pair = grouped.setdefault(key, {})
        if color_index in pair:
            raise ValueError("checkpoint contains duplicate pair color")
        pair[color_index] = record
    complete_pairs = games = wins = inconclusive_pairs = 0
    for pair in grouped.values():
        if len(pair) != 2:
            continue
        if all(record.get("conclusive") is True for record in pair.values()):
            complete_pairs += 1
            games += 2
            wins += sum(record.get("our_win") is True for record in pair.values())
        else:
            inconclusive_pairs += 1
    return {
        "complete_pairs": complete_pairs,
        "games": games,
        "a_wins": wins,
        "inconclusive_pairs": inconclusive_pairs,
    }


def schedule_pair_games(
    records: List[Mapping[str, object]], openings: List[Mapping[str, object]], *, phase: str, max_pair_attempts: int
) -> List[dict]:
    if phase not in {"screen", "confirm"}:
        raise ValueError("phase must be screen or confirm")
    if type(max_pair_attempts) is not int or max_pair_attempts <= 0:
        raise ValueError("maximum pair attempts must be positive")
    if not openings:
        raise ValueError("opening suite is empty")
    completed_keys = set()
    for record in records:
        if record.get("phase") != phase:
            raise ValueError("checkpoint phase does not match this run")
        attempt = record.get("pair_attempt")
        color_index = record.get("color_index")
        if type(attempt) is not int or not 0 <= attempt < max_pair_attempts:
            raise ValueError("checkpoint exceeds maximum pair attempts")
        expected = openings[attempt % len(openings)]
        if record.get("opening_id") != expected["id"]:
            raise ValueError("checkpoint opening does not match pair schedule")
        if record.get("opening_moves") != expected["moves"]:
            raise ValueError("checkpoint opening history does not match pair schedule")
        key = (attempt, color_index)
        if type(color_index) is not int or color_index not in {0, 1} or key in completed_keys:
            raise ValueError("checkpoint contains duplicate or malformed pair color")
        completed_keys.add(key)
    scheduled = []
    for attempt in range(max_pair_attempts):
        opening = openings[attempt % len(openings)]
        for color_index, a_color in enumerate(("B", "W")):
            if (attempt, color_index) not in completed_keys:
                scheduled.append(
                    {
                        "phase": phase,
                        "opening_id": opening["id"],
                        "pair_attempt": attempt,
                        "color_index": color_index,
                        "a_color": a_color,
                        "initial_history": list(opening["moves"]),
                    }
                )
    return scheduled


class _MockKaTrainForConfig(KaTrainBase):
    """Config-only double: reads the SAME shipping engine block engine.py ships with."""


def _valid_humansl_profile(profile: str) -> bool:
    """Mirror KataGo SGFMetadata::getProfile's accepted named-profile ranges."""
    if _RANK_PROFILE_RE.fullmatch(profile):
        return True
    proyear = _PROYEAR_PROFILE_RE.fullmatch(profile)
    return proyear is not None and 1800 <= int(proyear.group(1)) <= 2023


def make_player(spec: str, *, experimental_min_humansl_search_visits: int = 40) -> Tuple[str, LadderRung, str]:
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
    weighted vanilla HumanSL. HumanSL search requires at least the explicitly supplied experimental
    floor, which defaults to 40 visits. The floor must be a plain integer of at least 2."""
    if type(experimental_min_humansl_search_visits) is not int or experimental_min_humansl_search_visits < 2:
        raise ValueError("experimental HumanSL search minimum must be a plain int of at least 2")
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
    elif _valid_humansl_profile(prof):
        if visits == 1 and force_search:
            mech, selection, label = "humansl", "argmax_human", f"{prof}@1s"  # argmax humanPolicy @1
        elif visits == 1:
            mech, selection, label = "humansl", "weighted", f"{prof}@1"  # vanilla weighted humanSL
        elif force_search:
            raise ValueError("the 's' suffix is only supported by HumanSL '<profile>@1s'")
        elif visits < experimental_min_humansl_search_visits:
            raise ValueError(
                "HumanSL search has a supported minimum of "
                f"{experimental_min_humansl_search_visits} visits, got {visits}"
            )
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
    attestations: Optional[list] = None,
    player: Optional[str] = None,
):
    """Dispatch a self-play move and fail closed unless the executed model is fully attested."""
    spec = rung_strength_spec(rung)
    try:
        capability_identity = adapters._capability_identity(capabilities, spec)
    except LadderMoveError:
        return "unavailable"
    q = adapters.build_ladder_analysis_query(history, rung, BOARD_SIZE, KOMI, RULES, wrn)
    r = await client.post(f"{base_url}/analyze", json=q, timeout=httpx.Timeout(180.0, connect=10.0))
    r.raise_for_status()
    analysis = r.json()
    try:
        # Native HumanSL has no explicit route selector, but this experiment harness still requires
        # the wrapper to attest the default main model and its human model before using humanPolicy.
        attested_spec = (
            spec
            if spec.main_model is not None
            else dataclasses.replace(spec, main_model=capability_identity["selected_model"])
        )
        validate_analysis_attestation(analysis, attested_spec, capability_identity)
        if selection == "search":
            picked = pick_ladder_move(analysis, (BOARD_SIZE, BOARD_SIZE), rung.mechanism)
        elif selection == "weighted":
            picked = pick_ladder_move(analysis, (BOARD_SIZE, BOARD_SIZE), "humansl")
        elif selection == "argmax_human":
            hp = analysis.get("humanPolicy")
            if not _valid_policy(hp, BOARD_SIZE * BOARD_SIZE + 1):
                raise LadderMoveError("argmax HumanSL requires a valid humanPolicy")
            picked = _pick_argmax_human(hp, (BOARD_SIZE, BOARD_SIZE))
        else:
            raise LadderMoveError(f"unknown self-play selection {selection!r}")
    except (KeyError, LadderMoveError):
        return "unavailable"  # -> harness marks inconclusive_engine (never a fabricated move)
    if attestations is not None:
        if player not in {"A", "B"}:
            raise ValueError("attested self-play moves require player A or B")
        attestations.append({"ply": len(history), "player": player, "identity": dict(analysis["_wrapper"])})
    return "pass" if picked == "pass" else colrow_to_golaxy(picked[0], picked[1], BOARD_SIZE)


def _fname(label: str) -> str:
    return re.sub(r"[^0-9A-Za-z]+", "-", label)


def parse_matchups(spec: str, *, experimental_min_humansl_search_visits: int = 40) -> List[Tuple[str, str, int]]:
    """Parse ``A:B:target`` entries where target is fully conclusive color pairs."""
    out = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        bits = part.split(":")
        if len(bits) != 3:
            raise ValueError(f"matchup {part!r}: want 'A:B:complete_pairs'")
        a, b, g = bits[0].strip(), bits[1].strip(), int(bits[2])
        make_player(a, experimental_min_humansl_search_visits=experimental_min_humansl_search_visits)
        make_player(b, experimental_min_humansl_search_visits=experimental_min_humansl_search_visits)
        if g <= 0:
            raise ValueError(f"matchup {part!r}: complete pairs must be > 0")
        out.append((a, b, g))
    if not out:
        raise ValueError(f"no matchups parsed from {spec!r}")
    return out


def _json_value(value):
    """Convert frozen capability mappings to canonical JSON-compatible values."""
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _configuration_fingerprint(configuration: Mapping[str, object]) -> str:
    payload = json.dumps(
        _json_value(configuration), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _preflight_capabilities(capabilities: Mapping[str, object], players: Mapping[str, tuple]) -> dict:
    """Resolve and validate every player route plus the fixed b28 referee before games begin."""
    identities = {}
    try:
        for side in ("A", "B"):
            _label, rung, _selection = players[side]
            identities[side] = dict(adapters._capability_identity(capabilities, rung_strength_spec(rung)))
        _label, referee, _selection = make_player("b28@200")
        identities["referee"] = dict(adapters._capability_identity(capabilities, rung_strength_spec(referee)))
    except (KeyError, LadderMoveError) as exc:
        raise ValueError(f"self-play capability preflight failed: {exc}") from exc
    return identities


def _matchup_configuration(
    players: Mapping[str, tuple],
    identities: Mapping[str, Mapping[str, object]],
    *,
    capabilities: Mapping[str, object],
    wide_root_noise: float,
    target_pairs: int,
    max_pair_attempts: int,
    phase: str = "confirm",
    experiment4: bool = False,
    opening_suite: Optional[Mapping[str, object]] = None,
    experimental_min_humansl_search_visits: int = 40,
    boundary_protocol_version: Optional[str] = None,
) -> dict:
    if type(experimental_min_humansl_search_visits) is not int or experimental_min_humansl_search_visits < 2:
        raise ValueError("experimental HumanSL search minimum must be a plain int of at least 2")
    if type(target_pairs) is not int or target_pairs <= 0:
        raise ValueError("target complete pairs must be a positive plain int")
    if type(max_pair_attempts) is not int or max_pair_attempts <= 0:
        raise ValueError("maximum pair attempts must be a positive plain int")
    suite = dict(opening_suite or load_opening_suite())
    configured_players = {}
    for side in ("A", "B"):
        label, rung, selection = players[side]
        spec = rung_strength_spec(rung)
        query = adapters.build_ladder_analysis_query([], rung, BOARD_SIZE, KOMI, RULES, wide_root_noise)
        configured_players[side] = {
            "label": label,
            "profile": rung.human_sl_profile,
            "mechanism": rung.mechanism,
            "visits": spec.visits,
            "requested_main_model": spec.main_model,
            "requested_human_model": spec.human_model,
            "effective_overrides": dict(spec.override_settings),
            "http_effective_overrides": query["overrideSettings"],
            "selection": selection,
            "selection_algorithm_version": SELECTION_ALGORITHM_VERSION,
            "identity": dict(identities[side]),
        }
    return _json_value(
        {
            "capability_schema": capabilities.get("capability_schema"),
            "katago_version": capabilities.get("katago_version"),
            "capability_snapshot": capabilities,
            "boundary_protocol_version": boundary_protocol_version,
            "experimental_min_humansl_search_visits": experimental_min_humansl_search_visits,
            "players": configured_players,
            "game": {
                "board_size": BOARD_SIZE,
                "komi": KOMI,
                "rules": adapters.BaseEngine.get_rules(RULES),
                "move_cap": MOVE_CAP,
            },
            "referee": {
                "visits": REFEREE_VISITS,
                "requested_main_model": "b28",
                "requested_human_model": None,
                "http_effective_overrides": {
                    "model": "b28",
                    "reportAnalysisWinratesAs": "BLACK",
                },
                "identity": identities["referee"],
            },
            "adjudication_algorithm_version": ADJUDICATION_ALGORITHM_VERSION,
            "wide_root_noise": wide_root_noise,
            "symmetry_settings": SYMMETRY_SETTINGS,
            "phase": phase,
            "experiment4": experiment4,
            "target_complete_pairs": target_pairs,
            "max_pair_attempts": max_pair_attempts,
            "opening_suite": {
                "id": suite["suite_id"],
                "suite_id": suite["suite_id"],
                "seed": suite["seed"],
                "board_size": suite["board_size"],
                "checksum": suite["checksum"],
            },
        }
    )


def _validate_record_attestations(record: Mapping[str, object], configuration: Mapping[str, object]) -> None:
    attestations = record.get("move_attestations")
    if not isinstance(attestations, list):
        raise ValueError("checkpoint game record has no move attestations")
    attested_turn_count = record.get("attested_turn_count")
    if type(attested_turn_count) is not int or attested_turn_count < 0 or len(attestations) != attested_turn_count:
        raise ValueError("checkpoint does not attest every accepted move")
    a_color = record.get("a_color")
    if a_color not in ("B", "W"):
        raise ValueError("checkpoint game record has invalid A color")
    expected_players = configuration.get("players")
    if not isinstance(expected_players, Mapping):
        raise ValueError("checkpoint configuration has no players")
    opening_moves = record.get("opening_moves")
    if not isinstance(opening_moves, list):
        raise ValueError("checkpoint game record has no opening moves")
    opening_length = len(opening_moves)
    for attestation_index, attestation in enumerate(attestations):
        expected_ply = opening_length + attestation_index
        if not isinstance(attestation, Mapping):
            raise ValueError("checkpoint move attestation is malformed")
        side = attestation.get("player")
        if side not in ("A", "B") or type(attestation.get("ply")) is not int or attestation.get("ply") != expected_ply:
            raise ValueError("checkpoint game move attestation has invalid player or ply")
        expected_side = "A" if ((expected_ply % 2 == 0) == (a_color == "B")) else "B"
        if side != expected_side:
            raise ValueError("checkpoint move attestation names the wrong player")
        actual = attestation.get("identity")
        expected_player = expected_players.get(side)
        expected = expected_player.get("identity") if isinstance(expected_player, Mapping) else None
        if not isinstance(actual, Mapping) or not isinstance(expected, Mapping):
            raise ValueError("checkpoint move attestation identity is malformed")
        if any(field not in actual or actual.get(field) != expected.get(field) for field in _IDENTITY_FIELDS):
            raise ValueError("checkpoint move attestation does not match startup capability")


_RESULTS = {
    "our_win",
    "our_loss",
    "inconclusive_score",
    "inconclusive_unsettled",
    "inconclusive_engine",
    "inconclusive_terminal",
}
_END_REASONS = {
    "our_pass",
    "golaxy_pass",
    "golaxy_resign",
    "golaxy_terminal",
    "golaxy_illegal",
    "move_cap",
}


def _validate_game_record(
    record: Mapping[str, object], expected_index: int, configuration: Mapping[str, object]
) -> None:
    players = configuration.get("players")
    if not isinstance(record, Mapping) or not isinstance(players, Mapping):
        raise ValueError("checkpoint game record is malformed")
    required_fields = {
        "record_type",
        "fingerprint",
        "index",
        "player_a",
        "player_b",
        "a_color",
        "our_color",
        "result",
        "our_win",
        "num_moves",
        "black_score",
        "conclusive",
        "end_reason",
        "attested_turn_count",
        "move_attestations",
        "phase",
        "opening_id",
        "opening_moves",
        "pair_attempt",
        "color_index",
        "ts",
    }
    if not required_fields.issubset(record):
        raise ValueError("checkpoint game record is missing required fields")
    color_index = record.get("color_index")
    expected_color = "B" if color_index == 0 else "W"
    if type(record.get("index")) is not int or record.get("index") != expected_index:
        raise ValueError("checkpoint game indices must be unique, ordered, and gap-free")
    if record.get("a_color") != expected_color or record.get("our_color") != expected_color:
        raise ValueError("checkpoint game color parity is invalid")
    if record.get("phase") != configuration.get("phase"):
        raise ValueError("checkpoint game phase does not match the header")
    if (
        type(record.get("pair_attempt")) is not int
        or record.get("pair_attempt") < 0
        or type(color_index) is not int
        or color_index not in {0, 1}
        or record.get("index") != 2 * record.get("pair_attempt") + color_index
    ):
        raise ValueError("checkpoint game pair key is malformed")
    if not isinstance(record.get("opening_id"), str) or not isinstance(record.get("opening_moves"), list):
        raise ValueError("checkpoint game opening is malformed")
    if record.get("player_a") != players["A"]["label"] or record.get("player_b") != players["B"]["label"]:
        raise ValueError("checkpoint game player labels do not match the header")
    result = record.get("result")
    our_win = record.get("our_win")
    conclusive = record.get("conclusive")
    num_moves = record.get("num_moves")
    black_score = record.get("black_score")
    end_reason = record.get("end_reason")
    timestamp = record.get("ts")
    if (
        not isinstance(result, str)
        or result not in _RESULTS
        or type(our_win) is not bool
        or type(conclusive) is not bool
    ):
        raise ValueError("checkpoint game outcome fields are malformed")
    if type(num_moves) is not int or num_moves < 0:
        raise ValueError("checkpoint game num_moves is malformed")
    if black_score is not None and (
        isinstance(black_score, bool) or not isinstance(black_score, (int, float)) or not math.isfinite(black_score)
    ):
        raise ValueError("checkpoint game black_score is malformed")
    if not isinstance(end_reason, str) or end_reason not in _END_REASONS:
        raise ValueError("checkpoint game end_reason is malformed")
    if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp):
        raise ValueError("checkpoint game timestamp is malformed")
    expected_conclusive = result in {"our_win", "our_loss"}
    if conclusive != expected_conclusive or our_win != (result == "our_win"):
        raise ValueError("checkpoint game result flags are inconsistent")
    _validate_record_attestations(record, configuration)
    accepted_pass = end_reason in {"our_pass", "golaxy_pass"} and result != "inconclusive_engine"
    opening_length = len(record["opening_moves"])
    if num_moves < opening_length:
        raise ValueError("checkpoint game num_moves is shorter than its opening")
    expected_attested = num_moves - opening_length + (1 if accepted_pass else 0)
    if record.get("attested_turn_count") != expected_attested:
        raise ValueError("checkpoint game attested turn count is inconsistent with its ending")


def _already_done(path: Path, fingerprint: str, configuration: Mapping[str, object]) -> int:
    if not path.is_file():
        return 0
    with path.open() as f:
        records = [json.loads(line) for line in f if line.strip()]
    if not records:
        raise ValueError(f"checkpoint exists without a schema-{CHECKPOINT_SCHEMA} header")
    header = records[0]
    if header.get("record_type") != "header" or header.get("schema") != CHECKPOINT_SCHEMA:
        raise ValueError(f"checkpoint has no schema-{CHECKPOINT_SCHEMA} header")
    if header.get("fingerprint") != fingerprint:
        raise ValueError("checkpoint header fingerprint does not match this run")
    if _configuration_fingerprint(header.get("configuration", {})) != fingerprint:
        raise ValueError("checkpoint header configuration does not match its fingerprint")
    if _json_value(header.get("configuration")) != _json_value(configuration):
        raise ValueError("checkpoint header configuration does not match this run")
    for expected_index, record in enumerate(records[1:]):
        if record.get("record_type") != "game":
            raise ValueError("checkpoint contains an unexpected record type")
        if record.get("fingerprint") != fingerprint:
            raise ValueError("checkpoint game fingerprint does not match this run")
        _validate_game_record(record, expected_index, configuration)
    return len(records) - 1


def _prepare_checkpoint(path: Path, fingerprint: str, configuration: Mapping[str, object]) -> int:
    if path.exists():
        return _already_done(path, fingerprint, configuration)
    header = {
        "record_type": "header",
        "schema": CHECKPOINT_SCHEMA,
        "fingerprint": fingerprint,
        "configuration": _json_value(configuration),
    }
    with path.open("x") as f:
        f.write(json.dumps(header, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")
        f.flush()
    return 0


@contextmanager
def _checkpoint_lock(path: Path):
    """Hold a non-blocking process lock for one checkpoint's complete validate/append run."""
    lock_path = path.with_name(path.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = lock_path.open("a+b")
    locked = False
    try:
        try:
            if _fcntl is not None:
                _fcntl.flock(lock_file.fileno(), _fcntl.LOCK_EX | _fcntl.LOCK_NB)
            elif _msvcrt is not None:
                lock_file.seek(0, os.SEEK_END)
                if lock_file.tell() == 0:
                    lock_file.write(b"\0")
                    lock_file.flush()
                lock_file.seek(0)
                _msvcrt.locking(lock_file.fileno(), _msvcrt.LK_NBLCK, 1)
            else:  # unsupported Python/platform build
                raise RuntimeError("no supported checkpoint locking backend (need fcntl or msvcrt)")
            locked = True
        except (BlockingIOError, OSError) as exc:
            raise RuntimeError(f"self-play checkpoint is locked by another process: {path}") from exc
        yield
    finally:
        try:
            if locked and _fcntl is not None:
                _fcntl.flock(lock_file.fileno(), _fcntl.LOCK_UN)
            elif locked and _msvcrt is not None:
                lock_file.seek(0)
                _msvcrt.locking(lock_file.fileno(), _msvcrt.LK_UNLCK, 1)
        finally:
            lock_file.close()


def _validated_out_dir(path: Path) -> Path:
    path = Path(path)
    if path.resolve() == LEGACY_OUT_DIR.resolve():
        raise ValueError(f"legacy self-play results cannot be resumed; use the fresh namespace {DEFAULT_OUT_DIR}")
    return path


async def run_matchup(
    specA: str,
    specB: str,
    target_pairs: int,
    *,
    client: httpx.AsyncClient,
    base_url: str,
    wrn: float,
    out_dir: Path,
    capabilities: Mapping[str, object],
    phase: str = "confirm",
    experiment4: bool = False,
    max_pair_attempts: Optional[int] = None,
    experimental_min_humansl_search_visits: int = 40,
) -> dict:
    required = required_conclusive_pairs(phase, experiment4=experiment4)
    if type(target_pairs) is not int or target_pairs < required or (phase == "screen" and target_pairs != required):
        comparator = "exactly" if phase == "screen" else "at least"
        raise ValueError(f"{phase} target must be {comparator} {required} fully conclusive pairs")
    if max_pair_attempts is None:
        max_pair_attempts = max(target_pairs * 2, target_pairs + 10)
    elif type(max_pair_attempts) is not int or max_pair_attempts <= 0:
        raise ValueError("maximum pair attempts must be a positive plain int")
    opening_suite = load_opening_suite()
    playerA = make_player(specA, experimental_min_humansl_search_visits=experimental_min_humansl_search_visits)
    playerB = make_player(specB, experimental_min_humansl_search_visits=experimental_min_humansl_search_visits)
    labelA, rungA, selA = playerA
    labelB, rungB, selB = playerB
    players = {"A": playerA, "B": playerB}
    identities = _preflight_capabilities(capabilities, players)
    configuration = _matchup_configuration(
        players,
        identities,
        capabilities=capabilities,
        wide_root_noise=wrn,
        target_pairs=target_pairs,
        max_pair_attempts=max_pair_attempts,
        phase=phase,
        experiment4=experiment4,
        opening_suite=opening_suite,
        experimental_min_humansl_search_visits=experimental_min_humansl_search_visits,
        boundary_protocol_version=None,
    )
    fingerprint = _configuration_fingerprint(configuration)
    out_dir.mkdir(parents=True, exist_ok=True)
    ckpt = out_dir / f"selfplay_{phase}_{_fname(labelA)}__vs__{_fname(labelB)}.jsonl"
    with _checkpoint_lock(ckpt):
        return await _run_matchup_checkpoint(
            labelA=labelA,
            rungA=rungA,
            selA=selA,
            labelB=labelB,
            rungB=rungB,
            selB=selB,
            target_pairs=target_pairs,
            max_pair_attempts=max_pair_attempts,
            phase=phase,
            experiment4=experiment4,
            openings=opening_suite["openings"],
            client=client,
            base_url=base_url,
            wrn=wrn,
            capabilities=capabilities,
            configuration=configuration,
            fingerprint=fingerprint,
            ckpt=ckpt,
        )


async def _run_matchup_checkpoint(
    *,
    labelA,
    rungA,
    selA,
    labelB,
    rungB,
    selB,
    target_pairs,
    max_pair_attempts,
    phase,
    experiment4,
    openings,
    client,
    base_url,
    wrn,
    capabilities,
    configuration,
    fingerprint,
    ckpt,
) -> dict:
    _prepare_checkpoint(ckpt, fingerprint, configuration)
    records = []
    reason_counts: dict = {}
    if ckpt.is_file():
        with ckpt.open() as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                if rec.get("record_type") == "header":
                    continue
                records.append(rec)
                reason_counts[rec["result"]] = reason_counts.get(rec["result"], 0) + 1
    existing_sample = complete_pair_sample(records, phase=phase)
    if existing_sample["complete_pairs"] > target_pairs:
        raise ValueError(
            f"requested target {target_pairs} is smaller than existing complete pair count "
            f"{existing_sample['complete_pairs']}"
        )

    adj = partial(
        adapters.adjudicate,
        client,
        base_url,
        board_size=BOARD_SIZE,
        komi=KOMI,
        rules=RULES,
        visits=REFEREE_VISITS,
        capabilities=capabilities,
    )
    with ckpt.open("a") as f:
        scheduled = schedule_pair_games(records, openings, phase=phase, max_pair_attempts=max_pair_attempts)
        for scheduled_game in scheduled:
            sample = complete_pair_sample(records, phase=phase)
            if sample["complete_pairs"] >= target_pairs:
                break
            i = 2 * scheduled_game["pair_attempt"] + scheduled_game["color_index"]
            a_color = scheduled_game["a_color"]
            initial_history = scheduled_game["initial_history"]
            move_attestations = []

            async def a_move(history):
                return await _player_move(
                    client,
                    base_url,
                    history,
                    rung=rungA,
                    selection=selA,
                    wrn=wrn,
                    capabilities=capabilities,
                    attestations=move_attestations,
                    player="A",
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
                    attestations=move_attestations,
                    player="B",
                )

            # A occupies play_one_game's "our" slot, B the "golaxy" slot; both return int|'pass'|
            # 'unavailable' only (never resign/terminal/illegal), so the loop scores them normally.
            outcome: GameOutcome = await play_one_game(
                our_move=a_move,
                golaxy_move=b_move,
                adjudicate=adj,
                our_color=a_color,
                board_size=BOARD_SIZE,
                move_cap=MOVE_CAP,
                initial_history=initial_history,
            )
            reason_counts[outcome.result] = reason_counts.get(outcome.result, 0) + 1
            rec = {
                "record_type": "game",
                "fingerprint": fingerprint,
                "index": i,
                "player_a": labelA,
                "player_b": labelB,
                "a_color": a_color,
                "phase": phase,
                "opening_id": scheduled_game["opening_id"],
                "opening_moves": list(initial_history),
                "pair_attempt": scheduled_game["pair_attempt"],
                "color_index": scheduled_game["color_index"],
                **dataclasses.asdict(outcome),  # result/our_win(=A won)/num_moves/black_score/conclusive/end_reason
                "attested_turn_count": len(move_attestations),
                "move_attestations": move_attestations,
                "ts": time.time(),
            }
            f.write(json.dumps(rec, ensure_ascii=False, allow_nan=False) + "\n")
            f.flush()
            records.append(rec)
            log.info(
                "  %s vs %s game %d/%d: A_%s (%s, end=%s, conclusive=%s, moves=%d, score=%s)",
                labelA,
                labelB,
                i + 1,
                2 * max_pair_attempts,
                "win" if (outcome.conclusive and outcome.our_win) else ("loss" if outcome.conclusive else "?"),
                outcome.result,
                outcome.end_reason,
                outcome.conclusive,
                outcome.num_moves,
                outcome.black_score,
            )

    sample = complete_pair_sample(records, phase=phase)
    winsA, conclusive = sample["a_wins"], sample["games"]
    elo, lo, hi = elo_from_winrate(winsA, conclusive)
    if not conclusive:
        lo = hi = None
    interval = list(wilson_interval(winsA, conclusive)) if conclusive else [0.0, 1.0]
    attempted = 1 + max((record["pair_attempt"] for record in records), default=-1)
    target_reached = sample["complete_pairs"] == target_pairs
    classification = (
        classify_seam(winsA, conclusive, experiment4=experiment4)
        if phase == "confirm" and target_reached
        else "screen_complete" if phase == "screen" and target_reached else "insufficient_pairs"
    )
    summary = {
        "player_a": labelA,
        "player_b": labelB,
        "phase": phase,
        "target_complete_pairs": target_pairs,
        "complete_pairs": sample["complete_pairs"],
        "decision_games": conclusive,
        "pair_attempts": attempted,
        "inconclusive_pairs": sample["inconclusive_pairs"],
        "max_pair_attempts": max_pair_attempts,
        "max_attempts_reached": sample["complete_pairs"] < target_pairs and attempted >= max_pair_attempts,
        "conclusive": conclusive,
        "a_wins": winsA,
        "a_winrate": (winsA / conclusive if conclusive else None),
        "a_elo_vs_b": elo,
        "a_elo_ci95": [lo, hi],
        "wilson_ci95": interval,
        "classification": classification,
        "reason_counts": reason_counts,
    }
    log.info(
        "=== %s vs %s: A %d/%d (%.0f%%) Elo %+.0f [%s,%s] ===",
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
    matchups = parse_matchups(
        args.matchups,
        experimental_min_humansl_search_visits=args.experimental_min_humansl_search_visits,
    )
    if args.wide_root_noise is None:
        wrn = adapters.load_engine_wide_root_noise(
            dict(_MockKaTrainForConfig(force_package_config=True).config("engine"))
        )
        log.info("wide_root_noise = %.4f (from this checkout's config.json engine block)", wrn)
    else:
        wrn = args.wide_root_noise
        log.info("wide_root_noise = %.4f (override)", wrn)
    out_dir = _validated_out_dir(args.out)
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
                    phase=args.phase,
                    experiment4=args.experiment4,
                    max_pair_attempts=args.max_pair_attempts,
                    experimental_min_humansl_search_visits=args.experimental_min_humansl_search_visits,
                )
            )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "selfplay_summary.json").write_text(
        json.dumps(
            {"matchups": summaries, "wide_root_noise": wrn},
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
    )
    log.info("wrote %s", out_dir / "selfplay_summary.json")
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--matchups",
        required=True,
        help="'A:B:complete_pairs,...' e.g. 'rank_9d@80:rank_9d@40:20' (pairs, not games/attempts)",
    )
    p.add_argument("--base-url", default="http://127.0.0.1:8000", help="our KataGo HTTP analysis server")
    p.add_argument("--out", default=str(DEFAULT_OUT_DIR), help="checkpoint dir")
    p.add_argument(
        "--wide-root-noise", type=float, default=None, help="override wideRootNoise (default: shipping config)"
    )
    p.add_argument("--phase", choices=("screen", "confirm"), default="confirm")
    p.add_argument("--experiment4", action="store_true", help="apply the 40-complete-pair experiment-4 threshold")
    p.add_argument("--max-pair-attempts", type=int, default=None, help="separate guard including inconclusive pairs")
    p.add_argument(
        "--experimental-min-humansl-search-visits",
        type=int,
        default=40,
        help="explicit HumanSL-search visit floor for operator-run experiments (default: 40; minimum: 2)",
    )
    return p


def main() -> int:
    return asyncio.run(main_async(build_arg_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
