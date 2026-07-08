# Codex Review Feedback — Claude Kiosk UI Redesign Plan

**Verdict: needs rework before task execution.** The overall phase structure is salvageable, but the plan is not safe for a context-free implementer yet. The largest problems are cross-phase contradictions, compile holes in Phase C/D, and several places where the plan claims a design state is achieved by existing code that does not actually support it.

## Correctness Defects

### 1. B2.5 / D1.3: physical-tsumego wiring conflicts with itself

**Task IDs:** B2.5, D1.2, D1.3  
**Failure:** B2.5 adds `const [physicalMode, setPhysicalMode] = useState(readPhysicalMode());` to `TsumegoProblemPage`. D1.3 later instructs adding `const [physicalMode] = useState(() => readPhysicalMode());` in the same component. That is a redeclaration compile error. If an implementer “fixes” it by replacing the B2.5 state, the physical panel will not react to the toggle in the same page.

D1.3 also expects `screen.getByTestId('physical-state-panel')` with `data-phase="clearing"` immediately after `physical.enable()`, but D1.2 explicitly maps `clearing` to `null`, so the panel renders nothing. The test and implementation cannot both pass.

**Fix:** D1.3 must reuse the `physicalMode` state created in B2.5. Do not re-import/re-read `readPhysicalMode` except where B2.5 already does. Either make `enable()` set phase to `setup`, or make D1.2 render a visible `clearing` state. Then update D1.3 tests to match that chosen behavior.

### 2. B2.5: `PhysicalBoardGuard requireRecognition` blocks the default screen-only tsumego path

**Task IDs:** B2.5; route in `katrain/web/ui/src/kiosk/KioskApp.tsx`  
**Failure scenario:** `/kiosk/tsumego/problem/:problemId` is wrapped in `<PhysicalBoardGuard requireRecognition>`. `PhysicalBoardGuard` only passes if `phase === 'disabled'`, or `phase === 'ready' && session_calibrated && geometry_ready && recognition_ready`. A kiosk with camera/geometry enabled but no recognition model ready will be blocked before it reaches the solve page, even though physical mode is default OFF and screen solving should still work.

B2.5 only adds a `phase:'disabled'` pass-through test, which covers “no physical service” but not “physical service present, recognition unavailable, physical mode off”.

**Fix:** Make recognition conditional on physical mode. Options:

- Remove `requireRecognition` from the tsumego solve route and let the physical panel/toggle own physical readiness.
- Or change `PhysicalBoardGuard` to accept `requireRecognition={readPhysicalMode()}` for tsumego.
- Add tests for `phase:'ready', geometry_ready:true, recognition_ready:false` with physical mode off and on.

### 3. C1.6 has undeclared state/refs in the provided code snippets

**Task ID:** C1.6  
**Failure:** Step 4 and Step 6 use `setEtaSeconds`, `analysisStartRef`, and `hintsEnabledRef`, but Step 2 does not declare them. A direct implementation fails TypeScript.

**Fix:** Add the missing galaxy-derived declarations to Step 2:

```ts
const analysisStartRef = useRef<{ time: number; analyzed: number } | null>(null);
const hintsEnabledRef = useRef(false);
const [etaSeconds, setEtaSeconds] = useState<number | null>(null);
```

Also include these in C1.7 mocks/assertions if ETA text is rendered.

### 4. C1.6 / C1.8: `?kifu_id&analyze=1` can analyze an empty board

**Task IDs:** C1.6 Step 9, C1.8  
**Failure scenario:** C1.6 ports galaxy’s deep-link effect: fetch kifu, call `board.loadFromSGF(...)`, then `setTimeout(() => handleStartAnalysis(), 100)`. `loadFromSGF` updates React state asynchronously, while the `handleStartAnalysis` closure used by that effect can still read the old empty `board.moves`. Result: KifuPage “在研究中打开” navigates correctly but starts analysis on an empty session.

**Fix:** Do not start from a stale hook closure. Use one of these:

