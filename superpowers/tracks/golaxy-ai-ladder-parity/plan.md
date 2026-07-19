# Golaxy AI Ladder Parity — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 40-rung local-KataGo strength ladder whose rungs 1–39 match Golaxy (星阵) 39 levels by *measured* strength, driven by an explicit rung→engine-config table, calibrated by playing real games against Golaxy's genmove API; plus fix the Golaxy level data model (double-scale) it depends on.

**Architecture:** Two independent deliverables. **(A) Local ladder:** a new `LadderStrategy` (`ai:ladder`) reads a per-rung config (`katrain/core/ladder.py`) and injects `maxVisits` + `humanSLProfile` + humanSL search-bias params per game via a **non-persisted, fail-closed** session attribute (mirroring `platform_engine_color`), merged into strategy settings at `_do_ai_move` under `ai_lock` and sent through the existing `request_analysis(visits=…, extra_settings=…, time_limit=False)` seam — pure-visits, never touching global config. **(B) Golaxy remote table:** add `display_elo` + `ref_rank` columns to `GOLAXY_AI_LEVELS`. A calibration harness reuses the **same query-override construction and the same pure move-selection** as `LadderStrategy` (verified by a contract test), plays the shipping `engine_genmove` opponent, and **fails closed to "inconclusive" (never a win)** on every ambiguous outcome (unknown terminal, missing score, unsettled cap).

**Tech Stack:** Python 3.11 (backend, pytest, `httpx` + `httpx.MockTransport`), KataGo analysis engine over HTTP (b18c384nbt + human model @ `:8000`), React + TypeScript + MUI + Vitest (frontend).

## Global Constraints

- **Format:** `uv run black -l 120 katrain tests` before every commit (120-char lines).
- **Tests:** `CI=true uv run pytest tests` must stay green (CI skips GPU tests). New unit tests must pass under `CI=true` with **no live network** — all Golaxy/KataGo HTTP is mocked via `httpx.MockTransport`.
- **Layering:** `katrain/core/**` must NOT import from `katrain/web/**`. The ladder table + coordinate converters are self-contained in core; cross-consistency with the web `GOLAXY_AI_LEVELS` is enforced by a test, not an import.
- **Reproducible strength = pure visits.** `LadderStrategy` requests analysis with `time_limit=False` so strength = exactly `maxVisits` (hardware-independent, not truncated by `maxTime`). The calibration query must match (no `maxTime`).
- **No global-config mutation for per-game strength:** rung parameters are injected per-session/per-game only. Never `update_config("ai/…")` for rung params.
- **Fail closed, never fake:** an unresolved rung → the AI does not move (logged error), never silently rung 1. An ambiguous calibration outcome → `inconclusive`, excluded from Elo, never a win. A missing/non-finite score → `inconclusive`.
- **Golaxy wire safety by construction:** the calibration opponent function takes a `LadderRung` and reads `rung.golaxy_api_level` internally; it never accepts a raw level int. `display_elo` is structurally unreachable as a wire value.
- **Advertised metadata = shipping reality:** the `net` a rung exposes to API/UI equals the engine it actually plays on. v1 rung 40 = `b18` (b28 is a documented future ceiling, not exposed as `net`).
- **Coordinate frame is explicit + gold-standard tested:** ladder uses KaTrain-core `(col, row0)` bottom-left origin (row 0 = bottom); the Golaxy wire converter is defined and tested against the 10-move gold standard in `golaxy-protocol.md` §3. Do NOT route ladder moves through `katrain/web/platforms/golaxy/coords.py:katrain_to_golaxy` (its rows are top-anchored → vertical mirror).
- **i18n:** all new UI strings use `t('key','中文默认')`; Chinese default, never Japanese.

---

## Coordinate & Query Contracts (read before Tasks 1/3/8)

**Coordinate frame (single source of truth):**
- KaTrain-core move: `(col, row0)`, `col` 0..18 left→right, `row0` 0..18 **bottom→top** (row0=0 is the bottom edge; GTP label = `row0+1`). GTP columns skip `I`: `A..H,J..T`.
- Golaxy wire int: `coord = (bs-1-row0)*bs + col` (bs=19). Inverse: `col = coord % bs`, `row0 = bs-1 - coord//bs`.
- **Gold standard (from `golaxy-protocol.md` §3, must be asserted):** Q16→72, Q4→300, D4→288, D16→60, Q10→186, R6→263, D10→174, C6→249, K4→294, B4→286; corners A1→(bs-1)*bs+0=342, T19→0+18=18.

**Ladder analysis query (single builder, shared by runtime + harness):**
- Strength-relevant fields that BOTH paths must produce identically for a given (rung, position): `maxVisits` = `rung.max_visits`; `overrideSettings` = `{reportAnalysisWinratesAs:"BLACK", wideRootNoise:<engine cfg>, **rung humanSL overrides}` (humanSLProfile/ignorePreRootHistory/rootPolicyTemperature/humanSL bias); `rules`, `komi`, `boardXSize/Y`, `moves`, `includePolicy:true`; **no `maxTime`** (pure visits).
- Non-strength runtime-only fields (`priority`, ponder, `analyzeTurns`, `initialStones/Player`, `includeMovesOwnership`) are excluded from the contract — they do not affect which move is chosen at fixed visits. A contract test asserts the strength-relevant subset matches between the harness query and the runtime `build_analysis_query` output for the same node.

---

## File Structure

**New files:**
- `katrain/core/ladder.py` — `LadderRung`, `LADDER_RUNGS` (40, PROVISIONAL), `get_rung`, `rung_engine_params`, `ladder_override_settings`, `pick_ladder_move`, GTP + **Golaxy-wire** coord converters, `config_sanity_key`.
- `katrain/core/ladder_calibration.py` — pure: `elo_from_winrate`, `GameOutcome`, `play_one_game` (fail-closed, engine-agnostic).
- `tests/core/test_ladder.py`, `tests/core/test_ladder_strategy.py`, `tests/core/test_ladder_calibration.py`, `tests/web/test_ladder_injection.py`, `tests/platforms/test_golaxy_ladder_consistency.py`, `tests/platforms/test_golaxy_calibration_opponent.py`, `tests/platforms/test_ladder_query_contract.py`, `tests/core/test_bake_results.py`.
- `superpowers/tracks/golaxy-ai-ladder-parity/calibration/{__init__.py,adapters.py,run_calibration.py,run_smoke.py,bake_results.py,README.md}`.

**Modified files:**
- `katrain/core/constants.py` — add `AI_LADDER` + registry lists.
- `katrain/core/ai.py` — add `LadderStrategy`.
- `katrain/web/interface.py` — `WebKaTrain.__init__` `self.ladder_rung=None`; `_do_new_game(ladder_rung=None)` reset; `_do_ai_move` fail-closed merge.
- `katrain/web/server.py` — `new_game` thread + validate `ladder_rung` (422); `get_ai_constants` ladder default; `/api/ladder-rungs`.
- `katrain/web/models.py` — `NewGameRequest.ladder_rung: Optional[int]`.
- `katrain/config.json` — `"ai:ladder": {}` (empty; rung comes only from injection).
- `katrain/web/platforms/golaxy/engine_client.py` — `display_elo`+`ref_rank`.
- `tests/platforms/test_golaxy_engine_client.py` — key-set + double-scale checks.
- `katrain/web/ui/src/api.ts` — `EngineLevel` + `LadderRung` + `getLadderRungs`.
- `katrain/web/ui/src/galaxy/pages/AiSetupPage.tsx` — ladder opponent + rung selector.
- `katrain/web/ui/src/kiosk/pages/PlatformEngineSetupPage.tsx` — show `display_elo`/`ref_rank`.

---

# Phase P0 — Deliverable B: Golaxy remote double-scale

### Task B1: Add `display_elo` + `ref_rank` to `GOLAXY_AI_LEVELS`

**Files:**
- Modify: `katrain/web/platforms/golaxy/engine_client.py:519-559` (build `GOLAXY_AI_LEVELS` from a helper).
- Test: `tests/platforms/test_golaxy_engine_client.py:256-273` (`TestLevelTable`).

**Interfaces:**
- Produces: each row now has `{elo_score, level_name, name, goal_difference, timing, display_elo:int, ref_rank:str}`; `elo_score` unchanged (wire `level`).

- [ ] **Step 1: Failing test** — append to `TestLevelTable`:

```python
    def test_entries_have_double_scale_keys(self):
        for e in GOLAXY_AI_LEVELS:
            assert set(e.keys()) == {"elo_score","level_name","name","goal_difference","timing","display_elo","ref_rank"}
            assert isinstance(e["display_elo"], int) and isinstance(e["ref_rank"], str) and e["ref_rank"]

    def test_display_elo_scales(self):
        by = {e["level_name"]: e for e in GOLAXY_AI_LEVELS}
        assert by["5级"]["display_elo"] == 700 and by["准9段"]["display_elo"] == 2900  # middle == api
        assert by["6级"]["display_elo"] == 600 and by["18级"]["display_elo"] == -600   # bottom -100/step
        assert by["9段"]["display_elo"] == 3100 and by["星阵3星"]["display_elo"] == 4000 # top +300/step
```

- [ ] **Step 2: Run to verify fail** — `CI=true uv run pytest tests/platforms/test_golaxy_engine_client.py::TestLevelTable -v` → FAIL (`KeyError: display_elo`). Also mark the outdated `test_entries_have_required_keys` for replacement in Step 4.

- [ ] **Step 3: Implement** — replace the `GOLAXY_AI_LEVELS` literal (lines 519-559) with a builder. Keep the 39 rows/order/5 base values; append computed `display_elo`+`ref_rank`:

```python
_GOLAXY_ROWS = [
    (3300,"星阵3星","星猛虎",6,"60|60|3"),(3200,"星阵2星","星雄狮",6,"60|60|3"),(3100,"星阵1星","星巨象",6,"60|60|3"),
    (3000,"9段","星壮牛",5,"45|40|3"),(2900,"准9段","星蓝鲸",5,"45|40|3"),(2800,"8段","星美鹿",5,"45|40|3"),
    (2600,"准8段","星孤狼",5,"45|40|3"),(2500,"7段","星奇豚",4,"45|40|3"),(2400,"准7段","星萌猪",4,"45|40|3"),
    (2300,"6段","星骏马",4,"45|40|3"),(2200,"准6段","星呆羊",4,"45|40|3"),(2100,"5段","星跳鼠",4,"45|40|3"),
    (2000,"准5段","星云鹤",4,"40|30|3"),(1900,"4段","星灵狐",3,"40|30|3"),(1800,"准4段","星白鹭",3,"40|30|3"),
    (1700,"3段","星智狗",3,"40|30|3"),(1600,"准3段","星巧猫",3,"40|30|3"),(1500,"2段","星皮猴",3,"40|30|3"),
    (1400,"准2段","星乖兔",3,"40|30|3"),(1300,"1段","星树熊",3,"40|30|3"),(1200,"准1段","星长蛇",3,"40|30|3"),
    (1100,"1级","星铠虾",2,"30|30|3"),(1000,"2级","星夜鹰",2,"30|30|3"),(900,"3级","星憨鹅",2,"30|30|3"),
    (800,"4级","星刺头",2,"30|30|3"),(700,"5级","星黄鸭",2,"30|30|3"),(620,"6级","星轻燕",2,"30|30|3"),
    (540,"7级","星绿蛙",2,"30|30|3"),(460,"8级","星老龟",2,"30|30|3"),(380,"9级","星钳蟹",2,"30|30|3"),
    (300,"10级","星尾鱼",2,"30|30|3"),(290,"11级","星敏螳",2,"30|30|3"),(280,"12级","星鸣蝉",2,"30|30|3"),
    (270,"13级","星飞蜓",2,"30|30|3"),(260,"14级","星舞蝶",2,"30|30|3"),(250,"15级","星忙蜂",2,"30|30|3"),
    (240,"16级","星慢蜗",2,"30|30|3"),(230,"17级","星花虫",2,"30|30|3"),(220,"18级","星小蚁",2,"30|30|3"),
]
_DISPLAY_BOTTOM = {"6级":600,"7级":500,"8级":400,"9级":300,"10级":200,"11级":100,"12级":0,
                   "13级":-100,"14级":-200,"15级":-300,"16级":-400,"17级":-500,"18级":-600}
_DISPLAY_TOP = {"9段":3100,"星阵1星":3400,"星阵2星":3700,"星阵3星":4000}


def _display_elo(level_name, elo_score):
    if level_name in _DISPLAY_BOTTOM: return _DISPLAY_BOTTOM[level_name]
    if level_name in _DISPLAY_TOP: return _DISPLAY_TOP[level_name]
    return elo_score  # middle band 5级..准9段: identical (PRD §2)


def _ref_rank(level_name):
    # PROVISIONAL UI hint (Golaxy nominal runs strong; pro saturates to 野狐9D). Refined post-calibration.
    if level_name in ("星阵1星","星阵2星","星阵3星"): return "职业/野狐9D+"
    if level_name in ("9段","准9段","8段","准8段","7段","准7段"): return "野狐9D"
    return f"业余{level_name}"


GOLAXY_AI_LEVELS: list[dict] = [
    {"elo_score":elo,"level_name":n,"name":bot,"goal_difference":gd,"timing":t,
     "display_elo":_display_elo(n,elo),"ref_rank":_ref_rank(n)}
    for (elo,n,bot,gd,t) in _GOLAXY_ROWS
]
```

- [ ] **Step 4: Replace outdated assertion** — change `test_entries_have_required_keys` body to a subset check: `assert {"elo_score","level_name","name","goal_difference","timing"} <= set(e.keys())`.

- [ ] **Step 5: Run to verify pass** — `CI=true uv run pytest tests/platforms/test_golaxy_engine_client.py -v` → PASS (incl. unchanged `test_has_39_entries`, `test_strongest_first`, `test_get_level_1100_is_star_shrimp`).

- [ ] **Step 6: Format + commit**

```bash
uv run black -l 120 katrain/web/platforms/golaxy/engine_client.py tests/platforms/test_golaxy_engine_client.py
git add katrain/web/platforms/golaxy/engine_client.py tests/platforms/test_golaxy_engine_client.py
git commit -m "feat(golaxy): add display_elo + ref_rank double-scale to level table"
```

### Task B2: Frontend `EngineLevel` double-scale display

**Files:** Modify `katrain/web/ui/src/api.ts:99-105`; `katrain/web/ui/src/kiosk/pages/PlatformEngineSetupPage.tsx` (~327-352); test fixtures `PlatformEngineSetupPage.test.tsx` (+ `kiosk/__tests__/PlatformEngineSetupPage.test.tsx` if present).

- [ ] **Step 1: Extend `EngineLevel`** (`api.ts`): add `display_elo: number; ref_rank: string;` to the interface.
- [ ] **Step 2: Display** — subtitle → `` `${currentLevel.level_name} · 展示Elo ${currentLevel.display_elo} · ${currentLevel.ref_rank}` ``; dropdown `MenuItem` → `` `${l.name} · ${l.level_name} · 展示Elo ${l.display_elo}` ``.
- [ ] **Step 3: Fixtures** — add `display_elo`+`ref_rank` to every `mockLevels` row.
- [ ] **Step 4: Run** — `cd katrain/web/ui && npm test -- PlatformEngineSetupPage && npm run build && npm run build:kiosk-2d` → PASS + both builds green (shared `api.ts` + kiosk).
- [ ] **Step 5: Commit**

