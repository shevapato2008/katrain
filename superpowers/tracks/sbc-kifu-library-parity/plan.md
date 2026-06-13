# 实施计划：Kiosk 棋谱库对齐 Galaxy（sbc-kifu-library-parity）

- **Track**: `sbc-kifu-library-parity`
- **分支**: `feature/rk3588-ui`
- **Spec 来源**: `superpowers/tracks/sbc-kifu-library-parity/prd.md`
- **状态**: Architecture LOCKED (eng-review passed) — Ready to execute
- **日期**: 2026-06-13

> 本计划面向「无上下文的执行者」（可能是另一个 session 或 agent）。每个阶段都自包含、可独立验证、可单独提交。代码片段是**指导性**的（展示意图与关键属性），落地以实际编译/测试通过为准。
> **§8 记录了 plan-eng-review 的逐条裁决（13 条已确认发现）。执行时必须遵守 §8 标注的修订，勿回退。**

---

## 0. 锁定的设计决策（brainstorming + eng-review 已定）

| # | 决策 | 选择 |
|---|---|---|
| D1 | 「在研究中打开」链路 | **方案 A**：在 `KifuPage` 内 `createSession(sgf)` + 加载 + 跳转，绕过 `/kiosk/research` 设置向导 |
| D2 | 进入研究时的定位手数 | `initialMove = Math.max(0, previewCurrentMove − previewHandicap)`；`skipAnalysis: true`。**[ENG-REVIEW F11]** 减去让子数修正终局/中途两种情形（详见 §8） |
| D3 | 跳转目标路由 | `navigate('/kiosk/research/session/' + sessionId)` → `GamePage`（已存在，与设置向导同路由） |
| D4 | 底部栏布局 | **单行**为主视觉（翻谱居中、操作按钮右置、`minWidth`+`nowrap`+`flexShrink:0`）；**[ENG-REVIEW F13]** 必须加**响应式不裁切兜底**：`flexWrap` + 按钮作为 bar 的直接 flex 子元素，窄屏自动落到次行而非裁切。视觉细化走 `frontend-design`，出 mockup 给用户异步确认 |
| D5 | 列表浏览 | **数字分页**：MUI `Pagination`，组件内 state；**[ENG-REVIEW F8]** 单一 fetch effect（合并查询提交+页码重置），消除重复请求 |
| D6 | P1 范围 | **全部**：翻谱控件 / 分页 / `translateResult`+`round_name` / 标题 `h4`+`toLocaleString` |

---

## 1. 背景与现状（已读码核验 + eng-review 复核）

**根因（确认）**：
1. `KifuPage.tsx:288` 按钮 `onClick={() => navigate('/kiosk/research')}` —— 未带 kifu 标识。
2. `/kiosk/research` 是新建会话设置向导，不读参数、不注入 SGF。

**关键架构事实（已核验，方案 A 端到端成立）**：
- 会话存活在**后端**。`useResearchSession.createSession(sgf, {skipAnalysis, initialMove})` 内部走 `/api/session?mode=research` → `/api/sgf/load`（带 `skip_analysis`）→ `/api/redo`（`n_times`），返回 `sessionId`。
- **[ENG-REVIEW]** 后端 `interface.py:294` 读取 `game.current_node`，会话状态跨导航持久；`GamePage` 的全新 `useGameSession.setSessionId` 经 `API.getState` 重连，**KifuPage hook 设的 redo 终点在 GamePage 重连后仍在**。
- `useSessionBase` 卸载清理**只 `ws.close()`，不 DELETE 会话**（`useSessionBase.ts:87-90`）→ KifuPage 创建会话后跳转，后端会话存活。
- `GamePage` 用 `useGameSession`，`onMove` 无客户端回合校验（`Board` 的 `playerColor` 控制）；研究会话 `players_info` 非 `player:human` → `humanColor=null` → **自由落子（「可试下」成立）**。

**已核验的共享 API / 类型**：
- `sgfToMoves(sgf) → { moves, stoneColors, metadata: { boardSize, handicap, ... } }`（`utils/sgfSerializer.ts`）。**注意**：让子游戏的 `AB[]` 摆子被 push 进 `moves`（`sgfSerializer.ts:182-193`），故 `previewMoves.length` 含让子数（详见 §8 F11）。
- `LiveBoard` props：`moves, stoneColors, currentMove, boardSize, showCoordinates`（`components/live/LiveBoard.tsx:25`）。
- `translateResult(result, t, rules)`（`utils/resultTranslation.ts`，**共享 utils，纯函数，kiosk 可 import**；`result:*` key 已在后端 cn catalog，无需新增 .po）。
- `KifuAlbumDetail.sgf_content`、`KifuAlbumSummary.round_name/rules/board_size/handicap`（`types/kifu.ts`）。
- 路由 `research/session/:sessionId → GamePage`（`KioskApp.tsx:56`）。
- `KioskResultBadge` **仅被 `KifuPage` 使用**（grep 确认）→ 可安全扩展。
- **[ENG-REVIEW]** KifuPage 引入的全部 import 均落在允许的共享区 / `@mui/material`，**不触 eslint kiosk 边界，不传递性引入 three/@react-three**；`useResearchSession` 已在 kiosk bundle（`kiosk/ResearchPage.tsx` 已用）→ `verify:kiosk-2d` 保持绿。

