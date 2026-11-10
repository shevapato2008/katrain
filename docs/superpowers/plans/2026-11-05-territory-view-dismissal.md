# Territory View and Dismissal Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking. ROOT coordinates the independent Astra max plan review (at most 2 rounds) and the later independent Astra max code review; do not create a duplicate review queue.

**Goal:** 升降级与跨平台星阵人机局均支持“查询领地 → 弹窗查看 → 关闭并撤销盘面覆盖 → 同局面免费复看”，只展示可信来源的参考信息。

**Architecture:** 将当前局面的已取得结果与查看状态分开，沿用各自 API、配额与叠加互斥规则；仅共用一个轻量结果弹窗，不抽象通用分析服务。升降级领先信息需要一个可选 `score_lead` 字段，从同一次云端 KataGo 结果筛选返回；它属于视觉确认后的最小契约变更，不增加引擎调用、数据库迁移或收费规则。关闭与复看始终是本地视图动作。

**Tech Stack:** Existing React/TypeScript, MUI Dialog, Vitest/Testing Library, Playwright/Vite fixture preview; existing FastAPI/KataGo private territory endpoint and pytest fixtures.

---

## Baseline, evidence and delivery boundaries

- Fresh `git fetch --no-recurse-submodules origin develop` baseline: `fb916f12516dd510080fb736a48a825dc206bc37` (2026-11-05).
- Plan worktree: `/tmp/katrain-territory-view-dismissal-plan-20261105`; branch `plan/territory-view-dismissal-20261105`. Created with `--no-checkout`; sparse paths are only `/AGENTS.md`, `/CLAUDE.md`, `/docs/superpowers/plans/`. Source verification used Git objects. Expand only the required source/test paths for execution; do not disable sparsity or run whole-tree status/search/format/test commands.
- Hard boundary: no filesystem access, traversal, stat or status pathspec of `data/kifu-album/`, on any machine. Preserve other working changes. Real paid analysis, real games and hardware commands are excluded from tests and previews.
- Investigation: `/tmp/ladder-territory-exit-investigation-20261105/report.md`. RK hashes of the 5 relevant source files match this source; deployed browser bundle identity is not yet verified.
- Existing behavior: ranked `useRankedTerritory.ts:45` always requests, no dismissal; engine `GamePage.tsx:1195` closes on second click but discards data. Existing lobby hook separates `result` and `visible`; reuse that pattern without changing lobby behavior. Star protocol note `superpowers/tracks/kiosk-play-golaxy/golaxy-protocol.md:280` already calls for same-position cache reuse.
- This document is the only authorized output at this stage. Wait for ROOT's consolidated plan-review result before implementation. No deployment in this plan.
- Frontend gate comes from the user's AGENTS.md: “用户未明确确认前不得进入当前切片的后端阶段”. Produce the actual 1024×600 frontend preview with isolated fixtures and reference comparison first; ROOT collects user confirmation before Task 4.

## Scope and truthful information

| Source | Display | Consumption rule retained |
|---|---|---|
| Ranked private territory | Estimated black/white ownership regions, labelled “较确定区域 N 点”; optional “预计黑/白领先 N 目” from `score_lead`; missing lead says “暂未取得领先判断” | Cloud ledger permits at most 3 successful requests per game; failure/replay semantics unchanged |
| Star `area` | Existing signed ownership, black winrate and black-perspective `delta` as estimated lead; zero says “接近均势” | User's Star account-level `area` item count; no local 3-use rule, no local deduction/refund |

Neither API provides accurate absolute black and white score totals. `black_area`/`white_area` are counts above/below ownership thresholds, not points scored. Do not subtract them to invent a margin. Do not expose `moveInfos`, policy or complete `rootInfo` in ranked responses. Do not call `judge`, finish the game or change clocks to populate this dialog.

No persistent cache service: retain a single current-position territory result per source for this mounted page. Close/reopen and switching Star overlay kinds reuse that result. Scope change invalidates it; remount does not automatically query. A new explicit query after an unrecoverable remount still follows the source's real consumption rules, with visible explanatory copy.

## File responsibilities

