# Gomoku shared calibration release plan

**Goal:** Ship the verified five-point calibration and low-latency preview to both Go and Gomoku on RK3562 from pinned repository revisions.

**Architecture:** KaTrain owns the calibration backend and UI component. Gomoku imports the component from its `vendor/katrain` submodule and builds a separate static bundle. Deploy both source revisions and their matching bundles; do not rely on the existing static files.

**Tech stack:** Git submodules, Python/FastAPI, React/Vite, systemd, RK3562.

---

## Task 1: Land KaTrain

- [ ] Review and commit the calibration source, focused tests, reference images, and design notes on `fix/kiosk-ui-debug`.
- [ ] Merge current `origin/develop` into the branch; resolve conflicts without dropping either branch's behavior.
- [ ] Run the focused Python tests, frontend tests, and strict kiosk build on the merged tree.
- [ ] Push the branch, merge it into `develop`, verify the merged result, and push `develop`.

## Task 2: Pin SmartBox

- [ ] In a clean smartbox-software worktree at current `origin/main`, update `vendor/katrain` to the exact new KaTrain `develop` commit.
- [ ] Build Gomoku UI from the new vendor source; verify its bundle calls `/api/v1/geometry/snapshot`.
- [ ] Run Gomoku calibration contract tests and confirm the shared Python import resolves to the pinned submodule.
- [ ] Commit and push only the submodule pin and any necessary Gomoku integration fixes to `main`.

## Task 3: Deploy and verify

- [ ] Build Go strict kiosk and Gomoku static bundles from the pinned revisions.
- [ ] Deploy source and both static bundles to RK3562 while preserving unrelated on-device modules and the current mode.
- [ ] Verify actual served bundle versions, snapshot endpoint, camera readiness, and live preview in both modes.
- [ ] Measure Gomoku preview latency separately; restore the user's starting mode.

**Provisioning decision:** No new runtime dependency is needed. `install_gomoku` already installs vendored KaTrain editable. Its static-file existence check does not detect stale bundles, so deployment must explicitly build and sync Gomoku UI.