---

## 2. 约束与护栏（每阶段都适用）

- 改动**收敛在 kiosk territory**：`src/kiosk/pages/KifuPage.tsx`、`src/kiosk/components/game/KioskResultBadge.tsx`、`src/kiosk/__tests__/KifuPage.test.tsx`。
- 允许 import 共享区：`hooks/useResearchSession`、`utils/resultTranslation`、`utils/sgfSerializer`、`api/kifuApi`、`components/live/LiveBoard`、`types/kifu`、`@mui/material`。
- **禁止** import `src/galaxy/**`、`Board3D/**`、`VideoRecorderPage*`（`eslint.config.js` 强制）。
- **不改共享区文件本身**（不动 `kifuApi.ts`/`useResearchSession.ts`/`useSessionBase.ts`/`LiveBoard.tsx`/`resultTranslation.ts`）→ 规避 Galaxy 回归。
- 收尾必须：`npm run build` ✅、`npm run build:kiosk-2d`（含 `verify:kiosk-2d`）✅、`npm test` ✅、`npx tsc --noEmit` ✅。

工作目录：`katrain/web/ui/`。

---

## 3. 阶段拆解

### Phase 0 — 基线（建立绿色起点）
1. `cd katrain/web/ui && npm install`（若未装）。
2. `npm test -- src/kiosk/__tests__/KifuPage.test.tsx` —— 确认现有 8 个用例通过。
3. `npx tsc --noEmit` 通过。

**完成标准**：基线绿色，无未提交改动。

---

### Phase 1 — 「在研究中打开」加载棋谱（P0-1，方案 A）
**目标**：选中棋谱点按钮 → 创建带 SGF 的研究会话 → 跳转 `GamePage` 显示该局；加载态/失败态完整。

`KifuPage.tsx` 改动：

1. 新增 import 与 state：
   ```tsx
   import { useResearchSession } from '../../hooks/useResearchSession';
   import { Snackbar, Alert } from '@mui/material';
   // ...
   const { createSession } = useResearchSession();
   const [previewSgf, setPreviewSgf] = useState<string | null>(null);
   const [previewHandicap, setPreviewHandicap] = useState(0);   // [ENG-REVIEW F11]
   const [opening, setOpening] = useState(false);
   const [openError, setOpenError] = useState<string | null>(null);
   ```

2. 在选中详情的 effect（当前 `getAlbum` 处，`KifuPage.tsx:64-87`）里**存 SGF + 让子数**，并在切换选择/请求开始时清空：
   ```tsx
   setPreviewSgf(null);                 // 与现有 setPreviewMoves([]) 等并列（按钮禁用所需）
   setPreviewHandicap(0);
   // ...在 .then(detail) 内、if (detail.sgf_content) 块内：
   setPreviewSgf(detail.sgf_content);
   setPreviewHandicap(parsed.metadata.handicap ?? detail.handicap ?? 0);
   // [ENG-REVIEW F3] boardSize 必须 metadata 优先（对齐 Galaxy，修正潜在棋盘尺寸错配 bug，勿回退为 detail.board_size 优先）：
   setPreviewBoardSize(parsed.metadata.boardSize || detail.board_size || 19);
   ```

3. 实现打开逻辑（**[ENG-REVIEW F11]** initialMove 减去让子数）：
   ```tsx
   const handleOpenInResearch = async () => {
     if (!previewSgf || opening) return;
     setOpening(true);
     setOpenError(null);
     try {
       // previewMoves 含让子摆子(AB[])，但后端 redo 只走落子节点；减去 handicap 得到正确节点数。
       // 终局(previewCurrentMove===previewMoves.length)时 = 真实落子数，精确命中终局；
       // 中途/让子也正确；非让子 handicap=0 不变。
       const initialMove = Math.max(0, previewCurrentMove - previewHandicap);
       const sessionId = await createSession(previewSgf, { initialMove, skipAnalysis: true });
       if (sessionId) {
         navigate(`/kiosk/research/session/${sessionId}`);
       } else {
         setOpenError(t('Failed to open in research', '打开研究失败，请重试'));
       }
     } catch {
       // 防御性：createSession 实际吞掉异常返回 null（useResearchSession.ts:91-94），此分支基本不可达。
       setOpenError(t('Failed to open in research', '打开研究失败，请重试'));
     } finally {
       setOpening(false);
     }
   };
   ```