```bash
git add katrain/web/ui/src/api.ts katrain/web/ui/src/kiosk/pages/PlatformEngineSetupPage.tsx katrain/web/ui/src/kiosk/pages/PlatformEngineSetupPage.test.tsx
git commit -m "feat(golaxy-ui): show display_elo + ref_rank on engine level selector"
```

---

# Phase P1 — Ladder core, strategy, injection

### Task 1: `katrain/core/ladder.py` — model, table, coord converters, pure helpers

**Files:** Create `katrain/core/ladder.py`; Test `tests/core/test_ladder.py`.

**Interfaces (Produces):**
- `@dataclass(frozen=True) LadderRung(rung, golaxy_level_name, golaxy_api_level, display_elo, ref_rank, net, mechanism, human_sl_profile, max_visits, human_sl_params, backend_hint, root_policy_temperature)`.
- `LADDER_RUNGS: list[LadderRung]` (40; rung1=18级 … rung39=星阵3星; rung40 ceiling, `net='b18'`).
- `get_rung(n)`, `rung_engine_params(rung)->{"visits":int,"extra_settings":dict}`, `ladder_override_settings(rung)->dict`.
- `pick_ladder_move(analysis, board_size, mechanism)->(col,row0)|"pass"`; `gtp_to_colrow`/`colrow_to_gtp`; `colrow_to_golaxy(col,row0,bs)->int`, `golaxy_to_colrow(coord,bs)->(col,row0)`; `config_sanity_key(rung)->float` (NON-strict ordering; ties expected).

- [ ] **Step 1: Failing tests** — `tests/core/test_ladder.py`:

```python
import pytest
from katrain.core.ladder import (
    LADDER_RUNGS, get_rung, rung_engine_params, ladder_override_settings, pick_ladder_move,
    gtp_to_colrow, colrow_to_golaxy, golaxy_to_colrow, MECHANISMS,
)

WEAK_TO_STRONG = ["18级","17级","16级","15级","14级","13级","12级","11级","10级","9级","8级","7级","6级","5级",
    "4级","3级","2级","1级","准1段","1段","准2段","2段","准3段","3段","准4段","4段","准5段","5段",
    "准6段","6段","准7段","7段","准8段","8段","准9段","9段","星阵1星","星阵2星","星阵3星"]

def test_forty_rungs_map_weak_to_strong():
    assert len(LADDER_RUNGS) == 40 and [r.rung for r in LADDER_RUNGS] == list(range(1,41))
    assert [r.golaxy_level_name for r in LADDER_RUNGS[:39]] == WEAK_TO_STRONG

def test_rung_40_ceiling_net_b18():
    r = LADDER_RUNGS[39]
    assert r.golaxy_level_name is None and r.golaxy_api_level is None and r.net == "b18"

def test_all_rungs_net_b18_v1():
    # v1 ships every rung on the session's b18 engine; net must equal shipping reality.
    assert all(r.net == "b18" for r in LADDER_RUNGS)

def test_rung_engine_params_shape():
    for r in LADDER_RUNGS:
        p = rung_engine_params(r)
        assert p["visits"] == r.max_visits and "maxVisits" not in p["extra_settings"]
    r1 = get_rung(1)
    assert rung_engine_params(r1)["extra_settings"]["humanSLProfile"] == r1.human_sl_profile

def test_override_settings_forces_black_winrate_perspective():
    ov = ladder_override_settings(get_rung(1))
    assert ov["reportAnalysisWinratesAs"] == "BLACK"

# --- Golaxy wire coordinate converters: gold standard (golaxy-protocol.md §3) ---
@pytest.mark.parametrize("gtp,coord", [
    ("Q16",72),("Q4",300),("D4",288),("D16",60),("Q10",186),("R6",263),
    ("D10",174),("C6",249),("K4",294),("B4",286),("A1",342),("T19",18),
])
def test_golaxy_wire_gold_standard(gtp, coord):
    col, row0 = gtp_to_colrow(gtp, (19,19))
    assert colrow_to_golaxy(col, row0, 19) == coord
    assert golaxy_to_colrow(coord, 19) == (col, row0)   # exact inverse, no mirror

def test_golaxy_not_mirrored():
    # D4 and D16 must be DISTINCT wire ints (mirror bug would collide their handling)
    assert colrow_to_golaxy(*gtp_to_colrow("D4",(19,19)),19) != colrow_to_golaxy(*gtp_to_colrow("D16",(19,19)),19)

def test_pick_humansl_and_search():
    bs=(19,19)
    hp=[0.0]*(19*19+1); hp[(19-3-1)*19+3]=1.0   # (x=3,y=3)=D4
    assert pick_ladder_move({"humanPolicy":hp}, bs, "humansl") == (3,3)
    assert pick_ladder_move({"moveInfos":[{"move":"Q16","order":0}]}, bs, "net_search") == gtp_to_colrow("Q16",bs)
    assert pick_ladder_move({"moveInfos":[{"move":"pass","order":0}]}, bs, "net_search") == "pass"

def test_pick_fails_loud_no_cross_mechanism_fallback():
    from katrain.core.ladder import LadderMoveError
    bs=(19,19)
    # humansl rung with NO humanPolicy must NOT silently play a search move — it raises.
    with pytest.raises(LadderMoveError):
        pick_ladder_move({"moveInfos":[{"move":"Q16","order":0}]}, bs, "humansl")
    with pytest.raises(LadderMoveError):
        pick_ladder_move({"humanPolicy":[0.0]*(19*19+1)}, bs, "humansl")  # all-zero -> no valid dist
    with pytest.raises(LadderMoveError):
        pick_ladder_move({"humanPolicy":[0.1]*10}, bs, "humansl")          # wrong length
    with pytest.raises(LadderMoveError):
        pick_ladder_move({}, bs, "net_search")                             # empty moveInfos

def test_pick_search_malformed_entries_raise_not_crash():
    from katrain.core.ladder import LadderMoveError
    bs=(19,19)
    with pytest.raises(LadderMoveError):
        pick_ladder_move({"moveInfos":["not-a-dict"]}, bs, "net_search")       # non-dict entry (no AttributeError)
    with pytest.raises(LadderMoveError):
        pick_ladder_move({"moveInfos":[{"move":"II9","order":0}]}, bs, "net_search")  # invalid column
    with pytest.raises(LadderMoveError):
        pick_ladder_move({"moveInfos":[{"move":"Z99","order":0}]}, bs, "net_search")  # out-of-board
    with pytest.raises(LadderMoveError):
        pick_ladder_move({"moveInfos":[{"order":0}]}, bs, "net_search")        # missing move field
    with pytest.raises(LadderMoveError):
        pick_ladder_move({"moveInfos":[{"move":"Q16"}]}, bs, "net_search")     # missing order key
    with pytest.raises(LadderMoveError):
        pick_ladder_move({"moveInfos":[{"move":"Q16","order":True}]}, bs, "net_search")  # bool order (int subtype)
    with pytest.raises(LadderMoveError):
        pick_ladder_move({"moveInfos":[{"move":"Q16","order":-1}]}, bs, "net_search")    # negative order

def test_pick_search_any_malformed_entry_fails_closed_even_if_another_is_valid():
    # R6-H2/R7: ANY malformed entry must RAISE regardless of position — whether the malformed entry
    # is the min-order (selected) one OR a non-selected higher-order one. Covers shape, order, and
    # GTP/bounds malformations (the R7 case: valid order-0 + malformed-GTP order-1).
    from katrain.core.ladder import LadderMoveError
    bs=(19,19)
    bads = ["not-a-dict", {"order":0}, {"move":"Q16"}, {"move":"Q16","order":True},
            {"move":"Q16","order":-1}, {"move":"II9","order":0}, {"move":"Z99","order":0}]
    good0 = {"move":"D4","order":0}
    good1 = {"move":"D4","order":1}
    for bad in bads:
        with pytest.raises(LadderMoveError):
            pick_ladder_move({"moveInfos":[bad, good1]}, bs, "net_search")   # malformed is min-order
    # valid order-0 selected, malformed higher-order entry must STILL raise (R7 exact case)
    for bad_gtp in [{"move":"II9","order":1}, {"move":"Z99","order":1}, {"move":"Q16","order":True}]:
        with pytest.raises(LadderMoveError):
            pick_ladder_move({"moveInfos":[good0, bad_gtp]}, bs, "net_search")

def test_pick_non_dict_analysis_raises():
    from katrain.core.ladder import LadderMoveError
    bs=(19,19)
    for bad in [["a","list"], "a string", 42, None]:
        with pytest.raises(LadderMoveError):
            pick_ladder_move(bad, bs, "net_search")   # no AttributeError from .get on a non-dict
        with pytest.raises(LadderMoveError):
            pick_ladder_move(bad, bs, "humansl")
```

- [ ] **Step 2: Run to verify fail** — `CI=true uv run pytest tests/core/test_ladder.py -v` → FAIL (module missing).

- [ ] **Step 3: Implement `katrain/core/ladder.py`** — full module (layer-clean; no `katrain.web` import):

