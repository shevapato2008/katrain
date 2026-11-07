# Galaxy root routing — implementation verification and independent review

Product range: `09c2a167151e1e363e520785adfa3e885ac71420` → `495652db2d4faf845690dda2fc5d68359287760b`.

## Independent reviews

- An isolated spec reviewer inspected the actual complete diff and returned **Spec compliant**, no material missing/extra requirements. Separately verified 43 UI cases, 6 strict-Kiosk routing cases, 64 backend/WS routing cases and diff whitespace.
- A new independent `gpt-6-astra` / `max` agent reviewed product code, locked full/strict build output, the pinned cloud helper, and the frozen bounded RK3562 operator. Final result: **APPROVED**, no unresolved blocking or important issues.
- During operator review, the startup-failure recovery branch was strengthened: a newly started acceptance Go target may be cleaned up with HTTP unavailable only while the owned original page remains untouched at about:blank and the maintenance lock is still owned. Potential real-game state remains a refusal. A fault-injection test verifies file rollback, original Hermes mode, exact launcher URL and lock cleanup.
- Approved one-off RK operator: `output/releases/galaxy-root-20261108/rk-katrain-only.py`, SHA256 `a4c9cdad76929225f3696acfc9cd032d5b6afa265fa712b10d33d6fb83e0cb2f`. Nine offline tests independently passed. Instructions describe its bounded manifest and read-only/default vs explicit apply modes.
- Pinned existing cloud helper SHA256: `98e816acbe780baf95e8f8168073ba2894efe852bb0bd3c0b454264e89027108`.

## Verification

- Controller UI integration: 32 files, **304 passed / 4 build-mode skips**.
- Kiosk-only router: **6 passed / 10 full-mode skips**, both strict and non-strict configurations.
- Controller backend: new isolated SPA routes, four leave/forfeit destinations, WS route order and guest bootstrap: **69 passed**. No engine/lifespan startup or production database writes.
- Actual Chromium/Vite route journeys: **3 passed**. Root remains `/`, navigation/refresh/search/return use root URLs, old paths remain at 404, Kiosk stays separate, and legacy `POST /api/session` never occurs.
- Exact `git archive` source built after `npm ci`: full `npm run build` and `npm run build:smartbox-kiosk-2d` passed TypeScript, production build, module-based Galaxy exclusion, no-three/live checks and strict token guard. Locked Vite 8.0.16, Vitest 4.1.8 and React Router DOM 6.30.4.
- Full output: 492 files, index SHA256 `497dd4c90a38090cb7c3050d014f1d31036c4084d89fad83fab7b87462a033cd`; strict output: 385 files, index SHA256 `d52ff979c3ea1bec18a5e88dea809d124f6a59aef7791e3509e700192eb88e43`. Actual module report `{"galaxyModules":[]}` and strict manifest `{"box_sso_strict":true,"schema":1}`. Neither output contains a ZenModeApp chunk.
- Built assets were served through the actual FastAPI route registration without lifespan: root/new deep links and both slash forms returned the new immutable HTML; retired Galaxy URLs, missing API and missing JS remained 404; actual entry asset HTTP bytes matched its manifest hash.
- `git diff --check` passed. Existing bundle-size advisory and datetime deprecation warnings remain.

The full pre-existing termination test file has **5 passed / 28 setup errors** from missing `kifu_name_changes` immutability triggers in its lifespan fixture; this was reproduced before implementation. The new four URL tests use the established isolated no-lifespan fixture path. The unrelated fixture issue was not expanded into a database change.

Live Git publication, cloud rollout and physical-device acceptance are recorded separately in the release receipt; this review does not claim those actions have already occurred.