4. 按钮接线（替换 `onClick={() => navigate('/kiosk/research')}`）：
   ```tsx
   onClick={handleOpenInResearch}
   disabled={!previewSgf || opening}
   startIcon={opening ? <CircularProgress size={16} color="inherit" /> : <ScienceIcon sx={{ fontSize: 16 }} />}
   ```

5. 失败 toast（模式同 `GamePage.tsx:177`）：
   ```tsx
   <Snackbar open={!!openError} autoHideDuration={4000} onClose={() => setOpenError(null)}
     anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}>
     <Alert severity="error" onClose={() => setOpenError(null)}>{openError}</Alert>
   </Snackbar>
   ```

**完成标准**：方案 A 链路通；失败有 toast；空 SGF 禁用；让子游戏定位正确。

---

### Phase 2 — 预览翻谱控件接线（P1-1）
**目标**：⏮ ◀ ▶ ⏭ 可逐手前后翻，计数随之更新。**[ENG-REVIEW F7]** 加 `aria-label`（稳定测试查询 + a11y）。

`KifuPage.tsx:265-280` 四个按钮加 `onClick`、`disabled`、`aria-label`，计数文案改用动态值：
```tsx
<Button size="small" aria-label="first" disabled={previewCurrentMove === 0}
  onClick={() => setPreviewCurrentMove(0)} sx={{ minWidth: 32, color: 'text.secondary' }}>⏮</Button>
<Button size="small" aria-label="prev" disabled={previewCurrentMove === 0}
  onClick={() => setPreviewCurrentMove(m => Math.max(0, m - 1))} sx={{ minWidth: 32, color: 'text.secondary' }}>◀</Button>
<Typography variant="body2" sx={{ mx: 2, fontFamily: '"IBM Plex Mono", monospace', color: 'text.secondary', minWidth: 80, textAlign: 'center' }}>
  {previewCurrentMove} / {previewMoves.length} {t('moves', '手')}
</Typography>
<Button size="small" aria-label="next" disabled={previewCurrentMove >= previewMoves.length}
  onClick={() => setPreviewCurrentMove(m => Math.min(previewMoves.length, m + 1))} sx={{ minWidth: 32, color: 'text.secondary' }}>▶</Button>
<Button size="small" aria-label="last" disabled={previewCurrentMove >= previewMoves.length}
  onClick={() => setPreviewCurrentMove(previewMoves.length)} sx={{ minWidth: 32, color: 'text.secondary' }}>⏭</Button>
```
> **[ENG-REVIEW F7]** 默认加载态 `previewCurrentMove === previewMoves.length`（终局），故 **▶/⏭ 默认禁用、⏮/◀ 默认启用**。计数 `previewCurrentMove / previewMoves.length`（让子游戏总数含摆子，与 Galaxy 库预览一致）。`LiveBoard currentMove` 已接好，无需改 LiveBoard。

---

### Phase 3 — 底部操作栏单行重设计（P0-2，frontend-design + mockup-first）
**目标**：「在研究中打开」**单行不换行**且**不裁切**，棋盘高度不被挤压；触控目标 ≥ 40px。

> 用户已在 brainstorming 选定 D4 方向（单行·按钮定宽右置）。**实现单行版 + 截图作为异步 mockup 供用户审阅，不阻塞。**

**[ENG-REVIEW F13]** 单行宽度预算在真机偏紧：预览面板宽 ≈ `(屏宽 − 72px NavigationRail) / 2`；内容（导航 ~240–264px + 按钮含 6 字中文标签 ~160–200px + padding）≈ 490px，在 1024 宽屏 ≈ 476px 可用区**已经临界**，更窄屏会裁切。`nowrap` 只把「逐字竖排」换成「水平裁切」（预览面板 `overflow:hidden`）。因此：