- After album load, call a dedicated `startAnalysisFromSgf(album.sgf_content, initialMove)` that passes SGF directly to `session.createSession`.
- Or set `pendingAutoAnalyze` and trigger `handleStartAnalysis` from an effect keyed on `board.moves.length` after `loadFromSGF` has rendered.
- Add a C1.7 test that opens `?kifu_id=1&analyze=1` and asserts `createSession` receives the album SGF, not `undefined`.

### 5. B1.3: AI thinking / AI move banner misclassifies human-vs-human games

**Task ID:** B1.3  
**Contradicting code:** backend can emit both `player:human`/`player:ai` (`katrain/web/server.py`) and plain `human` for multiplayer (`katrain/web/session.py`). Current tests also use `human`/`ai`.

**Failure scenario:** In local/PVP games both players are human. The plan computes AI thinking as “`player_to_move !== humanColor`”, where `humanColor` is the first human color found. In a B-vs-W human game, White’s turn becomes “AI 思考中”, and the persistent “AI 已落子” banner can fire after a White human move.

**Fix:** Normalize player types and derive an explicit AI color:

```ts
const isHuman = (p?: string) => p === 'human' || p === 'player:human';
const isAI = (p?: string) => p === 'ai' || p === 'player:ai' || p?.startsWith('ai:');
const aiColor =
  isAI(gameState.players_info.B.player_type) ? 'B' :
  isAI(gameState.players_info.W.player_type) ? 'W' :
  null;
const humanColor =
  isHuman(gameState.players_info.B.player_type) && aiColor === 'W' ? 'B' :
  isHuman(gameState.players_info.W.player_type) && aiColor === 'B' ? 'W' :
  null;
const aiThinking = !!aiColor && gameState.player_to_move === aiColor && !gameState.end_result;
```

Add tests for AI game and both-human PVP.

### 6. B1.4: board-loss consolidation does not actually consolidate all surfaces

**Task ID:** B1.4  
**Contradicting code:** `VisionSyncOverlay` is kiosk-owned (`src/kiosk/components/vision/VisionSyncOverlay.tsx`) and owns its `board_lost` dialog internally.

**Failure:** The plan says priority is escalation > board_lost > recalibration, but only suppresses the new RecalibrationModal when escalation is open. `VisionSyncOverlay` can still open its internal board-lost dialog while `PhysicalSyncEscalationDialog` is open. So the stated “one-visible-at-a-time” invariant remains false.

**Fix:** Since `VisionSyncOverlay` is kiosk-owned, add a prop such as `suppressBoardLost` or `surfacePriorityBlocked`, and pass `suppressBoardLost={escalationOpen}` from GamePage. Better: lift board-lost state into GamePage and make `VisionSyncOverlay` report the event instead of owning the modal. Add an explicit test with simultaneous escalation + board_lost.

### 7. B1.4: endgame “继续对弈” uses an unsupported action

**Task ID:** B1.4  
**Contradicting code:** `useGameSession.handleAction` has no `resume` branch. It supports `pass`, `undo`, `back`, `redo`, `resign`, etc., but not `resume`.

**Failure:** The endgame card’s “继续对弈” button calls `session.handleAction('resume')`; clicking it is a no-op.

**Fix:** Decide the real behavior. If “continue” means undo the terminal scoring/pass, call `back` or a new backend endpoint and test it. If it means dismiss the result overlay while leaving the game ended, wire local UI state instead. Do not ship a dead action.

### 8. B1.4 claims Board already supports dead-stone red-X; it does not

**Task ID:** B1.4  
**Contradicting code:** `src/components/Board.tsx` only draws ownership as black/white translucent squares when `analysisToggles.ownership` is true. It does not render dead stones with opacity `.4` or red X marks.

**Failure:** Design §5.1 state C requires “死子淡化(opacity .4)红叉”. The plan says this is “already handled inside shared Board.tsx” and forbids shared edits, so no task will produce the required visual.

**Fix:** Either mark dead-stone red-X out of scope, or create a Gate S task to add a shared Board capability with full galaxy regression coverage. A kiosk-only overlay is possible only if GamePage has dead-stone coordinates from the backend; the current plan does not specify such data.