```python
"""Golaxy-parity strength ladder: 40 rungs of local-KataGo config + pure helpers
shared by LadderStrategy (runtime) and the calibration harness.

VALUES ARE PROVISIONAL (offline, PRD §6/§7); empirical calibration (P3b) overwrites
them. `config_sanity_key` is a config sanity check ONLY — ties between adjacent
same-profile rungs are EXPECTED and fine (PRD §2: adjacent Golaxy levels can have
near-identical real strength). True monotonicity comes from measured games, not
this key."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union

MECHANISMS = ("humansl", "humansl_search", "net_search")
_COLS = "ABCDEFGHJKLMNOPQRSTUVWXYZ"  # GTP columns, 'I' skipped


class LadderMoveError(Exception):
    """A rung's required analysis output is absent/malformed, so no certified move can be
    selected. Callers MUST NOT substitute an uncalibrated move: LadderStrategy converts this
    to LadderUnavailable (no move); the calibration harness converts it to an inconclusive game."""


@dataclass(frozen=True)
class LadderRung:
    rung: int
    golaxy_level_name: Optional[str]
    golaxy_api_level: Optional[int]   # eloScore = the `level` wire param (calibration only)
    display_elo: Optional[int]
    ref_rank: str
    net: str                          # v1: always 'b18' (== shipping engine)
    mechanism: str
    human_sl_profile: Optional[str]
    max_visits: int
    human_sl_params: Dict = field(default_factory=dict)
    backend_hint: str = "server"
    root_policy_temperature: float = 1.0


_GOLAXY_WEAK_TO_STRONG = [
    ("18级",220,-600,"业余18级"),("17级",230,-500,"业余17级"),("16级",240,-400,"业余16级"),
    ("15级",250,-300,"业余15级"),("14级",260,-200,"业余14级"),("13级",270,-100,"业余13级"),
    ("12级",280,0,"业余12级"),("11级",290,100,"业余11级"),("10级",300,200,"业余10级"),
    ("9级",380,300,"业余9级"),("8级",460,400,"业余8级"),("7级",540,500,"业余7级"),
    ("6级",620,600,"业余6级"),("5级",700,700,"业余5级"),("4级",800,800,"业余4级"),
    ("3级",900,900,"业余3级"),("2级",1000,1000,"业余2级"),("1级",1100,1100,"业余1级"),
    ("准1段",1200,1200,"业余1段"),("1段",1300,1300,"业余1段"),("准2段",1400,1400,"业余2段"),
    ("2段",1500,1500,"业余2段"),("准3段",1600,1600,"业余3段"),("3段",1700,1700,"业余3段"),
    ("准4段",1800,1800,"业余4段"),("4段",1900,1900,"业余4段"),("准5段",2000,2000,"业余5段"),
    ("5段",2100,2100,"业余5段"),("准6段",2200,2200,"业余6段"),("6段",2300,2300,"业余6段"),
    ("准7段",2400,2400,"野狐9D"),("7段",2500,2500,"野狐9D"),("准8段",2600,2600,"野狐9D"),
    ("8段",2800,2800,"野狐9D"),("准9段",2900,2900,"野狐9D"),("9段",3000,3100,"野狐9D"),
    ("星阵1星",3100,3400,"职业/野狐9D+"),("星阵2星",3200,3700,"职业/野狐9D+"),("星阵3星",3300,4000,"职业/野狐9D+"),
]

# Provisional humanSL profile per Golaxy level (kyu/amateur-dan bands, visits=1). Adjacent
# levels MAY share a profile (expected ties). PRD §7 anchors interpolated.
_KYU_PROFILE = {
    "18级":"rank_20k","17级":"rank_19k","16级":"rank_18k","15级":"rank_17k","14级":"rank_16k",
    "13级":"rank_15k","12级":"rank_14k","11级":"rank_13k","10级":"rank_12k","9级":"rank_11k",
    "8级":"rank_10k","7级":"rank_9k","6级":"rank_8k","5级":"rank_7k","4级":"rank_6k",
    "3级":"rank_5k","2级":"rank_4k","1级":"rank_3k",
}
_DAN_PROFILE = {
    "准1段":"rank_1d","1段":"rank_1d","准2段":"rank_2d","2段":"rank_2d","准3段":"rank_3d","3段":"rank_3d",
    "准4段":"rank_4d","4段":"rank_4d","准5段":"rank_5d","5段":"rank_5d","准6段":"rank_6d","6段":"rank_6d",
}
# High amateur / pro / super-pro: pure b18 search, increasing visits (strength-first).
_SEARCH_VISITS = {
    "准7段":8,"7段":12,"准8段":20,"8段":40,"准9段":80,"9段":140,"星阵1星":220,"星阵2星":350,"星阵3星":480,
}


def _band(name: str):
    if name in _KYU_PROFILE:
        temp = 1.1 if name in ("18级","17级","16级","15级") else 1.0
        return ("humansl", _KYU_PROFILE[name], 1, {}, temp)
    if name in _DAN_PROFILE:
        return ("humansl", _DAN_PROFILE[name], 1, {}, 1.0)
    return ("net_search", None, _SEARCH_VISITS[name], {}, 1.0)


def _build_ladder() -> List[LadderRung]:
    rungs = []
    for i, (name, api, disp, ref) in enumerate(_GOLAXY_WEAK_TO_STRONG):
        mech, prof, visits, params, temp = _band(name)
        rungs.append(LadderRung(i+1, name, api, disp, ref, "b18", mech, prof, visits, dict(params), "server", temp))
    # Rung 40: ceiling. v1 = b18@500 on the session engine (honest net='b18'). A true
    # b28@:8002 ceiling is a documented follow-up (calibration/README.md), NOT exposed as net.
    rungs.append(LadderRung(40, None, None, None, "最强", "b18", "net_search", None, 500, {}, "server", 1.0))
    return rungs


LADDER_RUNGS: List[LadderRung] = _build_ladder()
_BY_RUNG = {r.rung: r for r in LADDER_RUNGS}


def get_rung(n: int) -> LadderRung:
    if n not in _BY_RUNG:
        raise ValueError(f"rung out of range 1..40: {n!r}")
    return _BY_RUNG[n]


def ladder_override_settings(rung: LadderRung) -> Dict:
    """overrideSettings for a rung. Forces reportAnalysisWinratesAs=BLACK (matches the
    runtime engine + makes score/winrate black-relative for calibration scoring)."""
    ov: Dict = {"reportAnalysisWinratesAs": "BLACK"}
    if rung.human_sl_profile:
        ov["humanSLProfile"] = rung.human_sl_profile
        ov["ignorePreRootHistory"] = False
    if abs(rung.root_policy_temperature - 1.0) > 1e-9:
        ov["rootPolicyTemperature"] = rung.root_policy_temperature
    ov.update(rung.human_sl_params or {})
    return ov


def rung_engine_params(rung: LadderRung) -> Dict:
    """{'visits','extra_settings'}. visits -> top-level maxVisits; extra_settings ->
    overrideSettings. maxVisits is NEVER in extra_settings."""
    return {"visits": rung.max_visits, "extra_settings": ladder_override_settings(rung)}


def colrow_to_gtp(col: int, row0: int) -> str:
    return f"{_COLS[col]}{row0 + 1}"


def gtp_to_colrow(gtp: str, board_size: Tuple[int, int]) -> Union[Tuple[int, int], str]:
    g = gtp.strip().lower()
    if g in ("pass", "", "tt"):
        return "pass"
    return (_COLS.index(gtp[0].upper()), int(gtp[1:]) - 1)


def colrow_to_golaxy(col: int, row0: int, bs: int = 19) -> int:
    """KaTrain-core (col,row0 bottom-origin) -> Golaxy wire int. Gold-standard tested."""
    if not (0 <= col < bs and 0 <= row0 < bs):
        raise ValueError(f"colrow out of range for bs={bs}: ({col},{row0})")
    return (bs - 1 - row0) * bs + col


def golaxy_to_colrow(coord: int, bs: int = 19) -> Union[Tuple[int, int], str]:
    if not (0 <= coord < bs * bs):
        return "unknown"   # out-of-board wire value; caller treats as inconclusive terminal
    return (coord % bs, bs - 1 - coord // bs)


def _weighted_policy_pick(human_policy, board_size):
    from katrain.core.ai import weighted_selection_without_replacement
    bx, by = board_size
    moves = []
    for x in range(bx):
        for y in range(by):
            idx = (by - y - 1) * bx + x
            if idx < len(human_policy) and human_policy[idx] > 0:
                moves.append(((x, y), human_policy[idx]))
    if len(human_policy) > bx * by and human_policy[-1] > 0:
        moves.append(("pass", human_policy[-1]))
    if not moves:
        return "pass"
    return weighted_selection_without_replacement(moves, 1)[0][0]


def _valid_policy(hp, expected_len) -> bool:
    return (isinstance(hp, list) and len(hp) == expected_len
            and all(isinstance(v, (int, float)) and math.isfinite(v) for v in hp)
            and sum(v for v in hp if v > 0) > 0)


def _is_plain_int(x) -> bool:
    return type(x) is int   # excludes bool (a subclass of int) and float


def _validate_gtp_on_board(mv, board_size):
    """Parse a GTP move and bounds-check it, or raise LadderMoveError."""
    try:
        cr = gtp_to_colrow(mv, board_size)
    except (ValueError, IndexError, KeyError) as e:
        raise LadderMoveError(f"search mechanism: unparseable move {mv!r}: {e}") from e
    if cr != "pass":
        bx, by = board_size
        col, row0 = cr
        if not (0 <= col < bx and 0 <= row0 < by):
            raise LadderMoveError(f"search mechanism: out-of-board move {mv!r}")
    return cr


def _pick_search_move(analysis, board_size):
    infos = analysis.get("moveInfos")
    if not isinstance(infos, list) or not infos:
        raise LadderMoveError("search mechanism: missing/empty moveInfos")
    # FAIL CLOSED on ANY malformed entry — validate EVERY entry FULLY (shape + order + GTP parse +
    # board bounds) BEFORE selecting the min-order move. Do NOT skip a bad entry and select another,
    # and do NOT defer parse/bounds to only the selected entry (R6-H2/R7): a malformed non-selected
    # entry means the response is corrupt, so we must not play a "certified" move from it.
    for mi in infos:
        if not isinstance(mi, dict):
            raise LadderMoveError(f"search mechanism: non-dict moveInfo entry {mi!r}")
        mv, od = mi.get("move"), mi.get("order")
        if not (isinstance(mv, str) and mv):
            raise LadderMoveError(f"search mechanism: malformed move field {mv!r}")
        if not (_is_plain_int(od) and od >= 0):     # order must be present, plain int (not bool), >= 0
            raise LadderMoveError(f"search mechanism: malformed order {od!r}")
        _validate_gtp_on_board(mv, board_size)      # parse + bounds-check EVERY entry, not just best
    best = min(infos, key=lambda mi: mi["order"])
    return _validate_gtp_on_board(best["move"], board_size)  # already validated -> safe re-parse


def pick_ladder_move(analysis: Dict, board_size: Tuple[int, int], mechanism: str) -> Union[Tuple[int, int], str]:
    """Pure move selection shared by runtime + harness. (col,row0) bottom-origin, or 'pass'.
    Fails LOUD (LadderMoveError) when `analysis` is not a dict or the mechanism's required output
    is absent/malformed — NO silent cross-mechanism fallback (a degraded humanSL response must NOT
    become an uncalibrated 1-visit search move). Callers convert this to LadderUnavailable /
    inconclusive."""
    if not isinstance(analysis, dict):
        raise LadderMoveError(f"analysis is not a dict: {type(analysis).__name__}")
    bx, by = board_size
    if mechanism == "humansl":
        hp = analysis.get("humanPolicy")
        if not _valid_policy(hp, bx * by + 1):
            raise LadderMoveError("humansl mechanism: missing/malformed/empty humanPolicy")
        return _weighted_policy_pick(hp, board_size)
    return _pick_search_move(analysis, board_size)  # net_search / humansl_search use search output


def config_sanity_key(rung: LadderRung) -> float:
    """CONFIG sanity ordering (NON-strict; ties expected for same-profile rungs). NOT Elo."""
    if rung.mechanism == "humansl" and rung.human_sl_profile:
        tok = rung.human_sl_profile.split("_")[-1]
        base = -int(tok[:-1]) if tok.endswith("k") else int(tok[:-1])
        return base * 60.0 + math.log2(rung.max_visits) * 5.0 - (rung.root_policy_temperature - 1.0) * 20.0
    return 9 * 60.0 + math.log2(rung.max_visits) * 100.0
```

- [ ] **Step 4: Run to verify pass** — `CI=true uv run pytest tests/core/test_ladder.py -v` → PASS.

- [ ] **Step 5: Format + commit**

```bash
uv run black -l 120 katrain/core/ladder.py tests/core/test_ladder.py
git add katrain/core/ladder.py tests/core/test_ladder.py
git commit -m "feat(ladder): model, table, gold-standard Golaxy-wire coords, shared move-selection"
```

### Task 2: `AI_LADDER` constant + registry

**Files:** Modify `katrain/core/constants.py:55-100`. Test in `tests/core/test_ladder.py`.

- [ ] **Step 1: Failing test** — append:

```python
def test_ai_ladder_registered():
    from katrain.core import constants as C
    assert C.AI_LADDER == "ai:ladder"
    assert C.AI_LADDER in C.AI_STRATEGIES and C.AI_LADDER in C.AI_STRATEGIES_RECOMMENDED_ORDER and C.AI_LADDER in C.AI_STRENGTH
```

- [ ] **Step 2: Run → FAIL** (`AttributeError: AI_LADDER`).
- [ ] **Step 3: Implement** — after `AI_PRO = "ai:pro"` add `AI_LADDER = "ai:ladder"`; append `AI_LADDER` to `AI_STRATEGIES` (line 63); add `AI_LADDER,` after `AI_PRO,` in `AI_STRATEGIES_RECOMMENDED_ORDER`; add `AI_LADDER: float("nan"),` to `AI_STRENGTH`.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** — `uv run black -l 120 katrain/core/constants.py && git add -A && git commit -m "feat(ladder): register AI_LADDER constant"`.

### Task 3: `LadderStrategy` (fail-closed, pure-visits, shared query)

**Files:** Modify `katrain/core/ai.py` (add `LadderStrategy` after `HumanStyleStrategy` line 1807; add the `AI_LADDER` resignation exemption in `generate_ai_move` ~line 1820). Test `tests/core/test_ladder_strategy.py`.

**Interfaces:**
- Consumes: `get_rung`, `rung_engine_params`, `pick_ladder_move`, `colrow_to_gtp` (ladder); `engine.request_analysis(visits=…, extra_settings=…, time_limit=False, include_policy=True, callback, error_callback, priority)`.
- Produces: `@register_strategy(AI_LADDER) class LadderStrategy`. **Fail-closed:** raises `ValueError` if `self.settings` has no valid `rung`; raises `LadderUnavailable` on missing model / analysis failure / `LadderMoveError`. **Resignation parity:** `generate_ai_move` skips the generic `should_ai_resign` check for `AI_LADDER`, matching the harness (which never resigns our side).

- [ ] **Step 1: Failing tests** — `tests/core/test_ladder_strategy.py` (fake engine returns canned analysis; capture the query args):

```python
import pytest
from katrain.core.constants import AI_LADDER
from katrain.core.ai import STRATEGY_REGISTRY
from katrain.core.game import Move


class FakeEngine:
    def __init__(self, analysis, has_human_model=True, alive=True, call_back=True):
        self._a, self.has_human_model, self._alive, self._cb = analysis, has_human_model, alive, call_back
        self.last = {}
    def request_analysis(self, node, callback, error_callback=None, visits=None,
                         extra_settings=None, include_policy=True, priority=0, time_limit=True, **kw):
        self.last = {"visits": visits, "extra": extra_settings, "time_limit": time_limit}
        if self._cb:
            callback(self._a, False)          # deliver result; if False, never calls back (dead-worker sim)
    def check_alive(self, os_error="", exception_if_dead=False, **kw): return self._alive  # returns BOOL, never raises


class FakeNode:
    def __init__(self): self.player, self.next_player, self.policy_ranking = "B", "B", None


class FakeGame:
    def __init__(self, eng):
        self.board_size=(19,19); self.current_node=FakeNode(); self.engines={"B":eng,"W":eng}
        class _K:
            def log(self,*a,**k): pass
        self.katrain=_K()


def _mk(rung_val, analysis, hhm=True):
    eng = FakeEngine(analysis, hhm); s = STRATEGY_REGISTRY[AI_LADDER](FakeGame(eng), {"rung": rung_val}); return s, eng

def test_registered(): assert AI_LADDER in STRATEGY_REGISTRY

def test_humansl_rung_pure_visits_and_profile():
    hp=[0.0]*(19*19+1); hp[(19-3-1)*19+3]=1.0
    s,eng=_mk(1,{"humanPolicy":hp}); move,_=s.generate_move()
    assert eng.last["visits"]==1 and eng.last["time_limit"] is False
    assert eng.last["extra"]["humanSLProfile"]=="rank_20k" and eng.last["extra"]["reportAnalysisWinratesAs"]=="BLACK"
    assert move.gtp()=="D4"

def test_search_rung_high_visits_top_move():
    s,eng=_mk(39,{"moveInfos":[{"move":"Q16","order":0}]}); move,_=s.generate_move()
    assert eng.last["visits"]>=100 and eng.last["extra"].get("humanSLProfile") is None and move.gtp()=="Q16"

def test_missing_rung_fails_closed():
    s = STRATEGY_REGISTRY[AI_LADDER](FakeGame(FakeEngine({})), {})  # no 'rung'
    with pytest.raises(ValueError):
        s.generate_move()

def test_invalid_rung_fails_closed():
    s,_=_mk(999,{}) ;
    with pytest.raises(ValueError):
        s.generate_move()

def test_humansl_no_human_model_raises_unavailable():
    from katrain.core.ai import LadderUnavailable
    s,eng=_mk(1,{"moveInfos":[{"move":"Q16","order":0}]},hhm=False)
    with pytest.raises(LadderUnavailable):   # NO silent PolicyStrategy fallback (uncalibrated strength)
        s.generate_move()

def test_analysis_error_raises_unavailable():
    from katrain.core.ai import LadderUnavailable
    eng = FakeEngine({})
    def boom(node, callback, error_callback=None, **kw):
        error_callback("boom")
    eng.request_analysis = boom
    s = STRATEGY_REGISTRY[AI_LADDER](FakeGame(eng), {"rung": 1})
    with pytest.raises(LadderUnavailable):   # NO cached-top-policy fallback either
        s.generate_move()

def test_humansl_degraded_response_raises_unavailable():
    # humanSL rung 1 but response has NO humanPolicy (only moveInfos): must NOT play a search
    # move under the humanSL label -> LadderUnavailable (H2, no cross-mechanism fallback).
    from katrain.core.ai import LadderUnavailable
    s,eng=_mk(1,{"moveInfos":[{"move":"Q16","order":0}]})   # has_human_model True, but degraded output
    with pytest.raises(LadderUnavailable):
        s.generate_move()

def test_dead_engine_raises_unavailable_no_hang(monkeypatch):
    # Engine never calls back AND check_alive() -> False: LadderStrategy must raise promptly
    # (not spin forever holding ai_lock). Shrink the timeout so the deadline path is also covered.
    import katrain.core.ai as ai
    from katrain.core.ai import LadderUnavailable
    monkeypatch.setattr(ai, "LADDER_ANALYSIS_TIMEOUT_S", 0.2, raising=False)
    eng = FakeEngine({"moveInfos":[{"move":"Q16","order":0}]}, alive=False, call_back=False)
    s = STRATEGY_REGISTRY[AI_LADDER](FakeGame(eng), {"rung": 39})  # net_search, no human model needed
    with pytest.raises(LadderUnavailable):
        s.generate_move()

def test_empty_completed_analysis_raises_unavailable_no_hang():
    # Engine calls back with an EMPTY dict (falsy but COMPLETE): must NOT wait out the deadline —
    # the explicit `done` flag fires, then `not analysis` -> LadderUnavailable (M2).
    from katrain.core.ai import LadderUnavailable
    s,eng=_mk(39,{})    # net_search rung, callback delivers {} synchronously, alive=True
    with pytest.raises(LadderUnavailable):
        s.generate_move()
    assert eng.last["visits"] >= 100   # it DID issue the query, then failed closed on empty payload
```

- [ ] **Step 2: Run → FAIL** (`KeyError: 'ai:ladder'` / `ImportError: LadderUnavailable`).

- [ ] **Step 3: Implement `LadderStrategy`** — in `ai.py` after line 1807:

