# Galaxy root routing — implementation verification and independent review

Product range: `09c2a167151e1e363e520785adfa3e885ac71420` → `495652db2d4faf845690dda2fc5d68359287760b`.

## Independent reviews

- An isolated spec reviewer inspected the actual complete diff and returned **Spec compliant**, no material missing/extra requirements. Separately verified 43 UI cases, 6 strict-Kiosk routing cases, 64 backend/WS routing cases and diff whitespace.
- A new independent `gpt-6-astra` / `max` agent reviewed product code, locked full/strict build output, the pinned cloud helper, and the frozen bounded RK3562 operator. Final result: **APPROVED**, no unresolved blocking or important issues.
- During operator review, the startup-failure recovery branch was strengthened: a newly started acceptance Go target may be cleaned up with HTTP unavailable only while the owned original page remains untouched at about:blank and the maintenance lock is still owned. Potential real-game state remains a refusal. A fault-injection test verifies file rollback, original Hermes mode, exact launcher URL and lock cleanup.
- Initially approved one-off RK operator SHA256 `a4c9cdad76929225f3696acfc9cd032d5b6afa265fa712b10d33d6fb83e0cb2f`, with nine offline tests. Subsequent bounded amendments and the final executed hash are recorded below.
- Pinned existing cloud helper SHA256: `98e816acbe780baf95e8f8168073ba2894efe852bb0bd3c0b454264e89027108`.

## Verification

- Controller UI integration: 32 files, **304 passed / 4 build-mode skips**.
- Kiosk-only router: **6 passed / 10 full-mode skips**, both strict and non-strict configurations.
- Controller backend: new isolated SPA routes, four leave/forfeit destinations, WS route order and guest bootstrap: **69 passed**. No engine/lifespan startup or production database writes.
- Actual Chromium/Vite route journeys: **3 passed**. Root remains `/`, navigation/refresh/search/return use root URLs, old paths remain at 404, Kiosk stays separate, and legacy `POST /api/session` never occurs.
- Exact `git archive` source built after `npm ci`: full `npm run build` and `npm run build:smartbox-kiosk-2d` passed TypeScript, production build, module-based Galaxy exclusion, no-three/live checks and strict token guard. Locked Vite 8.0.16, Vitest 4.1.8 and React Router DOM 6.30.4.
- Initial reviewed archive output: 492 full files, index SHA256 `497dd4c90a38090cb7c3050d014f1d31036c4084d89fad83fab7b87462a033cd`; 385 strict files, index SHA256 `d52ff979c3ea1bec18a5e88dea809d124f6a59aef7791e3509e700192eb88e43`. Actual module report `{"galaxyModules":[]}` and strict manifest `{"box_sso_strict":true,"schema":1}`. Neither output contains a ZenModeApp chunk. The final published-checkout rebuild hashes are recorded below.
- Built assets were served through the actual FastAPI route registration without lifespan: root/new deep links and both slash forms returned the new immutable HTML; retired Galaxy URLs, missing API and missing JS remained 404; actual entry asset HTTP bytes matched its manifest hash.
- `git diff --check` passed. Existing bundle-size advisory and datetime deprecation warnings remain.

The full pre-existing termination test file has **5 passed / 28 setup errors** from missing `kifu_name_changes` immutability triggers in its lifespan fixture; this was reproduced before implementation. The new four URL tests use the established isolated no-lifespan fixture path. The unrelated fixture issue was not expanded into a database change.

## Approved release amendments and final artifacts

No product code changed after the reviewed range; software commit `16f60a1912c457db67eff033982fee5b6191a3eb` adds verification documentation only. Its clean published checkout was rebuilt with the lockfile, passing the same full/strict checks. Final full index SHA256: `def882d2dc6bd86fe88e155525908b780124ecbca1e5fb3aca77fe1e66d0a215`; final strict index: `f3677b7842bca169eb554a15979c4a3df51ce268a63ceb36eeef45a109ee5461`.

The independent Astra Max reviewer approved all final one-off operator amendments before their application:

- Cloud preparation `c3a4fdff1cafadfdb94bee71ce911cb3f618513b1c293c05201036265534dfda`: fresh baseline/prepared fingerprint equivalence, mount-shadow rejection, executable image verifier, and an ID-checked local base tag. Twenty offline cases passed.
- RK operator `3d38377dbeeb649eb479b916bfb3bf8e8cd06826025f7e9fa2cee8462c7817b7`: archive-based version evidence, stable systemd command fingerprint, and truthful signed-out library acceptance. Thirteen offline cases passed; unknown/loading/blank or wrong-feature states still fail.
- Same-filesystem candidate transfer `1c660547182aa454cd2e76b9ed4d88c0a65676fab80995bf8689dad26c7e8eb6`: exact inventory/hash/inode checks, retained backup/journal, no broad cleanup.

Final verdict remains **APPROVED**, no unresolved blocking or important findings. Actual Git publication, TEST/PROD rollout, RK recovery attempts and final device acceptance are recorded in [the release receipt](../../operations/galaxy-root-routing-release-2026-11-08.md).
