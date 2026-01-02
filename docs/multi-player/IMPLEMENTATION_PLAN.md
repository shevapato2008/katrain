# Multi-Player / Multi-Session Implementation Plan

## Overview

The current KaTrain Web UI architecture allows for multiple concurrent sessions via the `SessionManager` in `katrain/web/server.py`. Each session (`WebSession`) instantiates its own `WebKaTrain` instance, which in turn creates a dedicated `Game` and `Engine` instance. This means the server-side infrastructure for supporting multiple independent games (players) is already in place.

However, to fully satisfy the requirement that "katrain service should use it game id to communicate with KataGo engine via http request", we need to ensure that:
1.  A unique `game_id` is generated for each new game.
2.  This `game_id` is propagated to the `Engine`.
3.  The `Engine` includes this `game_id` in the analysis queries sent to the KataGo server.

## Implementation Steps

### 1. Generate Unique Game ID

**File:** `katrain/core/game.py`

*   **Current Behavior:** `game_id` is generated using a timestamp (`datetime.strftime(datetime.now(), "%Y-%m-%d %H %M %S")`). This is not unique enough for concurrent users starting games simultaneously.
*   **Change:** Update `Game.__init__` to generate a UUID (or append a UUID to the timestamp) for `self.game_id`.
*   **Propagate to Engine:** In `Game.__init__`, after `self.game_id` is generated, iterate through `self.engines` and set a `game_id` attribute on them.

```python
# katrain/core/game.py

import uuid

class Game(BaseGame):
    def __init__(self, ...):
        # ...
        self.game_id = f"{datetime.strftime(datetime.now(), '%Y-%m-%d %H %M %S')}_{uuid.uuid4().hex[:8]}"
        # ...
        
        # Propagate game_id to engines
        for engine in self.engines.values():
            if hasattr(engine, 'set_game_id'):
                engine.set_game_id(self.game_id)
            else:
                 # Fallback/Injection if method doesn't exist yet (though we will add it)
                engine.game_id = self.game_id
```

### 2. Update Engine to Handle Game ID

**File:** `katrain/core/engine.py`

*   **Current Behavior:** `BaseEngine` and its subclasses do not store or use `game_id`. `build_analysis_query` constructs the query without this field.
*   **Change:**
    1.  Update `BaseEngine.__init__` to initialize `self.game_id = None`.
    2.  Add a `set_game_id(self, game_id)` method to `BaseEngine`.
    3.  Update `BaseEngine.build_analysis_query` to include `game_id` in the returned query dictionary if `self.game_id` is set.

```python
# katrain/core/engine.py

class BaseEngine:
    def __init__(self, katrain, config):
        # ...
        self.game_id = None

    def set_game_id(self, game_id):
        self.game_id = game_id

    def build_analysis_query(self, ...):
        # ...
        query = {
            # ... existing fields
            "id": f"QUERY:...", # Existing logic for query ID
            # Add game_id
        }
        if self.game_id:
            query["gameId"] = self.game_id
        
        # ...
        return query, visits
```

### 3. Verify KataGo HTTP Engine

**File:** `katrain/core/engine.py`

*   **Check:** Ensure `KataGoHttpEngine` uses `build_analysis_query`.
*   **Result:** It does. By modifying the base class method, the HTTP engine (and local engine) will automatically include the `gameId` field in the JSON payload sent to the KataGo server.

## Verification

1.  **Unit Tests:** Create a test case that initializes a `Game` and checks if the underlying `Engine` has the correct `game_id`.
2.  **Integration Check:** Start the web server, create a session, start a game, and verify (via logs or network inspection) that the HTTP request to KataGo contains `gameId`.

## Summary

This plan leverages the existing multi-session architecture and simply ensures the unique Game ID flows from the Game logic down to the Engine communication layer.