```python
class LadderUnavailable(Exception):
    """Raised when a ladder rung cannot be played at its certified strength (missing human
    model, or analysis failure). The caller must NOT play an uncalibrated fallback move —
    it fails closed (no move) so the '对标星阵' strength label is never silently violated."""


@register_strategy(AI_LADDER)
class LadderStrategy(AIStrategy):
    """Golaxy-parity ladder opponent. Fail-closed on every uncertainty: no valid rung ->
    ValueError; missing model / analysis error -> LadderUnavailable (NO PolicyStrategy or
    cached-top-policy fallback — those are uncalibrated and would silently mislabel
    strength). Pure-visits (time_limit=False) for hardware-independent strength. Shares
    rung_engine_params + pick_ladder_move with the calibration harness."""

    def generate_move(self) -> Tuple[Move, str]:
        from katrain.core.ladder import get_rung, rung_engine_params, pick_ladder_move, LadderMoveError

        if "rung" not in self.settings or self.settings.get("rung") is None:
            raise ValueError("LadderStrategy invoked without an injected rung (fail closed)")
        rung = get_rung(int(self.settings["rung"]))  # raises ValueError if out of range
        params = rung_engine_params(rung)
        engine = self.game.engines[self.cn.player]

        if rung.human_sl_profile is not None and not getattr(engine, "has_human_model", False):
            # Certified humanSL rung with no human model -> cannot reproduce strength. Fail closed.
            raise LadderUnavailable(f"rung {rung.rung} requires human model but engine has none")

        analysis, error, done = None, False, False

        def set_analysis(a, partial):
            nonlocal analysis, done
            if not partial:
                analysis = a
                done = True   # explicit completion flag: an empty/malformed dict is 'done' too (M2)

        def set_error(a):
            nonlocal error, done
            error = True
            done = True
            self.game.katrain.log(f"[LadderStrategy] analysis error: {a}", OUTPUT_ERROR)

        engine.request_analysis(
            self.cn, callback=set_analysis, error_callback=set_error, priority=PRIORITY_EXTRA_AI_QUERY,
            visits=params["visits"], include_policy=True, extra_settings=params["extra_settings"],
            time_limit=False,  # pure visits -> reproducible strength (not truncated by maxTime)
        )
        # Bounded wait keyed on the explicit `done` flag (NOT analysis truthiness — an empty dict is
        # falsy but complete). check_alive returns a BOOL (KataGoHttpEngine.check_alive does NOT raise
        # for a dead worker), so inspect it and enforce a deadline; otherwise a lost callback / dead
        # engine would spin while _do_ai_move holds ai_lock, blocking new-game (G3/H3/M2).
        deadline = time.monotonic() + LADDER_ANALYSIS_TIMEOUT_S
        while not done:
            time.sleep(0.01)
            if not engine.check_alive(exception_if_dead=False):
                raise LadderUnavailable(f"rung {rung.rung}: engine died during analysis")
            if time.monotonic() > deadline:
                raise LadderUnavailable(f"rung {rung.rung}: analysis timed out ({LADDER_ANALYSIS_TIMEOUT_S}s)")

        if error or not analysis:  # error, or completed with an empty/missing payload
            # No uncalibrated fallback — the ladder's whole value is the certified strength.
            raise LadderUnavailable(f"rung {rung.rung} analysis failed/empty; refusing uncalibrated fallback")

        try:
            picked = pick_ladder_move(analysis, self.game.board_size, rung.mechanism)
        except LadderMoveError as e:
            # e.g. a humanSL rung whose response lacks humanPolicy: do NOT play a search move.
            raise LadderUnavailable(f"rung {rung.rung}: {e}") from e
        move = Move(None, player=self.cn.next_player) if picked == "pass" else Move(picked, player=self.cn.next_player)
        return move, f"[LadderStrategy] rung {rung.rung} · 对标星阵{rung.golaxy_level_name or '最强'} · visits={params['visits']}"
```

Add `AI_LADDER` to the existing `from katrain.core.constants import (...)` block in `ai.py`, and a module constant `LADDER_ANALYSIS_TIMEOUT_S = 60` near the top of `ai.py` (rung-40 @ 500 visits on the GPU finishes in <5s; 60s is generous while bounding how long a hung engine can hold `ai_lock` and block new-game). **Engine-side follow-up (recommended):** make `KataGoHttpEngine` route a final `noResults`/malformed response to `error_callback` rather than silently not calling back, so this path fails in <1s instead of waiting out the deadline — but the explicit `done` flag + deadline above make LadderStrategy correct even without that change.

- [ ] **Step 3b: Exempt AI_LADDER from the generic pre-strategy resignation (runtime==harness parity)** — `generate_ai_move` (`ai.py:1810-1827`) calls `should_ai_resign(...)` and returns `None` (AI resigns via the GLOBAL config) BEFORE ever constructing the strategy. The calibration harness (`adapters.our_move`) has NO such path, so a shipped ladder game could resign from global/uncalibrated logic while calibration plays on — a behavioral drift the query contract can't catch (R6-H1). The ladder is a *strength-calibrated* opponent; its stopping is governed only by its own move-selection (pass), never by the generic resignation. Guard the resignation check so it is skipped for `AI_LADDER`:

```python
    resignation_settings = game.katrain.config("ai/resignation") or {}
    if ai_mode != AI_LADDER and should_ai_resign(game, resignation_settings):   # ladder never global-resigns
        ...
        return None
```

- [ ] **Step 3c: Parity test through `generate_ai_move` (not just the strategy)** — in `tests/core/test_ladder_strategy.py`, add a test that drives `generate_ai_move(game, AI_LADDER, {"rung": ...})` in a position/config where `should_ai_resign` WOULD trigger for a normal AI, and assert the ladder does NOT resign (no `end_state` set, a move is produced by `LadderStrategy`). This proves the shipped path matches the harness (which never resigns). Reuse the fake game/engine; stub `should_ai_resign` to return True to force the condition.

- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** — `uv run black -l 120 katrain/core/ai.py tests/core/test_ladder_strategy.py && git add -A && git commit -m "feat(ladder): fail-closed pure-visits LadderStrategy + resignation-exempt parity"`.

### Task 4: Per-game rung injection (fail-closed) + lifecycle safety

**Files:** Modify `katrain/web/interface.py` (`__init__`, `_do_new_game`, `_do_ai_move`); `katrain/web/models.py` (`NewGameRequest`); `katrain/web/server.py:749-767` (`new_game` handler + 422 validation); `katrain/config.json` (`"ai:ladder": {}`). Test `tests/web/test_ladder_injection.py`.

**Interfaces:**
- Produces: `WebKaTrain.ladder_rung: Optional[dict]` (`{"rung":int}`, non-persisted); `resolve_ladder_rung(n)` raises `ValueError` on invalid, returns `None` only for genuinely absent (`None`); `_do_ai_move` snapshots `(game, rung)` under `ai_lock` and passes the locals to `generate_ai_move` (so a concurrent new game cannot swap strength mid-generation), catches `LadderUnavailable` → no move, and **fails closed** if a ladder player has no rung; `_do_new_game` performs its game/rung/engine-color state swap **under the same `ai_lock`**; `/api/new-game` returns **422** on out-of-range `ladder_rung`.
- **Concurrency invariant (fixes the new-game vs AI-thread race):** the background AI thread (`_do_ai_move`) and REST-driven game replacement (`_do_new_game`) both mutate/read `self.game` + `self.ladder_rung`; they MUST be serialized by `ai_lock`. `session.lock` does not protect the background thread, so it is insufficient alone.

- [ ] **Step 1: Failing test** — `tests/web/test_ladder_injection.py`:

```python
import pytest
from katrain.web.interface import resolve_ladder_rung

def test_resolve_valid():
    s = resolve_ladder_rung(1); assert s == {"rung": 1}

def test_resolve_absent_is_none():
    assert resolve_ladder_rung(None) is None

def test_resolve_invalid_raises():
    with pytest.raises(ValueError):
        resolve_ladder_rung(0)
    with pytest.raises(ValueError):
        resolve_ladder_rung(41)
```

- [ ] **Step 2: Run → FAIL** (import error).

- [ ] **Step 3a: `resolve_ladder_rung` + init + reset** — in `katrain/web/interface.py`:

```python
def resolve_ladder_rung(n):
    """Validate a rung number. None -> None (absent). Invalid -> ValueError (caller 422s).
    Valid -> {'rung': int}. Never silently downgrades."""
    if n is None:
        return None
    from katrain.core.ladder import get_rung
    get_rung(int(n))  # raises ValueError if out of range 1..40
    return {"rung": int(n)}
```

`WebKaTrain.__init__` (next to `self.platform_engine_color = None`): `self.ladder_rung = None`.

`_do_new_game` (add `ladder_rung=None` param): wrap the **game/rung/engine-color state swap in `ai_lock`** so it cannot interleave with an in-flight AI generation. Concretely, the block that currently reads `self.platform_engine_color = None` (line 520) and creates the new `self.game` must run under the lock, and set the rung there too:

```python
        with self.ai_lock:
            self.platform_engine_color = None
            self.ladder_rung = resolve_ladder_rung(ladder_rung)
            # ... existing new-game state setup that assigns self.game ...
```

**This is the fix for both (a) the SGF-load / plain-new-game stale-rung clear** — any new-game path that does not pass a rung clears it, so a leftover ladder player then fails closed (Step 3b); **and (b) the new-game vs AI-thread race** — the swap of `self.game`+`self.ladder_rung` is now atomic w.r.t. `_do_ai_move`. (Verify `_do_new_game` is only ever called from the REST/handler thread, never re-entrantly from within a code path already holding `ai_lock`, to avoid self-deadlock — it is: the AI thread never starts a new game.)

- [ ] **Step 3b: `_do_ai_move` local snapshot + fail-closed + `LadderUnavailable` catch** — replace lines 935-947. Capture `game`/`rung` as locals under `ai_lock` and pass the local `game` to `generate_ai_move` (never re-read `self.game` mid-generation), and catch `LadderUnavailable` so a certified-strength failure yields NO move (not an uncalibrated one):

```python
                game = self.game                       # snapshot under ai_lock
                mode = self.next_player_info.strategy
                settings = self.config(f"ai/{mode}")
                if mode == AI_LADDER:
                    rung = getattr(self, "ladder_rung", None)
                    if not rung:
                        self.log("[ladder] ai:ladder player has no injected rung; refusing to move "
                                 "(fail closed).", OUTPUT_ERROR)
                        return
                    settings = {**(settings or {}), "rung": rung["rung"]}
                if settings is not None:
                    from katrain.core.ai import generate_ai_move, LadderUnavailable
                    try:
                        result = generate_ai_move(game, mode, settings)   # local `game`, not self.game
                    except LadderUnavailable as e:
                        self.log(f"[ladder] engine unavailable at certified strength; no move: {e}", OUTPUT_ERROR)
                        self._surface_ladder_unavailable()   # set a state flag the client can render
                        return
                    if result is None:
                        return
                    self.play_stone_sound()
```

Add `from katrain.core.constants import AI_LADDER` to interface.py imports. `_surface_ladder_unavailable()` sets a small session flag (e.g. `self.last_ladder_error = True`, cleared on next successful move / new game) included in `get_state()` so the frontend can show "对标星阵引擎暂不可用".

- [ ] **Step 3c: model + server + config** —
  - `katrain/web/models.py` `NewGameRequest`: add `ladder_rung: Optional[int] = None`.
  - `katrain/web/server.py` `new_game` handler (line 749): validate + thread:
    ```python
            if request.ladder_rung is not None:
                from katrain.core.ladder import get_rung
                try:
                    get_rung(int(request.ladder_rung))
                except (ValueError, TypeError):
                    raise HTTPException(status_code=422, detail=f"invalid ladder_rung: {request.ladder_rung}")
            ...
            session.katrain("new_game", size=request.size, handicap=request.handicap,
                            komi=request.komi, rules=request.rules, ladder_rung=request.ladder_rung)
    ```
    (Keep whatever kwargs the current call already passes; add `ladder_rung=`.)
  - `katrain/config.json`: add `"ai:ladder": {}` under `"ai"` (empty — so `self.config("ai/ai:ladder")` is non-None, but the *rung* only ever comes from injection; there is no `{"rung":1}` silent default).

- [ ] **Step 4: Run + lifecycle + fail-closed + concurrency tests** — extend `tests/web/test_ladder_injection.py` with `WebKaTrain`-level tests (reuse the web test harness) asserting:
  - (a) a new game with `ladder_rung=5` sets `self.ladder_rung=={"rung":5}`;
  - (b) a subsequent new game / `load_sgf` **without** a rung resets `self.ladder_rung` to `None`;
  - (c) with an `ai:ladder` player and `self.ladder_rung is None`, `_do_ai_move` logs the fail-closed error and does NOT play a move (assert node count unchanged);
  - (d) **`LadderUnavailable` → no move:** with an `ai:ladder` player + valid rung but an engine reporting `has_human_model=False` for a humanSL rung, `_do_ai_move` catches `LadderUnavailable`, plays no move, and sets the surfaced flag (assert node count unchanged + `get_state()` shows the flag);
  - (e) **concurrency (deterministic):** patch `generate_ai_move` with a hook that blocks on an `Event` mid-generation; on the AI thread start a generation at rung 5, then from the main thread call `_do_new_game(ladder_rung=20)`; release the hook; assert (i) `_do_new_game` blocked until the in-flight generation released the lock (game/rung swap serialized), and (ii) the completed move used rung 5's local snapshot (not 20) and landed on the old game, while `self.ladder_rung == {"rung":20}` and `self.game` is the new game. This proves the `ai_lock` serialization + local `(game,rung)` snapshot fix.

Run `CI=true uv run pytest tests/web/test_ladder_injection.py -v` → PASS, then `CI=true uv run pytest tests/web -q` → no regressions.

- [ ] **Step 5: Commit** — `uv run black -l 120 katrain/web/interface.py katrain/web/models.py katrain/web/server.py tests/web/test_ladder_injection.py && git add -A katrain/config.json && git commit -m "feat(ladder): fail-closed per-game rung injection + lifecycle reset + 422 validation"`.

### Task 5: `/api/ladder-rungs` + `ai:ladder` default

**Files:** Modify `katrain/web/server.py` (endpoint near `get_ai_constants` line 1583; `strategy_defaults`). Test appends to `tests/web/test_ladder_injection.py`.

- [ ] **Step 1: Failing test** —

```python
def test_ladder_rungs_endpoint(client):
    rungs = client.get("/api/ladder-rungs").json()["rungs"]
    assert len(rungs) == 40 and rungs[0]["golaxy_level_name"] == "18级" and rungs[38]["golaxy_level_name"] == "星阵3星"
    assert rungs[39]["golaxy_level_name"] is None
    assert all(r["net"] == "b18" for r in rungs)                 # honest net metadata
    assert "human_sl_profile" not in rungs[0] and "human_sl_params" not in rungs[0]

def test_ai_constants_ladder_default(client):
    assert client.get("/api/ai-constants").json()["strategy_defaults"]["ai:ladder"] == {}
```

- [ ] **Step 2: Run → FAIL (404).**
- [ ] **Step 3: Implement** — add `"ai:ladder": {},` to `strategy_defaults`; add:

