# Lobby Game Plan Review — 2026-10-23

**Status: Approved**

Reviewed the single implementation chunk against the accepted 1024×600 screenshot and sibling HTML/CSS/JS artifact, then checked the relevant server, session, bridge, ranked territory, activity-lease, GamePage, control-panel and board-overlay source paths at base `5016186ed`. No implementation or sibling files were changed.

The plan is executable and appropriately bounded: it retains the current game/count/reconnect/exit flow, introduces a participant-only ownership request, uses central server-owned state, and confines the visual change to lobby games. The plan correctly distinguishes central ordinary multiplayer (`free`, two positive participant IDs, `pvp_lobby_human_session`) from the local `pvp_lobby` mirror. It does not relax general analysis guards or reuse ranked quotas. Focused mocked-engine contracts, hook/component tests and representative real React browser verification are sufficient for this slice.

No material blocking issues found. Carry these source-specific clarifications into implementation:

- Reuse `temporary_analysis_lease` from `katrain/web/core/ranked_session_guard.py:116`; it releases the activity lock before yielding and cleans up its temporary lease in `finally`. Do not use the server's persistent-analysis context across `await` or create a second tracking framework.
- Use existing `Icon` name `map-trifold` for the lobby territory action: the accepted image and artifact show a folded map. `grid-nine` is the old production territory icon, whereas the approved visual uses it for coordinates. This correction is lobby scoped.
- Return the same position identity as `WebKaTrain.get_state()` (`game.game_id`, `id(current_node)`), and define `move_count` consistently with the frontend input. For replay payloads retain setup stones and `initialPlayer` with the server's rules/komi, following `core/engine.py`. Recheck terminal and awaiting-count facts after analysis, including the game-level terminal state and `pvp_lobby_awaiting_count`; the current node's `end_state` alone is insufficient.
- Keep the existing urgent count/identity/hardware state above ordinary territory feedback, and retain the full-page central reconnect branch where the board cannot safely be presented. New ownership data must not enter `node.analysis`, ordinary game broadcasts or official count results.

The controller independently identified the first two clarifications during review and intends to make them explicit in the plan. They do not require another design decision or expanded review cycle.
