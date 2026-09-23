# Vision Recovery Voice Prompt Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为“棋子没放正”和“疑似落子”两个现有恢复弹窗各播放一次固定中文语音，同时保证重复渲染不重播、恢复目标变化会重播、弹窗消失后立即停播。

**Architecture:** 沿用现有离线 MP3 与 `useVoice` 播放链路。`useVoice` 负责同实例音频互斥和生命周期清理；`VisionSyncOverlay` 根据当前 stone recovery 的类型、坐标和可选来源坐标生成稳定身份，只在身份首次出现或改变时触发语音，并在 stone recovery 清除或切换为静默恢复类型时停止。

**Tech Stack:** React 18、TypeScript、Vitest、Testing Library、Vite、HTMLAudioElement、Edge TTS（仅开发时生成资产）。

**Approved spec:** `docs/superpowers/specs/2026-09-17-vision-recovery-voice-prompt-design.md`

---

## Constraints

- 只给两类 stone recovery 发声：`unbacked=true` 使用 `stone_offcenter`，`unbacked=false` 使用 `suspected_move`。
- capture、generic mismatch、board loss 和 toast 均保持静默。
- 语音仍服从独立的 `voice` 偏好；播放失败只静默吞掉，不能阻塞弹窗和恢复操作。
- 同一恢复身份只播一次；A 坐标直接变为 B 坐标时，即使 MP3 名称相同，也要再播一次。
- stone recovery 清除或切换为静默类型时停止当前语音；组件卸载时也停止。
- 不改后端协议、不新增 i18n 文案、不部署 RK3562。
- TypeScript 验收使用 `npx tsc -b`，不使用本仓空转的 `tsc --noEmit`。

## File map

- Modify: `katrain/web/ui/src/kiosk/hooks/useVoice.ts`
- Modify: `katrain/web/ui/src/utils/audioPrefs.test.ts`
- Modify: `katrain/web/ui/src/kiosk/components/vision/VisionSyncOverlay.tsx`
- Modify: `katrain/web/ui/src/kiosk/components/vision/VisionSyncOverlay.test.tsx`
- Modify: `scripts/generate_tsumego_voice.py`
- Create: `katrain/sounds/voice/stone_offcenter.mp3`
- Create: `katrain/sounds/voice/suspected_move.mp3`

## Chunk 1 — Voice lifecycle and assets

### Task 1: Give `useVoice` explicit stop and cleanup semantics

**Files:**

- Modify: `katrain/web/ui/src/utils/audioPrefs.test.ts`
- Modify: `katrain/web/ui/src/kiosk/hooks/useVoice.ts`

- [ ] **Step 1: Extend the audio test double and write failing lifecycle tests**

  In `audioPrefs.test.ts`, retain created `FakeAudio` instances and make `pause` observable:

  ```ts
  const createdAudio: FakeAudio[] = [];

  class FakeAudio {
    src: string;
    volume = 1;
    preload = '';
    pause = vi.fn();

    constructor(src = '') {
      this.src = src;
      createdAudio.push(this);
    }

    play() {
      played.push(this.src);
      return Promise.resolve();
    }

    cloneNode() {
      return new FakeAudio(this.src);
    }
  }
  ```

  Clear `createdAudio` in `beforeEach`, then add focused tests proving:

  ```ts
  it('new voice pauses the previous line before it starts', () => {
    const { result } = renderHook(() => useVoice());
    act(() => result.current.speak('place_black'));
    const first = createdAudio.find((audio) => audio.src.endsWith('/place_black.mp3'))!;

    act(() => result.current.speak('place_white'));

    expect(first.pause).toHaveBeenCalledTimes(1);
    expect(played.at(-1)).toBe('/assets/sounds/voice/place_white.mp3');
  });

  it('stop pauses the owned line and unmount also cleans up', () => {
    const voice = renderHook(() => useVoice());
    act(() => voice.result.current.speak('place_black'));
    const first = createdAudio.find((audio) => audio.src.endsWith('/place_black.mp3'))!;
    act(() => voice.result.current.stop());
    expect(first.pause).toHaveBeenCalledTimes(1);

    act(() => voice.result.current.speak('place_white'));
    expect(first.pause).toHaveBeenCalledTimes(1); // stop released the first element
    const second = createdAudio.find((audio) => audio.src.endsWith('/place_white.mp3'))!;
    voice.unmount();
    expect(second.pause).toHaveBeenCalledTimes(1);
  });
  ```

- [ ] **Step 2: Run the focused test and confirm the missing contract fails**

  Run:

  ```bash
  cd katrain/web/ui
  NODE_OPTIONS=--no-experimental-webstorage npx vitest run src/utils/audioPrefs.test.ts
  ```

  Expected: FAIL because `useVoice` does not return `stop` and does not stop on unmount.

