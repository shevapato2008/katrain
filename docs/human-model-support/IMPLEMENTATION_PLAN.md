# Implementation Plan: Human-Like Model Support for HTTP Engines

This document outlines the steps to enable human-like model support for the HTTP backend and details the data flow from the Web UI to the engine.

## 1. Core Implementation (`katrain/core`)

### 1.1 Update Configuration
*   **File:** `katrain/config.json` (Default)
*   **Action:** Add a new key `http_has_human_model` under the `engine` section.
*   **Default:** `false` (safest default).

### 1.2 Update `KataGoHttpEngine`
*   **File:** `katrain/core/engine.py`
*   **Class:** `KataGoHttpEngine`
*   **Change:**
    *   In `__init__`, read the new config value:
        ```python
        self.has_human_model = self.config.get("http_has_human_model", False)
        ```
    *   (Optional) If we want to be smarter, we could try to send a "dummy" query with `humanSLProfile` and check for errors, but a config flag is more robust for now.

### 1.3 Verify Query Construction
*   **File:** `katrain/core/engine.py`
*   **Method:** `BaseEngine.build_analysis_query`
*   **Verification:** Ensure `extra_settings` (which carries `humanSLProfile`) is merged into `overrideSettings` correctly.
    *   *Current Code check:*
        ```python
        "overrideSettings": {**settings, **(extra_settings or {})},
        ```
    *   *Conclusion:* This is already correct. No changes needed here.

## 2. Data Flow & Web UI Integration

This section addresses the specific scenarios for the Web UI.

### 2.1 Obtaining and Storing "AI Strategy" (Popup: New Game/Change Rules)

**Scenario:** User selects "Ranked" or "Pro" strategy for Black/White in the Web UI.

1.  **UI Side (Web):**
    *   The frontend (Vue/React/etc.) has a form for "Black Player" and "White Player".
    *   When the user selects a strategy (e.g., "ai:rank"), the frontend sends a POST request to the backend API (e.g., `/api/game/configure` or `/api/players`).
    *   **Payload Example:** `{"B": {"type": "ai", "strategy": "ai:rank"}, "W": {"type": "human"}}`

2.  **KaTrain Core Side:**
    *   The web server handler calls the `KaTrain` instance.
    *   **Method:** `katrain.players_info[color].update(player_type, player_subtype)`
    *   **Code Path:**
        ```python
        # In the API handler
        strategy = request_data['B']['strategy'] # e.g., "ai:human" (which maps to AI_HUMAN constant)
        katrain.players_info["B"].update(player_subtype=strategy)
        ```
    *   **Storage:** This updates the in-memory `Player` objects in `katrain.players_info`.

### 2.2 Obtaining and Storing "Level of Strength" (Popup: AI Settings F7)

**Scenario:** User sets "Ky Rank" to "5k" or "Pro Year" to "1920".

1.  **UI Side (Web):**
    *   The frontend displays inputs for specific settings based on the selected strategy.
    *   When changed, it sends a POST/PUT request to update settings (e.g., `/api/config`).
    *   **Payload Example:** `{"section": "ai", "key": "ai:human", "value": {"human_kyu_rank": 5}}`

2.  **KaTrain Core Side:**
    *   The handler updates the central configuration.
    *   **Method:** `katrain.config(path, value)` is effectively used, but usually specific methods like `update_config` are exposed.
    *   **Code Path:**
        ```python
        # Updates katrain/config.json in memory and potentially persists it
        katrain.config["ai"]["ai:human"]["human_kyu_rank"] = 5
        ```
    *   **Storage:** Stored in `katrain.config` (dictionary).

### 2.3 Passing Information to KataGo HTTP Engine

**Scenario:** It is the AI's turn to move.

1.  **Trigger:** `Game.game_loop` or `Game.play` determines it's an AI turn.
2.  **Strategy Lookup:**
    *   `ai_mode = game.current_player.player_subtype` (e.g., `AI_HUMAN`).
    *   `ai_settings = katrain.config("ai/" + ai_mode)` (Retrieves the dict `{ "human_kyu_rank": 5 }`).
3.  **Move Generation (`katrain/core/ai.py`):**
    *   `generate_ai_move` is called with `ai_mode` and `ai_settings`.
    *   It instantiates `HumanStyleStrategy(game, ai_settings)`.
    *   `HumanStyleStrategy.generate_move` executes:
        1.  **Profile Creation:** Calculates string `"rank_5k"` from `ai_settings["human_kyu_rank"]`.
        2.  **Override Settings:** Creates dict `{'humanSLProfile': 'rank_5k'}`.
        3.  **Request:** Calls `engine.request_analysis(..., extra_settings={'humanSLProfile': 'rank_5k'})`.
4.  **Engine Communication (`katrain/core/engine.py`):**
    *   `KataGoHttpEngine.request_analysis` receives `extra_settings`.
    *   It builds the JSON payload:
        ```json
        {
          "id": "...",
          "moves": [...],
          "overrideSettings": {
             "humanSLProfile": "rank_5k",
             ...
          }
        }
        ```
    *   It POSTs this JSON to the configured HTTP URL.
5.  **Server Side:**
    *   The running KataGo process (started with `-human-model`) receives the request.
    *   It sees `humanSLProfile`, activates the human model, and returns a move distribution matching "5k" strength.

## 3. Server-Side Setup (Reference)

For this to work, the user must run KataGo on the server as follows:

```bash
./katago analysis \
  -model /path/to/strong-model.bin.gz \
  -human-model /path/to/human-model.bin.gz \
  -config /path/to/analysis_config.cfg
```

*   **Note:** The `analysis_config.cfg` should be compatible with both models.