| File | Responsibility |
|---|---|
| Modify `katrain/web/ui/src/features/aiLadder/useRankedTerritory.ts` | Ranked current-result cache, local visible/dismiss state, in-flight/retry and scope invalidation |
| Modify its existing `.test.tsx` | Deterministic close/reopen/zero-quota/pending/stale/failure coverage |
| Create `katrain/web/ui/src/kiosk/components/game/TerritoryDialog.tsx` and `.test.tsx` | Present source-specific truthful summary and a large “关闭领地，继续下棋” action using existing dialog style |
| Modify `katrain/web/ui/src/kiosk/pages/GamePage.tsx` | Wire ranked dialog and Star current-position area cache; shared hide path, preserve other overlays/LED lifecycles |
| Modify `katrain/web/ui/src/kiosk/components/game/GameControlPanel.tsx` | Ranked pressed/disabled semantics; remove duplicate ranked result fold once dialog replaces it |
| Modify `katrain/web/ui/src/kiosk/__tests__/GamePageEngine.test.tsx` | Prove Star first/close/reopen is one request and kind switching preserves current area cache |
| Modify `katrain/web/ui/src/features/aiLadder/api.ts` | Optional nullable `score_lead` contract after visual approval |
| Modify `katrain/web/api/v1/endpoints/ai_ladder.py` | Select validated black-perspective lead from the existing private analysis result |
| Modify `tests/web_ui/test_ai_ladder_territory.py` and relevant assertion in `tests/web_ui/test_ai_ladder_api.py` | Updated narrow private response contract, replay and quota invariants |
| Modify `katrain/web/ui/tests/kiosk-screen-05-game.spec.ts`; create `katrain/web/ui/tests/kiosk-territory-dialog.spec.ts` | Adapt existing ranked screenshot expectation; one fixture-driven preview per source in the real runtime |
| Modify `katrain/i18n/locales/cn/LC_MESSAGES/katrain.po`, `katrain/i18n/locales/en/LC_MESSAGES/katrain.po` only if new keys are required | Use the existing `useTranslation` flow; reuse existing labels where possible |
| Create `superpowers/tracks/territory-view-dismissal/preview.md` | Short design/contract/fixture-deletion notes and approved screenshot references; image evidence may live under `/tmp` |

Do not edit the quota repository, Star adapter/client, hardware orchestrator, Board renderer or global dialog style unless a concrete failure proves a small change necessary. Both territory paths already render exclusively through `Board`'s Canvas overlay; closing requires `overlay=null`, not a global LED clear.

## Chunk 1: Frontend result lifecycle and reviewable preview

### Task 1: Establish the small dialog design and focused failing checks

- [ ] Read @ui-ux-pro-max and the existing kiosk design tokens/dialog rules. Reuse `kiosk-game-side-dialog` (380px paper, ≥42px action, board stays visible), existing colors/fonts and `DialogTitle`/`DialogContent`/`DialogActions`. Do not introduce a new visual system.
- [ ] Record the proposed 1024×600 composition in `superpowers/tracks/territory-view-dismissal/preview.md`: title “领地判断”, clear estimated-leading summary, optional ownership counts with “点”, source quota note, disclaimer “局中参考，正式胜负以终局数子为准”, and one large close action. Loading and failure use the same dialog shell and close action.
- [ ] Extend ranked hook tests with meaningful failures: first open invokes once; dismiss clears overlay but preserves result; reopen with `remaining=0` reuses result; dismiss pending then resolve stores result without reopening; new node/game/account/disabled→enabled generation discards late answers; failure retry uses the same request ID. Keep existing coordinate conversion coverage.
- [ ] Extend Star GamePage tests: area→close→area is one `platformEngineAnalysis` call; area→options→area reuses cached area; a move/end/session/account change invalidates cache; a closed pending area does not resurrect the dialog/Canvas when it resolves. Existing options/judge behavior remains covered by its present tests, not a new matrix.
- [ ] Run only the affected tests and verify the newly added assertions fail for the missing behavior:

  ```bash
  npm run test -- src/features/aiLadder/useRankedTerritory.test.tsx src/kiosk/__tests__/GamePageEngine.test.tsx -t 'territory|area|same active kind|overlay|quota|ranked'
  ```

  Expected: new close/reopen/pending assertions fail; failures must describe the current lifecycle gap, not fixture/import errors.

### Task 2: Implement ranked view state without changing billing

- [ ] Add visibility to the existing view and expose `visible`, `dismiss`, and the current-result-aware button action. Extend its scope with current game/account identity at the sole GamePage call site; use a generation that changes when that scope or enabled state changes, even if a string position is later revisited.

  Core behavior to implement inside the existing hook (names may follow existing conventions):

  ```ts
  type View = {
    position: string;
    phase: 'idle' | 'loading' | 'result' | 'error';
    result?: AiLadderTerritoryResult;
    visible: boolean;
  };
  // Existing valid result is checked BEFORE quota/request guards:
  // activate() => valid result ? toggle visible : perform existing request.
  // dismiss() => visible=false only; never call API, clear result or reset retry ID.
  // overlay => enabled && currentScope && view.visible && view.result ? area : null.
  // canActivate => currentResult || currentPendingView || existing canRequest.
  ```