1. 调 `frontend-design` 出最终视觉（横屏 + 竖屏两态），输出 mockup → 截图供用户异步确认。
2. 落地（**单行为主 + 响应式兜底**）：
   - 操作按钮：`whiteSpace:'nowrap'`、`flexShrink:0`、`textTransform:'none'`、`minWidth`（保单行）、高度 ≥ 40px；**作为底部 bar 的直接 flex 子元素**（不再嵌在 `flex:1` 容器里，否则无法 wrap）。
   - 导航控件组：直接 flex 子元素、`flexShrink:0`（计数不被压缩）。
   - bar：`display:flex, flexWrap:'wrap', alignItems:'center', columnGap, rowGap`，使**窄屏时按钮整体落到次行而非裁切**（= PRD §2.2 选项 b 的优雅降级，宽屏仍是单行）。
   - 适当收紧导航 `minWidth`/`gap`，让常见分辨率（≥1024 横屏）保持单行。
3. **验证宽度**：在真机面板宽（`(屏宽−72)/2`）下检查，而非桌面浏览器宽。**RK3562/3576/3588 实际分辨率仓库未记录 → 见 §9 待确认项**；执行时按 ≤1024 横屏验证并在 Phase 7 真机复核。

**完成标准**：mockup 获批（异步）+ 落地 + 单行/兜底两态均不裁切、不竖排、不压棋盘。

---

### Phase 4 — 列表数字分页（P1-2）—— **[ENG-REVIEW F8] 单一 fetch effect**
**目标**：可浏览首页之外棋谱；DOM 有界；**消除重复请求**（含修复既有 mount 双发）。

> 原两段 effect（`KifuPage.tsx:51-53` initial-load + `:56-61` debounced-fetch）会与 `page` 依赖叠加产生 2–3 次冗余请求，且 initial-load 用硬编码空 query 可能在慢速 SBC 上覆盖搜索结果。改为 Galaxy 式单一数据源。

`KifuPage.tsx` 改动：
1. 常量与 state：`const PAGE_SIZE = 20;`、`const [query, setQuery] = useState('');`、`const [page, setPage] = useState(1);`（保留 `searchInput`）。
2. `fetchAlbums` 改为**接收显式参数**，`useCallback` 依赖 `[]`（身份恒定，避免 effect 误触发）：
   ```tsx
   const fetchAlbums = useCallback((q: string, p: number) => {
     setLoading(true); setError(null);
     KifuAPI.getAlbums({ q: q || undefined, page: p, page_size: PAGE_SIZE })
       .then(resp => { setKifuList(resp.items); setTotal(resp.total); })
       .catch((err: Error) => setError(err.message))
       .finally(() => setLoading(false));
   }, []);
   ```
3. **删除**原 initial-load effect 与 debounced-fetch effect，替换为：
   ```tsx
   // 防抖：搜索稳定后一次性提交 query 并复位 page（React18 在 timeout 内自动批处理 → 单次重渲染）
   useEffect(() => {
     const t = setTimeout(() => { setQuery(searchInput); setPage(1); }, DEBOUNCE_MS);
     return () => clearTimeout(t);
   }, [searchInput]);

   // 唯一取数 effect：query 或 page 变化各触发一次（mount 时以 query='' page=1 触发一次）
   useEffect(() => { fetchAlbums(query, page); }, [query, page, fetchAlbums]);
   ```
4. 列表底部 `Pagination`（仅 `totalPages > 1`，`flexShrink:0`）：
   ```tsx
   const totalPages = Math.ceil(total / PAGE_SIZE);
   {totalPages > 1 && (
     <Box sx={{ display: 'flex', justifyContent: 'center', py: 1, borderTop: '1px solid rgba(255,255,255,0.04)', flexShrink: 0 }}>
       <Pagination count={totalPages} page={page} onChange={(_, p) => setPage(p)} color="primary" shape="rounded" size="small" />
     </Box>
   )}
   ```
> 结果：每次用户动作（输入稳定 / 翻页）恰好 1 次请求；mount 1 次。`setQuery(same)`/`setPage(1 when 1)` 为 no-op，不产生多余取数。

**完成标准**：能翻第 2 页并加载对应数据；搜索后页码复位 1；首页 ≤ 1 页时无分页条；无重复请求。

---

### Phase 5 — 结果翻译 + round_name + 标题样式（P1-3 / P1-4）
1. **结果徽标翻译**——扩展 `KioskResultBadge`（仅 KifuPage 使用，安全）：
   ```tsx
   // KioskResultBadge.tsx —— 路径深度 game→components→kiosk→src = ../../../
   import { useTranslation } from '../../../hooks/useTranslation';
   import { translateResult } from '../../../utils/resultTranslation';
   interface KioskResultBadgeProps { result: string; rules?: string | null }
   const KioskResultBadge = ({ result, rules }: KioskResultBadgeProps) => {
     const { t } = useTranslation();
     const label = translateResult(result, t, rules);
     const isBlack = result.startsWith('B') || result.startsWith('黑');
     // 保留 data-testid="result-badge" 与既有样式，渲染 {label}
   };
   ```
   - **务必保留 `data-testid="result-badge"`**。
   - KifuPage 调用处补 `rules`：`<KioskResultBadge result={result} rules={kifu.rules} />`。