```python
    @app.get("/api/ladder-rungs")
    def get_ladder_rungs():
        from katrain.core.ladder import LADDER_RUNGS
        return {"rungs": [
            {"rung": r.rung, "golaxy_level_name": r.golaxy_level_name, "display_elo": r.display_elo,
             "ref_rank": r.ref_rank, "net": r.net, "mechanism": r.mechanism}
            for r in LADDER_RUNGS
        ]}
```

- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** — `uv run black -l 120 katrain/web/server.py tests/web/test_ladder_injection.py && git add -A && git commit -m "feat(ladder): /api/ladder-rungs + ai:ladder default"`.

---

# Phase P2 — Provisional config sanity + cross-consistency (NOT strength proof)

### Task 6: Config-sanity guard + Golaxy cross-consistency

> **Framing (per adversarial review):** `config_sanity_key` is a **configuration sanity check only** — ties between adjacent same-profile rungs (e.g. 准1段/1段, both `rank_1d` visits=1) are **expected and correct** (PRD §2: adjacent Golaxy levels can be near-identical strength). This phase does NOT claim measured monotonic strength; that is established empirically in P3b with confidence intervals. We assert **non-decreasing** config key + document expected ties.

**Files:** Test `tests/core/test_ladder.py` (append) + new `tests/platforms/test_golaxy_ladder_consistency.py`.

- [ ] **Step 1: Tests** — append to `tests/core/test_ladder.py`:

```python
from katrain.core.ladder import config_sanity_key

def test_config_key_non_decreasing():
    keys = [config_sanity_key(r) for r in LADDER_RUNGS]
    for i in range(1, len(keys)):
        assert keys[i] >= keys[i-1] - 1e-9, (
            f"config regressed at rung {i+1} ({LADDER_RUNGS[i].golaxy_level_name})")

def test_expected_ties_documented():
    # Adjacent same-profile + same-visits rungs are EXPECTED to tie on the config key.
    by = {r.golaxy_level_name: r for r in LADDER_RUNGS}
    assert by["准1段"].human_sl_profile == by["1段"].human_sl_profile   # both rank_1d
    assert abs(config_sanity_key(by["准1段"]) - config_sanity_key(by["1段"])) < 1e-9  # tie, by design

def test_rung_40_max_key():
    assert config_sanity_key(LADDER_RUNGS[39]) == max(config_sanity_key(r) for r in LADDER_RUNGS)
```

New `tests/platforms/test_golaxy_ladder_consistency.py` (may import web):

```python
from katrain.core.ladder import LADDER_RUNGS
from katrain.web.platforms.golaxy.engine_client import GOLAXY_AI_LEVELS

def test_ladder_1_39_match_golaxy_levels():
    for rung, gx in zip(LADDER_RUNGS[:39], reversed(GOLAXY_AI_LEVELS)):
        assert (rung.golaxy_level_name, rung.golaxy_api_level, rung.display_elo, rung.ref_rank) == \
               (gx["level_name"], gx["elo_score"], gx["display_elo"], gx["ref_rank"])
```

- [ ] **Step 2: Run** — `CI=true uv run pytest tests/core/test_ladder.py tests/platforms/test_golaxy_ladder_consistency.py -v`. Expected PASS. **If the non-decreasing key fails**, fix the `_SEARCH_VISITS`/profile ordering in `ladder.py` (a genuine config bug); **do NOT** invent temperature/visit nudges purely to break legitimate ties. **If consistency fails**, reconcile `_GOLAXY_WEAK_TO_STRONG` (ladder) with `_display_elo`/`_ref_rank` (Task B1).

- [ ] **Step 3: Commit** — `uv run black -l 120 ... && git add -A && git commit -m "test(ladder): config-sanity (non-decreasing, ties allowed) + golaxy cross-consistency"`.

---

# Phase P3a — Calibration harness + smoke gate (fail-closed)

### Task 7: `katrain/core/ladder_calibration.py` — pure, fail-closed primitives

**Files:** Create `katrain/core/ladder_calibration.py`; Test `tests/core/test_ladder_calibration.py`.

**Interfaces (Produces):**
- `elo_from_winrate(wins:float, conclusive_games:int) -> (elo, lo95, hi95)`.
- `@dataclass GameOutcome(our_color, result, our_win, num_moves, black_score, conclusive, end_reason)` where `result ∈ {"our_win","our_loss","inconclusive_score","inconclusive_unsettled","inconclusive_engine","inconclusive_terminal"}` and `end_reason ∈ {"our_pass","golaxy_pass","golaxy_resign","golaxy_terminal","move_cap"}`.
- `async def play_one_game(*, our_move, golaxy_move, adjudicate, our_color, board_size=19, move_cap=400) -> GameOutcome`. `our_move(history)->int|"pass"|"unavailable"`; `golaxy_move(history)->int|"pass"|"resign"|"terminal"` (the adapter classifies the reply: a board coord → int; a coord matching a **smoke-verified** pass/resign code → `"pass"`/`"resign"`; any OTHER out-of-board value → `"terminal"` = UNVERIFIED/malformed); `adjudicate(history)->(black_score:Optional[float], settled:bool)`.
- **Only VERIFIED stops are trusted (fixes H1 both directions):**
  - our-side `"pass"` (our own trusted engine) → adjudicate → `settled` conclusive by score, else inconclusive.
  - Golaxy `"pass"` (smoke-verified) → adjudicate identically (symmetric with our-pass).
  - Golaxy `"resign"` (smoke-verified) → **conclusive `our_win`** (opponent conceded).
  - Golaxy `"terminal"` (UNVERIFIED out-of-board / malformed, e.g. `coord=99999`) → **`inconclusive_terminal`, NEVER adjudicated/scored** — a corrupted response must not enter Elo even if the position is coincidentally settled.
  - our `"unavailable"` (`LadderMoveError`) → `inconclusive_engine`.
  - `move_cap` → adjudicate.
- **v1 note:** pre-smoke, no verified pass/resign codes exist, so `golaxy_move` returns `"terminal"` for every stop → those games are inconclusive (safe; a KNOWN directional bias documented in Task 9). The smoke gate captures the codes; the real calibration (P3b) runs WITH them, so Golaxy resigns/passes are handled → unbiased. **The `history` holds ONLY valid Golaxy wire coords — no sentinel is ever appended.** Elo counts only conclusive games.

- [ ] **Step 1: Failing tests** — `tests/core/test_ladder_calibration.py`:

```python
import math, pytest
from katrain.core.ladder_calibration import elo_from_winrate, play_one_game

def test_elo_math():
    assert abs(elo_from_winrate(25,50)[0]) < 1e-6
    assert elo_from_winrate(40,50)[0] > 0 > elo_from_winrate(10,50)[0]
    assert math.isfinite(elo_from_winrate(50,50)[0])
    assert elo_from_winrate(0,0) == (0.0, float("-inf"), float("inf"))  # no conclusive games

@pytest.mark.asyncio
async def test_unverified_golaxy_terminal_never_scored_even_if_settled():
    """H1 (round 4): an UNVERIFIED out-of-board golaxy reply (e.g. coord=99999) is a possibly
    corrupted response — it must NEVER be adjudicated/counted, even in a coincidentally-settled
    position. It is inconclusive_terminal, not a win/loss."""
    async def our(m): return 0
    async def gx(m): return "terminal"           # adapter maps any unverified out-of-board coord here
    async def adj(m): return (5.0, True)         # settled + we'd be winning — still must NOT count
    r = await play_one_game(our_move=our, golaxy_move=gx, adjudicate=adj, our_color="B", move_cap=10)
    assert r.conclusive is False and r.result == "inconclusive_terminal" and r.our_win is False

@pytest.mark.asyncio
async def test_verified_golaxy_resign_is_our_win():
    async def our(m): return 0
    async def gx(m): return "resign"             # adapter recognized the smoke-verified resign code
    async def adj(m): return (-99.0, True)       # even if the raw position looks bad, resign = concede
    r = await play_one_game(our_move=our, golaxy_move=gx, adjudicate=adj, our_color="B", move_cap=10)
    assert r.conclusive and r.result == "our_win" and r.end_reason == "golaxy_resign"

@pytest.mark.asyncio
async def test_verified_golaxy_pass_adjudicates_like_our_pass():
    """Symmetry for VERIFIED stops: a smoke-verified golaxy pass adjudicates the same settled
    position identically to an our-pass."""
    async def adj(m): return (-5.0, True)        # white ahead, settled
    async def our_move(m): return 0
    async def gx_pass(m): return "pass"          # verified golaxy pass
    r = await play_one_game(our_move=our_move, golaxy_move=gx_pass, adjudicate=adj, our_color="W", move_cap=10)
    assert r.conclusive and r.result == "our_win" and r.end_reason == "golaxy_pass"  # W ahead -> our(W) win

@pytest.mark.asyncio
async def test_our_pass_unsettled_is_inconclusive():
    async def our(m): return "pass"
    async def gx(m): return 0
    async def adj(m): return (1.0, False)        # NOT settled -> inconclusive
    r = await play_one_game(our_move=our, golaxy_move=gx, adjudicate=adj, our_color="B", move_cap=10)
    assert r.conclusive is False and r.result == "inconclusive_unsettled" and r.our_win is False

@pytest.mark.asyncio
async def test_our_unavailable_is_inconclusive_engine():
    async def our(m): return "unavailable"     # rung couldn't produce a certified move
    async def gx(m): return 0
    async def adj(m): return (5.0, True)
    r = await play_one_game(our_move=our, golaxy_move=gx, adjudicate=adj, our_color="B", move_cap=10)
    assert r.conclusive is False and r.result == "inconclusive_engine"

@pytest.mark.asyncio
async def test_no_sentinel_ever_reaches_golaxy():
    """G1 regression: history passed to golaxy_move must contain only valid wire coords."""
    seen_histories = []
    calls = {"n": 0}
    async def our(m):
        calls["n"] += 1
        return 5 if calls["n"] <= 2 else "pass"   # two real moves, then pass
    async def gx(m):
        seen_histories.append(list(m))
        return 7
    async def adj(m): return (1.0, True)
    await play_one_game(our_move=our, golaxy_move=gx, adjudicate=adj, our_color="B", board_size=19, move_cap=10)
    for h in seen_histories:
        assert all(isinstance(c, int) and 0 <= c < 19 * 19 for c in h)  # no -1 / sentinel / invalid

@pytest.mark.asyncio
async def test_unsettled_cap_is_inconclusive():
    async def mv(m): return 0
    async def adj(m): return (2.0, False)   # not settled
    r = await play_one_game(our_move=mv, golaxy_move=mv, adjudicate=adj, our_color="B", move_cap=4)
    assert r.conclusive is False and r.result == "inconclusive_unsettled"

@pytest.mark.asyncio
async def test_missing_score_is_inconclusive():
    async def our(m): return "pass"
    async def gx(m): return 0
    async def adj(m): return (None, True)
    r = await play_one_game(our_move=our, golaxy_move=gx, adjudicate=adj, our_color="B", move_cap=10)
    assert r.conclusive is False and r.result == "inconclusive_score"
```

- [ ] **Step 2: Run → FAIL** (module missing). (Confirm `pytest-asyncio` is available — `tests/platforms/test_golaxy_engine_client.py` already runs `async def test_...`; match that config.)

- [ ] **Step 3: Implement `katrain/core/ladder_calibration.py`**

```python
"""Pure calibration primitives: fail-closed engine-agnostic game loop + Elo math. No
network, no engine coupling. Ambiguous outcomes -> inconclusive (never a win)."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Awaitable, Callable, List, Optional, Tuple, Union

MoveVal = Union[int, str]  # our_move: int|"pass"|"unavailable"; golaxy_move: int|"pass"|"resign"|"terminal"


def elo_from_winrate(wins: float, conclusive_games: int) -> Tuple[float, float, float]:
    if conclusive_games <= 0:
        return (0.0, float("-inf"), float("inf"))
    p = wins / conclusive_games
    eps = 1.0 / (2 * conclusive_games + 2)
    def elo(x):
        x = min(1 - 1e-9, max(1e-9, x)); return -400.0 * math.log10(1.0 / x - 1.0)
    pc = min(1 - eps, max(eps, p))
    se = math.sqrt(max(pc * (1 - pc), eps) / conclusive_games)
    return (elo(pc), elo(min(1 - eps, max(eps, pc - 1.96 * se))), elo(min(1 - eps, max(eps, pc + 1.96 * se))))


@dataclass
class GameOutcome:
    our_color: str
    result: str          # our_win|our_loss|inconclusive_score|inconclusive_unsettled|inconclusive_engine|inconclusive_terminal
    our_win: bool
    num_moves: int
    black_score: Optional[float]
    conclusive: bool
    end_reason: str = "move_cap"   # our_pass | golaxy_pass | golaxy_resign | golaxy_terminal | move_cap


async def play_one_game(
    *,
    our_move: Callable[[List[int]], Awaitable[MoveVal]],
    golaxy_move: Callable[[List[int]], Awaitable[MoveVal]],
    adjudicate: Callable[[List[int]], Awaitable[Tuple[Optional[float], bool]]],
    our_color: str,
    board_size: int = 19,
    move_cap: int = 400,
) -> GameOutcome:
    """Alternate our engine & Golaxy on a shared history of ONLY valid Golaxy wire coords
    (NO sentinel ever appended; G1). Trust only VERIFIED stops (H1): our-'pass' and a
    smoke-verified golaxy-'pass' adjudicate; a verified golaxy-'resign' is our win; an
    UNVERIFIED golaxy-'terminal' (out-of-board/malformed) is inconclusive_terminal — never
    scored. our-'unavailable' -> inconclusive_engine. move_cap -> adjudicate."""
    history: List[int] = []   # valid Golaxy wire coords only
    to_play = "B"
    end_reason = "move_cap"

    for _ in range(move_cap):
        is_our_turn = to_play == our_color
        val = await (our_move if is_our_turn else golaxy_move)(history)
        if val == "unavailable":               # our_move only: no certified move -> inconclusive
            return GameOutcome(our_color, "inconclusive_engine", False, len(history), None, False, "our_pass")
        if val == "resign":                    # golaxy_move only, VERIFIED: opponent conceded -> our win
            return GameOutcome(our_color, "our_win", True, len(history), None, True, "golaxy_resign")
        if val == "terminal":                  # golaxy_move only, UNVERIFIED/malformed -> never scored
            return GameOutcome(our_color, "inconclusive_terminal", False, len(history), None, False, "golaxy_terminal")
        if val == "pass":                      # our-pass (trusted) OR golaxy verified-pass -> adjudicate
            end_reason = "our_pass" if is_our_turn else "golaxy_pass"
            break
        history.append(int(val))               # guaranteed a real wire coord
        to_play = "W" if to_play == "B" else "B"

    black_score, settled = await adjudicate(history)
    if black_score is None or not math.isfinite(black_score):
        return GameOutcome(our_color, "inconclusive_score", False, len(history), None, False, end_reason)
    if not settled:
        return GameOutcome(our_color, "inconclusive_unsettled", False, len(history), black_score, False, end_reason)
    winner = "B" if black_score > 0 else "W"
    our_win = winner == our_color
    return GameOutcome(our_color, "our_win" if our_win else "our_loss", our_win, len(history), black_score, True, end_reason)
```

- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Commit** — `uv run black -l 120 katrain/core/ladder_calibration.py tests/core/test_ladder_calibration.py && git add -A && git commit -m "feat(calibration): fail-closed game loop + elo math (conclusive-only)"`.

### Task 8: Real-engine adapters + shared-query contract + typed opponent

**Files:** Create `superpowers/tracks/golaxy-ai-ladder-parity/calibration/{__init__.py,adapters.py,run_calibration.py}`. Tests `tests/platforms/test_golaxy_calibration_opponent.py`, `tests/platforms/test_ladder_query_contract.py`.

**Interfaces (Produces in `adapters.py`):**
- `build_ladder_analysis_query(moves_golaxy, rung, board_size, komi, rules, wide_root_noise) -> dict` — the shared strength-relevant query (maxVisits + `ladder_override_settings(rung)` + wideRootNoise; **no maxTime**).
- `async def our_move(client, base_url, moves_golaxy, rung, board_size, komi, rules, wide_root_noise) -> int|"pass"|"unavailable"` — `"unavailable"` when `pick_ladder_move` raises `LadderMoveError` (degraded/malformed analysis; no cross-mechanism fallback).
- `load_engine_wide_root_noise(engine_config) -> float` — the CLI reads wideRootNoise from the shipping engine config and passes it in (never the hard-coded default).
- `async def golaxy_move(client, moves_golaxy, rung, token, board_size, komi, rule, pass_code=None, resign_code=None) -> int|"pass"|"resign"|"terminal"` — reads `rung.golaxy_api_level` internally (typed; never a raw int); rejects a rung whose api level is not a real wire level; classifies the reply against smoke-verified `pass_code`/`resign_code` (None pre-smoke → every out-of-board reply is `"terminal"`).
- `async def adjudicate(client, base_url, moves_golaxy, board_size, komi, rules, visits) -> (black_score|None, settled)` — `reportAnalysisWinratesAs:BLACK` → black-relative `scoreLead`; missing/non-finite → `(None, False)`; settled iff endgame criteria met.

- [ ] **Step 1: Failing tests** — `tests/platforms/test_golaxy_calibration_opponent.py`:

```python
import sys, importlib
from pathlib import Path
import httpx, pytest
sys.path.insert(0, str(Path(__file__).parents[2] / "superpowers/tracks/golaxy-ai-ladder-parity/calibration"))
adapters = importlib.import_module("adapters")
from katrain.core.ladder import get_rung, LadderRung

TOKEN = "tok"
def mk(h): return httpx.AsyncClient(transport=httpx.MockTransport(h))

def test_golaxy_move_takes_rung_not_raw_int():
    # signature must not accept a bare level int -> display_elo can't be passed as wire
    import inspect
    sig = inspect.signature(adapters.golaxy_move)
    assert "rung" in sig.parameters and "level" not in sig.parameters

def test_display_elo_unreachable_as_wire():
    # a rung's display_elo (e.g. 4000 for 星阵3星) is never used as the wire level
    r = get_rung(39)  # 星阵3星: api_level 3300, display_elo 4000
    assert r.golaxy_api_level == 3300 and r.display_elo == 4000

@pytest.mark.asyncio
async def test_golaxy_move_decodes_and_rejects_bad_api_level():
    seen = {}
    def h(req):
        seen["url"] = str(req.url)
        return httpx.Response(200, json={"code":"0","msg":"","data":{"coord":72,"prob":0.2}})
    val = await adapters.golaxy_move(mk(h), moves_golaxy=[], rung=get_rung(18), token=TOKEN)  # 1级=1100
    assert isinstance(val, int) and "level=1100" in seen["url"]
    bad = LadderRung(1,"x",4000,4000,"",  "b18","net_search",None,1,{},"server",1.0)  # api_level=4000 (a display Elo)
    with pytest.raises(Exception):
        await adapters.golaxy_move(mk(h), moves_golaxy=[], rung=bad, token=TOKEN)

@pytest.mark.asyncio
async def test_golaxy_move_unknown_coord_is_terminal():
    def h(req): return httpx.Response(200, json={"code":"0","msg":"","data":{"coord":99999,"prob":0.0}})
    # pre-smoke (no codes): any out-of-board reply is UNVERIFIED "terminal", never scored
    assert await adapters.golaxy_move(mk(h), moves_golaxy=[], rung=get_rung(18), token=TOKEN) == "terminal"

@pytest.mark.asyncio
async def test_golaxy_move_classifies_verified_pass_and_resign():
    def h(req): return httpx.Response(200, json={"code":"0","msg":"","data":{"coord":361,"prob":0.0}})
    # smoke-verified codes: 361 (out-of-board on 19x19) == pass here
    assert await adapters.golaxy_move(mk(h), moves_golaxy=[], rung=get_rung(18), token=TOKEN, pass_code=361) == "pass"
    def h2(req): return httpx.Response(200, json={"code":"0","msg":"","data":{"coord":-1,"prob":0.0}})
    assert await adapters.golaxy_move(mk(h2), moves_golaxy=[], rung=get_rung(18), token=TOKEN, resign_code=-1) == "resign"

@pytest.mark.asyncio
async def test_invalid_sentinels_never_score_ordinary_replies():
    # An IN-BOARD 'code' (e.g. 100) must be rejected so a normal move (coord 100) is NOT misread as
    # resign/pass. And equal pass==resign codes are ambiguous -> both dropped (R5-H2).
    def h(req): return httpx.Response(200, json={"code":"0","msg":"","data":{"coord":100,"prob":0.5}})
    assert await adapters.golaxy_move(mk(h), moves_golaxy=[], rung=get_rung(18), token=TOKEN,
                                      resign_code=100) == 100          # in-board resign_code dropped -> plain move
    def h2(req): return httpx.Response(200, json={"code":"0","msg":"","data":{"coord":361,"prob":0.0}})
    assert await adapters.golaxy_move(mk(h2), moves_golaxy=[], rung=get_rung(18), token=TOKEN,
                                      pass_code=361, resign_code=361) == "terminal"  # equal -> neither trusted

@pytest.mark.asyncio
async def test_our_move_sends_shared_query_and_returns_gold_wire():
    seen = {}
    def h(req):
        import json; seen["body"] = json.loads(req.content)
        hp=[0.0]*(19*19+1); hp[(19-3-1)*19+3]=1.0   # D4
        return httpx.Response(200, json={"humanPolicy":hp})
    val = await adapters.our_move(mk(h), "http://x:8000", moves_golaxy=[], rung=get_rung(1),
                                  board_size=19, komi=7.5, rules="chinese")
    assert seen["body"]["maxVisits"] == 1
    assert seen["body"]["overrideSettings"]["humanSLProfile"] == "rank_20k"
    assert seen["body"]["overrideSettings"]["reportAnalysisWinratesAs"] == "BLACK"
    assert "maxTime" not in seen["body"]
    assert val == 288   # D4 gold-standard wire (proves no mirror)

@pytest.mark.asyncio
async def test_our_move_degraded_humansl_returns_unavailable():
    # humanSL rung 1 but response lacks humanPolicy -> our_move must return "unavailable"
    # (NOT a silent search move). The harness turns this into inconclusive_engine.
    def h(req): return httpx.Response(200, json={"moveInfos":[{"move":"Q16","order":0}]})
    val = await adapters.our_move(mk(h), "http://x:8000", moves_golaxy=[], rung=get_rung(1))
    assert val == "unavailable"

@pytest.mark.asyncio
async def test_adjudicate_missing_score_inconclusive():
    def h(req): return httpx.Response(200, json={"rootInfo":{}})
    score, settled = await adapters.adjudicate(mk(h), "http://x:8000", moves_golaxy=[288], visits=50)
    assert score is None and settled is False

def test_load_engine_wide_root_noise_from_config():
    assert adapters.load_engine_wide_root_noise({"wide_root_noise": 0.07, "max_visits": 50}) == 0.07
```

And the contract test `tests/platforms/test_ladder_query_contract.py` — this builds a **REAL `GameNode` history** (via the standard `Game`/`Move` API used across `tests/test_board.py`) and calls `build_analysis_query` **on a REAL `KataGoHttpEngine` instance** (worker thread stubbed out, no network) so its `override_settings`/`config` come from the ACTUAL engine `__init__` — a future change to `KataGoHttpEngine.override_settings` is reflected here, so drift can't pass silently (R5-M1). Asserts EXACT strength-subset equality vs the harness query across humanSL / temperature / net_search rungs, plus a regression proving an injected extra runtime override makes the contract FAIL:

```python
import sys, importlib
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parents[2] / "superpowers/tracks/golaxy-ai-ladder-parity/calibration"))
adapters = importlib.import_module("adapters")
from katrain.core.base_katrain import KaTrainBase
from katrain.core.engine import KataGoHttpEngine
from katrain.core.game import Game, Move
from katrain.core.game_node import GameNode
from katrain.core.ladder import get_rung, rung_engine_params


class _MockKaTrain(KaTrainBase):
    pass


class _MockEngine:
    def request_analysis(self, *a, **k):
        pass


class _NoStartHttpEngine(KataGoHttpEngine):
    """REAL KataGoHttpEngine __init__ (so override_settings/config are the genuine values), but
    start() is stubbed so no worker thread / network is created. This is the drift-sensitive
    runtime double."""
    def start(self):
        pass


def _runtime_engine(wide_root_noise):
    kt = _MockKaTrain(force_package_config=True)
    cfg = dict(kt.config("engine"))          # the REAL engine config block from config.json
    cfg["wide_root_noise"] = wide_root_noise
    return _NoStartHttpEngine(kt, cfg)


def _real_current_node(moves):  # moves: list[(player, gtp)]
    # RU=chinese so node.ruleset == "chinese" -> runtime rules == get_rules("chinese") == harness rules
    game = Game(_MockKaTrain(force_package_config=True), _MockEngine(),
                move_tree=GameNode(properties={"SZ": 19, "RU": "chinese", "KM": 7.5}))
    for player, gtp in moves:
        game.play(Move.from_gtp(gtp, player=player))
    return game.current_node


def _runtime_query(engine, rung, node):
    params = rung_engine_params(rung)
    query, _visits = engine.build_analysis_query(   # real builder on a real engine; real (query, visits)
        node, visits=params["visits"], extra_settings=params["extra_settings"], time_limit=False,
    )
    return query


def _strength_subset_matches(rung, engine, wrn):
    node = _real_current_node([("B", "D4"), ("W", "Q4")])
    runtime = _runtime_query(engine, rung, node)
    harness = adapters.build_ladder_analysis_query([288, 300], rung, 19, 7.5, "chinese", wide_root_noise=wrn)
    return (harness["maxVisits"] == runtime["maxVisits"] == rung_engine_params(rung)["visits"]
            and harness["overrideSettings"] == runtime["overrideSettings"]   # EXACT dict equality
            and harness["moves"] == runtime["moves"]
            and (harness["komi"], harness["boardXSize"], harness["boardYSize"], harness["rules"])
                == (runtime["komi"], runtime["boardXSize"], runtime["boardYSize"], runtime["rules"])
            and "maxTime" not in runtime["overrideSettings"] and "maxTime" not in harness["overrideSettings"])


@pytest.mark.parametrize("rung_n", [20, 1, 32])  # 20=1段 humansl; 1=18级 humansl+temp(1.1); 32=7段 net_search
def test_harness_query_equals_runtime_strength_subset(rung_n):
    """Exact-equality parity vs a REAL KataGoHttpEngine's build_analysis_query, across the three
    mechanism/knob classes. wideRootNoise from ONE source (the real engine config)."""
    eng = _runtime_engine(0.04)
    wrn = adapters.load_engine_wide_root_noise(eng.config)   # single shared source (the real config)
    rung = get_rung(rung_n)
    assert _strength_subset_matches(rung, eng, wrn)
    # sanity: humanSL rungs carry the profile; net_search does not
    q = _runtime_query(eng, rung, _real_current_node([("B","D4"),("W","Q4")]))
    if rung.human_sl_profile:
        assert q["overrideSettings"]["humanSLProfile"] == rung.human_sl_profile
    else:
        assert "humanSLProfile" not in q["overrideSettings"]


def test_contract_fails_on_runtime_override_drift():
    """If a future engine adds an override the harness doesn't replicate, the contract MUST break.
    Proves the test actually guards drift (not just passes against a duplicated double)."""
    eng = _runtime_engine(0.04)
    eng.override_settings = {**eng.override_settings, "someFutureKnob": 1}  # simulate runtime drift
    assert not _strength_subset_matches(get_rung(20), eng, 0.04)   # harness lacks the knob -> mismatch
```

> **Note:** exact `overrideSettings` equality against a REAL engine instance is what proves parity — if `KataGoHttpEngine.__init__` ever sets an additional override, `test_contract_fails_on_runtime_override_drift`-style divergence surfaces in the main test and forces `ladder_override_settings` to be updated in lockstep. If constructing `_NoStartHttpEngine` still touches the network in `super().__init__` on some platform, also stub `HttpEngineStatus`/`start` as needed — the REAL `override_settings` assignment (engine.py:548) is the one thing that must remain genuine.

- [ ] **Step 2: Run → FAIL** (module missing).

- [ ] **Step 3: Implement `adapters.py`**