- [ ] Keep authoritative `remaining` updates separate from visibility. Retain the current request-ID retry, cloud single-flight and stale-result behavior. On result resolution use the latest current-scope visibility intent, not the `visible=true` closure captured when the request started. A user dismissal must win over the delayed response.
- [ ] While pending, allow the dialog close action; repeat activation must not enqueue analysis. Reopening pending work may show loading but must not fire another POST. Scope/enable/account changes invalidate local view intent and request generation; old-session completion must not overwrite the new session's quota or error state.
- [ ] Make the ranked button `aria-pressed={visible}`; quota 0 blocks only a new request, never closing/reviewing an already obtained result. Remove its old result fold and duplicate area totals when the shared dialog is wired; keep the existing quota badge/exhausted explanation honest and concise.

### Task 3: Add the shared result dialog and Star current-position cache

- [ ] Implement `TerritoryDialog.tsx` as a presentation-only component: source, open/phase, optional finite lead/winrate/ownership counts, quota note, error/retry props and `onClose`. Route button close, backdrop and Escape through the same `onClose`. Do not give this component transport, charging, hardware, clock or game-ending responsibilities.
- [ ] Use a single lead formatter in this component: finite positive→“预计黑领先 X 目”; negative→“预计白领先 X 目”; zero→“接近均势”; missing/non-finite→“暂未取得领先判断”. Only Star shows its actual winrate; never render NaN, fabricated black/white totals, or area-count-derived lead.
- [ ] In `GamePage`, retain one successful current-position Star `area` payload independently of `activeEngineKind`. Existing active-area click and dialog close both hide area/evaluation/dialog without deleting that cache. Reactivating cached area restores it locally before any API call or item-count checks. Switching to another overlay hides the dialog but retains the current-position area cache; a successful area activation still replaces other overlays and preserves existing options→nonoptions `hintDismiss` behavior.
- [ ] Add a small area view intent/generation to the existing in-flight guard. Closing in-flight area must suppress later automatic display while retaining its valid result for explicit review. Keep the platform's insufficient/error handling, quota refresh after actual calls and stale result rejection. Do not claim network failure implies the platform did not charge; do not add auto-retry/refund logic.
- [ ] On move/pass/end/new game/account/logout/unmount, invalidate cached area, close dialog and remove Canvas overlay. Clear no physical lights for `area`; leave current options/judge cleanup paths untouched. No historical-result store or options/variation cache refactor in this task.
- [ ] Add only focused dialog assertions (trustworthy/missing/zero lead and close callback). Run the two lifecycle suites plus the dialog suite once; fix actual failures. Use the existing typecheck:

  ```bash
  npm run test -- src/features/aiLadder/useRankedTerritory.test.tsx src/kiosk/__tests__/GamePageEngine.test.tsx src/kiosk/components/game/TerritoryDialog.test.tsx
  npx tsc -b
  ```

- [ ] Create fixture routes in `kiosk-territory-dialog.spec.ts` for one ranked result and one Star area result. Mock all API/WS activity needed by the page; fixtures remain in tests and are never a production fallback. Before backend work, ranked's proposed lead field exists only in the fixture/presentation input; do not deploy a pretend business result.
- [ ] Start only Vite via the existing visual config, on an exclusive port; do not use the default Playwright backend-launching config:

  ```bash
  KATRAIN_PW_VISUAL_PORT=5187 npm run test:e2e -- --config=playwright.visual.config.ts tests/kiosk-territory-dialog.spec.ts --project=chromium --workers=1
  ```

  Expected: actual 1024×600 runtime opens each source's dialog, close removes overlay, reopen does not issue a second analysis request; no rail overflow and the close target remains visible.
- [ ] Produce one representative design reference and implementation screenshot per source at 1024×600, plus side-by-side and overlay/difference images. Record the relevant composition/spacing/type/color/copy/state differences in `preview.md`; avoid all-state re-shooting. ROOT presents the concrete preview for the user's confirmation.
- [ ] **Gate: stop before Task 4 until the user explicitly confirms the visual result.** The existing user instructions authorize preparing this frontend demo; they do not replace the AGENTS visual-confirmation boundary for backend work. Commit the focused frontend/demo changes using explicit file paths after its checks pass.

## Chunk 2: Minimal ranked contract and integrated verification

