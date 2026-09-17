# RK3562 Kiosk Fast Entry and Launcher Polish

**Date:** 2026-09-17  
**Status:** Approved design  
**Repositories:** `smartbox-software` launcher/setup wizard and this KaTrain web UI

## Goal

Make chess-module transitions feel complete and stable on the 1024×600 RK3562 kiosk, make login usable before authentication when WiFi is not configured, align launcher typography with the product, and shorten the perceived Go startup without introducing a second concurrent KataGo process on the 2 GB device.

## Findings

A recent cold Go start on the board showed this sequence:

- KaTrain's board-mode web service was usable after about 16 seconds.
- The normal `g170-b6c96` network took about 16 seconds to load.
- The HumanSL network then took about 26 seconds.
- Warm-up completed at about 46 seconds total.

The KaTrain service and KataGo service already start concurrently. The normal and HumanSL networks are arguments to one KataGo process and load serially. Starting two KataGo processes in parallel is not selected because the device has 2 GB RAM and a single Mali/OpenCL device; peak memory and GPU contention would be a larger risk than the expected benefit.

OpenCL tuning is already cached. `openclUseFP16` is currently disabled even though the device advertises FP16 support, so FP16 is a benchmark candidate rather than an assumed fix.

The launcher progress bar already has a `ready` visual state, but successful switching navigates before JavaScript commits and paints that state. The cursor is not being hidden by a cursor-management daemon; the flicker appears only while the full-screen transform animation is active on the Rockchip X11/Mali stack.

## Selected approach

Use a staged, low-risk improvement:

1. Enter the Go web UI as soon as the web service is reachable, while KataGo continues warming.
2. Show an honest, nonblocking engine-warming status inside the Go UI and disable only the local-AI entry points until the existing health endpoint reports the engine reachable.
3. Benchmark FP16 on the real board and enable it only if it is stable and materially faster.
4. Keep the single KataGo process and existing two-model feature set. Lazy HumanSL loading is deferred unless this approach remains insufficient.

## Launcher readiness contract

### Go mode

The launcher distinguishes two readiness levels:

- `ui_ready`: the configured `LAUNCHER_GO_URL` (currently `http://127.0.0.1:8001/kiosk`) satisfies the launcher's existing `_probe` contract: after redirects, any HTTP response below 500 counts as reachable; connection errors and 5xx responses do not.
- `engine_ready`: KataGo `/health` reports `phase=ready` and `ready=true`.

`switch_to("go")` still performs the existing serialized stop, cgroup-release verification, and systemd target start. It returns success once `ui_ready` is true; it does not wait for `engine_ready`. The KataGo service keeps warming under systemd after the launcher lock is released.

Launcher status preserves `ready` as full engine readiness for compatibility and adds `ui_ready` for early navigation and recovery from a concurrent-switch `409`. Other chess modes retain their existing full-readiness behavior.

The updated launcher JavaScript uses `ui_ready` for Go. During a one-version rolling deployment, if `ui_ready` is absent it falls back to the older conservative `ready` field; it never treats a missing field as early readiness.

If the KaTrain UI does not become reachable within the existing start timeout, switching fails normally and remains on the launcher. Engine warm-up failure after UI entry is handled in the Go UI rather than represented as a successful engine start.

### Transition completion

Every successful mode switch uses one navigation helper:

1. Set `data-stage="ready"`.
2. Replace the subtitle with the localized ready text.
3. Wait for two `requestAnimationFrame` callbacks so the ready state has reached a paint opportunity, then wait a 300 ms timer whose duration is exposed as a test seam.
4. Navigate to the target URL.

The minimum timer dwell is therefore 300 ms after the second animation-frame callback. If the helper receives a missing or empty URL, it enters the existing visible error state instead of navigating. Once a valid URL is assigned to `window.location`, browser navigation owns the outcome. The same helper is used by the direct switch response and polling/recovery paths.

### Cursor behavior

While the transition overlay is showing an active stage (`stopping`, `starting`, `warming`, or `ready`), the overlay and all descendants use `cursor: none`. The destination page restores the normal cursor automatically. Error state does not hide the cursor, so mouse users can see and activate Retry.

The spinner remains; this design avoids relying on uncertain compositor hints to correct a Rockchip driver interaction.

## Go UI warm-up state

The existing KaTrain `GET /api/v1/health` endpoint is the Go UI's source of truth. It already reports the local engine as `reachable`, `error_503`, or `unreachable`, so no new backend endpoint is required. In the current deployment it requests the same KataGo `/health` URL used by the launcher: KataGo returns HTTP 503 during `warming_normal` and `warming_human`, and HTTP 200 only for `phase=ready` with `ready=true`. Consequently KaTrain's `engines.local == "reachable"` is the UI-facing equivalent of launcher `engine_ready`. This equivalence is covered by a focused contract test; if KataGo health semantics change, both consumers must change together.

A small shared kiosk hook starts its clock on the first health request after the kiosk mounts and polls every two seconds whenever the local engine is not reachable. `error_503`, `unreachable`, a request failure, or a malformed response are all non-ready. For the first 120 seconds they render as warming; at 120 seconds they render as unavailable. Polling continues every two seconds after that boundary, so a later `reachable` response still recovers automatically without a reload. The kiosk shell shows a compact status banner:

- Warming: `AI 引擎准备中，可先使用棋谱、课程等功能`
- Unavailable after the normal warm-up budget: `AI 引擎暂未就绪，可稍后重试`

The free-AI and ranked-AI cards on the play home are disabled while warming and explain why. Local two-player, records, tutorials, and other non-engine paths remain available. When health changes to `reachable`, polling stops, the banner disappears, and the AI cards enable without a reload.

Existing backend error handling remains the final guard for deep links and failures that occur after readiness.

