# Vision Recovery Voice Prompt Design

**Date:** 2026-09-17

## Goal

When physical-board play opens the existing stone recovery dialog, give the player one short offline voice prompt. This first iteration covers only off-centre stones and backed low-confidence suspected moves. Capture removal, generic board mismatch, and board-loss dialogs remain silent.

## Prompt set

Use two pre-generated Chinese MP3 assets through the existing kiosk `useVoice` hook:

- `stone_offcenter.mp3`: off-centre or adjacent-relocation recovery — “棋子没放正，请摆正后继续。”
- `suspected_move.mp3`: backed low-confidence suspected move — “检测到疑似落子，请在屏幕上确认。”

Add `stone_offcenter` and `suspected_move` to the existing `VoiceName` union and to `scripts/generate_tsumego_voice.py`'s source-line map. Playback continues to obey the independent `voice` audio preference. A new prompt must interrupt the voice line previously started by the same `useVoice` instance.

## Trigger and deduplication

`VisionSyncOverlay` owns the recovery dialog and therefore owns this prompt trigger. It derives a stable prompt identity from the active `blocking.kind === 'stone'` recovery:

- off-centre identity includes the recovery type, destination row/column, and optional source row/column;
- suspected-move identity includes the recovery type and row/column.

Play once when that identity first becomes active. Here “content changes” means the active recovery target changes, not merely that the spoken MP3 basename changes: if stone recovery A changes directly to stone recovery B at another coordinate, B speaks once even when both use `stone_offcenter`. React re-renders and unrelated vision events must not replay it. Clearing the recovery resets the remembered identity; a later new stone recovery may speak again, including at the same coordinate.

No speech is triggered for `capture`, `mismatch`, persistent board loss, or non-blocking toasts.

## Assets and runtime behavior

Generate the two MP3 files with the repository's existing voice-generation approach and store them under `katrain/sounds/voice/`, alongside the current physical-board voice assets. No browser speech synthesis or network TTS is used at runtime.

Playback is advisory: missing/failed audio must not block dialog rendering or recovery actions. Extend `useVoice` to return `stop` as well as `speak`; `stop` pauses and releases only the audio element owned by that hook instance. The hook also calls the same cleanup on unmount. `VisionSyncOverlay` calls `stop` when its stone recovery clears or changes to a silent recovery kind, so a recovery voice cannot continue after its dialog disappears.

## Verification

Focused tests will verify:

- each of the two stone dialog variants selects the correct voice asset;
- re-rendering the same dialog does not replay it;
- changing directly from stone recovery A to stone recovery B speaks B once, even when both select the same fixed asset;
- clearing and later reopening a stone dialog permits one new playback;
- capture, mismatch, and board-loss dialogs do not speak;
- prompt A followed by prompt B pauses A before playing B;
- clearing the stone recovery and unmounting the overlay each pause the audio owned by that hook instance;
- disabling the `voice` preference remains silent through the existing `useVoice` contract;
- TypeScript build and the strict SmartBox kiosk production build still pass.

RK3562 deployment remains paused until explicitly resumed.