- [ ] **Step 3: Implement the minimal hook lifecycle**

  In `useVoice.ts`:

  - import `useEffect`;
  - add `stone_offcenter` and `suspected_move` to `VoiceName`;
  - add a stable `stop` callback that pauses the current element and clears `currentRef`;
  - call `stop()` at the start of `speak`, before reading the preference, so a newly requested prompt cannot leave an older line playing even if voice has just been disabled;
  - register `useEffect(() => stop, [stop])` for unmount cleanup;
  - return `{ speak, stop }`.

  Target shape:

  ```ts
  const stop = useCallback(() => {
    currentRef.current?.pause();
    currentRef.current = null;
  }, []);

  const speak = useCallback((name: VoiceName) => {
    stop();
    if (!readAudioPref('voice')) return;
    const audio = new Audio(`/assets/sounds/voice/${name}.mp3`);
    currentRef.current = audio;
    const played = audio.play();
    if (played && typeof played.catch === 'function') played.catch(() => {});
  }, [stop]);

  useEffect(() => stop, [stop]);
  ```

- [ ] **Step 4: Re-run the hook tests**

  Run:

  ```bash
  cd katrain/web/ui
  NODE_OPTIONS=--no-experimental-webstorage npx vitest run src/utils/audioPrefs.test.ts src/kiosk/hooks/usePhysicalTsumego.test.tsx
  ```

  Expected: PASS. The existing `usePhysicalTsumego` mock may continue returning only `speak`, because that consumer does not call `stop`.

### Task 2: Add the two offline voice assets without rewriting existing MP3s

**Files:**

- Modify: `scripts/generate_tsumego_voice.py`
- Create: `katrain/sounds/voice/stone_offcenter.mp3`
- Create: `katrain/sounds/voice/suspected_move.mp3`

- [ ] **Step 1: Record the canonical source lines**

  Add to `LINES`:

  ```python
  "stone_offcenter": "棋子没放正，请摆正后继续。",
  "suspected_move": "检测到疑似落子，请在屏幕上确认。",
  ```

- [ ] **Step 2: Generate only the two new files**

  Do not run the all-lines script, which would rewrite the existing committed MP3s. Run the existing Edge TTS CLI directly with the same voice:

  ```bash
  .venv/bin/edge-tts --voice zh-CN-XiaoxiaoNeural --text '棋子没放正，请摆正后继续。' --write-media katrain/sounds/voice/stone_offcenter.mp3
  .venv/bin/edge-tts --voice zh-CN-XiaoxiaoNeural --text '检测到疑似落子，请在屏幕上确认。' --write-media katrain/sounds/voice/suspected_move.mp3
  ```

- [ ] **Step 3: Verify the assets are non-empty MP3s and no old asset changed**

  Run:

  ```bash
  test -s katrain/sounds/voice/stone_offcenter.mp3
  test -s katrain/sounds/voice/suspected_move.mp3
  file katrain/sounds/voice/stone_offcenter.mp3 katrain/sounds/voice/suspected_move.mp3
  git status --short katrain/sounds/voice scripts/generate_tsumego_voice.py
  ```

  Expected: only the generator plus the two new MP3s appear; no existing voice file is modified.

- [ ] **Step 4: Commit the hook and assets**

  Run:

  ```bash
  git add katrain/web/ui/src/kiosk/hooks/useVoice.ts katrain/web/ui/src/utils/audioPrefs.test.ts scripts/generate_tsumego_voice.py katrain/sounds/voice/stone_offcenter.mp3 katrain/sounds/voice/suspected_move.mp3
  git commit -m "add recovery voice assets"
  ```

## Chunk 2 — Recovery-trigger integration

### Task 3: Speak once per stone-recovery identity

**Files:**

- Modify: `katrain/web/ui/src/kiosk/components/vision/VisionSyncOverlay.test.tsx`
- Modify: `katrain/web/ui/src/kiosk/components/vision/VisionSyncOverlay.tsx`

- [ ] **Step 1: Mock the hook with stable functions**

  Add `voiceSpeak` and `voiceStop` to the existing `vi.hoisted` mocks and mock `../../hooks/useVoice`:

  ```ts
  vi.mock('../../hooks/useVoice', () => ({
    useVoice: () => ({ speak: mocks.voiceSpeak, stop: mocks.voiceStop }),
  }));
  ```

- [ ] **Step 2: Write failing behavior tests**

  Add focused cases to `VisionSyncOverlay.test.tsx` that prove:

  1. `ambiguous_stone` with `unbacked: true` calls `voiceSpeak('stone_offcenter')` once; rerendering unchanged props and then appending an unrelated `degraded` event do not replay it.
  2. `ambiguous_stone` with `unbacked: false` calls `voiceSpeak('suspected_move')` once.
  3. Appending a second ambiguous event at another row/column calls the same applicable voice a second time, proving identity is target-based rather than asset-based.
  4. Appending `synced` stops the active prompt; appending the same-coordinate stone event after that clear permits one new playback.
  5. capture, generic mismatch, persistent board loss, and toast events never call `voiceSpeak`.
  6. A stone recovery followed by capture calls `voiceStop` when the active dialog becomes silent. Test generic mismatch separately as an initially silent recovery; the reducer intentionally does not let mismatch replace an already active stone recovery.

  Use `waitFor` for effects/state transitions and reset both voice mocks in the existing `beforeEach` via `vi.clearAllMocks()`.

