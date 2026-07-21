#!/usr/bin/env python3
"""Self-play strength assessment (operator-run): pit two of OUR OWN KataGo configs against
each other via the local /analyze engine, adjudicated by an impartial b28 referee. NO Golaxy,
NO token, NO daily budget -- pure self-assessment of how humanSL ranks scale with search.

Reuses the TESTED calibration primitives:
  * adapters query/identity -- builds the canonical ladder query and verifies the executed model
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
      --out superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/selfplay_v2_pikl

Each matchup is "A:B:games"; A wins are counted (from A's alternating color). Checkpoints per
matchup to selfplay_<A>__vs__<B>.jsonl (resumable -- a re-run skips finished games)."""
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
    pick_ladder_move,
    rung_strength_spec,
    validate_analysis_attestation,
)
from katrain.core.ladder_calibration import play_one_game, elo_from_winrate, GameOutcome  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("run_selfplay")

_RESULTS_DIR = Path(__file__).parent / "results"
DEFAULT_OUT_DIR = _RESULTS_DIR / "selfplay_v2_pikl"
LEGACY_OUT_DIR = _RESULTS_DIR / "selfplay"
_RANK_TOKEN = r"(?:[1-9]d|(?:[1-9]|1[0-9]|20)k)"
_RANK_PROFILE_RE = re.compile(rf"(?:rank|preaz)_{_RANK_TOKEN}(?:_{_RANK_TOKEN})?\Z")
_PROYEAR_PROFILE_RE = re.compile(r"proyear_([0-9]{4})\Z")
CHECKPOINT_SCHEMA = 2
SELECTION_ALGORITHM_VERSION = "selfplay-selection-v1"
SYMMETRY_SETTINGS = {"mode": "katago-default", "requested_symmetry": None}
OPENING_SUITE = {"id": "empty-board-v1", "seed": None}
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


class _MockKaTrainForConfig(KaTrainBase):
    """Config-only double: reads the SAME shipping engine block engine.py ships with."""


def _valid_humansl_profile(profile: str) -> bool:
    """Mirror KataGo SGFMetadata::getProfile's accepted named-profile ranges."""
    if _RANK_PROFILE_RE.fullmatch(profile):
        return True
    proyear = _PROYEAR_PROFILE_RE.fullmatch(profile)
    return proyear is not None and 1800 <= int(proyear.group(1)) <= 2023


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
    elif _valid_humansl_profile(prof):
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


def _json_value(value):
    """Convert frozen capability mappings to canonical JSON-compatible values."""
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _configuration_fingerprint(configuration: Mapping[str, object]) -> str:
    payload = json.dumps(_json_value(configuration), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
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
) -> dict:
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
                "http_effective_overrides": {
                    "model": "b28",
                    "reportAnalysisWinratesAs": "BLACK",
                },
                "identity": identities["referee"],
            },
            "adjudication_algorithm_version": ADJUDICATION_ALGORITHM_VERSION,
            "wide_root_noise": wide_root_noise,
            "symmetry_settings": SYMMETRY_SETTINGS,
            "opening_suite": OPENING_SUITE,
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
    for expected_ply, attestation in enumerate(attestations):
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
        "ts",
    }
    if not required_fields.issubset(record):
        raise ValueError("checkpoint game record is missing required fields")
    expected_color = "B" if expected_index % 2 == 0 else "W"
    if type(record.get("index")) is not int or record.get("index") != expected_index:
        raise ValueError("checkpoint game indices must be unique, ordered, and gap-free")
    if record.get("a_color") != expected_color or record.get("our_color") != expected_color:
        raise ValueError("checkpoint game color parity is invalid")
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
    expected_attested = num_moves + (1 if accepted_pass else 0)
    if record.get("attested_turn_count") != expected_attested:
        raise ValueError("checkpoint game attested turn count is inconsistent with its ending")


def _already_done(path: Path, fingerprint: str, configuration: Mapping[str, object]) -> int:
    if not path.is_file():
        return 0
    with path.open() as f:
        records = [json.loads(line) for line in f if line.strip()]
    if not records:
        raise ValueError("checkpoint exists without a schema-2 header")
    header = records[0]
    if header.get("record_type") != "header" or header.get("schema") != CHECKPOINT_SCHEMA:
        raise ValueError("checkpoint has no schema-2 header")
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
        f.write(json.dumps(header, sort_keys=True, ensure_ascii=False) + "\n")
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
    games: int,
    *,
    client: httpx.AsyncClient,
    base_url: str,
    wrn: float,
    out_dir: Path,
    capabilities: Mapping[str, object],
) -> dict:
    playerA = make_player(specA)
    playerB = make_player(specB)
    labelA, rungA, selA = playerA
    labelB, rungB, selB = playerB
    players = {"A": playerA, "B": playerB}
    identities = _preflight_capabilities(capabilities, players)
    configuration = _matchup_configuration(players, identities, capabilities=capabilities, wide_root_noise=wrn)
    fingerprint = _configuration_fingerprint(configuration)
    out_dir.mkdir(parents=True, exist_ok=True)
    ckpt = out_dir / f"selfplay_{_fname(labelA)}__vs__{_fname(labelB)}.jsonl"
    with _checkpoint_lock(ckpt):
        return await _run_matchup_checkpoint(
            labelA=labelA,
            rungA=rungA,
            selA=selA,
            labelB=labelB,
            rungB=rungB,
            selB=selB,
            games=games,
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
    games,
    client,
    base_url,
    wrn,
    capabilities,
    configuration,
    fingerprint,
    ckpt,
) -> dict:
    start = _prepare_checkpoint(ckpt, fingerprint, configuration)
    if games < start:
        raise ValueError(f"requested target {games} is smaller than existing checkpoint count {start}")
    winsA = conclusive = 0
    reason_counts: dict = {}
    if ckpt.is_file():  # fold prior games into the running totals (resume)
        with ckpt.open() as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                if rec.get("record_type") == "header":
                    continue
                if rec["conclusive"]:
                    conclusive += 1
                    winsA += 1 if rec["our_win"] else 0
                reason_counts[rec["result"]] = reason_counts.get(rec["result"], 0) + 1
    if start >= games:
        log.info("matchup %s vs %s: already have %d/%d, skipping", labelA, labelB, start, games)
    else:
        log.info("matchup %s vs %s: resuming at game %d/%d", labelA, labelB, start, games)

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
        for i in range(start, games):
            a_color = "B" if i % 2 == 0 else "W"  # alternate A's color for a fair B/W split
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
            )
            if outcome.conclusive:
                conclusive += 1
                winsA += 1 if outcome.our_win else 0
            reason_counts[outcome.result] = reason_counts.get(outcome.result, 0) + 1
            rec = {
                "record_type": "game",
                "fingerprint": fingerprint,
                "index": i,
                "player_a": labelA,
                "player_b": labelB,
                "a_color": a_color,
                **dataclasses.asdict(outcome),  # result/our_win(=A won)/num_moves/black_score/conclusive/end_reason
                "attested_turn_count": len(move_attestations),
                "move_attestations": move_attestations,
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
    p.add_argument("--out", default=str(DEFAULT_OUT_DIR), help="checkpoint dir")
    p.add_argument(
        "--wide-root-noise", type=float, default=None, help="override wideRootNoise (default: shipping config)"
    )
    return p


def main() -> int:
    return asyncio.run(main_async(build_arg_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
