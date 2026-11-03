# Go stone appearance and KataGo model display implementation plan

> **For agentic workers:** Use `superpowers:subagent-driven-development` for independent tasks. Keep review and tests proportional to the changed behavior.

**Goal:** Give Galaxy and Kiosk a consistent, publishable 2D Go stone appearance, align Galaxy 3D materials, and show the actual analysis KataGo model ID in Settings → About.

**Architecture:** A small stone appearance registry owns a default original shell/slate skin and an optional 3D material recipe. Existing Canvas and SVG boards consume it without changing board geometry, moves, or overlays. The KaTrain backend reads the *same* report analysis service configured for cron, resolves the default route to the loaded model's real metadata, and exposes only a display-safe name; the UI does not label it as a report model or expose gameplay model details.

**Tech stack:** React, TypeScript, Canvas/SVG, Three.js, FastAPI, pytest, Vitest.

---

## Chunk 1: Model identity

### Task 1: Safe analysis model endpoint

**Files:** `katrain/web/core/config.py`, `katrain/web/api/v1/endpoints/health.py`, `docker-compose.yml`, `tests/web_ui/test_health.py` (or nearest existing focused test).

- [ ] Add an optional environment-configured report-engine health URL, wired to the same analysis service as cron's `KATAGO_URL` in deployment config; in board mode, read the **normalized remote KaTrain health field** instead of guessing the local gameplay engine.
- [ ] Resolve `models[default_model]` from the actual analysis service `/health` response, require it to be running and checksum verified, and derive a display name from actual model metadata (safe basename of `model_path`, without weight extensions); `default_model` is only a route alias and must not be displayed as the model ID. Return only a bounded display name, never paths, hashes, or internal URLs. If unavailable, report no ID; never substitute the gameplay model.
- [ ] Keep existing `status`, `version`, and `engines` contract unchanged and test configured, unavailable, and malformed upstream responses.
- [ ] Confirm deployment configuration supplies the report service URL in the server environment and matches cron's actual analysis endpoint; no hardcoded `TF3` or `B28` in UI.

### Task 2: About row

**Files:** `katrain/web/ui/src/api.ts`, `katrain/web/ui/src/kiosk/pages/SettingsPage.tsx`, `katrain/web/ui/src/kiosk/__tests__/SettingsPage.test.tsx`.

- [ ] Add a single `KataGo 模型` row showing the dynamic analysis model ID, with a truthful unavailable state. Do not show a gameplay model ID or call it a report model.
- [ ] Check the row at 1024×600 without changing settings navigation or typography behavior.

## Chunk 2: Original 2D stone skin

### Task 3: Shared appearance

**Files:** `katrain/web/ui/src/components/board/stoneAppearance.ts`, new original assets beside it, focused tests.

- [ ] Create a small registry keyed by appearance ID, with 2D black/white sprite URLs and optional 3D recipe. Default to an original procedurally drawn shell/slate visual; do not ship the tutorial photo texture, which the manifest limits to TEST.
- [ ] Keep a deterministic coordinate-based white-stone variation and a safe default fallback so more skins can be added without editing each board. Keep the registry pure data; Three.js material translation belongs in `Board3D`.

### Task 4: 2D consumers

**Files:** `katrain/web/ui/src/components/Board.tsx`, `katrain/web/ui/src/components/board/boardUtils.ts`, `katrain/web/ui/src/components/live/LiveBoard.tsx`, `katrain/web/ui/src/components/tsumego/TsumegoBoard.tsx`, `katrain/web/ui/src/components/tutorials/SGFBoard.tsx`, `katrain/web/ui/src/kiosk/shell/GoBoardSvg.tsx`, `katrain/web/ui/src/kiosk/tutorial/OgsCourseBoard.tsx`, and small preview boards only where they show playable stones.

- [ ] Route Canvas and SVG stone images through the shared appearance; preserve hit targets, coordinates, number/last-move overlays, and 1024×600 Kiosk geometry.
- [ ] Preview representative Galaxy/Kiosk play, tutorial, kifu, and review boards at target sizes. Compare the page against the existing design, including contrast of numbers and markers.

## Chunk 3: Galaxy 3D and delivery

### Task 5: Material mapping

**Files:** `katrain/web/ui/src/components/Board3D/StoneMesh.tsx`, `katrain/web/ui/src/components/Board3D/StoneGroup.tsx`, `katrain/web/ui/src/components/Board3D/tutorialStoneTextures.ts`, `katrain/web/ui/src/components/tutorials/tutorialStoneSprites.ts`, focused tests.

- [ ] Apply the selected appearance's original 3D color/roughness/shell recipe to Galaxy 3D stones, with deterministic coordinate variation for static, animated, and ghost stones. Replace random material variation. Preserve existing top-down recording behavior but keep its TEST photo sprites isolated from production board imports; move any pure hash helper needed by normal 3D into the safe shared module. Keep Kiosk 2D only.
- [ ] Check 2D/3D toggle and inspect stone material without adding new dependencies or 3D payload to the Kiosk bundle.

### Task 6: Focused verification

- [ ] Run focused backend/frontend tests, `npm run build:kiosk-2d`, and one real 1024×600 Galaxy/Kiosk preview with the stone changes; verify the About row with live or representative health data.
- [ ] Confirm production board chunks and the Kiosk build contain no tutorial source photograph or derived `tutorial-stones` sprite; confirm clean diff and document any environment configuration needed before deployment.
