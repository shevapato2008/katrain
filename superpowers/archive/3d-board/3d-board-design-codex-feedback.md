# 3D Board Design Review Feedback

## 1. Critical issues

- **Task 2 `constants.ts` (`gridToWorld` / `worldToGrid` / `gridToSurface`, lines 220-259) + Task 4 `BoardMesh.tsx` coordinate labels (lines 621-626) + Task 3/5 camera placement (`Canvas` camera at line 422, `OrbitControls` target at line 735)**: 当前坐标系会把 `row = 0` 放到负 `z` 方向，而相机放在正 `z` 侧 `[0, 20, 22]`。这会让 3D 棋盘的上下方向和现有 2D 棋盘相反，也就是 2D 里靠近玩家的第 1 行，在 3D 里会跑到远端。这个问题不只影响落子位置，还会同时影响坐标标注、raycast 点击、领地/提示/策略图所有叠层。建议二选一：要么在 `gridToWorld/worldToGrid/gridToSurface` 里反转行坐标，要么整体把棋盘/相机绕 Y 轴旋转 180 度，确保视觉朝向和现有 `Board.tsx` 一致。

- **Task 6 `StoneMesh.tsx` (`raycast={null as any}`, line 878)**: 这里用 `null` 禁用射线命中的写法不安全。Three/R3F 的命中流程预期 `raycast` 是函数；把它设成 `null` 可能在指针事件遍历时直接炸运行时。这里应该改成 `raycast={() => null}`，或者用交互层/专门的点击平面来隔离，而不是把实例方法置空。

- **Task 7 `StoneGroup.tsx` new-move detection (lines 938-959)**: 用 `current_node_index` 增长且 `stones.length` 增长来判断“新下了一手”，这个判定在两个常见场景下都会错。第一，吃子手之后棋盘总子数可能不增反减，新落子不会触发动画。第二，终局后做前进导航时，`current_node_index` 和 `stones.length` 也可能一起增长，结果会把“浏览历史”误判成“刚下了一手”。这个逻辑至少要改成基于 `current_node_id` / `last_move` / 最后新增坐标做比对，而不是基于总石子数。

- **Task 11 `LastMove.tsx` marker Y calculation (lines 1351-1357) + Task 12 `EvalDots.tsx` dot Y calculation (lines 1420-1426)**: `gridToWorld` 返回的是棋子中心点，高度已经是 `BOARD_SURFACE_Y + STONE_HEIGHT`。现在 `ringY = pos[1] + STONE_HEIGHT * 0.1` 会把最后一手圆环埋进棋子内部；`dotY = pos[1] + STONE_HEIGHT * 0.95` 也几乎贴在曲面里，容易裁切或闪烁。这里应该按“棋子顶部高度 + epsilon”来算，而不是再乘一个经验系数。

- **Task 3/4/7 与仓库 TS 约束不一致，计划里的阶段性 `tsc --noEmit` 校验会直接失败**: Task 3 的 `Board3D/index.tsx` 在 lines 410-417 导入和解构了多个未使用变量，但文档又在 lines 439-445 要求这一步必须无类型错误；Task 4 的 `BoardMesh.tsx` 在 lines 470-560 里直接用了 `THREE`、`useMemo`、`useRef`、`useEffect`、`memo`，却没有对应 import；Task 7 的 `StoneGroup.tsx` 在 line 918 导入了 `STONE_HEIGHT` 和 `BOARD_SURFACE_Y` 但后文没用。按当前仓库 `tsconfig.app.json` 的 `noUnusedLocals/noUnusedParameters/verbatimModuleSyntax`，这些片段都过不了。

## 2. Important suggestions

- **Task 9 `GhostStone.tsx` hover preview gating (lines 1180-1217)**: 当前 3D 方案没有把 `playerColor` 传入 `GhostStone`，hover 预览只检查 `end_result` 和占位，不检查“是不是轮到你下”。现有 2D `Board.tsx` 会在 hover 预览前判断 `!playerColor || gameState.player_to_move === playerColor`。如果不补这层，观战者和非当前行棋方都会看到误导性的“可下子”预览。