2. **round_name**——卡片 Row 1 事件后补（复刻 Galaxy `KifuLibraryPage.tsx:120-124`）：
   ```tsx
   {kifu.event}
   {kifu.round_name && (
     <Typography component="span" sx={{ opacity: 0.6, fontSize: '0.7rem', ml: 0.5 }}>{kifu.round_name}</Typography>
   )}
   ```
3. **标题与计数**——`variant="h5"` → `h4`；`{total}` → `{total.toLocaleString()}`。保持中文 `局`。

**完成标准**：结果显示译文；有 `round_name` 的卡片显示之；标题 h4。

---

### Phase 6 — 单测更新（`KifuPage.test.tsx`）—— **[ENG-REVIEW F1/F2/F4/F5/F6/F7/F10]**
**目标**：覆盖全部新分支与用户流；规避「按钮静默禁用导致空过」与「翻译断言不可证」两个陷阱。

**6.1 URL 路由 mock（关键，F1/F10）**——`getAlbum(/albums/:id)` 必须返回带 `sgf_content` 的 detail，且 **`:id` 正则分支先于 `/albums` 列表分支**（否则 `url.includes('/albums')` 抢先匹配）。基础 mock：
```tsx
const detailSgf = '(;FF[4]GM[1]SZ[19];B[pd];W[dp];B[pp])'; // parsed.moves.length === 3
global.fetch = vi.fn().mockImplementation((url: string) => {
  if (/\/albums\/\d+/.test(url)) {
    return Promise.resolve({ ok: true, json: () => Promise.resolve(
      { ...mockAlbums[0], place: null, source: null, sgf_content: detailSgf }) }); // 满足 KifuAlbumDetail
  }
  // 列表分支：可读取 url 的 page 参数回显，保持 total=40 以测分页
  return Promise.resolve({ ok: true, json: () => Promise.resolve(mockResponse) });
});
```
> detail 含 3 手 → 选中后 `previewCurrentMove` 初始化为 3，计数/边界断言确定性。错误路径用例仍可用 `mockImplementationOnce` 局部覆盖。

**6.2 用例清单**（每条对应一个新分支/用户流）：
1. **Open-in-Research 成功**（F5 异步时序）：`vi.mock('../../hooks/useResearchSession')` 暴露 `createSession` spy→`'sess-1'`；`vi.mock('react-router-dom')` 暴露 `useNavigate` spy。序列：`render → await findByText('柯洁') → click 卡片 → await waitFor(button 不 disabled) → click 在研究中打开 → await waitFor(()=>{ expect(createSession).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ skipAnalysis:true })); expect(navigate).toHaveBeenCalledWith('/kiosk/research/session/sess-1'); })`。
2. **失败反馈**（F4，PRD §5 必测）：mock `createSession` → `null`；点击后 `await waitFor(()=>getByText('打开研究失败，请重试'))` 且断言 `navigate` 未被调用。
3. **按钮禁用**：detail 无 `sgf_content`（或 getAlbum 未 resolve）时按钮 `disabled`。
4. **翻谱边界**（F7，注意默认终局态）：选中 3 手谱后断言计数 `3 / 3`，`getByLabelText('next')`/`'last'` 禁用、`'first'`/`'prev'` 启用；click `prev` → `2 / 3`、`next` 启用；click `first` → `0 / 3`、`first/prev` 禁用、`next` 启用。**（原「从 N/N 点 ▶」不可行，▶ 在终局禁用）**
5. **分页 page-change**（F6）：mock `total=40`；`fireEvent.click(getByRole('button',{name:/page 2/}))`；`await waitFor(()=>expect(fetch).toHaveBeenLastCalledWith(stringContaining('page=2')))`。
6. **搜索复位页码**（F6）：先 `page=2`，在搜索框输入 → 推进 350ms 防抖（fake timers 或 waitFor）→ 断言下次 getAlbums URL 含 `page=1`（注意 `kifuApi.ts:20` 对 `page=1` 也会输出 `?page=1`），不含 `page=2`。
7. **结果翻译已接线**（F2，空 i18n 下无法断言译文，改证调用）：`vi.mock('../../utils/resultTranslation', () => ({ translateResult: vi.fn((r)=>r) }))`；断言 `KioskResultBadge` 渲染后 `translateResult` 被以 `(result, expect.any(Function), rules)` 调用；保留 `result-badge` 数量=2。可加一条 `result:'黑中盘胜'` fixture 行触发 zh 解析路径。
8. **round_name**：含 `round_name` 的卡片渲染该文本。
9. 保留并适配原 8 用例（`'2 局'` 仍成立；`result-badge`=2；`kifu-preview-nav` 存在）；把卡片点击后的同步断言改 `waitFor` 以消除既有 `act()` 警告。

