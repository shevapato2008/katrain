# Golaxy AI-ladder calibration — operator runbook

This directory holds the **operator-run** (NOT CI-tested) calibration tools for the 37-rung
hybrid strength ladder (`katrain/core/ladder.py`). Only Golaxy-aligned Band B rungs 26..36
are valid calibration opponents; native HumanSL Band A and the api-less ceiling are not:

| File | Purpose |
|---|---|
| `adapters.py` | Shared, unit-tested primitives: `our_move` (our engine via `/analyze`), `golaxy_move` (typed Golaxy genmove-tunnel opponent), `adjudicate` (black-relative final score). |
| `run_smoke.py` | **Task 9 (this doc).** Level re-verify (5 rungs) + a ~10-game smoke + timing, BEFORE committing hours to the full run. Writes `results/smoke_report.json`. |
| `run_calibration.py` | **Task 8/P3b.** The full empirical calibration: 7 anchors × ~50 games each, checkpointed, resumable. Reads `pass_code`/`resign_code` from `results/smoke_report.json`. |
| `bake_results.py` | **Task 10.** Turns measured Elo into corrected `ladder.py` rung values: per-band (kyu/amateur-dan/pro/super-pro) offset+slope fit, tie/reversal-aware (`banded_correction`/`classify_pairs`/`apply_corrections`/`bump_ladder_version` — unit-tested in `tests/core/test_bake_results.py`). Never edits `ladder.py` itself; prints/writes values for a human to paste in (see Steps 8–11 below). |
| `results/` | Checkpoints + reports. `smoke_report.json` (token-free) is safe to commit; per-anchor `.jsonl` checkpoints and raw logs generally are not needed in the repo. |

Everything below is written to be **executed**, not just read. Follow it top to bottom the
first time you calibrate against a freshly deployed engine.

---

## Step 1: Obtain a Golaxy access token

The genmove tunnel (`katrain/web/platforms/golaxy/engine_client.py`) needs a live
`Authorization: bearer <access_token>` header. Two ways to get one:

