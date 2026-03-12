# 3D Board Design — Review Assessment

> Cross-evaluation of Codex and Gemini feedback against the implementation plan and source code.

---

## Reviewer Quality Summary

| Dimension | Codex | Gemini |
|-----------|-------|--------|
| Critical bugs found | 5 (all valid) | 3 (2 overlap, 1 unique) |
| Domain knowledge (Go) | Strong — caught capture edge case | Weak — missed capture logic |
| R3F expertise | Good | Good — caught useFrame rendering bug |
| Code-level precision | High — cited exact lines | Medium — some claims imprecise |
| Completeness | Thorough — covered coord orientation, end-game overlay, playerColor | Narrower scope |
| False positives | 0 | 0 |

**Codex** is the stronger review overall: more issues found, better Go domain understanding, and caught problems Gemini missed (coordinate flip, capture detection, GhostStone playerColor, end-game overlay, analysis field inconsistency). **Gemini** contributed one uniquely critical insight (useFrame mutation won't trigger React re-render) that Codex missed entirely.

---

## Issue-by-Issue Verdict

### MUST FIX — Critical

| # | Issue | Source | Verdict | Reasoning |
|---|-------|--------|---------|-----------|
| 1 | **useFrame ref mutation won't animate** | Gemini | **Fix** | `animRef.current.yOffset` is mutated in `useFrame`, but `<StoneMesh position={pos}>` reads it during React render phase only. Since ref mutations don't trigger re-render, the stone position JSX never updates. Must use a mesh ref and mutate `meshRef.current.position.y` directly in `useFrame`. |
| 2 | **New-move detection breaks on captures** | Codex | **Fix** | `stones.length > prevStoneCountRef.current` fails when a capture reduces total stone count. A 19x19 capture can remove 1-100+ stones while adding 1. Must detect by comparing `last_move` coordinate instead. |
| 3 | **Coordinate orientation flipped vs 2D** | Codex | **Fix** | Board.tsx line 140: `invertedY = boardSize - 1 - y` puts row=0 at canvas bottom (near player). 3D plan: `gridToWorld(col, row=0)` → z=-9, camera at z=+22, so row=0 is far away. The 3D board is visually upside-down. Must negate Z: `z = -offset - row * GRID_SPACING` or equivalently `z = extent/2 - row * GRID_SPACING`. |
| 4 | **LastMove ring buried inside stone** | Both | **Fix** | `gridToWorld` returns stone center y=1.42. Stone top is at y=1.64. `ringY = 1.42 + 0.022 = 1.442` → inside stone. Ring needs to be at stone top: `pos[1] + STONE_HEIGHT` (1.64) + small epsilon. |
| 5 | **EvalDots clip through stone surface** | Both | **Fix** | `dotY = 1.42 + 0.209 = 1.629`, stone top is 1.64, so dot is 0.011 below apex. The flat circle likely clips the curved sphere surface. Move to `pos[1] + STONE_HEIGHT + 0.005`. |
| 6 | **`raycast={null as any}` unsafe** | Codex | **Fix** | R3F event system calls `object.raycast()` as a function. Setting to `null` causes runtime crash during raycaster traversal. Use `raycast={() => {}}` (noop). |
| 7 | **TS constraint violations in plan code** | Codex | **Fix** | Multiple snippets have unused imports or missing imports that fail `noUnusedLocals`/`noUnusedParameters`. Must audit every file in the plan. |

### MUST FIX — Important

| # | Issue | Source | Verdict | Reasoning |
|---|-------|--------|---------|-----------|
| 8 | **GhostStone missing playerColor check** | Codex | **Fix** | Board.tsx line 366: `!playerColor \|\| gameState.player_to_move === playerColor`. Without this, spectators and wrong-turn players see misleading hover previews. |
| 9 | **CameraController target [0, 0, 1] is wrong** | Codex | **Fix** | Orbit center should be board surface center `[0, BOARD_SURFACE_Y, 0]`. Current target is below the board and offset, making zoom/tilt feel unnatural. |
| 10 | **PolicyMap text unreadable at low angles** | Codex | **Fix** | Surface-projected text becomes a thin line at 5-38° polar angle. Must use billboard `<Text>` like BestMoves, or hide text below a threshold angle. |
| 11 | **useMemo resource disposal is render-phase side effect** | Codex | **Fix** | Disposing textures/materials inside `useMemo` violates React rules. Move disposal to `useEffect` cleanup with dependency on `boardSize`. |
| 12 | **Missing end-game result overlay** | Codex | **Fix** | Board.tsx lines 390-415 renders a semi-transparent overlay with translated result text. 3D plan has no equivalent. Must add `GameResult.tsx` or an HTML overlay. |
| 13 | **`analysis.moves` vs `analysis.top_moves` field name** | Codex | **Investigate** | GamePage.tsx line 321 uses `top_moves`, all other code uses `moves`. The plan perpetuates the `moves` usage. This is a pre-existing bug, not introduced by the 3D plan — but worth fixing while touching GamePage. |

### SHOULD FIX — Optimization

| # | Issue | Source | Verdict | Reasoning |
|---|-------|--------|---------|-----------|
| 14 | **Stones: share geometry & material** | Both | **Fix** | Each stone creates its own `SphereGeometry` and `MeshStandardMaterial`. At minimum, share one geometry + two materials (B/W). InstancedMesh is ideal but can be a follow-up. |
| 15 | **Grid: 38 separate Line draw calls** | Both | **Fix in plan** | Use `THREE.LineSegments` with a single `BufferGeometry` instead of 38 drei `<Line>` components. |
| 16 | **Z-fighting offset constants** | Gemini | **Fix** | Define named constants (`SURFACE_EPSILON`, `OVERLAY_OFFSET`) in constants.ts instead of magic numbers 0.005, 0.01, 0.003 scattered across files. |
| 17 | **toneMapping magic number `3`** | Codex | **Fix** | Replace with `THREE.ACESFilmicToneMapping` for readability. |

### NO CHANGE NEEDED

| # | Issue | Source | Verdict | Reasoning |
|---|-------|--------|---------|-----------|
| 18 | RaycastClick invisible plane approach | Gemini (positive) | **Keep** | Both reviewers consider this correct design. Gemini explicitly praises it. |
| 19 | Lazy loading strategy | Neither questioned | **Keep** | `lazy()` + `<Suspense>` is standard and appropriate. |
| 20 | File decomposition (~15 files) | Neither questioned | **Keep** | Granularity matches R3F scene graph pattern. |
| 21 | BoardProps sharing interface | Neither questioned | **Keep** | Both 2D and 3D accept same props — clean design. |
| 22 | Coordinate label margin (0.75 vs 0.8 padding) | Codex (minor) | **Defer** | Visual tuning, can adjust after first render. |
| 23 | Test coverage gaps | Codex (minor) | **Defer** | Valid but can add tests incrementally. The plan already has constants.test.ts. |
| 24 | `view3d` in analysisToggles vs separate state | Codex (question) | **Keep current** | Pragmatic choice. Refactoring into a separate viewMode context is overengineering for one toggle. |
| 25 | Accessibility degradation in 3D | Both (question) | **Accept** | 3D Canvas inherently lacks screen reader support. This is an opt-in premium view, not the default. |
| 26 | Right-click undo | Gemini (question) | **Not needed** | Board.tsx doesn't handle right-click for undo. Undo is sidebar button/keyboard shortcut. |
| 27 | Window resize | Gemini (question) | **Already handled** | R3F `<Canvas>` auto-resizes with its container. |

---

## Answers to Reviewer Questions

**Codex Q1 — Must 3D match 2D orientation?**
Yes. Row 1 must be at the near side (closest to camera) in both views. Fix #3 above resolves this.

**Codex Q2 — End-game overlay: board-level or page-level?**
Board-level, matching current Board.tsx behavior. An HTML overlay div on top of the Canvas is the simplest approach — no need for a 3D text mesh in the scene.

**Codex Q3 — `view3d` state split between GamePage and GameRoomPage?**
Acceptable. GamePage stores it in `analysisToggles` (which has its own setter), GameRoomPage uses independent state. Both persist to the same `localStorage` key. This is pragmatic, not ideal, but refactoring both pages' state management is out of scope.

**Gemini Q1 — Accessibility?**
Accepted degradation for opt-in 3D view. See #25 above.

**Gemini Q2 — Right-click?**
Not applicable. See #26 above.

**Gemini Q3 — Window resize?**
Handled by R3F. See #27 above.