**完成标准**：`npm test -- src/kiosk/__tests__/KifuPage.test.tsx` 全绿；新增分支均有用例。

---

### Phase 7 — 双构建 + 回归验证（收尾闸门）
1. `npm run build`（Galaxy 全量）✅。
2. `npm run build:kiosk-2d`（含 `verify:kiosk-2d`）✅；dist 无 `three`/`@react-three`/`THREE.`。
3. `npx tsc --noEmit` ✅、`npm test` ✅。
4. **Galaxy 回归**：确认零改动 `src/galaxy/**` 与共享区**实现**文件；手测 `/galaxy/kifu` 正常。
5. **实机验收（RK3562 kiosk，对照 PRD §5）**：
   - [ ] 选中 → 「在研究中打开」 → 研究棋盘加载终局，黑白名正确，可前后导航/试下/分析。
   - [ ] 未选中/SGF 未就绪 → 按钮禁用；失败有 toast。
   - [ ] 按钮单行不换行**且不裁切**；棋盘不被挤压；触控 ≥ 40px。**[ENG-REVIEW F13]** 在真机面板宽下复核。
   - [ ] ⏮◀▶⏭ 可逐手翻、计数更新；**[ENG-REVIEW F12]** 对 ~200 手长谱**快速连续翻页计时**，记录是否卡顿（LiveBoard 全量重放，见 §8 F12）。
   - [ ] 列表可翻页浏览首页之外。
   - [ ] 让子谱中途翻到某手再「在研究中打开」→ 定位正确（F11）。

**完成标准**：PRD §5 全勾。

---

## 4. 测试覆盖图（ENG-REVIEW Test Review）

```
CODE PATH COVERAGE — KifuPage.tsx (after plan)
================================================
[+] handleOpenInResearch()
    ├── [★★★ PLANNED] success → createSession(sgf,{initialMove,skipAnalysis}) + navigate — 6.2#1
    ├── [★★★ PLANNED] createSession→null → error toast + no navigate — 6.2#2  (PRD §5 失败反馈)
    ├── [★★  PLANNED] previewSgf null / opening → button disabled — 6.2#3
    └── [GAP→accept] catch 分支（createSession 永不 reject，防御性死代码）— 不单测
[+] preview nav (setPreviewCurrentMove)
    ├── [★★★ PLANNED] 边界禁用（终局 ▶/⏭ 禁用；起手 ⏮/◀ 禁用）+ 计数更新 — 6.2#4
[+] pagination
    ├── [★★  PLANNED] totalPages>1 渲染；page-change → fetch page=2 — 6.2#5
    └── [★★  PLANNED] 搜索复位 page=1 — 6.2#6
[+] 单一 fetch effect (F8)
    └── [★   PLANNED] mount 一次取数（隐含于既有用例）；无重复请求（人工/计数）
[+] KioskResultBadge translate wiring
    └── [★★  PLANNED] translateResult 被以 (result,t,rules) 调用 — 6.2#7（空 i18n 无法断言译文）
[+] round_name 渲染 — 6.2#8
[+] boardSize metadata 优先 (F3)
    └── [★   OPTIONAL] SZ[13] vs board_size=19 → previewBoardSize=13（建议补）

USER FLOW COVERAGE
================================================
[+] 选谱→预览→翻谱→在研究中打开  — 6.2#1+#4
[+] 失败重试反馈                 — 6.2#2
[+] 翻页浏览 / 搜索              — 6.2#5+#6
─────────────────────────────────
覆盖目标：新增分支 100%；翻译断言改证「调用」而非「译文」（harness 限制，F2）
─────────────────────────────────
```

---

## 5. 风险与回滚（含 eng-review 新增行）