### 9. C1.6 session cleanup uses a stale closure

**Task ID:** C1.6 Step 3  
**Failure:** The proposed unmount effect is:

```ts
useEffect(() => () => { if (activeSessionIdRef.current) session.destroySession(); }, []);
```

With an empty dependency array, this cleanup captures the initial `session.destroySession`, whose internal `base.sessionId` can still be `null`. On route unmount, `activeSessionIdRef.current` may be set but `destroySession()` can delete nothing.

**Fix:** Use the ref directly for cleanup:

```ts
useEffect(() => () => {
  const sid = activeSessionIdRef.current;
  if (sid) fetch(`/api/session/${sid}`, { method: 'DELETE', keepalive: true }).catch(() => {});
  session.destroySession();
}, [session]);
```

Or change `useResearchSession.destroySession(sessionId?: string)` to accept the explicit id, but that is a shared edit and must be Gate S.

### 10. B6.3 code snippet does not compile

**Task ID:** B6.3  
**Failure:** Step 2 uses `t('Camera','摄像头')` and `t('Calibration','几何标定')`, but Step 1’s skeleton imports only `Box`, `Typography`, and `useGeometry`. There is no `useTranslation` import or `const { t } = useTranslation()`.

**Fix:** Add:

```ts
import { useTranslation } from '../../../hooks/useTranslation';
const { t } = useTranslation();
```

Also add a tiny render test for `PhysicalBoardStatus`; build-only is too weak for a new component with hooks.

### 11. B2.1 test uses the wrong MUI icon test id

**Task ID:** B2.1  
**Failure:** The plan says assert `container.querySelector('[data-testid="EmojiEvents"]')`. MUI icon test ids are normally suffixed with `Icon` (`EmojiEventsIcon`), and D1.2 uses that convention.

**Fix:** Either assert `getByTestId('EmojiEventsIcon')`, or set an explicit `data-testid="success-trophy"` on the icon and assert that.

### 12. B2.5 duplicates A11 immersive wiring

**Task IDs:** A11, B2.5  
**Failure:** A11 already imports `useImmersive`, calls it, and adds the mount/unmount effect in `TsumegoProblemPage`. B2.5 says to add the same import/hook/effect again. Following tasks literally can create duplicate declarations or duplicate effects.

**Fix:** Change B2.5 Step 1 to “verify/preserve the A11 immersive effect” and only add it if A11 was not landed. The dependency graph says Phase B runs after A, so it should not re-add it.

### 13. C1.2 contradicts the “19-only” / 9x9/13x13 dropped constraint

**Task ID:** C1.2  
**Failure:** The task says to retain `setBoardSize` so imported SGFs can honor `SZ[]`. That means kiosk research can become 9x9/13x13 through SGF import even though the review request explicitly says 9x9/13x13 boards are deliberately dropped.

**Fix:** For kiosk, reject non-19 SGFs with a clear modal/toast, or clamp to 19 only if that is acceptable. If non-19 research is intentionally supported, remove it from the out-of-scope list and add visual/test coverage for 9/13.

## Sequencing / Dependency Errors

- **D1 depends on B2.5 state but does not acknowledge it.** D1.3 should be written as a patch on top of the B2.5 toggle, not as a fresh `readPhysicalMode` snapshot.
- **C1.6 and C1.7 must land atomically.** The plan says C1.6 runs `npx vitest run src/kiosk/__tests__/ResearchPage.test.tsx` rewritten in C1.7. If C1.6 and C1.7 are separate commits, C1.6 cannot pass its own gate. Combine them or weaken C1.6’s gate to build/lint only and require C1.7 immediately after.
- **B6.2 violates the A12 logout redirect contract.** A12 says callers must `navigate('/kiosk/login', { replace: true })`; B6.2’s skeleton uses `navigate('/kiosk/login')`. Use `replace: true`.
- **Gate S is inconsistent.** The matrix says “newly consumes shared territory” requires full build, but many tasks newly consume shared components and claim Gate K (for example A9 `LiveBoard`). Either define Gate S as “shared edits only” or enforce full build for new shared consumes. The current wording will create review churn.

