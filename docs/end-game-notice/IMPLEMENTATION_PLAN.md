# Implementation Plan: End Game & Pass Notifications

## 1. Components to Modify

### `katrain/web/ui/src/App.tsx`
This is the main controller that receives the `gameState` from the backend. It will handle the detection of "Pass" moves and "Game End" states to trigger notifications.

*   **State Management:**
    *   **Settings (Persistent):**
        *   `showPassAlert` (boolean): Default `true`.
        *   `playPassSound` (boolean): Default `true`.
        *   `showEndAlert` (boolean): Default `true`.
        *   `playEndSound` (boolean): Default `true`.
    *   **Notification State:**
        *   `notification` object: `{ open: boolean, message: string, severity: 'info' | 'success' }`.
    *   **Refs:**
        *   `prevNodeId`: To track the last processed node and avoid duplicate alerts on re-renders.
        *   `prevGameEnded`: To track if the game was already in an ended state (to avoid spamming "Game Ended" alerts).

*   **Logic (useEffect):**
    *   **Pass Detection:**
        *   Check if `gameState.current_node_id` changed.
        *   If `gameState.is_pass` is true:
            *   Identify the player who passed.
            *   Trigger `showPassAlert` (Visual) and `playPassSound` (Audio).
    *   **Game End Detection:**
        *   Check if `gameState.end_result` is present (truthy).
        *   If it transitioned from `null`/`false` to a value:
            *   Trigger `showEndAlert` (Visual) with result text.
            *   Trigger `playEndSound` (Audio).
    *   **Helper:**
        *   `playSound(soundName)`: Uses existing audio assets.

*   **Rendering:**
    *   Render a `<Snackbar>` with `<Alert>` at the top-center or bottom-center.

### `katrain/web/ui/src/components/Sidebar.tsx`
Add a new settings section for these UI notifications.

*   **UI Additions:**
    *   New Section: "NOTIFICATIONS" (or "UI SETTINGS").
    *   Toggles (Switch):
        *   "Pass Alert (Visual)"
        *   "Pass Sound"
        *   "Game End Alert (Visual)"
        *   "Game End Sound"
*   **Props:**
    *   Receive the boolean states and their setters from `App.tsx`.

## 2. Dependencies
*   **Material-UI:** `Snackbar`, `Alert` (from `@mui/material`), `Switch` (from `@mui/material`), `NotificationsIcon` (from `@mui/icons-material`).
*   **Assets:**
    *   `assets/sounds/boing.wav` (Pass sound).
    *   `assets/sounds/countdownbeep.wav` (Game End sound).

## 3. Step-by-Step Guide

### Step 1: Sidebar Updates
1.  **Imports:** Add `Switch`, `NotificationsIcon` to `Sidebar.tsx`.
2.  **Interface:** Update `SidebarProps` to include:
    *   `settings: { showPassAlert: boolean, playPassSound: boolean, ... }`
    *   `onUpdateSettings: (key: string, value: boolean) => void`
3.  **JSX:** Add the "NOTIFICATIONS" section with list items containing the switches.

### Step 2: Main App Logic (App.tsx)
1.  **Imports:** Import `Snackbar`, `Alert` from `@mui/material`.
2.  **State Init:** Initialize settings state, reading from `localStorage` for persistence.
    *   *Optimization:* Create a persistent `Audio` object map (or simple cache) outside the component or in a ref to avoid recreating `HTMLAudioElement`s on every render/sound.
3.  **Pass Detection Logic (Refined):**
    *   Use refs to track `prevGameId`, `prevNodeId`, and `prevHistoryLength`.
    *   In the `gameState` effect:
        ```typescript
        // Reset refs if game_id changes
        if (gameState.game_id !== prevGameId.current) {
            prevGameId.current = gameState.game_id;
            prevNodeId.current = gameState.current_node_id;
            prevHistoryLength.current = gameState.history.length;
            prevGameEnded.current = !!gameState.end_result;
            return;
        }

        const isNewMove = gameState.history.length > prevHistoryLength.current;
        const isDifferentNode = gameState.current_node_id !== prevNodeId.current;
        const isAtTip = gameState.current_node_index === gameState.history.length - 1;

        // Detect Pass: Must be a new move, different node, AND at the end of history
        // Note: Backend does not currently emit 'sound' events for passes, so we handle it here.
        if (isNewMove && isDifferentNode && isAtTip && gameState.is_pass) {
             let passedPlayer = 'Unknown';
             if (gameState.player_to_move === 'B') passedPlayer = 'White';
             else if (gameState.player_to_move === 'W') passedPlayer = 'Black';
             
             if (showPassAlert) {
                 // Safe label derivation
                 const msg = passedPlayer === 'Unknown' 
                    ? t('Pass') 
                    : `${t(passedPlayer)} ${t('Passed')}`;
                 setNotification({ open: true, message: msg, severity: 'info' });
             }
             if (playPassSound) {
                 playSound('boing'); 
             }
        }
        
        // Update refs
        prevNodeId.current = gameState.current_node_id;
        prevHistoryLength.current = gameState.history.length;
        ```