### Task 4: Return optional trustworthy lead from the same private analysis

- [ ] After the visual gate, add targeted pytest assertions in `test_ai_ladder_territory.py`: valid positive/negative/zero `rootInfo.scoreLead` yields `score_lead`; missing, bool, non-number or non-finite lead yields `null` without failing valid ownership; response still excludes raw rootInfo/winrate/moves/policy. Same request replay returns the same result and invokes the mock engine once; success still consumes one of three uses.
- [ ] Update only the relevant private-field expectation in `test_ai_ladder_api.py::test_box_ranked_territory_reaches_cloud_and_deducts_once` to allow `score_lead` while continuing to forbid full score/analysis structures. The generic box forwarding requires no new route or service.
- [ ] Run the cloud territory file before implementation and confirm the new contract assertion fails:

  ```bash
  CI=true python -m pytest tests/web_ui/test_ai_ladder_territory.py -q
  ```

- [ ] In `analyze_ranked_territory`, explicitly request black-perspective analysis using the same existing engine override mechanism, then select only the optional score field from that same response:

  ```python
  payload["overrideSettings"] = {"reportAnalysisWinratesAs": "BLACK"}
  root_info = analysis.get("rootInfo")
  lead = root_info.get("scoreLead") if isinstance(root_info, dict) else None
  score_lead = float(lead) if (
      not isinstance(lead, bool)
      and isinstance(lead, (int, float))
      and math.isfinite(lead)
  ) else None
  result = {**existing_result_fields, "score_lead": score_lead}
  ```

  Here `existing_result_fields` means the currently constructed move_count/ownership/black_area/white_area dictionary, not a new abstraction. Preserve 200 visits, 30-second timeout, complete/fail/replay ledger calls and private delivery; no second `analyze` request.
- [ ] Extend `AiLadderTerritoryResult` with `score_lead?: number | null`. Older persisted successful receipts may lack it: display missing-lead copy and reuse their already paid ownership instead of recomputing. Do not migrate receipts or reject such replays. Connect this trusted field to the reviewed ranked dialog presentation.
- [ ] Run the cloud file again, plus the narrow box replay case only in its synthetic test fixture. Before running any app-creating test, verify its startup uses a temporary synthetic album root or skips album initialization; do not touch the prohibited data path even for an existence check. If the current fixture lacks this isolation, limit this boundary check to a pure ASGI fixture that installs only the territory routes, rather than starting the whole app.

  ```bash
  CI=true python -m pytest tests/web_ui/test_ai_ladder_territory.py -q
  # Run the existing box test only after its fixture's forbidden-path isolation is verified:
  CI=true python -m pytest tests/web_ui/test_ai_ladder_api.py::test_box_ranked_territory_reaches_cloud_and_deducts_once -q
  ```

  Expected: successful query/replay still consumes exactly once, failures do not consume, stale result cannot display, and no private analysis fields except the named optional lead are released.
- [ ] Commit the exact API/type/test changes. No quota repository, migration or platform billing changes belong in this commit.

### Task 5: Finish the slice with proportional evidence and ROOT handoff

- [ ] Re-run only the affected frontend lifecycle/dialog suites, cloud territory contract checks and the fixture preview if integration changed its result shape. Update the old ranked result screenshot assertions in `kiosk-screen-05-game.spec.ts` to reflect the dialog and truthful labels; do not run unrelated full visual/regression suites.
- [ ] Confirm fixtures occur only in test/preview files, no production mock fallback exists, and close/reopen never invokes either analysis endpoint. Record checks, user visual approval and known cache-remount limitation in `preview.md`. Remove any temporary runtime fixture entry point if one was required; test fixtures may remain.
- [ ] Report source-specific acceptance: ranked 3-success quota unchanged; Star account items unchanged; one request for open→close→reopen; quota 0 cached result still closes/reopens; pending close/new move cannot revive old overlay; missing lead stays honest; no new physical-board command.
- [ ] Hand ROOT the explicit changed-file list, commits and evidence paths. ROOT arranges the required independent Astra max code review and fixes until approved. Do not self-dispatch duplicate reviewers, merge, push or deploy from this plan; those steps are coordinated with the other three fixes.

## Non-goals

- No precise absolute black/white scoring, ownership-based score invention, second engine query or local fallback in Star games.
- No change to ranked quota ledger, Star platform pricing, legacy/membership billing, judge/end-game rules, hint/attention LED ownership or other game scenes.
- No persistent cross-page cache, generic state machine framework, full UI redesign, broad security audit, full database scan or unrelated repository cleanup.
