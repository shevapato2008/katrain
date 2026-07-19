# Golaxy AI-ladder calibration — operator runbook

This directory holds the **operator-run** (NOT CI-tested) calibration tools for the 40-rung
"对标星阵" ladder (`katrain/core/ladder.py`):

| File | Purpose |
|---|---|
| `adapters.py` | Shared, unit-tested primitives: `our_move` (our engine via `/analyze`), `golaxy_move` (typed Golaxy genmove-tunnel opponent), `adjudicate` (black-relative final score). |
| `run_smoke.py` | **Task 9 (this doc).** Level re-verify (5 rungs) + a ~10-game smoke + timing, BEFORE committing hours to the full run. Writes `results/smoke_report.json`. |
| `run_calibration.py` | **Task 8/P3b.** The full empirical calibration: 7 anchors × ~50 games each, checkpointed, resumable. Reads `pass_code`/`resign_code` from `results/smoke_report.json`. |
| `bake_results.py` | **Task 10.** Turns measured Elo into corrected `ladder.py` rung values (not built yet as of Task 9). |
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
1. **Level re-verify** — one genmove each at 5 rungs spanning the whole wire range
   (18级/12级/1级/9段/星阵3星 → api levels 220/280/1100/3000/3300), timed, with any wire error
   (`Retryable`/`Fatal`/`QuotaExhausted`/`AuthExpired`) recorded instead of crashing the sweep.
2. **~10-game smoke** — 2 anchors (rung 18 = 1级, rung 28 = 5段; 5 games each by default,
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
2. **Strong-level per-move time is within tolerance** — inspect `per_move_timing["36"]`
   (9段) and `per_move_timing["39"]` (if present) `golaxy_move_s` entries plus the two smoke
   anchors' timings: none should be uncomfortably close to the 180s HTTP timeout ceiling
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

---

## Known open items (carried from `plan.md`)

- Rung 40 is a `net='b18'@500` visits ceiling in v1 (no real b28@:8002 super-ceiling exposed
  yet) — not part of the calibration anchors above.
- The 98%-decisive / lead-margin thresholds in `adapters._is_settled` are conservative
  starting values from offline reasoning; Step 7 point 4 above is the first live check —
  refine them from real smoke endgames if they look too strict/loose in practice.
- If 19x19.com's client changes its genmove response shape or pass/resign convention (protocol
  drift), the Step 5 capture and this whole smoke gate should be re-run before trusting a new
  P3b run against the same anchors.