- **整个任务列表缺少 2D 棋盘现有的终局结果覆盖层**: 当前 `Board.tsx` 会直接在棋盘上渲染带翻译的终局结果遮罩；3D 计划里没有对应任务，也没有引入 `useTranslation`。在 AI 对局页，这会导致切到 3D 后丢失现有的终局呈现能力。建议补一个 `GameResultOverlay`，或者明确说明页面级 Dialog 会替代棋盘内结果显示。

- **Task 15 `GamePage.tsx` hints state 与现有数据契约没有对齐 (lines 1744-1746)**: 计划新增的 3D 代码统一读 `gameState.analysis?.moves`，但当前 `GamePage.tsx` 的 `isAnalysisPending` 仍然在读 `gameState.analysis?.top_moves`。现在代码库里这两个字段已经不一致了，3D 方案又扩散了 `analysis.moves` 的使用面。建议先把 `analysis` 抽成明确类型，并统一一个规范字段，否则 sidebar loading 状态和棋盘实际渲染很容易继续跑偏。

- **Task 14 `PolicyMap.tsx` text rendering (lines 1621-1629)**: policy 百分比文本现在是平贴在棋盘表面的。配合 Task 5 的低视角 tilt，这些数字在多数角度下几乎不可读。这里要么和 `BestMoves` 一样改成 billboard，要么只在 hover / 高缩放级别显示文本，否则用户只会看到一层发糊的字。

- **Task 5 `CameraController.tsx` target (line 735)**: `OrbitControls` 的 target 现在是 `[0, 0, 1]`，也就是棋盘下方且略偏前的位置。这样旋转和缩放的视觉中心会偏离棋盘面，手感会比较怪，尤其是锁定方位角以后更明显。建议 target 对齐到棋盘中心，比如 `[0, BOARD_SURFACE_Y, 0]`，并把这个点提成共享常量。

- **Task 4 `BoardMesh.tsx` 在 `useMemo` 里执行资源销毁 (lines 562-565)**: 这属于 render phase side effect。即使功能上能跑，在 React StrictMode 下也容易出现双调用和调试时的诡异行为。材质/纹理创建可以 `useMemo`，但销毁应放到 `useEffect` cleanup 里按依赖回收。

## 3. Minor notes

- **Task 6 `StoneMesh.tsx` performance profile (lines 849-880)**: 现在每颗棋子都是独立材质、独立几何体。19x19 满盘时先不一定非上 `InstancedMesh`，但至少可以先共享一份黑棋几何/材质和一份白棋几何/材质，成本会比“361 份 sphere geometry”低很多。

- **Task 4 `BoardMesh.tsx` coordinate label margin (line 617)**: `labelOffset = 0.75`，而 board padding 只有 `0.8`。这会让坐标文字几乎贴到木板边缘，视觉上比较挤，也容易被阴影/透视吃掉。可以考虑把 offset 收回一点，或者把 board padding 稍微放大。

- **Task 3 `Board3D/index.tsx` renderer config (line 423)**: `toneMapping: 3` 这种魔法数字建议换成具名常量，后续维护会更安全，也方便别人快速看懂当前到底在用哪种 tone mapping。

- **测试覆盖面偏窄**: 当前只规划了 `constants.test.ts`。建议至少再补 3 类测试：坐标朝向/round-trip、吃子与历史导航时的动画判定、`view3d` 本地持久化与 hover preview 权限控制。

## 4. Questions

- 3D 视角是否必须和现有 2D 棋盘保持同一朝向，也就是“第 1 行在用户近侧”？如果你们接受一个“站在白方一侧看棋盘”的摄影机视角，那坐标系统设计就要和现在明确区分开。

- 终局时你们想保留 `Board.tsx` 那种棋盘内结果遮罩，还是准备统一依赖页面级弹窗/侧栏来展示结果？这会决定 3D 是否需要补一个专门的 overlay 组件。

- `view3d` 现在在 `GamePage` 里被塞进 `analysisToggles`，在 `GameRoomPage` 里又是独立 `view3d` state。这个分裂是临时过渡，还是你们接受两个页面长期维持不同状态模型？