```python
"""Calibration adapters: shared ladder query + typed Golaxy opponent + black-relative
scoring. Injected httpx.AsyncClient (MockTransport in tests). Imports katrain.*; nothing
imports this. Golaxy wire uses ladder.colrow_to_golaxy (gold-standard tested), NOT
web/platforms/golaxy/coords (top-anchored -> mirror)."""
from __future__ import annotations

import math
from typing import List, Optional, Tuple, Union

import httpx

from katrain.core.engine import BaseEngine  # for get_rules: send the SAME normalized rules as runtime
from katrain.core.ladder import (
    LadderRung, rung_engine_params, ladder_override_settings, pick_ladder_move,
    colrow_to_gtp, colrow_to_golaxy, golaxy_to_colrow, LadderMoveError,
)
from katrain.web.platforms.golaxy.engine_client import engine_genmove, GOLAXY_AI_LEVELS

_VALID_WIRE = {row["elo_score"] for row in GOLAXY_AI_LEVELS}  # only real api levels; excludes display_elo


def _assert_real_wire_level(level: int) -> None:
    if level not in _VALID_WIRE:
        raise ValueError(f"refusing to send non-wire level {level!r} (not a GOLAXY_AI_LEVELS elo_score; "
                         f"never send display_elo)")


def _golaxy_history_to_gtp(moves_golaxy: List[int], bs: int) -> list:
    out = []
    for i, c in enumerate(moves_golaxy):
        dec = golaxy_to_colrow(c, bs)
        player = "B" if i % 2 == 0 else "W"
        out.append([player, colrow_to_gtp(dec[0], dec[1]) if dec != "unknown" else "pass"])
    return out


def build_ladder_analysis_query(moves_golaxy, rung: LadderRung, board_size, komi, rules, wide_root_noise) -> dict:
    """Shared strength-relevant query (contract-tested vs the REAL runtime builder). `rules`
    is a ruleset NAME (e.g. 'chinese'); it is normalized via the SAME BaseEngine.get_rules the
    runtime uses, so the emitted `rules` value is byte-identical. No maxTime (pure visits)."""
    ov = dict(ladder_override_settings(rung))
    ov["wideRootNoise"] = wide_root_noise
    moves = _golaxy_history_to_gtp(moves_golaxy, board_size)
    return {
        "rules": BaseEngine.get_rules(rules), "komi": komi, "boardXSize": board_size, "boardYSize": board_size,
        "moves": moves, "analyzeTurns": [len(moves)], "maxVisits": rung_engine_params(rung)["visits"],
        "includePolicy": True, "includeOwnership": False, "overrideSettings": ov,
    }


async def our_move(client, base_url, moves_golaxy, rung: LadderRung, board_size=19, komi=7.5,
                   rules="chinese", wide_root_noise=0.04) -> Union[int, str]:
    q = build_ladder_analysis_query(moves_golaxy, rung, board_size, komi, rules, wide_root_noise)
    r = await client.post(f"{base_url}/analyze", json=q, timeout=httpx.Timeout(180.0, connect=10.0))
    r.raise_for_status()
    try:
        picked = pick_ladder_move(r.json(), (board_size, board_size), rung.mechanism)
    except LadderMoveError:
        return "unavailable"   # certified move not derivable -> harness marks the game inconclusive_engine
    if picked == "pass":
        return "pass"
    return colrow_to_golaxy(picked[0], picked[1], board_size)


def load_engine_wide_root_noise(engine_config: dict) -> float:
    """Read wideRootNoise from the SAME shipping engine config the runtime uses (config.json's
    `engine.wide_root_noise`). run_calibration passes this into our_move — never the hard-coded
    default — so calibration and production can never use different values (G2)."""
    return float(engine_config["wide_root_noise"])


def _valid_sentinels(pass_code, resign_code, board_size):
    """Return (pass_code, resign_code) keeping only values that are plain ints, OUT of the board
    range [0, bs*bs), and DISTINCT from each other. Anything else -> None (so it can never turn an
    ordinary reply into a scored resign/pass). Guards R5-H2: equal or in-board codes are rejected."""
    n = board_size * board_size
    def ok(c):
        return type(c) is int and not (0 <= c < n)
    p = pass_code if ok(pass_code) else None
    r = resign_code if ok(resign_code) else None
    if p is not None and r is not None and p == r:      # ambiguous -> trust neither
        return (None, None)
    return (p, r)


async def golaxy_move(client, moves_golaxy, rung: LadderRung, token, board_size=19, komi=7.5,
                      rule="chinese", pass_code=None, resign_code=None) -> Union[int, str]:
    """Classify Golaxy's reply. A board coord -> int. A coord matching a SMOKE-VERIFIED, VALIDATED
    (out-of-board, distinct) resign/pass code -> 'resign'/'pass'. Any OTHER out-of-board value ->
    'terminal' (UNVERIFIED/malformed) — the harness never scores those (H1). Codes are None until
    smoke captures them (Task 9); invalid codes are dropped by _valid_sentinels, so pre-smoke (and
    on any misconfig) every stop is 'terminal' (safe). resign is checked before pass."""
    level = rung.golaxy_api_level
    _assert_real_wire_level(level)                      # display_elo structurally unreachable
    pass_code, resign_code = _valid_sentinels(pass_code, resign_code, board_size)
    res = await engine_genmove(client, moves=moves_golaxy, level=level, access_token=token,
                               komi=komi, rule=rule, board_size=board_size)
    if resign_code is not None and res.coord == resign_code:
        return "resign"
    if pass_code is not None and res.coord == pass_code:
        return "pass"
    if golaxy_to_colrow(res.coord, board_size) == "unknown":
        return "terminal"                               # unverified out-of-board -> inconclusive upstream
    return res.coord


async def adjudicate(client, base_url, moves_golaxy, board_size=19, komi=7.5, rules="chinese",
                     visits=200) -> Tuple[Optional[float], bool]:
    """Black-relative final score via reportAnalysisWinratesAs=BLACK. Missing/non-finite ->
    (None, False). `settled` requires a low-uncertainty endgame (see criteria)."""
    q = {
        "rules": BaseEngine.get_rules(rules), "komi": komi, "boardXSize": board_size, "boardYSize": board_size,
        "moves": _golaxy_history_to_gtp(moves_golaxy, board_size), "analyzeTurns": [len(moves_golaxy)],
        "maxVisits": visits, "includeOwnership": True, "includePolicy": False,
        "overrideSettings": {"reportAnalysisWinratesAs": "BLACK"},
    }
    r = await client.post(f"{base_url}/analyze", json=q, timeout=httpx.Timeout(180.0, connect=10.0))
    r.raise_for_status()
    a = r.json()
    root = a.get("rootInfo") or {}
    lead = root.get("scoreLead")
    if lead is None or not isinstance(lead, (int, float)) or not math.isfinite(lead):
        return (None, False)
    return (float(lead), _is_settled(a, board_size, lead))


def _is_settled(analysis: dict, board_size: int, lead: float) -> bool:
    """Conservative endgame check (G5). Requires: (1) ownership array present with EXACTLY
    board_size**2 finite entries; (2) >=98% of points decisively owned (|own|>0.9); (3) the
    undecided margin cannot flip the winner — the count of undecided points (which could each
    swing ~2 pts) is comfortably smaller than the current lead. Anything else -> NOT settled
    (caller records inconclusive_unsettled). A separate score-stability re-check (re-analyze
    at higher visits, assert |Δ scoreLead| < 1.0) is applied by run_calibration before trusting
    a move-cap game; two-natural-pass games are inherently more trustworthy."""
    own = analysis.get("ownership")
    n = board_size * board_size
    if not isinstance(own, list) or len(own) != n or not all(isinstance(o, (int, float)) and math.isfinite(o) for o in own):
        return False
    undecided = sum(1 for o in own if abs(o) <= 0.9)
    if undecided / n > 0.02:            # <98% decisive -> live fight/dame remains
        return False
    # undecided points could each swing ~2 points; require the lead to dominate that swing.
    if abs(lead) <= 2.0 * undecided + 1.0:
        return False
    return True
```

