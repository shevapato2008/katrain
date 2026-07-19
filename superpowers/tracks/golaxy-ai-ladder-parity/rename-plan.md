# 棋力阶梯 De-branding & 段位 Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebrand the local 40-rung strength-ladder AI so it never references 星阵/Golaxy in any user-visible string, shows each rung by its 段位 name only (no elo, no rung index), and surfaces that 段位 as the opponent's rank on the board nameplate.

**Architecture:** The ladder's internal calibration metadata (`golaxy_level_name`, `golaxy_api_level`, `display_elo`) stays untouched in `ladder.py` (keeps the calibration harness and the cross-consistency test with `engine_client.py` green) but is no longer sent to the browser. A new `rank_name` field on `LadderRung` carries the user-facing 段位 string (top 3 rungs renamed to pro-tier descriptions, rung 40 = "KataGo 中等算力"). The `/api/ladder-rungs` response shrinks to `{rung, rank_name}`. The opponent-type label becomes "棋力阶梯". The board 段位 is shown via a new per-player `rank_display` string computed on the fly in `get_state()` from the injected rung (no `Player`-class or reset plumbing needed).

**Tech Stack:** Python 3 (FastAPI backend, frozen dataclass), React + TypeScript + Vite (MUI), Vitest/RTL (frontend tests), pytest (backend tests), gettext `.po`/`.mo` i18n.

## Global Constraints

- **No "星阵"/"Golaxy" in ANY user-visible product string** (no license/authorization). Applies to: opponent-type labels, rung labels, player names, board nameplates. Internal fields (`golaxy_level_name`, `golaxy_api_level`) may keep their names as calibration metadata but MUST NOT be sent to the browser or displayed.
- **Do NOT touch the kiosk real-星阵 tunnel** — `katrain/web/platforms/golaxy/engine_client.py` (`_GOLAXY_ROWS`/`GOLAXY_AI_LEVELS`, animal names), `katrain/web/platforms/golaxy/adapter.py`, `katrain/web/ui/src/kiosk/pages/PlatformEngineSetupPage.tsx`. That is a separate authorization question, explicitly out of scope.
- **Keep `golaxy_level_name`, `golaxy_api_level`, `display_elo` UNCHANGED** as `LadderRung` fields (calibration + `tests/platforms/test_golaxy_ladder_consistency.py` cross-checks them against `engine_client.py`). Only stop *sending* and *displaying* them.
- **No elo numbers and no "第 N/40 档" subtitle in the UI.** Each rung shows ONLY its `rank_name` (段位).
- **Rung display names (`rank_name`)**: rungs 1–36 = the generic Go rank (`18级`…`9段`, identical to `golaxy_level_name`); rung 37 = `职业棋手`; rung 38 = `职业顶尖`; rung 39 = `超越职业`; rung 40 = `KataGo 中等算力`.
- **Opponent-type name** (replacing `对标星阵`) = `棋力阶梯`. **Board nameplate**: player `name` = `AI (棋力阶梯)`; 段位/rank slot = the rung's `rank_name`.
- **Keep the nan→`None` `calculated_rank` contract** for `ai:ladder` (JSON-safe; the 段位 rides the new `rank_display` field, never `calculated_rank`).
- **Both web builds stay green** — run `npm run build` AND `npm run build:kiosk-2d` before finishing frontend tasks. `PlayerCard.tsx` is shared territory (consumed by galaxy + kiosk + ZenMode).
- **Chinese-first**: `rank_name` values stay Chinese data (consistent with existing `段/级` data, which is not gettext-keyed). Only the `t()`-keyed labels (`棋力阶梯`, `棋力等级`) get 11-language `.po` entries.

---

## File Structure

**Modified:**
- `katrain/core/ai.py` — commit the already-applied nan→`None` fix; sweep the `对标星阵` comment/log (Task 1).
- `katrain/core/ladder.py` — add `rank_name` to `LadderRung`; `_RANK_NAME_OVERRIDE`; rung-40 name (Task 2).
- `katrain/web/server.py:1674-1692` — `/api/ladder-rungs` response → `{rung, rank_name}` (Task 3).
- `katrain/web/ui/src/api.ts` — `LadderRung` type → `{rung, rank_name}`; `PlayerInfo` += `rank_display`; comment (Tasks 3, 5).
- `katrain/web/ui/src/galaxy/pages/AiSetupPage.tsx` — opponent label `棋力阶梯`; rung dropdown → `rank_name` only; comment (Task 4).
- `katrain/web/interface.py` — `get_state()` emits computed `rank_display`; sweep `:1018` docstring (Task 5).
- `katrain/web/ui/src/components/PlayerCard.tsx` — prefer `info.rank_display` for the 段位 slot (Task 5).
- `katrain/i18n/locales/*/LC_MESSAGES/katrain.po` (11 locales) — `ai:golaxy_parity`, `ai:golaxy_parity_rung` (Task 6).

**Tests modified/created:**
- `tests/test_ai.py` — already has `test_ladder_rank_estimation_is_json_safe` (Task 1).
- `tests/core/test_ladder.py` — assert `rank_name` values + `golaxy_level_name` unchanged (Task 2).
- `tests/platforms/test_golaxy_calibration_opponent.py:40` — insert `rank_name` into the manual `LadderRung(...)` construction (Task 2).
- `tests/web_ui/test_ladder_injection.py` — `/api/ladder-rungs` schema + a new `rank_display` get_state test (Tasks 3, 5).
- `katrain/web/ui/src/galaxy/pages/AiSetupPage.test.tsx` — rename assertions (Task 4).
- `katrain/web/ui/src/components/PlayerCard.test.tsx` — create; `rank_display` precedence (Task 5).

**Do NOT modify** (out of scope): `engine_client.py`, `adapter.py`, `PlatformEngineSetupPage.tsx`, and their tests; `bake_results.py` (its `replace()` calls preserve the new field automatically).

---

### Task 1: Commit the nan→None calculated_rank fix (foundation)

The ladder's `calculated_rank` must be `None` (not `float('nan')`) or `/api/player` returns HTTP 500 (nan is not JSON-serializable), blocking game start. This fix is **already applied to the working tree**; this task only verifies and commits it. **All `ai.py` 星阵 de-branding — the `:1826` docstring AND the user-visible LadderStrategy `ai_thoughts` log at `:1896-1899` — is done in Task 2**, because that log must be rewritten to use `rank_name` (which does not exist until Task 2), never `golaxy_level_name`.

**Files:**
- Modify: `katrain/core/ai.py` (`ai_rank_estimation`, ~lines 92-100 — the nan→None fix ONLY)
- Test: `tests/test_ai.py` (`test_ladder_rank_estimation_is_json_safe`, already present)

**Interfaces:**
- Produces: `ai_rank_estimation(AI_LADDER, settings) -> None` (contract relied on by Task 5, which keeps `calculated_rank` numeric-or-None everywhere else).

- [ ] **Step 1: Verify the fix is present in `katrain/core/ai.py`**

Confirm `ai_rank_estimation` begins with the AI_LADDER special-case returning `None`:

```python
def ai_rank_estimation(strategy, settings) -> Optional[int]:
    if strategy == AI_LADDER:
        # Ladder strength is per-rung (injected at game start), not derivable from settings here,
        # and AI_STRENGTH[AI_LADDER] is nan. Returning it verbatim into players_info.calculated_rank
        # makes FastAPI's JSONResponse raise (nan is not JSON-serializable -> HTTP 500, blocks game
        # start). None is the JSON-safe contract; the rung's 段位 is surfaced via rank_display instead.
        return None
    ...
```

If the `if strategy == AI_LADDER: return None` guard is missing, add it as the first check in the function.

- [ ] **Step 2: Run the JSON-safety test**

