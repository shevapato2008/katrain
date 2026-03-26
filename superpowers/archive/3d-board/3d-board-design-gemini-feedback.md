# 3D Board Design Review Feedback

Here is the review of the 3D Board implementation plan (`2026-03-11-3d-board-design.md`) based on the provided context and React Three Fiber best practices.

## 1. Critical Issues

**Task 7: Drop Animation Logic is Broken (React State vs R3F `useFrame`)**
*   **Issue:** In `StoneGroup.tsx`, the `useFrame` hook modifies `animRef.current` (mutating `yOffset` and `scale`). However, the `pos` and `scale` variables are read during the React render phase (`const pos = anim ? [..., anim.yOffset, ...]`). Because mutating a ref does not trigger a React re-render, the stone will not animate. It will remain at the initial `yOffset` until an external state change forces a re-render.
*   **Fix:** You must attach a React ref directly to the animating `<mesh>` and mutate its properties within `useFrame` (e.g., `meshRef.current.position.y = ...`). Alternatively, use an animation library like `@react-spring/three` which handles this seamlessly in R3F.

**Task 11: LastMove Overlay is Hidden Inside the Stone**
*   **Issue:** In `LastMove.tsx`, the marker ring is placed at `y = pos[1] + STONE_HEIGHT * 0.1` with an inner/outer radius of `0.12/0.18`. Since `pos[1]` is the *center* of the stone geometry (which has an XZ radius of `0.42`), this small ring will be completely embedded *inside* the opaque stone mesh and will be invisible.
*   **Fix:** If the ring should surround the base of the stone, place it on the board surface (`BOARD_SURFACE_Y + 0.01`) and increase its radius to be larger than the stone (`args={[0.44, 0.5, 32]}`). If it should be on top, place it above the stone's apex (`pos[1] + STONE_HEIGHT + 0.01`).

**Task 12: EvalDots Overlay Placement**
*   **Issue:** In `EvalDots.tsx`, dots are placed at `pos[1] + STONE_HEIGHT * 0.95`. Because the stone is a sphere scaled on the Y-axis, a flat circle placed slightly below the apex may either clip through the curved edges of the stone or be hidden entirely if the stone material is opaque.
*   **Fix:** Place the dot slightly *above* the stone's maximum Y height to guarantee it sits cleanly on top without z-fighting or clipping: `y = pos[1] + STONE_HEIGHT + 0.005`.

## 2. Important Suggestions

**Task 4, 6, 10, 14: Draw Call Performance & Instancing**
*   **Issue:** The plan creates individual `<mesh>` elements for every stone, territory patch, policy map cell, and eval dot. On a fully populated 19x19 board, this will result in over 1,000 draw calls (361 stones + 361 territory overlays + 361 eval dots, etc.). While R3F can handle this on powerful desktop machines, it is highly inefficient and may cause dropped frames or high CPU usage.
*   **Fix:** Use `<InstancedMesh>` for the stones and flat overlays (Territory, PolicyMap). Since Go stones are static once placed, instancing will reduce the 361 stone draw calls to exactly 2 (one for Black, one for White).

**Task 4: Grid Line Efficiency**
*   **Issue:** Using 38 separate drei `<Line>` components means 38 separate draw calls for the grid.
*   **Fix:** Combine the grid lines into a single `THREE.LineSegments` geometry. This reduces the entire grid to a single draw call.

**Task 7: Drop Animation False Positives**
*   **Issue:** The animation triggers whenever `gameState.current_node_index > prevNodeIndexRef.current` and the stone count increases. This means if a user rapidly navigates forward through the move history using arrow keys, every stone will trigger a drop animation, which might feel laggy or confusing compared to instant placement.
*   **Fix:** Consider adding a check to ensure the animation only plays if the new move is actually being *played* in real-time, or disable the animation if multiple nodes are traversed in a single update.

## 3. Minor Notes & Optimizations

*   **Task 8 (RaycastClick):** Using an invisible plane for raycasting and setting `raycast={null}` on the stones is an excellent design choice. It vastly simplifies pointer event logic and improves raycasting performance.
*   **Task 13 (BestMoves):** Overlapping billboard text might become cluttered if multiple top moves are adjacent. You could consider scaling down the text slightly or adding a background plane with low opacity to the text to ensure readability against the wood texture.
*   **Task 4 (BoardMesh):** The memory cleanup in `useEffect` is implemented correctly for materials and textures. However, note that `createWoodTexture` generates temporary `<canvas>` elements that will be garbage collected automatically. This is fine, but if the board size changes frequently (unlikely), it could cause minor GC pauses.
*   **Z-Fighting Offsets:** You've used `0.005`, `0.01`, and `0.003` for various overlays. This is generally fine, but consider defining these offsets as constants in `constants.ts` (e.g., `Z_OFFSET_GRID`, `Z_OFFSET_TERRITORY`) to ensure consistent stacking order.

## 4. Questions & Edge Cases

*   **Accessibility:** The 2D Canvas might have aria-labels or basic screen reader support. The 3D Canvas currently has none. Is this an acceptable degradation for users toggling on the 3D view?
*   **Right-Click (Undo):** The existing `Board.tsx` might support right-clicking to undo a move. The `RaycastClick` component only binds `onClick` (left click). Should `onContextMenu` be implemented to match 2D behavior parity?
*   **Window Resize:** Does the `<Canvas>` component automatically handle window resizing in this UI layout? (Usually R3F handles this gracefully, but ensure the parent `div` in `index.tsx` behaves correctly with flexbox).