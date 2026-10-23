# Lobby Game Independent Code Review — 2026-10-23

**Status: Approved**

Independent Astra Max review of `5016186ed..351b28dc4947d80b656ad8bea493daf1180a0c94`, including backend commit `0e223cb454458e549874e98ce3159a3c4283a652`. Read the applicable repository instructions, approved implementation plan, actual product/test diff, and relevant existing session, bridge, lease, engine-client and game-operation code. No material findings requiring revision.

- The new endpoint authenticates ordinary human lobby seats, snapshots the server-owned position, releases session locks before awaiting bounded analysis, and rechecks eligibility/session/position before returning. Existing temporary-analysis leases and the new single-flight flag clean up on success, failure and cancellation.
- Box forwarding validates the active identity generation and mapped room again after awaiting, projects only position identity and finite ownership data, and neither applies a state response nor broadcasts private analysis. General analysis restrictions are unchanged.
- The click-only client drops results after position or availability changes, converts ownership coordinates for the existing board renderer, and keeps failures retryable. Lobby presentation retains existing count/respond, degraded-count retry, result, pass/resign/exit and physical-board flows. Other game modes retain their existing panel; connection state becomes true only when the current socket opens.

Fresh focused verification performed by this reviewer:

- `./.venv/bin/python -m pytest -q tests/web_ui/test_pvp_territory.py tests/web_ui/test_pvp_box_routes.py -k 'territory' --tb=short` — **48 passed**, 19 deselected, exit 0.
- From `katrain/web/ui`: `npx vitest run src/kiosk/hooks/useLobbyTerritory.test.tsx src/kiosk/components/game/LobbyGamePanel.test.tsx src/hooks/useGameSession.connection.test.tsx src/api.lobbyTerritory.test.ts` — **33 passed across 4 files**, exit 0.
- `git diff --check 5016186ed..HEAD` — exit 0; reviewed product HEAD remains `351b28dc4947d80b656ad8bea493daf1180a0c94`.

The controller's broader integrated checks, production build and browser/visual evidence are documented separately; this review did not repeat them or the unrelated baseline failures. Focused engine tests use deterministic substitutes, so approval does not claim live GPU or two-device acceptance. No product code changed, no push/deployment/restart performed.
