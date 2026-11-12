# Local reference startup implementation plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development to implement this plan. Steps use checkbox syntax for tracking.

**Goal:** A fresh local physical-board game acquires its empty-board reference without a manual LED clear or recovery action.

**Architecture:** Keep the accepted reference-lifecycle design intact. At a genuine, current local-confirmation bootstrap enable transition, enqueue one existing non-strict LED clear before the MODE command. The normal queue, fresh SHOW ACK, 200 ms wait, two qualified frames and final owner gate remain the only reference authority. Repeated mode publications perform no additional clear.

**Tech Stack:** Existing Python VisionService, LedService, in-process worker and pytest fakes. No frontend, model, averaging, USB reset or new recorder changes.

**Base:** Published `ca78083a0d27a22d69a93c1dc25b5ae417308531` in isolated `reference-startup-20261112`, branch `fix/reference-startup-20261112`.

## Evidence and scope

- RK process started normally with the published code. The physical board and event 000002 were empty; camera metadata had matching applied/requested generations, effective controls, known ownership and a frame newer than controls completion.
- A new local physical game stayed in bootstrap, reference source unavailable and ordinary witness budget unspent. The LED startup handshake had ACKed CLEAR/SHOW/BRIGHT but did not populate the reference-lighting receipt; local orchestration and empty-guidance recovery do not guarantee another batch.
- After an ordinary LED clear and the existing UI's explicit recheck, the same empty game acquired a reference and became synced. The ordinary witness took 287.8 ms. This is not a second-retry measurement and does not satisfy a 50 ms processing target.
- Independent Astra Max cause/option review: root ignored artifact `output/diagnostics/reference-lifecycle-20261112/startup-plan-review1.md`. Option C avoids fabricating a startup receipt or overwriting a queued lighting intent.

## Chunk 1: One guarded initialization action

### Task 1 — Real bootstrap regression, then minimal service wiring

**Files:**
- Modify: `katrain/vision/service.py`, `VisionService.set_local_confirmation_mode`.
- Extend: `tests/test_vision/test_local_confirmation_window.py` and existing service-routing tests only where needed for source fencing.

- [ ] Add a failing regression by extending the existing real-bind/local-bootstrap fixture. Use actual LedService startup and its existing ACK fake, with no manual initial clear and no `lighting_disabled=True` shortcut. Bind a real local session, enable local confirmation, and publish the matching expected source as the API does.
- [ ] Before the queued clear's SHOW ACK, qualified camera frames must not create a reference or debit ordinary witness attempts. After real batch completion, two distinct frames later than `shown_at + 0.2` must create a real reference and release the bootstrap. Camera and detector may use the existing deterministic fakes; do not create a second framework.
- [ ] Confirm RED with the focused new test; record the actual failure.
- [ ] Add the initialization immediately after the existing supported-worker and identical-mode-tuple early returns, before nonce rotation or `SET_LOCAL_CONFIRMATION_MODE` is sent. On `enabled=True` only, call the existing `lighting_owner.clear(strict=False)` once when all of these are true:
  - LED ownership is present and lighting is not explicitly disabled;
  - session ID matches the current bound session, the worker is the bound worker and the current binding mode is still the anchored mode;
  - `binding_game_identity(bound_session)` equals its anchored identity;
  - the bound session's actual KaTrain game type is `pvp_local` and its existing game object's `game_id` equals the supplied game ID.
- [ ] Read existing attributes under the metadata lock. Do not acquire the game lock, call `get_state`, wait for serial ACK, or call public clear while holding the USB lock. The existing lock order is metadata → clear's intent → USB. A clear exception is logged and cannot fabricate a receipt or turn a successful binding into an exception; the existing bootstrap reports unavailable if qualification never arrives.
- [ ] Preserve all MODE/source/expected command ordering. `enabled=False` does not clear. Identical repeated True and redundant local bind do not clear. The existing explicit retry's False→True adds exactly one clear. Do not clear on generic `force_rearm`, ordinary expected publication or every polling tick.
- [ ] Extend the same fixture/call-count assertions for repeated bind/True, explicit retry, and stale session/game/worker plus disabled-lighting cases. Stale invocations must never clear another physical source. Reuse existing LED missing-ACK/new-intent tests instead of duplicating a concurrency matrix.
- [ ] Run the focused real-bootstrap regression and direct service binding/local-window regressions. Use the root environment `/Users/fan/Repositories/katrain-kiosk-debug/.venv/bin/python`; no installation or broad GPU run. Suggested final command: `python -m pytest -q tests/test_vision/test_local_confirmation_window.py tests/test_vision_bind_state.py tests/test_vision/test_service_event_routing.py`; run the existing real move-poller integrations separately if touched.
- [ ] Commit only this plan, the service and scoped tests. The runtime change must remain in the service; do not alter the LED handshake, worker eligibility, inference, status UX or existing budgets.

## Chunk 2: Review, integration and real deployment acceptance

- [ ] Obtain independent Astra model / Max effort plan approval (at most two rounds total), then use a fresh implementation subagent. Prepare the one-source deployment artifact independently while implementation runs. Root performs the existing focused integration check and obtains independent Astra Max code approval before publishing.
- [ ] Follow the user's four steps: fetch/merge develop into this feature branch and verify/push; merge/push develop; update/push smartbox-software main's vendor/katrain pointer using the isolated parent checkout; deploy to RK3562. Preserve unrelated working trees. No cloud deployment or UI rebuild is needed for this backend-only addition.
- [ ] Stop the owned temporary diagnostic run without restarting a live game, preserve its Mac evidence and receipts, normally finish only root's zero-move diagnostic game, and restore the old trace's three clean source states through its reviewed operator while idle. Never force-end a user game or restore account/DB/calibration snapshots.
- [ ] Publish the new service source through a separately reviewed, exact one-source app delta and preserve the current configuration, current calibration, USB state, resident services and whole-device stamp. Restore through the real authenticated launcher and verify camera, LED, engine and HTTP health.
- [ ] Rebase the unpublished diagnostic overlay onto the published fixed source; preserve its accepted three-panel semantics and source-only hooks. Review its narrow resulting delta/hash binding, then install and arm a fresh bounded run and Mac collector. The old trace restoration must never later reinstall the pre-fix service source.
- [ ] On the real empty board, open one normal local physical game using existing UI and calibration controls. Without calling manual `/led/clear` or recovery, prove bootstrap ready, a current accepted empty-board reference and its verified three-panel PNG on Mac. Read existing witness timing; label an ordinary witness honestly and do not claim a second retry or ≤50 ms unless observed.
- [ ] Leave the ready game to the user for physical placement and missing-stone/E18 restoration acceptance. Report actual published child/parent commits, installed app delta, evidence folder, measured timing and any physical checks still requiring the user.