Run: `CI=true uv run pytest tests/test_ai.py::TestAI::test_ladder_rank_estimation_is_json_safe -v`
Expected: PASS (asserts `ai_rank_estimation(AI_LADDER, {}) is None` and `json.dumps` succeeds).

- [ ] **Step 3: Run the broader ai rank test to confirm no regression**

Run: `CI=true uv run pytest tests/test_ai.py::TestAI::test_ai_rank_estimation -v`
Expected: PASS (non-ladder strategies still return `-20 <= rank <= 9`).

- [ ] **Step 4: Commit**

```bash
git add katrain/core/ai.py tests/test_ai.py
git commit -m "fix(ladder): ai_rank_estimation(AI_LADDER)->None (JSON-safe)"
```

---

### Task 2: Add `rank_name` to LadderRung + rename pro tiers + rung-40 ceiling

Introduce the user-facing 段位 string. Keep `golaxy_level_name` unchanged so calibration + cross-consistency tests stay green.

**Files:**
- Modify: `katrain/core/ladder.py` (`LadderRung` dataclass ~32-45; add `_RANK_NAME_OVERRIDE`; `_build_ladder` ~149-157)
- Modify: `katrain/core/ai.py` (add a module-level `logger`; extract `_ladder_thought_label` helper + rewrite the `LadderStrategy` `ai_thoughts` return at ~1896-1899 to use `rank_name`; route the rung/visits detail to the stdlib `logger.debug` — NOT `katrain.log`; de-brand docstring at ~1826)
- Modify: `tests/platforms/test_golaxy_calibration_opponent.py:40` (manual `LadderRung(...)` construction — insert `rank_name`)
- Test: `tests/core/test_ladder.py` (add `rank_name` assertions + no-星阵 sweep); `tests/test_ai.py` (thought-label helper test); `tests/core/test_ladder_strategy.py` (broadcast-channel regression: rung/visits never reach `katrain.log`, codex round 3)

**Interfaces:**
- Produces: `LadderRung.rank_name: str` — non-null for all 40 rungs. Values: rungs 1–36 == `golaxy_level_name`; rung 37 `职业棋手`; 38 `职业顶尖`; 39 `超越职业`; 40 `KataGo 中等算力`. Consumed by Tasks 3 (API) and 5 (rank_display).
- Produces: `_ladder_thought_label(rung) -> str` in `katrain/core/ai.py` — the user-visible `ai_thoughts`/SGF-comment string = `棋力阶梯 {rank_name}` ONLY (star阵-free, and no rung index / visits / debug prefix). The rung/visits detail goes to a **server-side stdlib `logging` sink** (`logger = logging.getLogger(__name__)`, i.e. `"katrain.core.ai"`), NOT `self.game.katrain.log`.
- **Why NOT `katrain.log(..., OUTPUT_DEBUG)` (codex round 3, verified):** `WebKaTrain.log` (`interface.py:338-340`) invokes `message_callback` for **every** level including `OUTPUT_DEBUG`; `SessionManager._on_message` (`session.py:141-146`) broadcasts it as a `{"type":"log"}` WebSocket message; `ZenModeApp.tsx:122-123` renders every log's `message` in the TopBar status bar with **no level filtering**. So routing rung/visits through `katrain.log` — at any level — would still expose them in the UI. The stdlib `logger.debug` path never touches `message_callback`, so it stays server-side.

**Why the ai.py change lives here (codex round 1, high):** the `LadderStrategy` return at `ai.py:1896-1899` builds `ai_thoughts` as `f"[LadderStrategy] rung {r} · 对标星阵{golaxy_level_name or '最强'} · visits=..."`. That string is set on `played_node.ai_thoughts` (`ai.py:1932`), written into SGF comments (`game_node.py:381-382`) and pushed as a WebSocket log the ZenMode TopBar renders — i.e. **user-visible**. It leaks both `对标星阵` (every rung) and `星阵1/2/3星` (rungs 37–39). It MUST be rewritten to use `rank_name`, which is why it belongs in this task (after `rank_name` exists), not Task 1.

- [ ] **Step 1: Write failing tests in `tests/core/test_ladder.py`**

```python
def test_rank_name_generic_ranks_match_level_name_for_amateur_rungs():
    from katrain.core.ladder import LADDER_RUNGS
    # rungs 1..36 (amateur 级/段): rank_name is the plain Go rank, identical to golaxy_level_name
    for r in LADDER_RUNGS[:36]:
        assert r.rank_name == r.golaxy_level_name

def test_rank_name_renames_pro_tiers_and_ceiling():
    from katrain.core.ladder import get_rung
    assert get_rung(37).rank_name == "职业棋手"
    assert get_rung(38).rank_name == "职业顶尖"
    assert get_rung(39).rank_name == "超越职业"
    assert get_rung(40).rank_name == "KataGo 中等算力"

def test_golaxy_level_name_unchanged_internally():
    # De-branding is display-only: internal calibration metadata is untouched.
    from katrain.core.ladder import get_rung
    assert get_rung(37).golaxy_level_name == "星阵1星"
    assert get_rung(39).golaxy_level_name == "星阵3星"
    assert get_rung(40).golaxy_level_name is None

def test_no_rank_name_leaks_xingzhen():
    # Every user-visible 段位 label must be star阵-free (rank_name feeds the UI + ai_thoughts).
    from katrain.core.ladder import LADDER_RUNGS
    for r in LADDER_RUNGS:
        assert "星阵" not in r.rank_name
```

Also add the user-visible-thought regression test to `tests/test_ai.py` (guards the codex-round-1 leak):

```python
def test_ladder_thought_label_is_rank_name_only(self):
    # User-visible (SGF comment + ZenMode log): the branded 段位 label ONLY — star阵-free AND free
    # of the rung index / visits / debug prefix (codex round 2).
    from katrain.core.ai import _ladder_thought_label
    from katrain.core.ladder import get_rung

    label = _ladder_thought_label(get_rung(39))  # rung 39 == 超越职业 (was 星阵3星)
    assert "超越职业" in label
    for banned in ("星阵", "对标星阵", "rung", "visits", "39", "[LadderStrategy]"):
        assert banned not in label
```

Also add the **end-to-end broadcast-channel regression test** to `tests/core/test_ladder_strategy.py` (guards the codex-round-3 AND -round-5 leaks). It MUST drive the whole `generate_ai_move(...)` path with the `katrain.log` spy installed **before strategy construction** — the base `AIStrategy.__init__` (`ai.py:336`) logs the injected settings `{'rung': 39}` at construction time, so a spy installed after `_mk(...)` (which constructs the strategy) is blind to it (codex round 5, high). This file already has the `FakeEngine`/`FakeGame`/`FakeKatrain` harness:

```python
def test_ladder_generate_ai_move_keeps_rung_off_katrain_log(caplog):
    # katrain.log is the WS-broadcast channel: WebKaTrain.log forwards EVERY level via
    # message_callback -> SessionManager WS -> ZenModeApp TopBar (codex round 3/5, verified).
    # NOTHING on the ladder path may push the rung index / visits / 星阵 through it:
    #   - AIStrategy.__init__ settings-dump ({'rung': 39})  -> routed to stdlib logger (round 5 fix)
    #   - LadderStrategy success detail (rung · visits)     -> routed to stdlib logger (round 3 fix)
    #   - the returned ai_thoughts                          -> clean 段位 label only
    # The spy is installed BEFORE generate_ai_move so it sees the construction-time init log.
    import logging
    from katrain.core.ai import generate_ai_move
    from katrain.core.constants import AI_LADDER

    eng = FakeEngine({"moveInfos": [{"move": "Q16", "order": 0}]})
    game = FakeGame(eng)
    seen = []
    game.katrain.log = lambda *a, **k: seen.append(str(a[0]) if a else "")

    with caplog.at_level(logging.DEBUG, logger="katrain.core.ai"):
        move, node = generate_ai_move(game, AI_LADDER, {"rung": 39})  # rung 39 == 超越职业

    assert node.ai_thoughts == "棋力阶梯 超越职业"          # clean user-visible thought (SGF + TopBar)
    joined = " ".join(seen)
    for banned in ("星阵", "rung", "visits", "39"):           # per codex round 5 recommendation
        assert banned not in joined
    assert "visits=" in caplog.text                            # observability preserved server-side
```