> **Verify against live `:8000` during smoke (Task 9):** (a) `/analyze` accepts this minimal body and returns `humanPolicy`/`moveInfos`/`rootInfo`/`ownership` with `len(ownership)==board_size**2`; (b) with `reportAnalysisWinratesAs:BLACK`, `scoreLead` is black-relative (matches the runtime engine's own forced setting; confirm and adjust only if the live server disagrees); (c) tune the 98%/lead-margin thresholds from real smoke endgames. Leave a TODO until confirmed. **`run_calibration` must additionally apply the score-stability re-check to any move-cap (non-two-pass) game before counting it conclusive.**

- [ ] **Step 4: Implement `run_calibration.py`** — CLI (NOT CI-tested): args `--anchors "rung:games,..." --throttle --base-url --token-env --out [--wide-root-noise]`. **Source `wide_root_noise` from the live engine** (query `:8000` config / `/health`, or require the flag to match the deployed engine config) and pass it into `adapters.our_move` — never rely on the hard-coded 0.04 default (G2: calibration must use the shipping engine's actual setting). Loads token from env/redacted file (never commit tokens). Per anchor plays `games` (half each color) via `play_one_game(our_move=partial(adapters.our_move, client, base_url, rung=get_rung(r), wide_root_noise=wrn), golaxy_move=partial(adapters.golaxy_move, gx_client, rung=get_rung(r), token=token, pass_code=PASS_CODE, resign_code=RESIGN_CODE), adjudicate=partial(adapters.adjudicate, client, base_url), our_color=...)`, where `PASS_CODE`/`RESIGN_CODE` are read from the smoke report (Task 9). If the smoke run did NOT capture them (both None), log a prominent WARNING that Golaxy resigns/passes will be inconclusive (a directional bias that UNDER-counts our wins) and record the golaxy-terminal rate per anchor so the operator can judge whether the bias is material before trusting the numbers. **For any game NOT ended by a verified two-pass (i.e. `end_reason` in {`move_cap`,`golaxy_terminal`}, and — until a two-pass encoding is confirmed — also `our_pass`), before counting it conclusive, re-run `adjudicate` at higher visits and require `|Δ scoreLead| < 1.0`; otherwise mark inconclusive** (G5 stability re-check; applies symmetrically to whichever side stopped). **Checkpoint each game to `results/<anchor>.jsonl`** (resume skips finished indices); throttle + `AuthExpired`-refresh; summary via `elo_from_winrate(wins, conclusive)` recording `conclusive/total` + inconclusive-reason counts.

- [ ] **Step 5: Run adapter + contract tests → PASS** — `CI=true uv run pytest tests/platforms/test_golaxy_calibration_opponent.py tests/platforms/test_ladder_query_contract.py -v`.

- [ ] **Step 6: Commit** — `uv run black -l 120 superpowers/tracks/golaxy-ai-ladder-parity/calibration tests/platforms/test_golaxy_calibration_opponent.py tests/platforms/test_ladder_query_contract.py && git add -A && git commit -m "feat(calibration): typed opponent, shared-query contract, black-relative scoring"`.

### Task 9: `run_smoke.py` — probe pass/resign encoding + level re-verify + 10-game gate

**Files:** Create `.../calibration/run_smoke.py`; write `.../calibration/README.md`. Test appends to `tests/platforms/test_golaxy_calibration_opponent.py`.

**Interfaces:** `run_smoke.py` writes `results/smoke_report.json`: `{level_probes:[{level,level_name,coord,ok,elapsed_s,error}], games:[...], per_move_timing, per_anchor_golaxy_terminal_rate, errors, pass_code:null, resign_code:null}` (the two codes are filled by the manual browser capture, Step 5b). `probe_level(client, rung, token)` (uses `rung.golaxy_api_level`; times one genmove; catches `Retryable/Fatal/QuotaExhausted` into the record).

- [ ] **Step 1: Failing test** —

```python
@pytest.mark.asyncio
async def test_smoke_probe_records(monkeypatch):
    import importlib
    smoke = importlib.import_module("run_smoke")
    def h(req): return httpx.Response(200, json={"code":"0","msg":"","data":{"coord":72,"prob":0.2}})
    rec = await smoke.probe_level(mk(h), rung=get_rung(18), token=TOKEN)  # 1级
    assert rec["ok"] and rec["coord"] == 72 and rec["elapsed_s"] >= 0
```

- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement `run_smoke.py`** with:
  - `probe_level(client, rung, token)` — time one genmove at `rung.golaxy_api_level`; record coord/ok/error/elapsed; catch errors into the record (no crash). Probes rungs for 18级/12级/1级/9段/星阵3星 (api 220/280/1100/3000/3300).
  - `main()` — level probes → ~10 games at 2 anchors (rung 18=1级, rung 28=5段) via `play_one_game`; record per-move `time.monotonic()` deltas (esp. strong levels vs the 180s ceiling); tally the per-anchor **golaxy-terminal rate** (how often golaxy returns an unverified out-of-board reply — this sizes the pre-code selection bias); write `smoke_report.json` including `pass_code`/`resign_code` (filled by the manual capture below, else null).
  - **NOTE — no API pass/resign probe:** you cannot elicit a Golaxy pass/resign via genmove, because the `history` only holds board coords and the pass/resign wire encoding is exactly the unknown. Sentinel capture is a **manual browser step** (Step 5b), not an API call.
- [ ] **Step 4: Run smoke unit test → PASS.**
- [ ] **Step 5: Write `README.md`** — obtain token (existing platform-adapter login OR paste browser `access_token` into `GOLAXY_TOKEN`, with redaction reminder); dev engine = prod HTTP `:8000` (`has_human_model:true`, verify `/health`); how to run smoke.
- [ ] **Step 5b: Manual pass/resign sentinel capture (browser)** — document the executable procedure: log into 19x19.com, start a 人机 game, open DevTools and hook `XMLHttpRequest` on `/genmove` (the same method that reverse-engineered the protocol; see `golaxy-protocol.md` §6), then (a) **pass** in the UI and record the exact `data.coord` Golaxy returns/accepts for a pass, and (b) **resign** and record its coord (or confirm resign is a separate control, not a genmove reply). Redact the token; write `pass_code`/`resign_code` into `smoke_report.json`. Then feed them to `run_calibration`. **Validation is enforced in code (`_valid_sentinels`): only distinct out-of-board ints are honored; anything else is ignored (treated as terminal).**
- [ ] **Step 5c: go/no-go criteria (README):** (1) all 5 level probes `code=0`, no `7003` on genmove; (2) strong-level per-move time within tolerance; (3) ~10 games complete, no quota errors; (4) `scoreLead` confirmed black-relative under `reportAnalysisWinratesAs:BLACK`; (5) **either** `pass_code`+`resign_code` captured & validated, **or** the per-anchor golaxy-terminal rate is ~0 so exclusion is immaterial. **If neither (5) holds, P3b must NOT draw parity conclusions from affected anchors** — unverified terminals may be passes from positions favorable to either side, so excluding them is selection bias of **unknown direction**, not a mere under-count.
- [ ] **Step 6: Commit** — `uv run black -l 120 ... && git add -A && git commit -m "feat(calibration): smoke gate (pass/resign probe + level re-verify + timing)"`.
- [ ] **Step 7: OPERATOR RUN (gated; needs live token — user runs)**

```bash
GOLAXY_TOKEN=<redacted> uv run python superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_smoke.py \
  --base-url http://localhost:8000 --out superpowers/tracks/golaxy-ai-ladder-parity/calibration/results
```
Review `smoke_report.json` against the criteria. **STOP; report results to the user before P3b.** Commit the token-free report.

---

# Phase P3b — Full empirical calibration (operator-gated on smoke)

### Task 10: `bake_results.py` (measured Elo, per-band, tie/reversal-aware) + runbook

> **Framing (per adversarial review):** measured Elo per rung/adjacent-group with confidence intervals is the ONLY source of the shipped strength labels. Indistinguishable (overlapping CI) and reversed rungs are **detected and documented/merged**, never fake-distinguished. Correction is **per-band** (kyu / amateur-dan / pro / super-pro), never a single global line.

**Files:** Create `.../calibration/bake_results.py`; Modify `katrain/core/ladder.py` (values + `LADDER_VERSION`, via bake output). Test `tests/core/test_bake_results.py`.

**Interfaces:** `banded_correction(anchors) -> per-band {offset,slope}`; `apply_corrections(rungs, corr) -> new configs`; `classify_pairs(measured_elos_with_ci) -> {"ok","tie","reversed"}` (adjacent-rung status); `LADDER_VERSION` bump.

- [ ] **Step 1: Failing tests** — `tests/core/test_bake_results.py`:

```python
import sys, importlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / ".." / "superpowers/tracks/golaxy-ai-ladder-parity/calibration"))
bake = importlib.import_module("bake_results")

def test_correction_is_per_band():
    corr = bake.banded_correction([
        {"band":"kyu","rung":12,"elo_diff":+120},
        {"band":"amateur","rung":28,"elo_diff":-80},
        {"band":"super","rung":39,"elo_diff":+30},
    ])
    assert corr["kyu"]["offset"] != corr["amateur"]["offset"]

def test_classify_tie_and_reversal():
    # overlapping CIs -> tie; strictly lower-with-gap despite higher label -> reversed
    st = bake.classify_pairs([
        {"rung":1,"elo":0,"lo":-60,"hi":60},
        {"rung":2,"elo":10,"lo":-50,"hi":70},   # overlaps rung1 -> tie
        {"rung":3,"elo":-200,"lo":-260,"hi":-140}, # below, no overlap -> reversed
    ])
    assert st[(1,2)] == "tie" and st[(2,3)] == "reversed"
```

- [ ] **Step 2: Run → FAIL.**
- [ ] **Step 3: Implement `bake_results.py`** — per-band offset+slope fit over the 7 anchors, applied locally; re-derive non-anchor rung visits (search band) / profile (kyu band) toward corrected targets; `classify_pairs` from measured Elo±CI; re-run `config_sanity_key` non-decreasing check; print new table values + `LADDER_VERSION`. **Never** a single global linear fit; **never** fabricate distinctions for tied rungs — record them as documented ties.
- [ ] **Step 4: Run → PASS.**
- [ ] **Step 5: Runbook** (`README.md`): **HARD PRE-GATE — parity conclusions require trustworthy terminals:** for each anchor, either (a) validated `pass_code`+`resign_code` are in effect, or (b) that anchor's golaxy-terminal rate is ~0. An anchor failing BOTH is marked **untrusted** — its win rate must NOT be used to bake/label rungs (the excluded terminals are a selection bias of unknown direction). Then: 7 anchors (7级/540, 1级/1100, 1段/1300, 5段/2100, 9段/3000, 星阵1星/3100, 星阵3星/3300) × ~50 games (half color); resume/throttle/refresh; `bake_results.py` → paste anchored values into `ladder.py` (`LADDER_VERSION` bump) → re-run `tests/core/test_ladder.py` + consistency → spot-check 3–4 non-anchor rungs → record per-band tolerances (deep kyu ±1.5 段, mid kyu ±1 段), documented ties/reversals, per-anchor SC2 pass/fail (win rate ∈ [40,60] over conclusive games), and each anchor's trusted/untrusted status + golaxy-terminal rate.
- [ ] **Step 6: Commit code** — `uv run black -l 120 ... && git add -A && git commit -m "feat(calibration): measured-Elo banded bake with tie/reversal handling"`.
- [ ] **Step 7: OPERATOR RUN (gated on smoke go — user runs, hours)** — run full calibration → bake → update `ladder.py` → re-guard → spot-check → report SC2 + ties/reversals to the user; commit anchored `ladder.py` + token-free logs.

---

# Phase P4 — UI: 40-rung "对标星阵" selector

### Task 11: `AiSetupPage` ladder opponent + rung selector

**Files:** Modify `katrain/web/ui/src/api.ts`; `katrain/web/ui/src/galaxy/pages/AiSetupPage.tsx`; test `AiSetupPage.test.tsx`.

- [ ] **Step 1: API + type** — `api.ts`: add `LadderRung` (`{rung, golaxy_level_name:string|null, display_elo:number|null, ref_rank, net, mechanism}`) + `getLadderRungs()` (GET `/api/ladder-rungs`).
- [ ] **Step 2: Wire selector** —
  - State `ladderRungs`, `ladderRung` (default 18 = 1级); fetch in the constants `useEffect`.
  - `getStrategyDisplay` map: `'ladder': t('ai:golaxy_parity','对标星阵')` (so it labels in the opponent Select; it's in `AI_STRATEGIES_RECOMMENDED_ORDER` from Task 2).
  - When `opponent === 'ai:ladder'`: render a rung Select over `ladderRungs`, label `${r.golaxy_level_name ?? '最强'} · 对标星阵 · 展示Elo ${r.display_elo ?? '—'}`; suppress the human-rank slider + generic settings panel.
  - `handleStartGame`: `const isLadder = opponent === 'ai:ladder';` pass `...(isLadder ? { ladder_rung: ladderRung } : {})` into `API.newGame(...)`; skip the `human_kyu_rank`/strategySettings config writes when `isLadder`.
- [ ] **Step 3: Failing test** — `AiSetupPage.test.tsx`: mock `getAIConstants` (incl. `ai:ladder`), `getLadderRungs`, `newGame`; select ladder opponent, pick a rung, click Start; assert `API.newGame` called with `ladder_rung`. (Follow `PlatformEngineSetupPage.test.tsx`'s Vitest/RTL pattern.)
- [ ] **Step 4: Run + both builds** — `cd katrain/web/ui && npm test -- AiSetupPage && npm run build && npm run build:kiosk-2d` → PASS + green.
- [ ] **Step 5: Commit** — `git add ... && git commit -m "feat(ladder-ui): 对标星阵 40-rung opponent selector"`.

### Task 12: End-to-end verification (dev → prod `:8000` human model)

- [ ] **Step 1:** Set dev `engine.backend='http'`, `engine.http_url='http://<prod>:8000'`; verify `/health` → `has_human_model:true`. Document in `README.md`.
- [ ] **Step 2:** Start web UI, pick "对标星阵" @ 1级, play a few moves; grep server KataGo query log to confirm the query carried `humanSLProfile` + `maxVisits` + no `maxTime` (SC3).
- [ ] **Step 3:** Full suite `CI=true uv run pytest tests -q` → PASS.
- [ ] **Step 4:** Commit doc updates.

---

## Success Criteria (revised)

- **SC1:** 40-rung table exists, versioned (`LADDER_VERSION`); config-sanity non-decreasing (ties allowed/documented). **Measured** strength non-decreasing within CI after P3b; ties/reversals explicitly documented (not fake-distinguished).
- **SC2:** 7 anchors measured vs Golaxy: win rate ∈ [40%,60%] over **conclusive** games; spot-checks same. Inconclusive + golaxy-terminal rate recorded per anchor. **A parity conclusion is only valid for an anchor that is "trusted"** — either validated `pass_code`+`resign_code` are in effect, or that anchor's golaxy-terminal rate is ~0. Untrusted anchors are reported as such and NOT used to label rungs.
- **SC3:** `AiSetupPage` selects a rung, builds a game, and the injected `humanSLProfile`/`maxVisits` (no `maxTime`) are verifiable in the KataGo query log; a ladder player with no rung **fails closed** (no move), not silent rung 1.
- **SC4:** Golaxy double-scale correct (`elo_score` unchanged; `display_elo`/`ref_rank` added); existing Golaxy engine-play tests green.
- **SC5:** deep-kyu tolerances + documented ties/reversals recorded; no silent truncation; every ambiguous calibration outcome is `inconclusive`, never a win.

## Self-Review

**Spec coverage:** G1→T1/T6; G2→T1; G3→T1(provisional)+T7-10; G4→T11; G5→`backend_hint`/`net`(v1 b18); G6→B1/B2+T9(V1 re-verify). §2 double-scale→B1. §6 bands→T1 `_band`. §7 calibration→T7-10. §8.2→T3/T4. §11 risks→ coord gold-standard (T1), inconclusive-not-win (T7), typed wire (T8), per-band bake (T10), fail-closed rung (T4), config-sanity-not-strength (T6). All 8 adversarial findings addressed: F1 T1 coords+tests; F2 T7 terminal→inconclusive + T9 pass probe; F3 T8 BLACK scoring + reject-missing + T7 settled/inconclusive; F4 T8 shared builder + contract test + T3 pure-visits; F5 T4 fail-closed + 422 + lifecycle; F6 T8 typed rung opponent; F7 T1/T5 net=b18; F8 T6 non-decreasing sanity + measured-Elo arbiter.

**Round-2 adversarial findings (G1–G5) addressed:** G1 (T7 `play_one_game` history holds only valid wire coords; no sentinel ever appended; `test_no_sentinel_ever_reaches_golaxy`); G2 (T8 contract test drives the REAL `BaseEngine.build_analysis_query`, not a re-impl; harness sources `wide_root_noise` from the engine config, not a hard-coded default); G3 (T4 `_do_new_game` game/rung swap under `ai_lock` + `_do_ai_move` local `(game,rung)` snapshot + deterministic concurrency test); G4 (T3 `LadderUnavailable` — no PolicyStrategy/cached-policy fallback; T4 `_do_ai_move` catches it → no move + surfaced flag; tests assert tree unchanged); G5 (T8 `_is_settled` validates ownership length==bs²/finite + ≥98% decisive + lead-dominates-undecided-margin + `run_calibration` score-stability re-check for move_cap games).

**Round-3 adversarial findings (H1–H3, M1) addressed:** H1 (T7 symmetric handling of VERIFIED stops); H2 (T1 `pick_ladder_move` raises `LadderMoveError` on absent/malformed/wrong-length required output — no cross-mechanism fallback; T3 → `LadderUnavailable`; T8 `our_move` → `"unavailable"` → T7 `inconclusive_engine`); H3 (T3 bounded wait — inspects `check_alive`'s BOOLEAN return + a `LADDER_ANALYSIS_TIMEOUT_S` deadline → `LadderUnavailable`, so a dead HTTP engine never spins holding `ai_lock`; `test_dead_engine_raises_unavailable_no_hang`); M1 (T8 contract test builds a REAL `GameNode`, calls the real builder, asserts EXACT `overrideSettings` equality across rungs).

**Round-6 adversarial findings addressed:** R6-H1 (T3 Step 3b exempts `AI_LADDER` from the generic pre-strategy `should_ai_resign` in `generate_ai_move`, so the shipped ladder never global-resigns — matching the harness which never resigns our side; T3 Step 3c parity test drives `generate_ai_move` with `should_ai_resign` forced True and asserts no resignation); R6-H2/R7-H1 (T1 `_pick_search_move` validates EVERY moveInfo entry FULLY — shape + int order + GTP parse + board bounds — inside the loop BEFORE selecting min-order, raising `LadderMoveError` on any malformation regardless of position; `test_pick_search_any_malformed_entry_fails_closed_even_if_another_is_valid` covers malformed-as-min-order AND valid-order-0 + malformed-higher-order, incl. bad-GTP entries).

**Round-5 adversarial findings addressed:** R5-H1 (T1 `pick_ladder_move` requires `isinstance(analysis, dict)` before any `.get`; `_pick_search_move` requires an explicit `type(order) is int` (excludes bool subtype) + `order>=0` + present key; tests for non-dict analysis / missing / boolean / negative order); R5-H2 (T9 replaces the impossible API pass-probe with a documented **manual browser capture** of pass/resign wire codes; T8 `_valid_sentinels` honors only distinct out-of-board int codes — in-board or equal codes are dropped so ordinary replies can't become scored resigns; T9/T10 make trusted terminals a HARD gate for parity conclusions and reframe the pre-code exclusion as selection bias of **unknown direction**); R5-M1 (T8 contract test runs the REAL `KataGoHttpEngine.build_analysis_query` with `start()` stubbed — drift-sensitive — plus `test_contract_fails_on_runtime_override_drift`).

**Round-4 adversarial findings (2×H1-refinement, H2-refinement, M2) addressed:** H1-round4 (T7 distinguishes a SMOKE-VERIFIED golaxy pass/resign from an UNVERIFIED out-of-board `"terminal"`: resign → our_win, verified-pass → adjudicate, unverified-terminal → `inconclusive_terminal` NEVER scored even if the position is coincidentally settled; `test_unverified_golaxy_terminal_never_scored_even_if_settled`; T8 `golaxy_move` classifies via `pass_code`/`resign_code`; pre-smoke bias documented in T8/T9/`run_calibration`); H2-round4 (T1 `_pick_search_move` filters non-dict entries, validates int order + non-empty str move, wraps GTP parse in try/except, bounds-checks — every failure → `LadderMoveError`, no AttributeError/ValueError escape; `test_pick_search_malformed_entries_raise_not_crash`); M2 (T3 explicit `done` flag independent of analysis truthiness so an empty/malformed completed response fails closed immediately instead of waiting the deadline, `LADDER_ANALYSIS_TIMEOUT_S=60`, engine noResults→error_callback follow-up noted; `test_empty_completed_analysis_raises_unavailable_no_hang`); M1-round4 (T8 `get_rules = staticmethod(BaseEngine.get_rules)` on the test double so the real builder is callable).

**Placeholder scan:** operator-run steps (T9.7, T10.7) + CLI bodies (`run_*.py`, `bake_results.py`) are structure-level by design (live token/GPU, not CI-tested); every unit-tested module has complete code + tests. `_is_settled` thresholds (98% decisive + lead-margin) are concrete and refined from smoke data.

**Type consistency:** `rung_engine_params`→`{"visits","extra_settings"}` used in T3/T8; `ladder_override_settings` used in T1/T3/T8 (contract); `pick_ladder_move(analysis, bs_tuple, mechanism)` identical T1/T3/T8; `colrow_to_golaxy`/`golaxy_to_colrow` identical T1/T8; `play_one_game(our_move, golaxy_move, adjudicate, our_color, ...)` identical T7/T8; `GameOutcome.result` enum consistent; `ladder_rung` int threads AiSetupPage→`NewGameRequest`→`new_game`(422)→`_do_new_game`→`resolve_ladder_rung`→`self.ladder_rung`→`_do_ai_move`(fail-closed)→`LadderStrategy` reads `self.settings["rung"]` (raises if absent).

## Open items for re-review
- Rung 40 = b18@500 (honest `net='b18'`); real b28@:8002 ceiling is a documented follow-up, not exposed.
- `scoreLead` black-relative under `reportAnalysisWinratesAs:BLACK` — to be confirmed in smoke (matches the runtime engine's forced setting).
- Golaxy pass/resign encodings unknown until a **manual browser capture** (Task 9 Step 5b) — no API probe can elicit them. UNVERIFIED golaxy stops are `inconclusive_terminal` (never scored); `_valid_sentinels` honors only distinct out-of-board codes. Excluding unverified terminals is selection bias of **unknown direction** → parity conclusions require trusted anchors (codes captured, or golaxy-terminal rate ~0); untrusted anchors are reported, not used. our-pass adjudication + `_is_settled` + stability re-check gate every conclusive game — the key assumption to validate on real smoke endgames.
- The contract test stubs `KataGoHttpEngine.start()` to avoid the worker thread/network while keeping the real `override_settings`; confirm `super().__init__` does no network on the target platform (health-check lives in `create_engine`, not `__init__`), else stub `HttpEngineStatus` too.
- `_is_settled` thresholds (98% decisive + lead > 2·undecided+1) are conservative starting values; move_cap games additionally require a score-stability re-check before counting; tune from smoke endgames.
- Concurrency: `_do_new_game` acquiring `ai_lock` assumes it is never called re-entrantly from a lock-holding path — verified for the AI thread; implementer must confirm no other caller holds `ai_lock` when starting a game.