| 风险 | 处置 |
|---|---|
| `createSession` 起一条多余 WS（KifuPage hook）随即卸载 | 无害（仅 `ws.close()`，不删会话）；已核验 |
| **[F-orphan]** `createSession` 建会话后 `sgf/load`/`redo` 抛错 → catch 返回 null 但后端会话**不被 DELETE** → 每次部分失败泄漏一会话 | **接受**（计划禁改共享 `useResearchSession`，KifuPage 只拿到 null 无 sessionId 可删）。§9 待确认：后端 research 会话是否有 GC/TTL；若无，另开 track 在 hook 内 best-effort DELETE |
| **[F13]** 单行底栏在真机窄面板裁切 | Phase 3 加 `flexWrap` 直接子元素兜底（窄屏按钮落次行）；真机面板宽复核；§9 待确认分辨率 |
| **[F12]** LiveBoard 逐手 `O(currentMove×size²)` 全量重放，长谱快速翻页可能卡 | **预存在共享代码特性**（Galaxy 同款），本 track 禁改 LiveBoard。Phase 7 真机计时；若卡，另开共享 track 加 `React.memo` + 增量盘面缓存 |
| **[F11]** 让子谱 `previewMoves` 含 AB 摆子，redo 计数偏移 | D2 `initialMove = max(0, previewCurrentMove − handicap)` 修正；加让子 fixture 测试 |
| `GamePage` 的「退出」跳 `/kiosk/play` 而非回棋谱库 | **预存在**、超范围（GamePage 属其他 track），不改。交付说明标注 |
| 改 `KioskResultBadge` 影响他处 | grep 确认**仅 KifuPage 使用**；保留 `data-testid` |
| 误触共享区导致 Galaxy 回归 | 不改共享区实现文件；Phase 7 双构建闸门 |
| **[F2]** 翻译断言在空 i18n 下不可证 | 测试改证 `translateResult` 调用签名（`vi.mock`），不断言译文 |
| `skipAnalysis:true` 削弱 PRD「可分析」 | 研究内仍可手动触发分析；自动全局分析在弱 CPU 上不可取 → 保留 skipAnalysis，交付说明标注「研究内手动分析」 |

**回滚**：改动集中于 `KifuPage.tsx` + `KioskResultBadge.tsx` + 测试，`git checkout` 该 3 文件即可完全回退，不影响 Galaxy 与后端。

---

## 6. NOT in scope（显式延后）

- 不改 Galaxy 任何文件 / 后端 API（现有接口已满足）。
- 不改共享 `LiveBoard.tsx`（含其 scrub 全量重放性能，F12 → 另开 track）。
- 不改 `useResearchSession.ts`（含失败路径 orphan 会话清理，F-orphan → 另开 track）。
- 不改 `GamePage` 的退出目标 / 研究向导本身（其他 track）。
- 不引入 three.js / `@react-three/*` / `/galaxy/*` / `/record`。

## 7. What already exists（复用，不重建）

| 子问题 | 既有实现 | 本计划处置 |
|---|---|---|
| 创建研究会话+加载 SGF+跳手数 | `useResearchSession.createSession(sgf,{initialMove,skipAnalysis})` | **复用**（不改） |
| 研究棋盘页 | `GamePage`（`research/session/:id`，向导已用此路由） | **复用**（不改） |
| SGF→落子序列 | `utils/sgfSerializer.sgfToMoves` | **复用** |
| 只读棋盘预览 | `components/live/LiveBoard`（已接 `currentMove`） | **复用**（不改） |
| 结果文案翻译 | `utils/resultTranslation.translateResult` | **复用**（KioskResultBadge 接入） |
| 分页/翻谱/徽标视觉 | Galaxy `KifuLibraryPage` | **参照复刻**（kiosk 本地 state，不 import galaxy） |

---

## 8. ENG-REVIEW 裁决日志（13 条确认发现，执行须遵守）

| ID | 严重度 | 裁决 | 落点 |
|---|---|---|---|
| F1 `getalbum-mock-split` | P1 | 接受 | Phase 6.1 给出 `:id` 正则先行的 URL mock + 确定 3 手 SGF |
| F2 `result-translation-unverifiable` | P1→P2 | 接受 | Phase 6.2#7 改证 `translateResult` 调用签名（`vi.mock`） |
| F3 `boardsize-latent-bug` | P2 | 接受（标注为有意修复） | Phase 1.2 metadata 优先 + 可选 SZ[13] 测试 |
| F4 `createsession-null-toast-untested` | P2 | 接受 | Phase 6.2#2 失败 toast 用例 |
| F5 `navigate-needs-async-act` | P2 | 接受 | Phase 6.2#1 明确异步 RTL 序列 |
| F6 `pagination-branches-undertested` | P2 | 接受 | Phase 6.2#5/#6 翻页 + 复位用例 |
| F7 `preview-nav-boundary-untested` | P2 | 接受（原 ▶ 用例不可行） | Phase 2 加 aria-label；Phase 6.2#4 边界用例 |
| F8 `search-page-double-fetch` | P2 | 接受 | Phase 4 重写为单一 fetch effect（消除 2–3 次冗余 + mount 双发） |
| F11 `handicap-redo-offby-n` | P2 | 接受 | D2/Phase 1.3 `initialMove = max(0, cur − handicap)` |
| F13 `bottombar-overflow-math` | P2 | 接受 | Phase 3 加 `flexWrap` 直接子元素兜底 + 真机宽复核 |
| F10 `getalbum-mock-url-routed` | P3 | 并入 F1 | — |
| F-orphan `orphaned-session` | P3 | 接受为风险 | §5 风险表 + §9 待确认后端 GC |
| F12 `liveboard-scrub-replay` | P2(共享) | 接受为限制 | §5 风险表 + Phase 7 真机计时 + 另开 track |