- [ ] **Step 3: Run the component tests and confirm they fail**

  Run:

  ```bash
  cd katrain/web/ui
  NODE_OPTIONS=--no-experimental-webstorage npx vitest run src/kiosk/components/vision/VisionSyncOverlay.test.tsx
  ```

  Expected: FAIL because `VisionSyncOverlay` does not yet call `useVoice`.

- [ ] **Step 4: Derive a primitive prompt identity and trigger playback**

  In `VisionSyncOverlay.tsx`, import the runtime hook and type separately so the repository's `verbatimModuleSyntax` TypeScript setting remains valid:

  ```ts
  import { useVoice, type VoiceName } from '../../hooks/useVoice';
  ```

  Then add:

  ```ts
  const { speak, stop } = useVoice();
  const spokenRecoveryRef = useRef<string | null>(null);
  const stoneRecovery = recovery.blocking?.kind === 'stone' ? recovery.blocking : null;
  const recoveryVoiceName: VoiceName | null = stoneRecovery
    ? (stoneRecovery.unbacked ? 'stone_offcenter' : 'suspected_move')
    : null;
  const recoveryVoiceIdentity = stoneRecovery && recoveryVoiceName
    ? [
        recoveryVoiceName,
        stoneRecovery.row,
        stoneRecovery.col,
        stoneRecovery.from?.[0] ?? '-',
        stoneRecovery.from?.[1] ?? '-',
      ].join(':')
    : null;
  ```

  Add an effect with exactly these semantics:

  ```ts
  useEffect(() => {
    if (recoveryVoiceIdentity === null || recoveryVoiceName === null) {
      if (spokenRecoveryRef.current !== null) stop();
      spokenRecoveryRef.current = null;
      return;
    }
    if (spokenRecoveryRef.current === recoveryVoiceIdentity) return;
    spokenRecoveryRef.current = recoveryVoiceIdentity;
    speak(recoveryVoiceName);
  }, [recoveryVoiceIdentity, recoveryVoiceName, speak, stop]);
  ```

  The primitive identity keeps ordinary rerenders quiet. Clearing resets the ref; A→B changes the identity and relies on `useVoice.speak` to interrupt A before playing B.

- [ ] **Step 5: Run the component and hook regression tests**

  Run:

  ```bash
  cd katrain/web/ui
  NODE_OPTIONS=--no-experimental-webstorage npx vitest run src/kiosk/components/vision/VisionSyncOverlay.test.tsx src/utils/audioPrefs.test.ts src/kiosk/hooks/usePhysicalTsumego.test.tsx
  ```

  Expected: PASS.

- [ ] **Step 6: Commit the integration**

  Run:

  ```bash
  git add katrain/web/ui/src/kiosk/components/vision/VisionSyncOverlay.tsx katrain/web/ui/src/kiosk/components/vision/VisionSyncOverlay.test.tsx
  git commit -m "announce stone recovery dialogs"
  ```

## Chunk 3 — Final verification, no deployment

### Task 4: Prove the scoped change is shippable

- [ ] **Step 1: Run focused tests**

  Run:

  ```bash
  cd katrain/web/ui
  NODE_OPTIONS=--no-experimental-webstorage npx vitest run src/kiosk/components/vision/VisionSyncOverlay.test.tsx src/utils/audioPrefs.test.ts src/kiosk/hooks/usePhysicalTsumego.test.tsx
  ```

  Expected: PASS.

- [ ] **Step 2: Run the real TypeScript gate**

  Run:

  ```bash
  cd katrain/web/ui
  npx tsc -b
  ```

  Expected: exit 0.

- [ ] **Step 3: Run the strict kiosk production build**

  Run:

  ```bash
  cd katrain/web/ui
  npm run build:smartbox-kiosk-2d
  ```

  Expected: build and `verify:kiosk-2d` pass. This proves the strict SPA boundary only; MP3s are served separately by the backend.

- [ ] **Step 4: Verify the separately served audio assets**

  Run:

  ```bash
  test -s katrain/sounds/voice/stone_offcenter.mp3
  test -s katrain/sounds/voice/suspected_move.mp3
  file katrain/sounds/voice/stone_offcenter.mp3 katrain/sounds/voice/suspected_move.mp3
  rg -n 'app.mount\("/assets/sounds"' katrain/web/server.py
  ```

  Expected: both non-empty files are recognized as MP3 audio, and the existing backend mount still serves `katrain/sounds` at `/assets/sounds`.

- [ ] **Step 5: Inspect the final scope**

  Run:

  ```bash
  git status --short
  git diff --stat origin/fix/kiosk-ui-debug...HEAD
  git log --oneline --max-count=6
  ```

  Expected: the three approved design/plan documentation commits plus the two focused implementation commits are ahead; the worktree is clean, and no generated old assets, unrelated code, or device-side files changed.

- [ ] **Step 6: Perform two-stage review**

  Use a fresh reviewer for spec compliance, then a fresh reviewer for code quality. Fix only findings within this feature's scope and rerun the affected focused checks.

- [ ] **Step 7: Stop before external actions**

  Report local commits and verification results. Do not push and do not deploy RK3562 unless the user explicitly resumes those actions.