## Route / Screen Coverage Gaps

- `/kiosk/play/pvp/setup` still routes to `PlaceholderPage`; no task owns it. If local PVP setup is in the approved IA, it needs a real task or the PlayPage card should be disabled/敬请期待.
- `/kiosk/kifu/:kifuId` still routes to `PlaceholderPage`; no task owns or removes it.
- `LobbyPage`, `PlatformConnectPage`, and `PlatformLobbyPage` are user-visible play routes. The plan says some are “already tokens” but does not assign artifact comparison, emoji/hex gates, or tests. At minimum add a verification-only task or explicitly mark them out of scope.
- Game state C’s dead-stone treatment has no owner, as noted above.

## Boundary / Verification Gaps

- The emoji gate regex does not catch existing navigation glyphs such as `⏮`, `◀`, `▶`, `⏭` because they sit outside the regex range. B3.3 and C1.6 remove some, but the gate can still report clean while glyph tofu remains. Add an explicit grep for these transport symbols or make the rule “no pictographic/control glyphs, MUI icons only”.
- D1.1 says “the redesign side has no `api/ledApi.ts` yet”, but `katrain/web/ui/src/api/ledApi.ts` exists and is used by Baipu. The no-import choice is still right for the stub, but the factual note should be corrected.
- C1 down-port stays within the galaxy boundary if imports are repointed as written. Keep `npm run lint` first; that part of the plan is correct.

## Verdicts On §7 Decisions

1. **Atomic A3 is correct.** Removing `isPortrait` changes the hook shape and will redden TS until all consumers/tests are updated. Keep it atomic, but make the task checklist generated from `rg "isPortrait" src` rather than fixed line lists.
2. **ImmersiveContext is acceptable.** Provider scope works because `KioskLayout` wraps its `<Outlet />` with `ImmersiveProvider`. Add a layout test where an Outlet child calls `setImmersive(true)` and Header/Dock disappear.
3. **Static SmartBoardConsole is acceptable as a stub** if the UI labels it as no feed/live preview unavailable. Do not imply it is recognized-board data.
4. **Header hardware cluster is the right replacement for StatusBar**, but the engine dot is static. Either label it as app/engine assumed-ready, or wire real engine health later.
5. **Baipu as Phase B is fine.** It already has the physical fall-throughs; Phase D should stay focused on tsumego.
6. **Kifu retarget post-C is correct**, but C1.6 must fix the `?kifu_id&analyze=1` stale-state race before C1.8 depends on it.
7. **Single owners for `theme.ts` and `navTabs.tsx` are worth it.** Those are high-conflict files.
8. **Stub-first for physical tsumego is okay only with an adapter commitment.** The plan honestly notes the real hook is not drop-in. Make the indirection file’s future target “adapter over real hook”, not “one-line raw re-export”.

## Verdicts On §8 Risks

- **Immersive provider scope:** works structurally; test it through `KioskLayout` rather than only mocking `useImmersive`.
- **Research down-port:** component self-containment is mostly real, but C1.6 has compile holes, stale cleanup, and the kifu auto-analyze race. `analysisScan` does resume incrementally because backend `_do_analysis_scan` only queues nodes where `analysis_exists` is false.
- **AI thinking arbitration:** current plan is not safe. `move_pending` is a valid event, but AI detection must be explicit and support both `player:ai` and `ai`/plain player types.
- **Guard pass-through:** disabled-service pass-through is not sufficient. Recognition must be conditional on physical mode.
- **i18n:** B6.1’s scope is honest if the UI copy says only the settings chip is wired. Do not claim “English kiosk works” until hardcoded kiosk strings are wrapped.
- **Panel widths:** plausible but must be screenshot-tested at 1024×600. The 404px report rail plus board area is tight but viable.
- **A3 mock sweep:** likely right, but use `rg "isPortrait"` as the source of truth; current comments also contain the string.
- **Board-loss consolidation:** not achieved by the proposed steps; `VisionSyncOverlay` needs an explicit suppression/ownership change.
