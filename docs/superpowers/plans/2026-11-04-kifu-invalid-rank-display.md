# Kifu Explicit Empty Rank Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kiosk 与 Galaxy 尊重 API 已验证的空等级，不把无效原值“前人”重新显示为段位，同时保留现有“九段”、明确业余前缀和旧响应兼容行为。

**Architecture:** 只在棋谱共享 `formatKifuRank` 增加显式空字符串的早返回。API 保持等级裁定权，页面继续使用现有共享入口；不改通用 `formatRank`、后端、数据库或原始棋谱。

**Tech Stack:** 现有 TypeScript formatter、React 页面与 Vitest 测试；一个生产页面代表预览。

---

## Chunk 1: Respect the API empty-rank contract

### 已核实的边界

- 已发现的真实记录：`1934-06-03`、album `149564`，黑方原值为“前人”，API `display_black_rank` 为 `''`。当前 formatter 遍历 display/raw 并跳过空值，错误地重新展示原值。
- `katrain/web/api/v1/endpoints/kifu.py:148-149` 将 display 字段定义为 `Optional[str] = None`；当前 `_summary` / `_rank_displays` 明确填充展示值。`tests/web_ui/test_kifu_rank_snapshots_api.py::test_invalid_original_rank_without_snapshot_stays_source_and_never_displays_a_fallback` 和 `tests/web_ui/test_kifu_localization.py::test_invalid_explicit_ranks_never_fall_through_to_raw_frontend_fields` 已证明无效等级应返回 `''`。
- **精确 `''` 表示权威空值，返回 `null`，不得回退 raw；`null` / `undefined` 继续表示旧响应未提供规范展示等级，保留 raw fallback。** 非规范纯空白 `' '` 继续既有 fallback；不扩大为新过滤器。
- 保留已验证 `9p → 九段`、规范 `9d → 业余9段 / 業餘9段`、未验证 raw `7d → 7段`、裸段与级位行为；不凭人名或 raw `d` 新增业余/职业判断。未知占位符沿用现有逻辑，通用 `formatRank` 仍保留自由文本。
- `getListRank` 的 saved user-game 调用传入 `null`，其既有明确业余约定保持；不修改 `listRecordPresentation.ts` 或任何页面产品代码。
- 不读取、列举或遍历 `data/kifu-album`，不输出 SGF、secret 或整份详情响应。

### Task 1: Add focused regressions, then the one-line guard

**Files:**
- Modify: `katrain/web/ui/src/utils/rank.ts:80-94` — API 权威空值的展示边界。
- Test: `katrain/web/ui/src/utils/rank.test.ts:46` — 直接覆盖契约与 legacy 兼容。
- Test: `katrain/web/ui/src/kiosk/pages/KifuPage.test.tsx:86` — Kiosk 卡片实际使用共享边界。
- Test: `katrain/web/ui/src/galaxy/pages/KifuLibraryPage.localization.test.tsx:58` — Galaxy 卡片实际使用共享边界。
- Read-only regression: `katrain/web/ui/src/kiosk/utils/listRecordPresentation.test.ts` — 复用 saved user-game 现有测试，不新增测试层。

- [x] **Step 1: 在 formatter 测试加入下面的聚焦用例。** 已有专业、业余、裸段与 free-text 测试继续复用。

```ts
it('respects an explicit API empty rank while retaining legacy fallback', () => {
  expect(formatKifuRank('', '前人', t, 'cn')).toBeNull();
  expect(formatKifuRank('', '9p', t, 'en')).toBeNull();
  expect(formatKifuRank(null, '9p', t, 'cn')).toBe('九段');
  expect(formatKifuRank(undefined, '7d', t, 'cn')).toBe('7段');
  expect(formatKifuRank(' ', '9p', t, 'cn')).toBe('九段');
  expect(formatRank('前人', t)).toBe('前人');
});
```

- [x] **Step 2: 给两个现有页面测试文件各加一个代表用例。** 沿用各文件现有 helper/mock；不建立新 fixture 或截图套件。

Kiosk `KifuPage.test.tsx`：