(Keep the pure-helper `test_ladder_thought_label_is_rank_name_only` in `tests/test_ai.py` as the fast unit test of the label; this end-to-end test covers the three ladder-code broadcast channels — init dump, success detail, returned thought.)

**Scope note (codex round 6, user-confirmed out of scope):** this test uses `FakeEngine`, which does not emit KataGo's own query/result logs. The REAL KataGo engine separately logs `maxVisits`/visit counts via `self.katrain.log` (`engine.py`), which also reaches the TopBar — but that is a generic, mode-agnostic engine diagnostic (no 星阵, no rung ladder index), explicitly excluded from this plan's no-leak invariant (see Known Limitations). Do NOT extend this test or the plan to sanitize engine.py logging.

- [ ] **Step 2: Run to verify they fail**

Run: `CI=true uv run pytest tests/core/test_ladder.py tests/test_ai.py tests/core/test_ladder_strategy.py -k "rank_name or golaxy_level_name_unchanged or thought_label or keeps_rung_off" -v`
Expected: FAIL — `AttributeError: 'LadderRung' object has no attribute 'rank_name'`, `ImportError: cannot import name '_ladder_thought_label'`, and the end-to-end test fails because (a) the current return routes `对标星阵…rung…visits` through the thought and (b) `AIStrategy.__init__` still broadcasts `{'rung': 39}` via `katrain.log`.

- [ ] **Step 3: Add the `rank_name` field to the `LadderRung` dataclass**

In `katrain/core/ladder.py`, insert `rank_name` immediately after `ref_rank` (a required field, before any defaulted field):

```python
@dataclass(frozen=True)
class LadderRung:
    rung: int
    golaxy_level_name: Optional[str]
    golaxy_api_level: Optional[int]  # eloScore = the `level` wire param (calibration only)
    display_elo: Optional[int]
    ref_rank: str
    rank_name: str  # user-facing 段位 label (星阵-free); NEVER derived from golaxy_level_name at display time
    net: str  # v1: always 'b18' (== shipping engine)
    mechanism: str
    human_sl_profile: Optional[str]
    max_visits: int
    human_sl_params: Dict = field(default_factory=dict)
    backend_hint: str = "server"
    root_policy_temperature: float = 1.0
```

- [ ] **Step 4: Add the pro-tier override map and populate `rank_name` in `_build_ladder`**

Above `_build_ladder` (near the table), add:

```python
# Display-only 段位 rename for the top tiers (星阵1/2/3星 have no standard dan name).
# Keys are the internal golaxy_level_name; values are the user-facing 段位 label.
_RANK_NAME_OVERRIDE = {"星阵1星": "职业棋手", "星阵2星": "职业顶尖", "星阵3星": "超越职业"}
```

Update the two `LadderRung(...)` constructions in `_build_ladder` to pass `rank_name` positionally after `ref`:

```python
def _build_ladder() -> List[LadderRung]:
    rungs = []
    for i, (name, api, disp, ref) in enumerate(_GOLAXY_WEAK_TO_STRONG):
        mech, prof, visits, params, temp = _band(name)
        rank_name = _RANK_NAME_OVERRIDE.get(name, name)
        rungs.append(LadderRung(i + 1, name, api, disp, ref, rank_name, "b18", mech, prof, visits, dict(params), "server", temp))
    # Rung 40: ceiling. v1 = b18@500 on the session engine. rank_name is the honest "中等算力"
    # ceiling label (NOT max KataGo). golaxy_level_name stays None (no Golaxy tier maps to it).
    rungs.append(LadderRung(40, None, None, None, "最强", "KataGo 中等算力", "b18", "net_search", None, 500, {}, "server", 1.0))
    return rungs
```

- [ ] **Step 5: Fix the other positional `LadderRung(...)` construction site**