**Option A — reuse the existing platform-adapter login** (if you already have a working
Golaxy account wired into KaTrain's platform login flow): extract the `access_token` your
session already holds (see `katrain/web/platforms/golaxy/adapter.py`'s auth flow) and export
it directly — skip to "Export the token" below.

**Option B — paste a browser-captured token** (simplest if you don't have a scripted login):
1. Log into <https://19x19.com> in a normal browser.
2. Open DevTools → Network tab, start a 人机 (vs-AI) game, and make one move.
3. Find the `genmove` request (`api.19x19.com/api/engine/dcnn/tunnel/genmove`) in the Network
   panel; open its Request Headers and copy the `Authorization: bearer <...>` value's token
   part (everything after `bearer `).

**Export the token** (never commit it, never paste it into a shared doc/ticket):
```bash
export GOLAXY_TOKEN='<paste the token here>'
# or, if you'd rather not export it into every shell session:
mkdir -p ~/.katrain && echo '<paste the token here>' > ~/.katrain/golaxy_token.txt
```
Both `run_smoke.py` and `run_calibration.py` read `$GOLAXY_TOKEN` first, falling back to
`~/.katrain/golaxy_token.txt`. **Redaction reminder:** if you paste captured request
headers/URLs anywhere (chat, a ticket, a commit message) for debugging, redact the token
value first — it is a live credential for a real Golaxy account.

Tokens expire; if a run starts failing partway through with `AuthExpired`
(`code=6003 msg="invalid token"`), re-capture and re-export/re-write the token file (see
`run_calibration.py`'s `_golaxy_move_with_reauth`, which retries once after doing exactly this).

## Step 2: Point the dev engine at prod `:8000`

Calibration needs a **real, reachable KataGo HTTP analysis server with the human-SL model
loaded** (`has_human_model: true`) — not a local subprocess engine, and not a server without
the human model, since most rungs (`humansl`/`humansl_search` mechanism) require
`humanSLProfile` support.

In this checkout's `~/.katrain/config.json` (or `katrain/config.json` if running unconfigured),
set:
```json
{
  "engine": {
    "backend": "http",
    "http_url": "http://<prod-host>:8000",
    "http_analyze_path": "/analyze",
    "http_health_path": "/health"
  }
}
```
Verify before running anything:
```bash
curl -s http://<prod-host>:8000/health | python3 -m json.tool
```
Confirm the response includes `"has_human_model": true` (see `katrain/core/engine.py`'s
`create_engine`, which auto-detects this from `/health` and sets `engine.has_human_model`
accordingly). If it's `false` or absent, the humanSL rungs (most of the ladder) cannot be
calibrated against this server — point at the correct deployment first.

`run_smoke.py --base-url` / `run_calibration.py --base-url` both default to
`http://127.0.0.1:8000` — pass the real address explicitly if the engine isn't local
(e.g. `--base-url http://<prod-host>:8000`), independent of whichever `config.json` this
checkout has on disk (that config is only used to source `wide_root_noise`, see below — the
`--base-url` the HTTP calls actually hit is a separate, explicit flag).

## Step 3: `wide_root_noise` must match the DEPLOYED server

`adapters.our_move` accepts a `wide_root_noise` override, but it is **never** allowed to fall
back to its hard-coded default during calibration (G2: calibrating against a different
`wideRootNoise` than production serves would measure the wrong engine). Both `run_smoke.py`
and `run_calibration.py` read it from THIS checkout's `katrain/config.json` `engine` block by
default and log what they used:
```
wide_root_noise = 0.0400 (from this checkout's katrain/config.json engine block)
```
If the deployed `:8000` server is known to run a different value, pass
`--wide-root-noise <value>` explicitly — and confirm that value against the live server's
actual config, since a silent mismatch calibrates against a different strength curve than
production actually serves.

## Step 4: Run the smoke gate

```bash
GOLAXY_TOKEN=<redacted> uv run python \
  superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_smoke.py \
  --base-url http://localhost:8000 \
  --out superpowers/tracks/golaxy-ai-ladder-parity/calibration/results
```

What it does (see `run_smoke.py`'s module docstring + `probe_level`/`run_smoke_anchor`
docstrings for the exact contract):
1. **Level re-verify** — one genmove each at 5 representative Band B rungs
   (准6段/准7段/准8段/9段/星阵3星 → api levels 2200/2400/2600/3000/3300), timed, with any wire error
   (`Retryable`/`Fatal`/`QuotaExhausted`/`AuthExpired`) recorded instead of crashing the sweep.
2. **~10-game smoke** — 2 anchors (rung 26 = 准6段, rung 30 = 准8段; 5 games each by default,
   `--games-per-anchor` to widen), alternating our color, using the SAME fail-closed
   `play_one_game` loop the full calibration harness uses. Records per-move timing for both
   sides and the **golaxy-terminal rate** per anchor (see "Trusted terminals" below).
3. Writes `results/smoke_report.json` with `pass_code`/`resign_code` both `null` — these are
   filled in MANUALLY (Step 5 below), never by this script.

Expect this to take a few minutes (mostly Golaxy's own genmove latency + the `--throttle 2.0`
default between games — raise `--throttle` if Golaxy starts rate-limiting/erroring).

**Important — no API pass/resign probe exists.** You cannot make `run_smoke.py` (or any
script) elicit a Golaxy pass or resign via genmove: the `moves` history this tunnel accepts
holds ONLY board coords (see `engine_client.engine_genmove`), and the pass/resign wire
*encoding* — which out-of-board int(s) Golaxy's reply uses to mean "I pass" / "I resign" — is
exactly the unknown this whole gate exists to resolve. There is no "keep playing until Golaxy
passes" code path to reverse-engineer it from; it can only be observed by watching the real
web client's own network traffic. That's Step 5 below.

## Step 5: Manual pass/resign sentinel capture (browser) — REQUIRED, cannot be scripted

This is the one part of Task 9 that is inherently a human-in-a-browser step, not code. Do this
once per Golaxy protocol version (i.e., re-do it if 19x19.com ships a client update and the
smoke-run golaxy-terminal rate suddenly jumps — see "Trusted terminals" below).

1. Log into <https://19x19.com>, start a 人机 (vs-AI) game (any level).
2. Open DevTools → Console and hook `XMLHttpRequest` to capture every `genmove` call's
   response body — this is the SAME method that originally reverse-engineered the protocol
   (see `superpowers/tracks/kiosk-play-golaxy/golaxy-protocol.md` §6 "复现方法"):
   ```js
   (function () {
     const open = XMLHttpRequest.prototype.open;
     XMLHttpRequest.prototype.open = function (method, url, ...rest) {
       this.__u = url;
       return open.call(this, method, url, ...rest);
     };
     const send = XMLHttpRequest.prototype.send;
     XMLHttpRequest.prototype.send = function (...args) {
       this.addEventListener("load", function () {
         if (this.__u && this.__u.includes("genmove")) {
           console.log("[genmove]", this.__u, "->", this.responseText);
         }
       });
       return send.apply(this, args);
     };
   })();
   ```
3. **(a) Pass:** click the UI's "停一手/pass" control. Read the console log line for that
   move — it will show either (i) a NEW `genmove` request/response for Golaxy's reply after
   your pass (record `data.coord` from THAT response as `pass_code` if it's a distinctive
   out-of-board value), or (ii) confirm the client never calls `genmove` again after a pass
   (in which case there IS no "pass reply coord" from Golaxy's side to capture for OUR pass —
   what you actually need is what coord GOLAXY sends when **Golaxy** passes, which you'll see
   as `data.coord` in a `genmove` response during normal play, whenever Golaxy elects not to
   place a stone. If Golaxy never passes in your sample game, you cannot observe `pass_code`
   this way — see "if you can't observe a code" below).
4. **(b) Resign:** click the UI's "认输/resign" control (do this in a SEPARATE game/tab from
   (a), since a resign ends the game). Watch whether resigning triggers its own distinct
   endpoint/response (i.e., resign might be a UI-only concession with NO `genmove` involved at
   all — in which case there is no `resign_code` to capture; Golaxy resigning is instead
   something you'd only ever observe as an unusual `data.coord` in a `genmove` RESPONSE when
   **Golaxy** is losing badly enough to concede — watch for that in a lopsided smoke game, or
   deliberately let a weak-rung game run long enough for Golaxy to fall far behind).
5. Record whatever exact `data.coord` value(s) you observe for each case, if any. **Redact the
   token** from anything you copy/paste elsewhere (the console log lines above don't include
   it, but the accompanying request URL does — the Authorization header is not shown by
   `console.log` here, but double-check before pasting a raw HAR export anywhere).
6. Write the values into `results/smoke_report.json`:
   ```json
   {
     ...
     "pass_code": <int or null>,
     "resign_code": <int or null>
   }
   ```
   (Everything else in that file — `level_probes`, `games`, `per_move_timing`,
   `per_anchor_golaxy_terminal_rate`, `errors` — was already written by `run_smoke.py`; only
   edit the two `*_code` fields.)

**If you can't observe a code either way:** leave it `null`. `run_calibration.py` degrades
gracefully — every Golaxy stop it can't classify as pass/resign is recorded as an unverified
`"terminal"` (never scored as a win/loss either way), and it logs a prominent warning
recommending you check the golaxy-terminal rate (below) before trusting the numbers.

**Validation is enforced in code, not by you:** `adapters._valid_sentinels` only honors
`pass_code`/`resign_code` that are (a) plain ints, (b) strictly out-of-board (`not in
[0, board_size**2)`), and (c) distinct from each other. Anything else — an in-board int, a
non-int, or `pass_code == resign_code` — is silently dropped back to `None`, so a
copy-paste mistake here can only ever make MORE stops "unverified terminal" (safe / conservative
direction), never mis-score an ordinary reply as a resign/pass.

## Step 6: Trusted terminals — the hard gate on parity conclusions

`adapters.golaxy_move` classifies every Golaxy genmove reply into exactly one of: a real board
coord, `"resign"` (only if `resign_code` is captured+valid and matches), `"pass"` (only if
`pass_code` is captured+valid and matches), or `"terminal"` — an **unverified** out-of-board
reply that `play_one_game` NEVER scores as a win or loss (`inconclusive_terminal`).

This means: **for any anchor where `pass_code`/`resign_code` were not captured (or don't
apply), an unknown fraction of that anchor's games are silently thrown out as inconclusive —
and you cannot know from the number alone whether the games thrown out were ones Golaxy was
winning, losing, or drawing.** Excluding them is a **selection bias of unknown direction**,
not a simple under-count you can mentally correct for.

`smoke_report.json`'s `per_anchor_golaxy_terminal_rate` (from the smoke run) exists exactly to
let you judge, BEFORE spending hours on the full P3b run, whether this bias is likely to
matter:

- If `per_anchor_golaxy_terminal_rate` for an anchor is **~0** (e.g. Golaxy essentially always
  produces a legible board-coord reply or a small number of natural passes you were able to
  classify), that anchor is **trusted** even without captured sentinel codes — exclusion is
  immaterial because there's almost nothing being excluded.
- If it is **non-trivial** (Golaxy frequently returns unclassified out-of-board replies) AND
  you did NOT capture valid `pass_code`/`resign_code` in Step 5, that anchor is **untrusted**.
  **Do not use an untrusted anchor's win rate to draw a parity conclusion or to bake/relabel
  rungs in Phase P3b** — report the rate, and the fact that it's untrusted, rather than a
  number the reader might mistake for a clean win/loss ratio.
- An anchor is **trusted** whenever EITHER holds: (pass_code AND resign_code captured+valid),
  **or** golaxy-terminal rate ~0. Both being absent (uncaptured codes AND a material
  golaxy-terminal rate) is the only "untrusted" case.

Record, per anchor, in whatever notes accompany a P3b run: the golaxy-terminal rate, whether
`pass_code`/`resign_code` were in effect, and therefore whether that anchor is trusted or
untrusted — this becomes part of Task 10's SC2 reporting.

## Step 7: Go/no-go criteria — review `smoke_report.json` before starting P3b

Before running the (hours-long) full calibration in `run_calibration.py`, confirm ALL of the
following from `results/smoke_report.json` + the smoke run's console log:

1. **All 5 `level_probes` entries have `ok: true`** (equivalently: no `error` field, meaning
   `code="0"` on every genmove) — in particular, **no `7003`** (`QuotaExhausted`) on plain
   genmove calls; a `7003` there would be unexpected (genmove itself isn't one of the metered
   道具 tunnels) and should be investigated before proceeding.
2. **Strong-level per-move time is within tolerance** — the strong-level single-move latency
   (9段/星阵3星) lives in `level_probes`, NOT `per_move_timing` (that key only covers the two
   ~10-game smoke anchors, rungs 26/30). Inspect the `level_probes` entries where
   `level == 3000` (9段) and `level == 3300` (星阵3星), field `elapsed_s`, plus the two smoke
   anchors' `per_move_timing["26"]` (准6段) and `per_move_timing["30"]` (准8段) `golaxy_move_s`/
   `our_move_s` entries: none should be uncomfortably close to the 180s HTTP timeout ceiling
   (`engine_client.GENMOVE_TIMEOUT_SECONDS`). A level probe that itself took >60-90s is a
   signal the live server/network is under load; consider re-running before committing to
   ~50-game anchors at that level.
3. **The ~10-game smoke completed with no quota errors** — check `errors` is empty (or only
   contains transient, already-retried issues you understand), and `games` has entries for
   (approximately) `games-per-anchor × 2` games total. A quota error (`QuotaExhausted`) here
   would be unexpected on the genmove path; if you see one, check whether the account has some
   other metered restriction in play before running the full anchors.
4. **`scoreLead` confirmed black-relative** — spot check at least one settled game's
   `black_score` in `games` against the actual board result you'd expect from its move list
   (e.g. a game your engine won convincingly as Black should show a clearly positive
   `black_score`, and vice versa for White). This confirms `reportAnalysisWinratesAs: BLACK`
   is actually honored by the live `:8000` server the same way the runtime engine forces it —
   see `adapters.adjudicate`'s docstring.
5. **Trusted-terminals gate (Step 6):** for EACH of the two smoke anchors, either (a)
   `pass_code`+`resign_code` are captured and valid (per `_valid_sentinels`), or (b) that
   anchor's `golaxy_terminal_rate` is ~0. **If neither holds for an anchor, do not draw parity
   conclusions from it in Phase P3b** — report it as untrusted (see Step 6) instead of quoting
   a win rate for it.

If all 5 pass: proceed to Phase P3b (`run_calibration.py`, Task 10's `bake_results.py`). If
any fail: fix the underlying issue (engine health, token, network, rate limiting) and re-run
`run_smoke.py` — don't sink hours into the full run on a shaky smoke result.

**Commit the token-free report.** `smoke_report.json` never contains the token by
construction (see `run_smoke.py`'s schema — only `level_probes`/`games`/timing/error data +
the two sentinel codes you add by hand), so it's safe to commit as-is once Step 5's codes are
filled in (or confirmed `null` with a documented golaxy-terminal rate per Step 6).

## Step 8: HARD PRE-GATE — trustworthy terminals, per anchor, before you bake anything

**Parity conclusions require trustworthy terminals.** This is a hard gate, re-stated here
because Task 10's `bake_results.py` is the point where a bad anchor's win rate would otherwise
get baked permanently into `ladder.py`. For **each** of the 7 anchors below, before using its
win rate for anything:

- **(a)** validated `pass_code`+`resign_code` (per `_valid_sentinels`, Step 5/6 above) are in
  effect for this run, **or**
- **(b)** that anchor's own `golaxy_terminal_rate` (from its `run_calibration.py` summary, NOT
  the smoke run's) is **~0**.

An anchor failing **BOTH** (a) and (b) is **untrusted**: its win rate must **NOT** be used to
bake or relabel rungs in `bake_results.py`, even informally — the excluded/unclassified
terminal games are a **selection bias of unknown direction** (you cannot know whether the
games thrown out were ones Golaxy was winning, losing, or drawing), not a simple under-count
you can mentally correct for. Report an untrusted anchor's rate AND its untrusted status; do
not feed it into `--anchors` derived corrections, and flag it in the final report (Step 11) so
a later re-run with a fresh sentinel capture (Step 5) can supersede it.

## Step 9: Run the full P3b calibration — 7 anchors × ~50 games

The 7 calibration anchors (rung numbers are this checkout's — re-derive via
`katrain.core.ladder.get_rung`/`golaxy_level_name` if `ladder.py` has since been edited):

| Golaxy level | `golaxy_api_level` | rung # | band (per `bake_results.band_of_rung`) |
|---|---|---|---|
| 准6段 | 2200 | 26 | amateur |
| 准7段 | 2400 | 28 | pro |
| 准8段 | 2600 | 30 | pro |
| 准9段 | 2900 | 32 | pro |
| 9段 | 3000 | 33 | pro |
| 星阵1星 | 3100 | 34 | super |
| 星阵3星 | 3300 | 36 | super |

These 7 span the complete Golaxy-aligned Band B range. Band A is intentionally absent because
its native HumanSL ranks have no Golaxy counterpart. The existing bake model is not compatible
with that hybrid split; see the Step 10 blocker before attempting to convert measurements.

Run ~50 games per anchor (half each color — `run_calibration.py` alternates automatically),
resumable/checkpointed, throttled to avoid rate-limiting:

```bash
GOLAXY_TOKEN=<redacted> uv run python \
  superpowers/tracks/golaxy-ai-ladder-parity/calibration/run_calibration.py \
  --anchors "26:50,28:50,30:50,32:50,33:50,34:50,36:50" \
  --base-url http://<prod-host>:8000 \
  --throttle 2.0 \
  --out superpowers/tracks/golaxy-ai-ladder-parity/calibration/results
```

This is a multi-hour run (350 games total, plus the score-stability re-check on any
non-two-pass game). If it's interrupted (crash, token expiry not auto-recovered, network
blip): **just re-run the exact same command** — `_already_done` counts each anchor's
checkpointed `results/rung_<n>.jsonl` lines and resumes at the first unplayed index, replaying
the SAME deterministic alternating-color sequence, so no game is replayed or double-counted.
If the token expired mid-run and the one automatic re-auth retry (`_golaxy_move_with_reauth`)
also failed, re-capture a fresh token (Step 1) and re-run the same command — resume picks up
from where the checkpoint left off. Watch the console for the golaxy-terminal-rate warnings;
if an anchor's rate looks materially worse than what the smoke run suggested, stop and
re-examine Step 8's gate for that anchor before continuing to burn hours on it.

When all 7 anchors finish, `results/summary.json` holds the per-anchor
`elo_vs_opponent`/`elo_ci95`/`golaxy_terminal_rate` that `bake_results.py` consumes next.

## Step 10: Bake — `bake_results.py`

> **Blocked for the 37-rung hybrid:** the current bake algorithm still models the superseded
> four-band Golaxy ladder and treats every api-less rung as a super-band search rung. Do not
> run it against the hybrid table until that calibration model is redesigned to leave native
> HumanSL Band A and the api-less ceiling untouched. The command below is retained only as
> historical operator context for that follow-up.

```bash
uv run python \
  superpowers/tracks/golaxy-ai-ladder-parity/calibration/bake_results.py \
  --summary superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/summary.json \
  --out superpowers/tracks/golaxy-ai-ladder-parity/calibration/results/baked_ladder.json
```

**Before running this, drop any untrusted anchor's row from `results/summary.json`** (or a
copy of it) per Step 8 — `bake_results.py` has no way to know an anchor is untrusted on its
own; that judgment is Step 8's, made by a human reading the golaxy-terminal rate and the
sentinel-capture status.

This prints, per band, the fitted `{offset, slope, n, rungs}` (per-band, **never** a single
global line — `corr["kyu"]["offset"] != corr["amateur"]["offset"]` etc. by construction), the
adjacent-anchor tie/reversal classification (`classify_pairs`: overlapping-CI pairs are
`"tie"`, CI-confirmed inversions are `"reversed"` — **neither is ever "corrected" by nudging a
knob**; they are recorded), whether `config_sanity_key` stayed non-decreasing across the full
baked 40-rung table after `apply_corrections` (it always should — that's the whole point of
the clamp; a logged "UNRESOLVED" regression here means a knob's range was exhausted and needs
a human look, not a re-run), and the bumped `LADDER_VERSION` (`bump_ladder_version`). The full
baked table (every rung's new `human_sl_profile`/`max_visits`) is written to `--out` as JSON.

**Paste the corrected values into `katrain/core/ladder.py` by hand** — `bake_results.py`
**never** edits `ladder.py` directly (this is deliberate: a bake is not a mechanical
find-replace, it's a judgment call an operator should look at, especially around any
documented tie/reversal). At minimum:
1. Bump `LADDER_VERSION` to the value `bake_results.py` printed.
2. For each rung `bake_results.py` changed, update its `_KYU_PROFILE`/`_DAN_PROFILE`/
   `_SEARCH_VISITS` entry (or `human_sl_profile`/`max_visits` directly) to match
   `results/baked_ladder.json`'s `"rungs"` list.
3. Leave anything in a band with **zero** anchor coverage untouched (it wasn't corrected —
   don't invent a correction for it).

## Step 11: Re-guard, spot-check, and record the report

After pasting the baked values in:

```bash
CI=true uv run pytest tests/core/test_ladder.py tests/core/test_bake_results.py -v
```
`test_config_key_non_decreasing`/`test_rung_40_max_key` etc. must still pass — if they don't,
the manual paste introduced an inconsistency `bake_results.py`'s own clamp would not have
produced; fix the transcription rather than the test.

**Spot-check 3–4 non-anchor rungs** (rungs that got NO direct anchor, only the interpolated
per-band offset+slope): play a handful of games at each against the corresponding Golaxy
level and sanity-check the result is in the right ballpark for that band's tolerance:
- **deep kyu** (weakest ~5 rungs, e.g. 18级–14级): tolerance **±1.5 段** (段=class/rank step) —
  wider, because deep-kyu humanSL profiles are coarser and noisier.
- **mid kyu / amateur-dan and above**: tolerance **±1 段**.

**Record, per anchor, in the P3b report:**
- Measured win rate over **conclusive** games, and whether it falls in **SC2's [40%, 60%]**
  window (pass/fail) — this is the primary "did this rung actually match its claimed Golaxy
  level" signal.
- Its **trusted/untrusted** status (Step 8) and **golaxy-terminal rate**.
- Any **documented tie** (adjacent anchors with overlapping CI) or **documented reversal**
  (CI-confirmed inversion) `bake_results.py` reported — ties/reversals are findings to report,
  not defects to silently paper over.
- The per-band `{offset, slope}` that was actually applied.
- The spot-check results for the 3–4 non-anchor rungs, against the tolerance above.

This report (SC2 pass/fail per anchor + ties/reversals + trusted/untrusted status) is what
gets handed back for the go/no-go decision on shipping the newly baked `ladder.py`.

---

## Known open items (carried from `plan.md`)

- Rung 37 is the api-less `b28@500` visits ceiling and is not a valid calibration anchor.
- The 98%-decisive / lead-margin thresholds in `adapters._is_settled` are conservative
  starting values from offline reasoning; Step 7 point 4 above is the first live check —
  refine them from real smoke endgames if they look too strict/loose in practice.
- If 19x19.com's client changes its genmove response shape or pass/resign convention (protocol
  drift), the Step 5 capture and this whole smoke gate should be re-run before trusting a new
  P3b run against the same anchors.