```tsx
it('omits a raw invalid rank when the API display rank is explicitly empty', async () => {
  api.list.mockResolvedValue({ items: [{ ...albums[0],
    display_black_rank: '', black_rank: '前人',
    display_white_rank: '9p', white_rank: '9p',
  }], total: 1 });
  render(<MemoryRouter><KifuPage /></MemoryRouter>);
  const card = await screen.findByRole('button', { name: /赛事 1/ });
  expect(card).toHaveTextContent('黑棋手');
  expect(card).toHaveTextContent('白棋手');
  expect(card).not.toHaveTextContent('前人');
  expect(card.querySelectorAll('.record-match__rank')).toHaveLength(1);
  expect(within(card).getByText('九段')).toBeInTheDocument();
});
```

Galaxy `KifuLibraryPage.localization.test.tsx` 的现有 describe 内：

```tsx
it('omits a raw invalid rank when the API display rank is explicitly empty', async () => {
  const ranks = { display_black_rank: '', black_rank: '前人',
    display_white_rank: '9p', white_rank: '9p' };
  getAlbums.mockResolvedValue({ items: [{ ...record('cn'), ...ranks }],
    total: 1, page: 2, page_size: 20 });
  getAlbum.mockResolvedValue({ ...detail('cn'), ...ranks });
  render(page());
  await screen.findByTestId('board');
  expect(screen.getByText('cn-black')).toBeInTheDocument();
  expect(screen.getByText('cn-white')).toBeInTheDocument();
  expect(screen.queryByText('前人')).not.toBeInTheDocument();
  expect(screen.getByText('九段')).toBeInTheDocument();
});
```

- [x] **Step 3: 在 `katrain/web/ui` 运行新测试，确认其在原实现上因“前人”/raw fallback 而失败。**

```bash
npm test -- src/utils/rank.test.ts src/kiosk/pages/KifuPage.test.tsx src/galaxy/pages/KifuLibraryPage.localization.test.tsx
```

- [x] **Step 4: 在 `formatKifuRank` 现有循环前加入唯一行为修改，并在函数注释说明 `''` 与 nullish 的兼容区别。** 不改变循环内部的格式化、未知值或类别逻辑。

```ts
if (displayRank === '') return null;
```

- [x] **Step 5: 运行以下定向测试，要求全部通过；不追加全量回归、GPU 测试或后端修改。**

```bash
npm test -- src/utils/rank.test.ts src/kiosk/pages/KifuPage.test.tsx src/galaxy/pages/KifuLibraryPage.localization.test.tsx src/kiosk/utils/listRecordPresentation.test.ts
```

### Task 1 implementation evidence

- RED：新增三个用例均按预期失败，formatter 返回“前人”，Kiosk/Galaxy 均仍显示该 raw 值；日志 `/tmp/kifu-empty-rank-red.log`。
- 首次 GREEN 仅剩既有 Galaxy 语言切换重试用例失败。单独运行该旧用例并检查请求时序，确认其在初次自动预览完成前点击同卡，导致初始请求被取消并重取；删除这次多余点击，直接等待自动预览，保留语言切换失败后的同卡重试断言。页面产品代码未改。
- 最终指定四文件测试：**4 files / 60 tests passed**，退出码 0；日志 `/tmp/kifu-empty-rank-green.log`。`git diff --check` 通过。
- 自审：生产行为仅增加精确 `''` guard；`formatRank`、循环内部、数据库与页面产品代码均未修改；未读取或遍历 `data/kifu-album`。

### Task 2: Independent review and one actual preview

- [ ] 计划先由父任务安排 **Astra max 独立审核，最多两轮**；通过后按 @superpowers:subagent-driven-development 交给一个新的 implementer 完成 Task 1，控制改动范围。
- [ ] 补丁完成后由父任务安排 **Astra 独立 code review**；确认精确空值 guard、nullish/空白兼容、专业/业余区别及定向测试证据，通过后才继续父任务已授权的提交/发布流程。此计划本身不提交、不部署，也不合入其他 agent 的文件。
- [ ] 父任务部署后，用已有 Playwright session 查看 [真实 Galaxy 页面](https://modelstella.com/galaxy/kifu?q=1934-06-03)，viewport **1440×900**，只留一张代表截图。核对 album `149564` 的黑方姓名正常、“前人”消失、已知对手等级仍显示且无空分隔符；不要输出详情 SGF。
- [ ] 本次是展示契约修正，不做设计重构或 Fixture，不要求用户再次视觉确认；两个页面的代表测试加一个真实页面预览即为最低充分验证。记录截图路径与部署版本后交还父任务。