In `tests/platforms/test_golaxy_calibration_opponent.py` around line 40, the manual `bad = LadderRung(...)` construction must insert a `rank_name` positional arg after its `ref_rank` arg (use any placeholder string that matches the test's intent, e.g. `"测试"` or mirror its `golaxy_level_name`). Read the existing call, then insert the arg in the correct position so the positional layout still matches the dataclass. Example shape:

```python
    bad = LadderRung(
        rung=39, golaxy_level_name="星阵3星", golaxy_api_level=3300, display_elo=4000,
        ref_rank="职业/野狐9D+", rank_name="超越职业", net="b18", mechanism="net_search",
        human_sl_profile=None, max_visits=480,
    )
```

(Prefer converting the call to keyword arguments as shown if it isn't already, to make it robust to future field additions.)

- [ ] **Step 6: Make the user-visible `ai_thoughts` rank_name-only in `katrain/core/ai.py`**

`ai_thoughts` reaches the user through SGF comments (`game_node.py:381-382`) and the ZenMode TopBar WS log, so it must be the branded 段位 label ONLY — no 星阵, and no rung index, no visits, no `[LadderStrategy]` prefix. Keep the rung/visits detail for observability, but on a **server-side-only** channel.

**Critical (codex round 3, verified):** do NOT use `self.game.katrain.log(..., OUTPUT_DEBUG)` for the detail. `WebKaTrain.log` (`interface.py:338-340`) pushes **every** level — `OUTPUT_DEBUG` included — through `message_callback`, which `SessionManager` (`session.py:141-146`) broadcasts as a `{"type":"log"}` WS message, and `ZenModeApp.tsx:122-123` renders it in the TopBar status bar with no level filter. So `OUTPUT_DEBUG` is NOT non-user-visible. Use the Python stdlib logger instead — it never reaches `message_callback`.

Add a module-level logger near the top of `katrain/core/ai.py` (alongside the existing stdlib imports `heapq`/`math`/`random`/`time`):

```python
import logging
...
logger = logging.getLogger(__name__)  # "katrain.core.ai" — server-side sink, NOT the WS log channel
```

Add a testable module-level helper near `LadderStrategy`:

```python
def _ladder_thought_label(rung) -> str:
    # User-visible: becomes played_node.ai_thoughts -> SGF comment + ZenMode TopBar log.
    # rank_name ONLY: star阵-free and free of rung index / visits / debug prefix.
    return f"棋力阶梯 {rung.rank_name}"
```

Replace the `LadderStrategy` return (currently `ai.py:1896-1899`) — emit the technical detail to the stdlib logger (server-side only), return the clean label:

```python
        logger.debug("[LadderStrategy] rung %s · %s · visits=%s", rung.rung, rung.rank_name, params["visits"])
        return (move, _ladder_thought_label(rung))
```

(`self.game.katrain` is valid — `self.game` is used at `ai.py:1891` — but is deliberately NOT used for this line; `logger.debug` keeps the rung/visits detail off the WebSocket log channel. The pre-existing `OUTPUT_ERROR` engine-failure log at `ai.py:1862` is left as-is: it is an exceptional diagnostic on engine death, not the normal 段位 display.)

**Also sanitize the base `AIStrategy.__init__` settings-dump (codex round 5, high).** At `ai.py:336` the base strategy constructor logs the raw settings dict via `self.game.katrain.log(..., OUTPUT_DEBUG)`. For a ladder player that dict is the injected `{'rung': 39}`, so this broadcasts the rung index to the ZenMode TopBar at construction time — before the success/failure paths run, and before any test spy installed after construction can see it. Route this generic init diagnostic to the same stdlib logger:

```python
        self.strategy_name = self.__class__.__name__
        logger.debug("Initializing %s with settings: %s", self.strategy_name, self.settings)
```

(Replaces `self.game.katrain.log(f"Initializing {self.strategy_name} with settings: {self.settings}", OUTPUT_DEBUG)`. **Blast radius, intentional:** this is the shared base constructor, so EVERY strategy's init-settings DEBUG line now goes to the Python logger instead of the app log channel — a net win, since dumping a raw settings dict into a user-facing status bar was never desirable for any strategy. This is the general fix at the right altitude, not a ladder special-case. The other `generate_ai_move` debug lines (`ai.py:1909`/`1925`/`1929`/`1931`/`1934`) stay on `katrain.log`: on the ladder path they carry only the mode string, the class name, move coords, and the already-clean `ai_thoughts` — no rung index / visits / 星阵, so the end-to-end test's banned-set `("星阵","rung","visits","39")` passes.)

De-brand the docstring at ~`ai.py:1826`:

```python
    it fails closed (no move) so the '棋力阶梯' strength label is never silently violated."""
```

- [ ] **Step 7: Run all affected ladder + ai tests**

Run: `CI=true uv run pytest tests/core/test_ladder.py tests/core/test_ladder_strategy.py tests/platforms/test_golaxy_ladder_consistency.py tests/platforms/test_golaxy_calibration_opponent.py tests/test_ai.py -v`
Expected: PASS — the pre-existing `test_forty_rungs_map_weak_to_strong` and `test_golaxy_ladder_consistency` stay green (`golaxy_level_name`/`display_elo` untouched), plus the new `rank_name` assertions, `test_no_rank_name_leaks_xingzhen`, `test_ladder_thought_label_is_rank_name_only`, and the end-to-end broadcast-channel `test_ladder_generate_ai_move_keeps_rung_off_katrain_log`. (The pre-existing `test_ladder_strategy.py` tests — `test_search_rung_high_visits_top_move` etc. — also stay green: the base-init log change only moves a DEBUG line to stdlib.)

- [ ] **Step 8: Commit**

```bash
git add katrain/core/ladder.py katrain/core/ai.py tests/core/test_ladder.py tests/core/test_ladder_strategy.py tests/test_ai.py tests/platforms/test_golaxy_calibration_opponent.py
git commit -m "feat(ladder): rank_name display field + de-brand LadderStrategy thoughts (star阵-free)"
```

---

### Task 3: Shrink `/api/ladder-rungs` to `{rung, rank_name}` + update TS type

Stop sending `golaxy_level_name`/`display_elo`/`ref_rank`/`net`/`mechanism` to the browser (星阵-free wire). The frontend only needs `rung` (value) and `rank_name` (label).

**Files:**
- Modify: `katrain/web/server.py:1674-1692` (`get_ladder_rungs`)
- Modify: `katrain/web/ui/src/api.ts:109-118` (`LadderRung` interface + comment)
- Test: `tests/web_ui/test_ladder_injection.py` (`test_ladder_rungs_endpoint`)

**Interfaces:**
- Consumes: `LadderRung.rank_name` (Task 2).
- Produces: `GET /api/ladder-rungs` → `{"rungs": [{"rung": int, "rank_name": str}, ...]}` (40 items). TS: `interface LadderRung { rung: number; rank_name: string; }`. Consumed by Task 4.

- [ ] **Step 1: Update the failing backend test in `tests/web_ui/test_ladder_injection.py`**

Rewrite `test_ladder_rungs_endpoint`'s assertions to the new schema:

```python
def test_ladder_rungs_endpoint(client):
    resp = client.get("/api/ladder-rungs")
    assert resp.status_code == 200
    rungs = resp.json()["rungs"]
    assert len(rungs) == 40
    # New star阵-free wire schema: only rung + rank_name.
    assert set(rungs[0].keys()) == {"rung", "rank_name"}
    assert rungs[0] == {"rung": 1, "rank_name": "18级"}
    assert rungs[38] == {"rung": 39, "rank_name": "超越职业"}
    assert rungs[39] == {"rung": 40, "rank_name": "KataGo 中等算力"}
    # No internal 星阵/elo fields leak to the browser.
    for r in rungs:
        assert "golaxy_level_name" not in r
        assert "display_elo" not in r
```

- [ ] **Step 2: Run to verify it fails**

Run: `CI=true uv run pytest tests/web_ui/test_ladder_injection.py::test_ladder_rungs_endpoint -v`
Expected: FAIL (current response still has `golaxy_level_name`/`display_elo`).

- [ ] **Step 3: Update the endpoint in `katrain/web/server.py`**

```python
@app.get("/api/ladder-rungs")
def get_ladder_rungs():
    from katrain.core.ladder import LADDER_RUNGS

    # UI-facing subset only. star阵-free: internal golaxy_level_name / golaxy_api_level /
    # display_elo / ref_rank / humanSL knobs are NOT exposed to the browser.
    return {"rungs": [{"rung": r.rung, "rank_name": r.rank_name} for r in LADDER_RUNGS]}
```

- [ ] **Step 4: Run the backend test to verify it passes**

Run: `CI=true uv run pytest tests/web_ui/test_ladder_injection.py -v`
Expected: PASS.

- [ ] **Step 5: Update the TS `LadderRung` interface in `katrain/web/ui/src/api.ts`**

```ts
// One rung of the local 棋力阶梯 (strength-ladder) 40-rung opponent — the UI-facing
// subset served by GET /api/ladder-rungs (see katrain/web/server.py). star阵-free.
export interface LadderRung {
  rung: number;
  rank_name: string;
}
```

- [ ] **Step 6: Commit**

```bash
git add katrain/web/server.py katrain/web/ui/src/api.ts tests/web_ui/test_ladder_injection.py
git commit -m "feat(ladder): /api/ladder-rungs returns only {rung, rank_name} (star阵-free wire)"
```

---

### Task 4: AiSetupPage — 棋力阶梯 opponent + rank_name-only rung dropdown

**Files:**
- Modify: `katrain/web/ui/src/galaxy/pages/AiSetupPage.tsx` (`:135`, `:370`, `:381`, comment `:47`)
- Test: `katrain/web/ui/src/galaxy/pages/AiSetupPage.test.tsx`

**Interfaces:**
- Consumes: `LadderRung { rung, rank_name }` (Task 3). `aiLabel` = `` `AI (${getStrategyDisplay('ladder')})` `` → `AI (棋力阶梯)` automatically once the map entry changes.

- [ ] **Step 1: Update the failing frontend test `AiSetupPage.test.tsx`**

Update the mock fixture and assertions. Mock rungs now expose `rank_name` (matching the new `LadderRung`):

```tsx
const mockRungsResponse = {
  rungs: [
    { rung: 18, rank_name: '1级' },
    { rung: 40, rank_name: 'KataGo 中等算力' },
  ],
};
```

Rename every `对标星阵` assertion to `棋力阶梯` and drop the `· 展示Elo` label format:

```tsx
describe('AiSetupPage — 棋力阶梯 ladder opponent', () => {
  it('lists 棋力阶梯 in the AI Strategy dropdown', async () => {
    // ...
    expect(screen.getByRole('option', { name: '棋力阶梯' })).toBeInTheDocument();
  });

  it('shows a rung selector (not the human-rank slider) once 棋力阶梯 is chosen', async () => {
    // ...
    await user.click(screen.getByRole('option', { name: '棋力阶梯' }));
    await waitFor(() => {
      expect(screen.getByText('1级')).toBeInTheDocument(); // rank_name only, no elo
    });
    expect(screen.queryByText('20k')).not.toBeInTheDocument();
  });

  it('starts the game with ladder_rung and skips human_kyu_rank/strategySettings writes', async () => {
    // ...
    await user.click(screen.getByRole('option', { name: '棋力阶梯' }));
    await waitFor(() => expect(screen.getByText('1级')).toBeInTheDocument());
    await user.click(comboboxForLabel('棋力等级'));
    await user.click(screen.getByRole('option', { name: 'KataGo 中等算力' }));
    // ...
    const ladderConfigCalls = mockUpdateConfig.mock.calls.filter(([, setting]) => setting === 'ai/ai:ladder');
    expect(ladderConfigCalls).toHaveLength(0);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd katrain/web/ui && npx vitest run src/galaxy/pages/AiSetupPage.test.tsx`
Expected: FAIL (current UI still renders `对标星阵` / `展示Elo`).

- [ ] **Step 3: Rename the strategy-display map entry (`AiSetupPage.tsx:135`)**

```tsx
        'ladder': t('ai:golaxy_parity', '棋力阶梯'),
```

- [ ] **Step 4: Rename the rung-section header (`AiSetupPage.tsx:370`)**

```tsx
        <Typography variant="subtitle2" gutterBottom color="primary">
            {t('ai:golaxy_parity', '棋力阶梯')}
        </Typography>
```

- [ ] **Step 5: Rung `<MenuItem>` shows `rank_name` only (`AiSetupPage.tsx:381`)**

```tsx
                {ladderRungs.map((r) => (
                    <MenuItem key={r.rung} value={r.rung}>
                        {r.rank_name}
                    </MenuItem>
                ))}
```

- [ ] **Step 6: Update the file-top comment (`AiSetupPage.tsx:47`)**

```tsx
    // 棋力阶梯 (strength ladder): 40 rungs fetched from GET /api/ladder-rungs.
```

- [ ] **Step 7: Run frontend test + both builds**

Run: `cd katrain/web/ui && npx vitest run src/galaxy/pages/AiSetupPage.test.tsx`
Expected: PASS.

Run: `cd katrain/web/ui && npm run build && npm run build:kiosk-2d`
Expected: both succeed (kiosk `verify:kiosk-2d` exits 0).

- [ ] **Step 8: Commit**

```bash
git add katrain/web/ui/src/galaxy/pages/AiSetupPage.tsx katrain/web/ui/src/galaxy/pages/AiSetupPage.test.tsx
git commit -m "feat(ladder): AiSetupPage opponent 棋力阶梯 + rank_name-only rung dropdown"
```

---

### Task 5: `rank_display` 段位 on the board nameplate + sanitize the ladder-error broadcast

Two interface.py concerns, one commit:
1. Surface the selected rung's `rank_name` as the opponent's 段位 in the rank slot of `PlayerCard`, while `name` stays `AI (棋力阶梯)` and `calculated_rank` stays `None`. Computed on the fly in `get_state()` (no `Player`-class field, no reset logic — `self.ladder_rung` is already reset per game at `interface.py:561`).
2. **Sanitize the ladder-error broadcast (codex round 4, high):** `_do_ai_move`'s two ladder failure branches log via `self.log(..., OUTPUT_ERROR)` — and the `LadderUnavailable` branch (`interface.py:1006`) interpolates the exception, whose message embeds `rung {rung.rung}` (e.g. `"rung 39: analysis timed out"`). `WebKaTrain.log` broadcasts **every** level through `message_callback` → `SessionManager` WS (`session.py:141-146`) → `ZenModeApp` TopBar (`ZenModeApp.tsx:122-123`), so the internal rung index would flash in the user's status bar on any engine failure. The user-facing surface for these failures is already the generic `last_ladder_error` flag (via `_surface_ladder_unavailable`); the diagnostic text must stay server-side. Route both branches to interface.py's existing stdlib `logger` (`logging.getLogger("katrain_web")`, `interface.py:31`) instead of `self.log`.

**Files:**
- Modify: `katrain/web/interface.py` (`get_state`, per-player dict ~475-485; add a small helper; route the two `_do_ai_move` ladder-error branches ~991-994 & ~1006 to the stdlib `logger`; sweep `:1018` docstring)
- Modify: `katrain/web/ui/src/api.ts:1-8` (`PlayerInfo` += `rank_display`)
- Modify: `katrain/web/ui/src/components/PlayerCard.tsx` (~77-79)
- Test: `tests/web_ui/test_ladder_injection.py` (new `get_state` rank_display test + broadcast-channel regression for the LadderUnavailable path)
- Create: `katrain/web/ui/src/components/PlayerCard.test.tsx`

**Interfaces:**
- Consumes: `LadderRung.rank_name` (Task 2); `self.ladder_rung == {'rung': int}` (already set at `interface.py:561`); `AI_LADDER` (already imported at `interface.py:13`); the existing module `logger` (`interface.py:31`).
- Produces: `players_info[bw].rank_display: str | None` in `get_state()` (REST + WS). TS `PlayerInfo.rank_display: string | null`.
- Invariant enforced: the ladder failure paths broadcast NO rung index / visits / 星阵 via `message_callback`; diagnostics go to the `"katrain_web"` stdlib logger only. User surface = the pre-existing `last_ladder_error` flag (unchanged).

- [ ] **Step 1: Write the failing backend test in `tests/web_ui/test_ladder_injection.py`**

Model the setup on the existing ladder-injection tests in this file (construct a `WebKaTrain`, start a ladder game with a rung, mark the AI player). The assertion:

```python
def test_get_state_emits_rank_display_for_ladder_ai(ladder_katrain):
    # ladder_katrain: a WebKaTrain whose AI player is ai:ladder with rung 39 injected.
    kt = ladder_katrain(rung=39, ai_color="W")
    state = kt.get_state()
    w = state["players_info"]["W"]
    assert w["rank_display"] == "超越职业"       # the rung's rank_name
    assert w["calculated_rank"] is None          # 段位 rides rank_display, not calculated_rank
    b = state["players_info"]["B"]
    assert b["rank_display"] is None              # human player: no ladder rank_display

def test_rank_display_none_when_seat_flipped_to_human_via_partial_update(ladder_katrain):
    # codex round 1 (medium): a partial /api/player update that changes only player_type must not
    # leave a human wearing the ladder 段位 while the rung is still set. Guard is `p.ai and ...`.
    from katrain.core.constants import PLAYER_HUMAN

    kt = ladder_katrain(rung=39, ai_color="W")
    kt.players_info["W"].player_type = PLAYER_HUMAN  # subtype intentionally left as "ai:ladder"
    assert kt.players_info["W"].player_subtype == AI_LADDER  # precondition: stale subtype
    state = kt.get_state()
    assert state["players_info"]["W"]["rank_display"] is None
```

If no reusable fixture exists, build the `WebKaTrain` inline the way the sibling tests in this file do (they already exercise `ladder_rung` injection); set `kt.ladder_rung = {"rung": 39}` and set the AI player's `player_type = PLAYER_AI` + `player_subtype = "ai:ladder"` via the same path the other tests use. Import `AI_LADDER` from `katrain.core.constants`.

Also add the **broadcast-channel regression test for the failure path** (codex round 4). Model it on the existing `test_ai_ladder_unavailable_no_move_and_flag_set` + the `monkeypatch`-of-`generate_ai_move` pattern already in `test_new_game_serialized_against_inflight_ai_move`. The `from katrain.core.ai import generate_ai_move` inside `_do_ai_move` is resolved at call time, so patching the module attribute takes effect:

```python
def test_ladder_unavailable_does_not_broadcast_rung_index(monkeypatch, caplog):
    # codex round 4 (high): the LadderUnavailable catch in _do_ai_move interpolated the exception
    # (whose message embeds `rung {n}`) into self.log(..., OUTPUT_ERROR). WebKaTrain.log broadcasts
    # EVERY level via message_callback -> SessionManager WS -> ZenModeApp TopBar. The rung index /
    # visits / 星阵 must NOT reach the client; only the generic last_ladder_error flag should.
    import logging
    import katrain.core.ai as ai

    wkt = _make_katrain()
    next_bw = wkt.game.current_node.next_player
    _make_ladder_player(wkt, next_bw)
    wkt.ladder_rung = {"rung": 39}

    def boom(game, mode, settings):
        raise ai.LadderUnavailable("rung 39: analysis timed out (visits=480)")

    monkeypatch.setattr(ai, "generate_ai_move", boom)

    broadcasts = []
    wkt.message_callback = lambda msg_type, data: broadcasts.append((msg_type, data))

    with caplog.at_level(logging.ERROR, logger="katrain_web"):
        wkt._do_ai_move()

    assert wkt.last_ladder_error is True  # user-facing surface = generic flag, not the diagnostic text
    logged = " ".join(str(d.get("message", "")) for (t, d) in broadcasts if t == "log")
    for banned in ("rung", "visits", "39", "星阵"):
        assert banned not in logged
    assert "rung 39" in caplog.text  # diagnostics preserved on the server-side stdlib logger
```

- [ ] **Step 2: Run to verify they fail**

Run: `CI=true uv run pytest tests/web_ui/test_ladder_injection.py -k "rank_display or does_not_broadcast_rung_index" -v`
Expected: FAIL — `test_get_state_emits_rank_display_for_ladder_ai` (`KeyError: 'rank_display'`) and `test_ladder_unavailable_does_not_broadcast_rung_index` (pre-fix, `self.log(...)` still broadcasts `rung 39 … visits=480`, so `"rung"` IS in the captured broadcast).

- [ ] **Step 3: Add the helper + emit `rank_display` in `katrain/web/interface.py`**

Add a helper method on `WebKaTrain` (near `get_state`):

```python
    def _ladder_rank_display(self, p):
        """User-facing 段位 string for the local 棋力阶梯 AI, computed from the injected rung.
        None for every other player. calculated_rank stays None (JSON-safe); this rides its own field.

        The `p.ai` guard matters (codex round 1): /api/player supports partial updates where only
        `player_type` changes (models.py), and Player.update() preserves the omitted `player_subtype`.
        Flipping a ladder seat to human while the game's rung is still set would otherwise stamp a
        human with the ladder 段位. Require BOTH the AI player_type AND the ladder subtype."""
        if p.ai and p.player_subtype == AI_LADDER:
            rung_info = getattr(self, "ladder_rung", None)
            if rung_info:
                from katrain.core.ladder import get_rung

                return get_rung(rung_info["rung"]).rank_name
        return None
```

Add the field to the per-player dict in `get_state()` (after `calculated_rank`):

```python
            "players_info": {
                bw: {
                    "player_type": p.player_type,
                    "player_subtype": p.player_subtype,
                    "name": p.name,
                    "calculated_rank": p.calculated_rank,
                    "rank_display": self._ladder_rank_display(p),
                    "periods_used": p.periods_used,
                    "main_time_used": self.main_time_used_by_player.get(bw, 0),
                }
                for bw, p in self.players_info.items()
            },
```

Also sweep the `:1018` docstring `'对标星阵引擎暂不可用'` → `'棋力阶梯引擎暂不可用'` (cosmetic; not yet rendered anywhere).

Then **sanitize the two ladder-error branches in `_do_ai_move`** so no ladder diagnostic reaches the WebSocket log channel. Route both to the module `logger` (`logging.getLogger("katrain_web")`, `interface.py:31`) instead of `self.log(..., OUTPUT_ERROR)`. The user-facing surface is unchanged — `_surface_ladder_unavailable()` still sets `last_ladder_error`.

No-rung fail-closed branch (currently `interface.py:991-994`):

```python
                        logger.error("[ladder] ai:ladder player has no injected rung; refusing to move (fail closed).")
                        self._surface_ladder_unavailable()
                        return
```

`LadderUnavailable` catch (currently `interface.py:1006`) — the exception carries `rung {n}`, so it MUST NOT be interpolated into a broadcast log:

```python
                    except LadderUnavailable as e:
                        # Certified-strength failure. The exception embeds the rung index -> server-side
                        # stdlib logger ONLY (self.log broadcasts every level to the ZenMode TopBar; see
                        # interface.py:338-340). User surface is the generic last_ladder_error flag.
                        logger.error("[ladder] engine unavailable at certified strength; no move: %s", e)
                        self._surface_ladder_unavailable()
                        return
```

(`logger` and `OUTPUT_ERROR` are both already available in `interface.py`; this change simply stops routing the two ladder diagnostics through `self.log`. Existing tests `test_ai_ladder_no_rung_fail_closed_sets_last_ladder_error` / `test_ai_ladder_unavailable_no_move_and_flag_set` assert only the flag + no-move, so they stay green.)

- [ ] **Step 4: Run the backend test to verify it passes**

Run: `CI=true uv run pytest tests/web_ui/test_ladder_injection.py -v`
Expected: PASS (both new tests + the pre-existing ladder-injection suite).

- [ ] **Step 5: Add `rank_display` to the TS `PlayerInfo` (`api.ts:1-8`)**

Make it **optional** (`rank_display?`) — codex round 1 (high): a required field breaks existing typed `PlayerInfo` literals (e.g. `DEFAULT_PLAYER: PlayerInfo` at `katrain/web/ui/src/pages/VideoRecorderPage.tsx:117-124`), failing both mandated `tsc` builds. The backend always emits the key (string or null), so optional is purely to keep existing object literals/fixtures valid; `info.rank_display ?? …` handles `undefined` identically to `null`.

```ts
export interface PlayerInfo {
  player_type: string;
  player_subtype: string;
  name: string;
  calculated_rank: string | null;  // pre-existing quirk: typed string|null though backend emits int|None; NOT changed here
  rank_display?: string | null;    // NEW: ladder 段位 (optional to avoid breaking existing PlayerInfo literals)
  periods_used: number;
  main_time_used: number;
}
```

After editing, grep for other `PlayerInfo` object literals and confirm none needs updating (optional field ⇒ they compile): `rg -n ": PlayerInfo" katrain/web/ui/src`.

- [ ] **Step 6: Prefer `rank_display` in `PlayerCard.tsx` (~77-79)**

```tsx
  // 段位: a ladder AI carries its 段位 as a string in rank_display; everyone else uses the
  // numeric calculated_rank rendered by localizedRank.
  const rawRank = info.rank_display ?? localizedRank(info.calculated_rank, lang);
  const displayRank = rawRank === "No Rank" ? t("No Rank", "No Rank") : rawRank;
```

- [ ] **Step 7: Create `katrain/web/ui/src/components/PlayerCard.test.tsx`**

```tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import PlayerCard from './PlayerCard';

// NB: PlayerInfo.calculated_rank is typed string|null (pre-existing quirk — do NOT pass a raw
// number here or tsc fails). rank_display is optional. Keep fixtures type-valid.
const ladderInfo = {
  player_type: 'player:ai', player_subtype: 'ai:ladder', name: 'AI (棋力阶梯)',
  calculated_rank: null, rank_display: '超越职业', periods_used: 0, main_time_used: 0,
};
const humanInfo = {
  player_type: 'human', player_subtype: '', name: 'User',
  calculated_rank: null, periods_used: 0, main_time_used: 0,  // rank_display omitted (optional)
};

describe('PlayerCard rank_display', () => {
  it('shows rank_display 段位 when present (ladder AI)', () => {
    render(<PlayerCard player="W" info={ladderInfo} captures={0} active={false} />);
    expect(screen.getByText('超越职业')).toBeInTheDocument();
    expect(screen.getByText('AI (棋力阶梯)')).toBeInTheDocument();
  });

  it('falls back to the calculated-rank path when rank_display is absent', () => {
    render(<PlayerCard player="B" info={humanInfo} captures={0} active={false} />);
    // rank_display absent + calculated_rank null -> "No Rank": proves `??` falls through, no 段位 leak
    expect(screen.getByText('No Rank')).toBeInTheDocument();
    expect(screen.queryByText('超越职业')).not.toBeInTheDocument();
  });
});
```

Adjust the `PlayerCard` props in the test to match its actual required props (read the component's prop types first; add any required props it needs to render, e.g. `captures`, `active`). If `t("No Rank", ...)` resolves to a localized string in the test environment, assert on that resolved value instead of the literal `"No Rank"`.

- [ ] **Step 8: Run frontend tests + both builds**

Run: `cd katrain/web/ui && npx vitest run src/components/PlayerCard.test.tsx`
Expected: PASS.

Run: `cd katrain/web/ui && npm run build && npm run build:kiosk-2d`
Expected: both succeed.

- [ ] **Step 9: Commit**

```bash
git add katrain/web/interface.py katrain/web/ui/src/api.ts katrain/web/ui/src/components/PlayerCard.tsx katrain/web/ui/src/components/PlayerCard.test.tsx tests/web_ui/test_ladder_injection.py
git commit -m "feat(ladder): rank_display 段位 nameplate + keep ladder-error diagnostics off the WS log channel"
```

---

### Task 6: i18n — 棋力阶梯 / 棋力等级 across all 11 languages

The keys `ai:golaxy_parity` and `ai:golaxy_parity_rung` currently have NO `.po` entries (they render their Chinese inline default in every language). Add real catalog entries so non-Chinese UIs localize correctly.

**Canonical workflow (per `.agents/skills/katrain-i18n-expert/SKILL.md`, codex round 7 fix):** Galaxy UI translations are NOT hand-edited in the `.po` files. The single source of truth is `GALAXY_TRANSLATIONS` in `scripts/batch_translate_galaxy.py`; running that script writes all 11 `.po` files (and clears the TODO comments so `i18n.py` won't overwrite them with English), then `i18n.py` compiles the `.mo`. Editing `.po` directly would be lost on the next batch run and is a workflow violation.

**Spanish (`es`) is INACTIVE at runtime (codex round 8, project policy — NOT a code change).** `i18n.py` skips `es` in both its TODO-scan and its `.mo`-compile loops (`i18n.py:19` `INACTIVE_LANGS = ["es"]`), and the runtime loads the compiled `.mo` (`core/lang.py:59` gettext; the web `/api/translations` reads the same catalog). So the batch script writes the Spanish translation into `es/katrain.po` (source stays complete for when `es` is reactivated), but `es/katrain.mo` is intentionally NOT recompiled — exactly how every other string in the catalog already behaves. This plan follows that established policy rather than force-compiling a one-off `es.mo` for two keys while the rest of the Spanish runtime catalog stays inactive. "All 11 languages" therefore means: 11 in the `.po` source; 10 active runtime `.mo` catalogs (es excluded by project policy). See Known Limitations.

**Files:**
- Modify (canonical source): `scripts/batch_translate_galaxy.py` — add two keys to `GALAXY_TRANSLATIONS`.
- Generated (do NOT hand-edit): `katrain/i18n/locales/*/LC_MESSAGES/katrain.po` (11 langs) via the batch script; `.mo` via `python i18n.py`.

**Interfaces:**
- Consumes: the `t('ai:golaxy_parity', ...)` / `t('ai:golaxy_parity_rung', ...)` call sites (Task 4). `t(key, default)` returns the catalog value when present, else the inline default (`i18n.ts:52-54`).

- [ ] **Step 1: Add both keys to `GALAXY_TRANSLATIONS` via the katrain-i18n-expert skill**

Invoke the `katrain-i18n-expert` skill to add two entries to the `GALAXY_TRANSLATIONS` dict in `scripts/batch_translate_galaxy.py`, each with **all 11 languages** (keys: en, cn, tw, jp, ko, de, es, fr, ru, tr, ua — cn ≠ zh, jp ≠ ja). Follow the existing entry shape in that file. Anchor values (the skill produces de/es/fr/jp/ko/ru/tr/ua):

| key | cn | en | tw |
|---|---|---|---|
| `ai:golaxy_parity` | 棋力阶梯 | Strength Ladder | 棋力階梯 |
| `ai:golaxy_parity_rung` | 棋力等级 | Rank Level | 棋力等級 |

- [ ] **Step 2: Run the batch script to write the `.po` catalogs**

Run: `uv run python scripts/batch_translate_galaxy.py`
Expected: it reports updating all 11 `katrain.po` files with the two new keys (and clears their TODO markers).

- [ ] **Step 3: Compile catalogs**

Run: `uv run python i18n.py`
Expected: `.mo` files regenerated for the 10 active languages, no errors. `es` is skipped by design (`INACTIVE_LANGS = ["es"]`) — its `.mo` is deliberately not recompiled; do NOT edit `i18n.py` or force an `es.mo` build.

- [ ] **Step 4: Verify the keys resolve (spot check)**

Run: `uv run python i18n.py -todo` (confirm no new "missing"/TODO warnings for these two keys among the active languages) and confirm the `en` catalog now contains `ai:golaxy_parity → "Strength Ladder"`. Optionally verify one more active language via gettext, e.g.:

```bash
uv run python -c "import gettext; t=gettext.translation('katrain','katrain/i18n/locales',languages=['cn']); print(t.gettext('ai:golaxy_parity'))"
```

Expected: `棋力阶梯`. (Spanish is intentionally source-only — `es/katrain.po` carries the translation, but its runtime `.mo` is not rebuilt, per the INACTIVE policy above. Do not assert the `es` runtime catalog.)

- [ ] **Step 5: Rebuild frontend so the served catalog picks up the change**

Run: `cd katrain/web/ui && npm run build`
Expected: success.

- [ ] **Step 6: Commit (include the canonical source, not just generated files)**

```bash
git add scripts/batch_translate_galaxy.py katrain/i18n/locales/
git commit -m "i18n(ladder): add 棋力阶梯 / 棋力等级 for all 11 languages"
```

---

## Known limitations / out of scope (documented, not TODO)

- **`rank_name` values stay Chinese data** (职业棋手 / 超越职业 / 5段 / KataGo 中等算力). They are backend data, not gettext keys — consistent with the existing untranslated `段/级` data. An English UI shows Chinese 段位 here. Localizing per-rung `rank_name` is a future follow-up, not this plan.
- **SGF export + DB rank columns** (`game.py:401` `rank_label(calculated_rank)`, `server.py` `black_rank`/`white_rank`) still read the numeric `calculated_rank` (None for ladder → `??`/empty). The 段位 is display-only via `rank_display`; recording it in saved games is a future follow-up.
- **Kiosk real-星阵 tunnel untouched** — `engine_client.py` / `PlatformEngineSetupPage.tsx` still show 星阵 names + elo. Separate authorization decision.
- **Spanish (`es`) ships source-only, not runtime (codex round 8).** `i18n.py` excludes `es` from `.mo` compilation (`INACTIVE_LANGS = ["es"]`), and the runtime loads compiled `.mo`. The two new ladder keys are written to `es/katrain.po` by the batch script (source complete for future reactivation) but the Spanish runtime catalog is not rebuilt — identical to how every other Galaxy string already behaves. A Spanish UI falls back to the English source string for these keys until `es` is reactivated. This matches the project's established i18n policy; forcing a one-off `es.mo` was rejected as inconsistent.
- **Generic KataGo engine query/result debug logging is OUT OF SCOPE (user-confirmed 2026-07-20).** The KataGo engine logs its outgoing query (with `maxVisits`) and completed-analysis stats (visit count, candidate count) via `self.katrain.log(...)` — local engine at `engine.py:430-434`/`480` (`OUTPUT_DEBUG`), HTTP engine at `engine.py:690-693` (`OUTPUT_INFO`) and its result log. `WebKaTrain.log` forwards these to the ZenMode TopBar, so a visit count can flash in the transient status bar during a ladder game. This is **not** a de-branding violation: it contains no 星阵 and no rung ladder index — only a generic KataGo `maxVisits`/`visits` number that appears identically for **every** AI mode and every interactive analysis, and always has. It is pre-existing, mode-agnostic engine diagnostics, not this task's ladder branding. Sanitizing core engine logging (all modes + all analysis, desktop + web) is a separate cross-cutting concern; the user chose to scope it out and document it here rather than change core engine behavior. **Scope of THIS plan's no-leak invariant:** the ladder AI's own durable + branded surfaces — nameplate (`AI (棋力阶梯)` + 段位), SGF `ai_thoughts`, the setup dropdown, the `/api/ladder-rungs` wire — carry no 星阵, no elo, no rung ladder index; and the ladder-SPECIFIC broadcast strings (the strategy-init settings dump, the success detail, the failure error) that named the rung index or 星阵 are rerouted server-side. The generic engine visit number is explicitly excluded.

## Self-Review

- **Spec coverage:** No 星阵 in user-visible strings → Task 4 (opponent + dropdown), Task 2 (the user-visible `ai_thoughts`/SGF/ZenMode log → `rank_name`, + no-星阵/no-rung regression on BOTH the success debug-log and the failure broadcast paths), Task 5 (nameplate 段位 + `:1018` docstring + ladder-error broadcast sanitized so no rung index reaches the TopBar), Task 3 (wire schema drops `golaxy_level_name`/`display_elo`). No elo / no 第N/40档 → Task 4 (rank_name only). Pro-tier + ceiling names → Task 2. Nameplate name vs 段位 split → Task 5. Commit nan fix → Task 1. i18n → Task 6. All covered.
- **Codex round 1 fixes folded in:** (high) ai.py `ai_thoughts` 星阵 leak → moved to Task 2 Step 6 (`_ladder_thought_label` from `rank_name`) + regression test. (high) `tsc` break → `rank_display?` optional (Task 5 Step 5) + type-valid PlayerCard test (Step 7). (medium) partial-update leak → `p.ai and …` guard + transition test (Task 5 Steps 1, 3).
- **Codex round 2 fix folded in:** (medium) the rewritten `ai_thoughts` still exposed the rung index + visits (user-visible via SGF/ZenMode) → `_ladder_thought_label(rung)` now returns `棋力阶梯 {rank_name}` only; rung/visits go to a separate debug channel; the regression test now also bans `rung`/`visits`/`39`/`[LadderStrategy]`.
- **Codex round 3 fix folded in:** (medium, verified) round 2's "`OUTPUT_DEBUG` log" was NOT actually non-user-visible — `WebKaTrain.log` (`interface.py:338-340`) broadcasts every level via `message_callback` → `SessionManager` WS (`session.py:141-146`) → `ZenModeApp` TopBar (`ZenModeApp.tsx:122-123`, no level filter), so rung/visits would still surface. Fixed: the success-path rung/visits detail now goes to the stdlib `logging.getLogger(__name__)` (`"katrain.core.ai"`) via `logger.debug`, which never reaches `message_callback`.
- **Codex round 4 fix folded in:** (high, verified) the SAME broadcast leak existed on the FAILURE path — `_do_ai_move`'s `LadderUnavailable` catch (`interface.py:1006`) interpolated the exception (which embeds `rung {n}`) into `self.log(..., OUTPUT_ERROR)`, and round 3's test only covered the success path. Fixed in Task 5 Step 3: both ladder-error branches (`interface.py:991-994` & `:1006`) now log via the module's stdlib `logger` (`"katrain_web"`); the user surface stays the generic `last_ladder_error` flag. Added `test_ladder_unavailable_does_not_broadcast_rung_index` (Task 5 Step 1) that triggers `LadderUnavailable` through `_do_ai_move` and asserts the `message_callback` broadcast carries no rung/visits/星阵 while the stdlib logger keeps `rung 39` for diagnostics.
- **Codex round 5 fix folded in:** (high, verified) a THIRD broadcast path — the shared base `AIStrategy.__init__` (`ai.py:336`) logs the raw settings dict via `katrain.log(..., OUTPUT_DEBUG)`; for a ladder player that dict is `{'rung': 39}`, leaking the rung index at construction time. Round 3's test was blind to it because `_mk(...)` constructs the strategy before installing the spy. Fixed in Task 2 Step 6: the base init settings-dump routes to the stdlib `logger.debug` (general fix, all strategies). Replaced the round-3 unit test with the end-to-end `test_ladder_generate_ai_move_keeps_rung_off_katrain_log` (Task 2 Step 1) that installs the `katrain.log` spy BEFORE `generate_ai_move(game, AI_LADDER, {'rung': 39})` and rejects `星阵`/`rung`/`visits`/`39` across every broadcast-bound log, while the stdlib logger keeps `visits=` for observability. This end-to-end test now covers all three ladder-code broadcast channels (init dump, success detail, returned thought).
- **Codex round 6 — scope decision (user-confirmed 2026-07-20, NOT a code change):** the exhaustive sweep found that the KataGo engine ITSELF logs its query (`maxVisits`) and result (visit count) via `self.katrain.log` (`engine.py:430-434`/`480` DEBUG, `:690-693` HTTP INFO), which `WebKaTrain.log` broadcasts. Codex's recommendation (sanitize core engine query/result logging for all modes + add engine-boundary tests) was assessed as **out of scope**: the leaked value is a generic KataGo `maxVisits`/visit number — no 星阵, no rung ladder index — present identically for every AI mode and every analysis, and a simple DEBUG level-gate wouldn't even catch the HTTP `OUTPUT_INFO` query log. The user confirmed scoping it out and documenting it (see Known Limitations) rather than changing core engine behavior. The three ladder-SPECIFIC broadcast fixes (rounds 3–5) stand; the plan's no-leak invariant is scoped to the ladder AI's own branded/durable surfaces, not the shared engine's diagnostics.
- **Type consistency:** `rank_name` (Python `LadderRung`, TS `LadderRung`) and `rank_display` (Python `get_state` per-player dict, TS `PlayerInfo`) are used identically in producing and consuming tasks. `/api/ladder-rungs` response `{rung, rank_name}` matches the TS `LadderRung` exactly.
- **Codex round 7 fix folded in:** (medium) Task 6 invoked the katrain-i18n-expert skill but only listed the generated `.po`/`.mo` files, omitting the skill's mandated canonical source `scripts/batch_translate_galaxy.py` (`GALAXY_TRANSLATIONS`). Fixed: Task 6 now edits `GALAXY_TRANSLATIONS` (both keys, all 11 langs), runs `scripts/batch_translate_galaxy.py` to write the `.po` files, then `i18n.py`, and commits the script alongside the locales. Codex accepted the round-6 engine-logging scope boundary and raised no other issue.
- **Codex round 8 fix folded in:** (medium) `i18n.py` excludes `es` from `.mo` compilation (`INACTIVE_LANGS = ["es"]`) and the runtime loads `.mo`, so the batch-written Spanish `.po` would not reach the Spanish runtime catalog — breaking a literal "all 11 runtime languages" reading. Reconciled to the project's existing policy: the Spanish translation ships in `es/katrain.po` (source), the runtime `.mo` for `es` is intentionally not rebuilt (consistent with every other string), and Task 6's compile/verify steps + a Known Limitation now state this explicitly. Codex accepted the round-6 scope boundary and the round-7 canonical-source fix; this was the only remaining issue.
- **Placeholder scan:** i18n de/es/fr/jp/ko/ru/tr/ua strings are produced by the katrain-i18n-expert skill (the sanctioned mechanism) into the canonical `GALAXY_TRANSLATIONS` source, not left as TBD; every code step shows complete code.