## FP16 benchmark gate

Compare the current `openclUseFP16=false` configuration with `true` on the RK3562 board using **service-cold, OS-cache-warm** Go-target starts, which represent normal kiosk mode switching. A measured start begins only after `smartbox-go.target` is stopped, its member processes and captured cgroups are gone, and the board temperature is at or below 65°C. Do not drop Linux page cache or KataGo's existing OpenCL tuning cache; those conditions remain identical for both configurations. The benchmark harness records the original effective value and restores it in a `finally`/trap path on interruption or failure; enabling FP16 after a passing result is a separate intentional configuration edit. Record, for each configuration:

- time until `warming_normal`, `warming_human`, and `ready`;
- successful completion of one normal-network analysis request and one HumanSL-profile request, with finite numeric output and a legal response;
- peak combined RSS for the Go target and any OpenCL/KataGo errors.

Perform one unmeasured conditioning start for each configuration, then six measured starts in the counterbalanced order FP32, FP16, FP16, FP32, FP32, FP16. Wait for the same temperature prerequisite before every run and record the starting temperature; if paired starts differ by more than 5°C, discard and repeat the hotter run. This yields three measured starts per configuration without grouping cache or thermal drift on one side.

Enable FP16 only if every run and both query types succeed, no new OpenCL/KataGo errors appear, and one of these numeric gates passes:

- median ready time improves by at least 10% while median peak combined RSS is no more than 5% above baseline; or
- median peak combined RSS improves by at least 10% while median ready time is no more than 5% slower than baseline.

Otherwise keep `openclUseFP16=false`. At the end of the experiment, verify the effective configuration and perform one successful cold start in the selected state. This experiment does not change model files or analysis settings.

## Homepage typography

Add a separate local font face, `SmartBox Display LongCang`, containing exactly the unique characters needed by `围棋`, `国际象棋`, `中国象棋`, and `五子棋`. Do not expand or rename `SmartBox Brand LongCang`; its three-glyph brand contract remains unchanged.

The four Chinese game labels use:

- `SmartBox Display LongCang`
- 28 px
- weight 400
- `font-synthesis: none`

English labels, status dots, card geometry, and imagery remain unchanged. Long Cang is display-only and is not used for small body copy.

## Login and registration

Keep the existing left brand panel and compact right-hand form. Use the user-approved compact network control in the title row:

- disconnected or unknown: `选择网络 ›`;
- connected: `<SSID> ›`;
- minimum 44×44 px touch area;
- click navigates to `/settings/wifi?return=login` or `return=register` according to the current form mode.

The SSID occupies a single bounded line with `overflow: hidden`, `text-overflow: ellipsis`, and `white-space: nowrap`; it cannot wrap or increase the card height.

Returning from WiFi settings restores the same login/register mode through the existing return contract. The submit-time offline modal remains as a race-condition fallback.

Visible Chinese UI copy on the auth gate uses the project's self-hosted `SmartBox Kai` / LXGW WenKai assets. The Latin brand lockup keeps its existing face. Font loading uses `font-display: swap`; the split assets ensure the browser downloads only the ranges present on screen.

The compact title-row control avoids increasing the registration card height at 1024×600.

## Error handling

- UI start timeout: stay on the launcher and show the existing retry state.
- Engine still warming: stay in the Go UI with honest status; do not show a generic fatal page.
- Engine warm-up fails or remains unavailable: change the banner from warming to unavailable and keep non-engine functions usable.
- WiFi status poll fails: render the network control as `选择网络 ›` rather than claiming a connection.
- Switch error: restore the cursor so Retry is usable.

## Tests and acceptance

Testing is limited to the changed behavior and likely regressions:

- launcher Python tests for separate Go `ui_ready` and `engine_ready` semantics, including `409` recovery;
- launcher JavaScript tests showing that successful paths commit `ready`, dwell, and navigate, and that WiFi selection preserves auth mode;
- focused KaTrain UI tests for warming banner and AI-card disable/enable behavior;
- a contract test pinning KaTrain `engines.local == "reachable"` to KataGo's HTTP-200 ready response and treating HTTP 503 as non-ready;
- font-build test verifying the display subset's exact cmap and leaving the brand subset unchanged;
- one representative 1024×600 browser preview for the launcher/auth typography and one board transition check;
- RK3562 timing and FP16 benchmark described above.

Acceptance criteria:

- Go leaves the launcher when the KaTrain UI is reachable instead of waiting for both networks.
- Local-AI actions cannot be started before KataGo is ready, and become available automatically afterward.
- The cursor never flickers during the transition because it is intentionally hidden, and it is visible on errors and destination pages.
- The final progress step is visibly reached before navigation for every module.
- Home game names use the approved Long Cang treatment.
- Login/register uses LXGW WenKai and provides a directly tappable WiFi selector without guest login.
- No second KataGo process is introduced.

## Non-goals

- Splitting normal and HumanSL networks into separate processes.
- Removing HumanSL-dependent features.
- Redesigning chess cards, the Go kiosk shell, or WiFi settings.
- Adding a new network-management backend.
- Broad launcher or KaTrain refactoring unrelated to these five issues.

## Delivery order

1. In `smartbox-software`, implement the approved launcher/auth typography and transition behavior with fixtureable UI states.
2. Produce a real 1024×600 preview and obtain user confirmation, as required by the repository workflow.
3. In `smartbox-software`, add the backward-compatible launcher `ui_ready` field and early-Go return behavior.
4. In KaTrain, consume its own health endpoint, show the warm-up banner, and gate the local-AI cards using the health equivalence defined above.
5. Run focused checks in each repository and the board transition acceptance with both versions deployed together.
6. Run the FP16 A/B benchmark and keep or revert the setting according to the gate above.