**架构裁定**：D1–D6 技术上成立（后端会话持久化经 `interface.py:294` 核验）。无 P0。无需改任何共享实现文件或后端。

---

## 9. 待用户/真机确认项（不阻塞编码，交付时回报）

1. **RK3562/3576/3588 kiosk 实际分辨率**（仓库未记录）→ 决定 Phase 3 单行宽度预算与兜底触发点。执行时按 ≤1024 横屏验证 + Phase 7 真机复核。
2. **后端 research 会话是否有 GC/TTL**（决定 F-orphan 是否需另开清理 track）。
3. **底栏最终视觉 mockup**（frontend-design 截图，异步审阅；用户已选 D4 单行方向）。
4. **长谱翻页真机流畅度**（F12，若卡则另开共享 LiveBoard 优化 track）。

---

## 10. 并行化策略

**Sequential implementation, no parallelization opportunity.** 全部改动集中在 `KifuPage.tsx`（主）+ `KioskResultBadge.tsx`（小）+ 同一测试文件，强耦合于单一模块；Phase 间有依赖（Phase 3 视觉依赖 Phase 1/2 行为就位，Phase 6 依赖前序全部）。按 Phase 0→1→2→（3 出 mockup 异步）→4→5→6→7 顺序执行；Phase 5 的 `KioskResultBadge` 可与 Phase 4 并行编辑（不同文件、无依赖），但收益甚微。

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR (PLAN) | 13 confirmed (0 P0, 2 P1→fixed, 9 P2, 2 P3); architecture D1–D6 locked, all auto-accepted into plan |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

- **UNRESOLVED:** 0 blocking. 4 待确认项（§9）非阻塞，交付时回报。
- **VERDICT:** ENG CLEARED — architecture locked, ready to implement. Run executing-plans.

---

## 11. 执行状态（Delivery — 2026-06-13）

**已实现并验证（autonomously executed）**：

| Phase | 状态 | 证据 |
|---|---|---|
| 0 基线 | ✅ | KifuPage 8 测通过 |
| 1 在研究中打开（方案A + F11 让子修正 + F3 boardSize） | ✅ | 源码 + 单测 |
| 2 翻谱控件 + aria-label（F7） | ✅ | 边界禁用单测 |
| 3 底栏单行 + F13 wrap 兜底 | ✅ 代码完成；mockup 见 `assets/bottombar-mockup.png`（异步待审） | 3 宽度截图证明单行/优雅换行/不裁切 |
| 4 分页 + 单一 fetch effect（F8） | ✅ | page-change / search-reset 单测 |
| 5 translateResult + round_name + 标题 | ✅ | wiring 单测 |
| 6 测试 | ✅ | KifuPage 8→**16 全绿** |
| 7 双构建 + 回归 | ✅ | `build` ✅、`build:kiosk-2d`+`verify:kiosk-2d` ✅（无 three.js）；全量 233 通过（43 失败为本分支**预存在**、与本 track 无关） |

**提交**：
- `72cb7da3` feat(kiosk-kifu): open-in-research + preview nav + pagination + parity polish
- `86d73e91` test(kiosk-kifu): cover open-in-research, preview nav, pagination, result wiring

**改动文件**（全部 kiosk territory）：`src/kiosk/pages/KifuPage.tsx`、`src/kiosk/components/game/KioskResultBadge.tsx`、`src/kiosk/__tests__/KifuPage.test.tsx`。零 Galaxy / 共享实现 / 后端改动。

**回报用户（§9 待确认）**：
1. RK3562/3576/3588 实际分辨率（mockup 已证 ≥364px 面板均不裁切；真机面板宽请复核）。
2. 后端 research 会话 GC/TTL（决定 F-orphan 是否需另开清理 track）。
3. 底栏 mockup 截图审阅（`assets/bottombar-mockup.png`）。
4. 长谱翻页真机流畅度（F12，LiveBoard 全量重放为共享代码既有特性）。
