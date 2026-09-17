# Vision Recovery Voice Prompt Design

**Date:** 2026-09-17

## Goal

When physical-board play opens the existing stone recovery dialog, give the player one short offline voice prompt. This first iteration covers only off-centre stones and backed low-confidence suspected moves. Capture removal, generic board mismatch, and board-loss dialogs remain silent.

## Prompt set

Use two pre-generated Chinese MP3 assets through the existing kiosk `useVoice` hook:

- Off-centre or adjacent-relocation recovery: “棋子没放正，请摆正后继续。”
- Backed low-confidence suspected move: “检测到疑似落子，请在屏幕上确认。”

The assets use distinct stable names added to the existing `VoiceName` union. Playback continues to obey the independent `voice` audio preference. A new prompt may interrupt a currently playing voice line, matching current `useVoice` behavior.

## Trigger and deduplication

`VisionSyncOverlay` owns the recovery dialog and therefore owns this prompt trigger. It derives a stable prompt identity from the active `blocking.kind === 'stone'` recovery:

- off-centre identity includes the recovery type, destination row/column, and optional source row/column;
- suspected-move identity includes the recovery type and row/column.

Play once when that identity first becomes active. React re-renders and unrelated vision events must not replay it. Clearing the recovery resets the remembered identity; a later new stone recovery may speak again, including at the same coordinate.

No speech is triggered for `capture`, `mismatch`, persistent board loss, or non-blocking toasts.

## Assets and runtime behavior

Generate the two MP3 files with the repository's existing voice-generation approach and store them under `katrain/sounds/voice/`, alongside the current physical-board voice assets. No browser speech synthesis or network TTS is used at runtime.

Playback is advisory: missing/failed audio must not block dialog rendering or recovery actions. Unmounting the overlay should stop any voice line it started so it cannot leak into another page or session.

## Verification

Focused tests will verify:

- each of the two stone dialog variants selects the correct voice asset;
- re-rendering the same dialog does not replay it;
- clearing and later reopening a stone dialog permits one new playback;
- capture, mismatch, and board-loss dialogs do not speak;
- disabling the `voice` preference remains silent through the existing `useVoice` contract;
- TypeScript build and the strict SmartBox kiosk production build still pass.

RK3562 deployment remains paused until explicitly resumed.