4.  **Game End Logic:**
    *   In the same effect:
        ```typescript
        // Edge trigger: Game just ended
        if (gameState.end_result && !prevGameEnded.current) {
             if (showEndAlert) {
                 setNotification({ 
                     open: true, 
                     message: `${t('Game Ended')}: ${gameState.end_result}`, 
                     severity: 'success' 
                 });
             }
             if (playEndSound) {
                 // 'tada.wav' does not exist, using 'countdownbeep.wav' or reusing 'boing.wav'
                 playSound('countdownbeep'); 
             }
        }
        prevGameEnded.current = !!gameState.end_result;
        ```
5.  **Render:** Add the `Snackbar` component to the `App` return JSX.

### Step 3: Verification
1.  **Pass:** Play a move, then Pass. Verify Alert + Sound.
2.  **AI Pass:** Force AI to pass (or play until end). Verify Alert + Sound.
3.  **End Game:** Pass twice. Verify "Game Ended" Alert + Sound (`countdownbeep`).
4.  **Navigation:**
    *   Go back 10 moves.
    *   Go forward (redo) to a pass move. **Verify NO alert** (because `history.length` didn't change).
    *   Click on a node in the tree that is a pass. **Verify NO alert**.
5.  **New Game:** Start a new game. Verify refs reset and no spurious alerts.

## 4. Code Snippets

### Audio Helper Optimization
```typescript
const audioCache = useRef<Record<string, HTMLAudioElement>>({});

const playSound = (sound: string) => {
  if (!audioCache.current[sound]) {
    audioCache.current[sound] = new Audio(`/assets/sounds/${sound}.wav`);
  }
  const audio = audioCache.current[sound];
  audio.currentTime = 0; // Reset to start for rapid replay
  audio.play().catch(e => console.warn("Failed to play sound", e));
};
```

### Detection Logic (Final)
```typescript
  // In App.tsx

  // State & Refs
  const [showPassAlert, setShowPassAlert] = useState(() => localStorage.getItem('showPassAlert') !== 'false');
  const [playPassSound, setPlayPassSound] = useState(() => localStorage.getItem('playPassSound') !== 'false');
  const [showEndAlert, setShowEndAlert] = useState(() => localStorage.getItem('showEndAlert') !== 'false');
  const [playEndSound, setPlayEndSound] = useState(() => localStorage.getItem('playEndSound') !== 'false');
  
  // Handlers for Sidebar
  const handleUpdateSettings = (key: string, value: boolean) => {
      localStorage.setItem(key, String(value));
      if (key === 'showPassAlert') setShowPassAlert(value);
      if (key === 'playPassSound') setPlayPassSound(value);
      if (key === 'showEndAlert') setShowEndAlert(value);
      if (key === 'playEndSound') setPlayEndSound(value);
  };

  const prevGameId = useRef<string | null>(null);
  const prevNodeId = useRef<number | null>(null);
  const prevHistoryLen = useRef(0);
  const prevGameEnded = useRef(false);

  useEffect(() => {
    if (!gameState) return;

    // Game change detection
    if (gameState.game_id !== prevGameId.current) {
        prevGameId.current = gameState.game_id;
        prevNodeId.current = gameState.current_node_id;
        prevHistoryLen.current = gameState.history.length;
        prevGameEnded.current = !!gameState.end_result;
        return; 
    }

    const isNewMove = gameState.history.length > prevHistoryLen.current;
    const isDifferentNode = gameState.current_node_id !== prevNodeId.current;
    const isAtTip = gameState.current_node_index === gameState.history.length - 1;

    // 1. Pass Detection
    if (isNewMove && isDifferentNode && isAtTip && gameState.is_pass) {
        let passedPlayer = 'Unknown';
        if (gameState.player_to_move === 'B') passedPlayer = 'White';
        else if (gameState.player_to_move === 'W') passedPlayer = 'Black';

        if (showPassAlert) {
            const msg = passedPlayer === 'Unknown' 
                ? t('Pass') 
                : `${t(passedPlayer)} ${t('Passed')}`;
            setNotification({ 
                open: true, 
                message: msg, 
                severity: 'info' 
            });
        }
        if (playPassSound) playSound('boing');
    }

    // 2. Game End Detection
    if (gameState.end_result && !prevGameEnded.current) {
         if (showEndAlert) {
             setNotification({ 
                 open: true, 
                 message: `${t('Game Ended')}: ${gameState.end_result}`, 
                 severity: 'success' 
             });
         }
         if (playEndSound) playSound('countdownbeep');
    }

    // Update refs
    prevNodeId.current = gameState.current_node_id;
    prevHistoryLen.current = gameState.history.length;
    prevGameEnded.current = !!gameState.end_result;

  }, [gameState, showPassAlert, playPassSound, showEndAlert, playEndSound, t]); 
```
