# 屏 15 棋谱:恢复默认名局列表、去掉直播(前后端)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 盒上「棋谱」屏一进来就是名局列表(搜索框常驻 + 一页六局 + 翻页),直播列表从 kiosk 前后端彻底拿掉。

**Architecture:** 纯前端切片改 `KifuPage.tsx`:删掉「搜棋谱」开关与三张卡,名局列表的请求从挂载起就发,
搜索框和「导入 SGF」合成列表头上一行。直播这一半的前端(路由、两屏、屏 15 直播组)已由
`feature/kiosk-go-live` 删掉并已并入本分支(`c87cf747`);本计划只收它留下的后端尾巴:
盒上 `/api/v1/board/live/*` 代理 + `RemoteAPIClient` 的 8 个 live 读方法,以及 kiosk 包里仍会去拉
`live/translations` 的共享 `i18n.ts`。kiosk 包「不许出现任何直播接口路径」写进 `verify-kiosk.sh` 构建闸。

**Tech Stack:** React 19 + TypeScript + Vite(vitest / Playwright),FastAPI + pytest。

**Spec:**
- Fan 2026-09-23 原话:「我之前要求把直播模块移除,但我发现直播模块的列表被移动到棋谱库模块了……
  请恢复棋谱库默认的棋谱列表,移除直播列表。」
- 设计稿屏 15(artifact `e4d3c7ef` 第 34 版;源 `smartbox-software` 分支
  `feat/kiosk-go-kifu-list-design-2026-09-23` 提交 `d3c67394f`,
  `superpowers/shared/kiosk-shell/sample-go/go-kiosk.tmpl.html` 的 `data-screen="kifu"`,参考图
  `shots/15-kifu.png` sha256 `3a868711d4314ab72240d0a5a0836786909c8bf9123d4f948c35dcc6a793ba62`)。
- 直播 kiosk 端删除的前一个裁定:Fan 2026-09-22「在 kiosk 界面,我们就直接删掉直播模块吧……在 galaxy 模块保留就好」。

## Global Constraints

- kiosk 文案一律 `t('ns:key', '中文默认')`,**中文默认必须与 cn PO 一致**(`kiosk-shell-contract` 闸四)。本计划**不新增 key**:
  用 `kifu:loading`「加载中...」、`kifu:no_results`「未找到棋谱」、`kifu:import_sgf`「导入 SGF」、
  `kifu:search_placeholder_cn`「棋手、赛事、年份都能搜」等已有 11 语种的 key。
- 一页 `PAGE_SIZE = 6`(屏 15 右栏是一段滚栏,列表之后还有「最近摆过」)。
- galaxy 的直播(`/api/v1/live/*`、`galaxy/pages/live/*`、`components/live/*`、`hooks/live/*`)**一概不动**。
- 共享地界改动(`src/i18n.ts`、`src/api/live.ts`)两个包都要构建:`npm run build` 与 `npm run build:kiosk-2d`;
  盒上部署用 `npm run build:smartbox-kiosk-2d`。
- Playwright 打的是**构建产物**:改源码后先 `npm run build` 再跑 e2e。
- 视觉关卡:屏 15 出四图(参考 / 实现 / 并排 / 差异),Fan 确认后才算过。

## Review Focus

1. **没搜任何东西时库是空的**(云端库还没导入)——屏上不能说「没有对得上的谱,换棋手名再试」(那是搜索结果的话),要说「未找到棋谱」。→ Task 1 用例「没搜的时候库是空的」。
2. **在第 3 页改了搜索词**——结果要回第 1 页,不能请求「新词的第 3 页」而空着。→ Task 1 用例「改搜索词回第 1 页」。
3. **盒子断网进棋谱屏**——列表那块说「棋谱库要联网才能搜」,「最近摆过」和「导入 SGF」照常可用,重试真的再发一次。→ Task 1 用例「503」与「重试」(改写既有两条)。
4. **第 1 页按「上一页」/ 末页按「下一页」**——键是灰的,不发越界请求;**刚进屏 350ms 内就按「下一页」不能被弹回第 1 页**(搜索防抖在挂载时也会触发一次 `setPage(1)`,列表藏在开关后面时碰不到,默认摊开后就碰得到)。→ Task 1 用例「翻页」「进来马上翻页」。
5. **kiosk 包里残留直播路径**——代理删了之后,任何还在 kiosk 包里的 `/api/v1/(board/)live` 调用都会在盒上 404。→ Task 2 `verify-kiosk.sh` 闸 + 变异一次。

---

### Task 1: 屏 15 名局列表默认摊开(前端 · 视觉切片)

**Files:**
- Modify: `katrain/web/ui/src/kiosk/pages/KifuPage.tsx`(删 `searchOpen` / 探数效应 / `KioskCard` 三张卡;列表效应无条件;列表头一行)
- Modify: `katrain/web/ui/src/kiosk-shell/go-screens.css:694-707`(`.ksearch` 改成「头一行 + 结果」)
- Test: `katrain/web/ui/src/kiosk/__tests__/KifuPage.test.tsx`(改写「三张卡」「开关」两组)
- Modify: `katrain/web/ui/tests/kiosk-shell-scroll.spec.ts:421-423`(不再先点「搜棋谱」)
- Modify: `katrain/web/ui/tests/kiosk-screen-15-kifu.fourup.spec.ts`(注释与图注)
- Modify: `katrain/web/ui/tests/helpers/reference-shots.json`(`15-kifu.png` 换指纹与分支)

**Interfaces:**
- Consumes: `KifuAPI.getAlbums({ q?: string, page: number, page_size: number }) → Promise<{ items: KifuAlbumSummary[], total: number, page: number, page_size: number }>`(不变)
- Produces: DOM 契约 —— `data-testid="kifu-search"` 从挂载起就在;里面 `.ksearch__bar` 放 `input.ksearch__box[type=search]` 与 `button.ksearch__import`(文案「导入 SGF」);结果行仍是 `.kiosk-rows > button.kiosk-row`;翻页 `.kpager`。屏上不再有 `.kiosk-card`。

- [x] **Step 1: 改写失败测试** —— 把 `KifuPage.test.tsx` 里 `describe('屏 15 棋谱 · 问候与三张卡')` 与 `describe('屏 15 棋谱 · 搜棋谱是开关不是跳转')` 两组整段换成:

```tsx
describe('屏 15 棋谱 · 问候与列表头', () => {
  // 副标去掉了稿子里的「职业直播」:Fan 2026-09-22 裁定 kiosk 端不做直播,屏上不许许诺没有的东西。
  it('问候行照稿子写「看别人的棋」,副标不提直播', () => {
    renderPage();
    expect(screen.getByText('看别人的')).toBeInTheDocument();
    expect(screen.getByText('棋')).toBeInTheDocument();
    expect(screen.getByText('名局，以及把谱摆到实体盘上')).toBeInTheDocument();
  });

  // 2026-09-23 Fan:列表要一进来就在。三张卡(搜棋谱 / 摆到实体盘 / 导入 SGF)拆了,
  // 「导入 SGF」挪到搜索框右边 —— 屏上一张卡都不剩,也就没有要先按的开关。
  it('没有卡片,搜索框和「导入 SGF」一进来就在同一行', () => {
    renderPage();
    expect(document.querySelectorAll('.kiosk-card')).toHaveLength(0);
    const bar = document.querySelector('[data-testid="kifu-search"] .ksearch__bar')!;
    expect(within(bar as HTMLElement).getByPlaceholderText('棋手、赛事、年份都能搜')).toBeInTheDocument();
    expect(within(bar as HTMLElement).getByRole('button', { name: /导入 SGF/ })).toBeInTheDocument();
  });

  it('「导入 SGF」按下去开的是本地文件选择框', () => {
    renderPage();
    const input = screen.getByTestId('kifu-sgf-input') as HTMLInputElement;
    const clicked = vi.spyOn(input, 'click');
    fireEvent.click(screen.getByRole('button', { name: /导入 SGF/ }));
    expect(clicked).toHaveBeenCalled();
  });
});

describe('屏 15 棋谱 · 名局列表默认摊开', () => {
  it('进来就拉第一页六局并铺出行 —— 不先探一个数、不等谁按开关', async () => {
    renderPage();
    const rows = await screen.findAllByText('柯洁 对 申真谞');
    expect(rows).toHaveLength(2);
    // 判据落在请求形状上:只有一发,就是列表本身。旧写法挂载时先发一发 page_size: 1 探总数。
    expect(getAlbums).toHaveBeenCalledTimes(1);
    expect(getAlbums).toHaveBeenCalledWith({ q: undefined, page: 1, page_size: 6 });
  });

  it('组标题右端写的是真数据「共 N 局」', async () => {
    getAlbums.mockResolvedValue({ items: [album(1)], total: 1234, page: 1, page_size: 6 });
    renderPage();
    expect(await screen.findByText('共 1,234 局')).toBeInTheDocument();
    expect(screen.queryByText('按棋手 / 赛事 / 日期搜')).not.toBeInTheDocument();
  });

  it('点一行进屏 16 的详情', async () => {
    renderPage();
    const rows = await screen.findAllByText('柯洁 对 申真谞');
    fireEvent.click(rows[0].closest('button')!);
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/kifu/1');
  });

  it('没搜的时候库是空的:说「未找到棋谱」,不说「换棋手名再试」', async () => {
    getAlbums.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 6 });
    renderPage();
    expect(await screen.findByText('未找到棋谱')).toBeInTheDocument();
    expect(screen.queryByText('没有对得上的谱')).toBeNull();
    expect(screen.queryByText('换棋手名、赛事名或者年份再试。')).toBeNull();
  });

  it('搜了对不上:说「没有对得上的谱」并给换词的提示', async () => {
    renderPage();
    await screen.findAllByText('柯洁 对 申真谞');
    getAlbums.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 6 });
    fireEvent.change(screen.getByPlaceholderText('棋手、赛事、年份都能搜'), { target: { value: '不存在' } });
    expect(await screen.findByText('没有对得上的谱')).toBeInTheDocument();
    expect(screen.getByText('换棋手名、赛事名或者年份再试。')).toBeInTheDocument();
    expect(getAlbums).toHaveBeenLastCalledWith({ q: '不存在', page: 1, page_size: 6 });
  });

  it('翻页:第 1 页「上一页」是灰的;「下一页」发第 2 页', async () => {
    getAlbums.mockResolvedValue({ items: [album(1)], total: 20, page: 1, page_size: 6 });
    renderPage();
    await screen.findByText('1 / 4');
    expect(screen.getByRole('button', { name: '上一页' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '下一页' }));
    await waitFor(() => expect(getAlbums).toHaveBeenLastCalledWith({ q: undefined, page: 2, page_size: 6 }));
  });

  // 搜索防抖原先挂载时也跑一次:350ms 后 setQuery('') + setPage(1)。列表藏在开关后面时没人能在
  // 350ms 内翻页;默认摊开后,进屏就点「下一页」会被它弹回第 1 页。
  it('进来马上翻页,不会被搜索防抖弹回第 1 页', async () => {
    // 全假时钟:点击一定落在挂载后 350ms 以内(`findBy*` 会让真时间流过去,点击可能晚于那一下)。
    vi.useFakeTimers();
    try {
      getAlbums.mockResolvedValue({ items: [album(1)], total: 20, page: 1, page_size: 6 });
      renderPage();
      await act(async () => { await vi.advanceTimersByTimeAsync(0); });
      expect(screen.getByText('1 / 4')).toBeInTheDocument();
      fireEvent.click(screen.getByRole('button', { name: '下一页' }));
      await act(async () => { await vi.advanceTimersByTimeAsync(0); });
      expect(screen.getByText('2 / 4')).toBeInTheDocument();
      await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
      expect(screen.getByText('2 / 4')).toBeInTheDocument();
      expect(getAlbums).toHaveBeenLastCalledWith({ q: undefined, page: 2, page_size: 6 });
    } finally {
      vi.useRealTimers();
    }
  });

  it('在第 3 页改搜索词,结果回第 1 页', async () => {
    getAlbums.mockResolvedValue({ items: [album(1)], total: 30, page: 1, page_size: 6 });
    renderPage();
    await screen.findByText('1 / 5');
    fireEvent.click(screen.getByRole('button', { name: '下一页' }));
    await screen.findByText('2 / 5');
    fireEvent.click(screen.getByRole('button', { name: '下一页' }));
    await screen.findByText('3 / 5');
    fireEvent.change(screen.getByPlaceholderText('棋手、赛事、年份都能搜'), { target: { value: '柯洁' } });
    await waitFor(() => expect(getAlbums).toHaveBeenLastCalledWith({ q: '柯洁', page: 1, page_size: 6 }));
  });

  it('库读不到时如实报错并给重试 —— 重试真的会再发一次请求', async () => {
    getAlbums.mockRejectedValue(new Error('boom'));
    renderPage();
    expect(await screen.findByText('棋谱库读不到')).toBeInTheDocument();
    expect(screen.getByText('boom')).toBeInTheDocument();
    const before = getAlbums.mock.calls.length;
    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    await waitFor(() => expect(getAlbums.mock.calls.length).toBe(before + 1));
  });

  it('棋谱库连不上云端(503)时说「要联网」,不印原文,也不说「没搜到」', async () => {
    getAlbums.mockRejectedValue(new ApiError(503, 'Request failed 503: {"detail":"Remote kifu service unavailable"}'));
    renderPage();
    expect(await screen.findByText('棋谱库要联网才能搜')).toBeInTheDocument();
    expect(screen.queryByText(/Request failed/)).toBeNull();
    expect(screen.queryByText('没有对得上的谱')).toBeNull();
    expect(screen.getByRole('button', { name: '重试' })).toBeInTheDocument();
    // 断网不连累另外两条路:导入 SGF 还在
    expect(screen.getByRole('button', { name: /导入 SGF/ })).toBeInTheDocument();
  });
});
```

同时把文件头注释里「收起时不拉列表 … `page_size: 1`」那条改成:
「列表默认摊开(2026-09-23 Fan)—— 断言落在 `getAlbums` 的调用次数与参数形状上:进来只有一发,就是第一页六局」。

- [x] **Step 2: 跑测试确认红**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/KifuPage.test.tsx`
Expected: FAIL —— 「没有卡片」(找到 3 张 `.kiosk-card`)、「进来就拉第一页」(第一发是 `page_size: 1`)等新用例红。

- [x] **Step 3: 实现** —— `KifuPage.tsx`:

  1. 删 `import { KioskCard } from '../shell/KioskCard';`,加 `import { Icon } from '../shell/icons';`。
  2. 删 `const [searchOpen, setSearchOpen] = useState(false);` 与整个「收起时只探一个数」效应。
  2b. 防抖效应只在输入真变了时才起表(挂载时 `'' === ''` 不起),否则进屏 350ms 内翻的页会被弹回第 1 页:

```tsx
  useEffect(() => {
    if (searchInput === query) return;
    const timer = setTimeout(() => {
      setQuery(searchInput);
      setPage(1);
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [searchInput, query]);
```

  3. 列表效应去掉 `if (!searchOpen) return;`,依赖改 `[query, page, reload]`。
  4. `<section>` 里 `<div className="kiosk-cards">…</div>` 与 `{searchOpen && (` 包裹换成:

```tsx
        <div className="ksearch" data-testid="kifu-search">
          <div className="ksearch__bar">
            <input
              type="search"
              className="ksearch__box"
              placeholder={t('kifu:search_placeholder_cn', '棋手、赛事、年份都能搜')}
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
            />
            <button
              type="button"
              className="kiosk-btn kiosk-btn--pill ksearch__import"
              onClick={() => fileInputRef.current?.click()}
            >
              <Icon name="upload-simple" />
              {t('kifu:import_sgf', '导入 SGF')}
            </button>
          </div>
          {listError ? (
            /* 原样保留:503 说要联网 / 其他照原样报 + 重试 */
          ) : albums == null ? (
            <div className="empty"><h4>{query ? t('kifu:searching', '正在找') : t('kifu:loading', '加载中...')}</h4></div>
          ) : albums.length === 0 ? (
            query ? (
              <div className="empty">
                <h4>{t('kifu:no_results_cn', '没有对得上的谱')}</h4>
                <p>{t('kifu:no_results_hint', '换棋手名、赛事名或者年份再试。')}</p>
              </div>
            ) : (
              <div className="empty"><h4>{t('kifu:no_results', '未找到棋谱')}</h4></div>
            )
          ) : (
            /* 原样保留:结果行 + .kpager */
          )}
        </div>
```

  `<input ref={fileInputRef} type="file" … />` 留在 `<section>` 里不动。文件头注释改写:去掉「三处和稿子不一样」里的 ②(搜索开关)与「直播」段,写明 2026-09-23 Fan 改判「名局列表一进来就摊开」。

  `go-screens.css` 的 `.ksearch` 一段换成:

```css
/* ── 屏 15 棋谱:名局列表(2026-09-23 起默认摊开)────────────────────────────
   头一行:搜索框 + 「导入 SGF」;下面是结果行与翻页。稿子同名类在 sample-go 模板里,高 44 圆角 11。 */
.ksearch { display: flex; flex-direction: column; gap: 10px; }
.ksearch__bar { display: flex; gap: 10px; }
.ksearch__box {
  flex: 1; min-width: 0;
  height: 44px; padding: 0 14px; border: 1px solid var(--hair); border-radius: 11px;
  background: var(--panel); color: var(--text);
  font-family: var(--font-sans); font-size: 14px;
}
.ksearch__box::placeholder { color: var(--dim); }
.ksearch__box:focus-visible { outline: none; border-color: var(--accent); }
.ksearch__import { height: 44px; flex: none; }
.ksearch__import svg { width: 16px; height: 16px; }
```

  (`.kpager` 两行不动。`.kiosk-row__end select.ksearch__box` 那条是别屏借用,`flex:1` 对它无害 —— 它在行尾 flex 里本来就被 `width` 定住;跑几何闸确认。)

- [x] **Step 4: 跑测试确认绿**

Run: `cd katrain/web/ui && npx vitest run src/kiosk/__tests__/KifuPage.test.tsx && npx tsc -b && npx eslint src/kiosk/pages/KifuPage.tsx src/kiosk/__tests__/KifuPage.test.tsx`
Expected: PASS;tsc 0;eslint 0 problems。

  **变异一次**:注掉 `if (searchInput === query) return;` → 「进来马上翻页」应红 → 恢复。(第一版用 `shouldAdvanceTime` 写的这条对变异是绿的:`findBy*` 让真时间流过 350ms,点击晚于那一下。)

- [x] **Step 5: 真浏览器 —— 滚动闸与几何闸**

`kiosk-shell-scroll.spec.ts` 屏 15 那条删掉两行「展开搜索」(`getByRole('button', { name: /搜棋谱/ }).click()` 与其注释),
保留 `await page.waitForSelector('[data-testid="kifu-search"] .kiosk-row');`。判据不变:造出溢出 > 100、真滚轮滚到底、「最近摆过」末行进得了视野。

Run: `cd katrain/web/ui && npm run build && KATRAIN_PW_E2E_PORT=8112 npx playwright test tests/kiosk-shell-scroll.spec.ts tests/kiosk-shell-geometry.spec.ts tests/kiosk-shell-contract.spec.ts`
Expected: 全过(与本分支改动前的名字集合比,只有屏 15 那条的步骤变了,没有用例消失)。

- [x] **Step 6: 四图**

`reference-shots.json` 的 `15-kifu.png` 改成
`{"sha256": "3a868711d4314ab72240d0a5a0836786909c8bf9123d4f948c35dcc6a793ba62", "shotFrom": "feat/kiosk-go-kifu-list-design-2026-09-23"}`。
`kiosk-screen-15-kifu.fourup.spec.ts` 注释 ①② 改为「稿子 2026-09-23 已按 Fan 改判重画(列表默认摊开、无直播组、无『界面未接』块),预期差异只剩 fixture 数据」,图注去掉「搜棋谱是开关」那句。

Run: `cd katrain/web/ui && KATRAIN_PW_VISUAL_PORT=5273 npx playwright test --config=playwright.visual.config.ts tests/kiosk-screen-15-kifu.fourup.spec.ts`
Expected: 生成 `superpowers/tracks/kiosk-go-shell-align/visual/15-kifu/1024x600/` 四张;逐项对比构图 / 间距 / 层级 / 字色 / 图标 / 文案 / 状态语义。**Fan 确认。**

- [x] **Step 7: Commit**

```bash
git add katrain/web/ui/src/kiosk/pages/KifuPage.tsx katrain/web/ui/src/kiosk-shell/go-screens.css \
  katrain/web/ui/src/kiosk/__tests__/KifuPage.test.tsx katrain/web/ui/tests/kiosk-shell-scroll.spec.ts \
  katrain/web/ui/tests/kiosk-screen-15-kifu.fourup.spec.ts katrain/web/ui/tests/helpers/reference-shots.json \
  superpowers/tracks/kiosk-go-shell-align/visual/15-kifu
git commit -m "feat(kiosk-go): 屏 15 棋谱名局列表一进来就摊开 —— 搜索框常驻、导入 SGF 贴在右边"
```

---

### Task 2: 拿掉盒上直播的后端代理与 kiosk 包里最后一处直播调用(后端 + 构建闸)

**Files:**
- Modify: `katrain/web/api/v1/endpoints/board.py:106-204`(删 8 条 `/live/*` 代理路由;`_get_remote_client` / `_proxy` 留给下面的教程代理)
- Modify: `katrain/web/core/remote_client.py:358-403`(删 `# ── Live (read-only) ──` 一段 8 个方法)
- Delete: `tests/web_ui/test_board_live_proxy.py`
- Create: `tests/web_ui/test_board_no_live.py`
- Modify: `katrain/web/ui/src/i18n.ts`(kiosk 包不拉 `live/translations`)
- Modify: `katrain/web/ui/src/api/live.ts:16-17`(`API_BASE` 只剩 `/api/v1/live`)
- Modify: `katrain/web/ui/scripts/verify-kiosk.sh`(kiosk 包里不许出现任何直播接口路径)

**Interfaces:**
- Consumes: 无(与 Task 1 无接口依赖)。
- Produces: 盒上 `GET /api/v1/board/live/*` → 404;kiosk-2d 包里 `grep -E "/api/v1/(board/)?live"` 零命中。

- [x] **Step 1: 写失败测试** —— `tests/web_ui/test_board_no_live.py`:

```python
"""盒上没有直播(Fan 2026-09-22:kiosk 端删掉整个直播模块,只在 galaxy 保留)。

原来 `/api/v1/board/live/*` 是给 kiosk 直播屏用的只读代理;直播屏删了之后它没有任何调用者。
这条守的是「盒上的直播后端也跟着没了」—— 代理回来了,kiosk 包里的直播调用也就有地方可去,
两边会一起悄悄长回来。
"""

import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from katrain.web.server import create_app


@pytest.fixture
def board_app(tmp_path):
    os.environ["KATRAIN_DATABASE_PATH"] = str(tmp_path / "board_no_live.db")
    app = create_app(enable_engine=False)
    client = MagicMock()
    client.get_tutorial_categories = AsyncMock(return_value=[])
    app.state.remote_client = client
    return app


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    ["/api/v1/board/live/matches", "/api/v1/board/live/matches/featured", "/api/v1/board/live/translations?lang=cn"],
)
async def test_board_has_no_live_proxy(board_app, path):
    async with AsyncClient(transport=ASGITransport(app=board_app), base_url="http://t") as c:
        r = await c.get(path)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_board_tutorial_proxy_still_served(board_app):
    """删直播时 `_get_remote_client` / `_proxy` 要留给教程代理 —— 这条防误删。"""
    async with AsyncClient(transport=ASGITransport(app=board_app), base_url="http://t") as c:
        r = await c.get("/api/v1/board/tutorials/categories")
    assert r.status_code == 200


def test_remote_client_has_no_live_reads():
    from katrain.web.core.remote_client import RemoteAPIClient

    assert [n for n in dir(RemoteAPIClient) if "live" in n] == []
```

- [x] **Step 2: 跑测试确认红**

Run: `CI=true uv run --extra web pytest tests/web_ui/test_board_no_live.py -q -p no:cacheprovider`
Expected: 4 条里 3 条 404 用例 FAIL(现在是 200)+ `test_remote_client_has_no_live_reads` FAIL;教程那条 PASS。

- [x] **Step 3: 实现后端** —— 删 `board.py` 从 `@router.get("/live/matches")` 到 `proxy_live_translations` 结束的 8 个函数(保留 `# ── Live Match Proxy` 注释块上方的 `_get_remote_client` / `_proxy`,把那段注释改成「盒上只读代理」通用说明);删 `remote_client.py` 的 `# ── Live (read-only) ──` 一段;`git rm tests/web_ui/test_board_live_proxy.py`。

- [x] **Step 4: 跑测试确认绿**

Run: `CI=true uv run --extra web pytest tests/web_ui/test_board_no_live.py tests/web_ui/test_live_list_demotion.py -q -p no:cacheprovider`
Expected: PASS(后一个文件是云端直播的,确认没被牵连)。

- [x] **Step 5: 前端两处 + 构建闸**

`src/i18n.ts` 的 `loadLiveTranslations` 开头加:

```ts
    // kiosk 包没有直播(Fan 2026-09-22),盒上也没有直播接口可拉 —— 人名 / 赛事译名表只给 galaxy 用。
    // 字面量 `if (true) return` 让打包器把下面整段连同 LiveAPI 一起摇掉,verify-kiosk.sh 查的就是这个。
    if (__KIOSK_2D_ONLY__) return;
```

`src/api/live.ts` 的 `API_BASE` 改为 `const API_BASE = '/api/v1/live';`,注释改成「kiosk 包里没有直播(verify-kiosk.sh 闸),这里只剩 galaxy 一个调用方」;`assertWritable` 不动。

`scripts/verify-kiosk.sh` 头注释第三条与「Live API base」一段换成:

```bash
# Live — the kiosk has no live module (Fan 2026-09-22; the board proxy /api/v1/board/live is gone).
# Any /api/v1/live or /api/v1/board/live string in the kiosk dist is a call that would 404 on the box.
if matches=$(grep -lE "/api/v1/(board/)?live" "$DIST"/assets/*.js 2>/dev/null); then
  echo "❌ Found live API path in kiosk dist (kiosk has no live module):" >&2
  echo "$matches" >&2
  fail=1
fi
```

并把末行 ✅ 文案里「non-board live API」改成「live API」。

Run: `cd katrain/web/ui && npm run build:kiosk-2d`
Expected: `✅ kiosk boundary clean`。

**变异一次**(闸的红分支要跑过):临时删掉 `i18n.ts` 那行 `if (__KIOSK_2D_ONLY__) return;` → `npm run build:kiosk-2d` 应输出 `❌ Found live API path` 并退出非 0 → 恢复。

- [x] **Step 6: 两个包 + 盒上严格包都要过**

Run: `cd katrain/web/ui && npm run build && npm run build:smartbox-kiosk-2d && npx vitest run`
Expected: 两次构建成功,严格包 verify 过;vitest 全绿。

- [x] **Step 7: Commit**

```bash
git add katrain/web/api/v1/endpoints/board.py katrain/web/core/remote_client.py tests/web_ui/test_board_no_live.py \
  katrain/web/ui/src/i18n.ts katrain/web/ui/src/api/live.ts katrain/web/ui/scripts/verify-kiosk.sh
git rm tests/web_ui/test_board_live_proxy.py
git commit -m "feat(kiosk-go): 盒上直播后端跟着删 —— board/live 代理、RemoteAPIClient 读方法,kiosk 包里不许再有直播路径"
```

---

### Task 3: 稿子进度回写与赛道文档

**Files:**
- Modify(smartbox 分支 `feat/kiosk-go-kifu-list-design-2026-09-23`):`superpowers/shared/kiosk-shell/sample-go/build.py` 的 `PROGRESS.kifu` 标回 `done`,重建两份 HTML、跑 `gate.mjs`、重发 artifact `e4d3c7ef`。
- Modify: `superpowers/tracks/kiosk-go-kifu/prd.md`(加一节「2026-09-23 改判」:列表默认摊开、K1 验收里「摆到实体盘卡展开搜索」那条作废;直播后端尾巴已收)。

- [x] **Step 1:** `build.py` 里 `kifu: ["shell", …]` 改 `kifu: ["done", "2026-09-23 · /kiosk/kifu —— 名局列表默认摊开、直播已删(前后端)"]`;`python3 build.py && python3 build.py --proto && node gate.mjs`,Expected `908 条合规断言全过`;还原除 `15-kifu.png` 以外抖动的截图;提交;用 Artifact 工具以同一 URL 重发 `go-kiosk.html`。
- [x] **Step 2:** PRD 追加改判一节,提交 `docs(kiosk-go-kifu): 2026-09-23 屏 15 列表默认摊开、直播后端收尾`。

---

## Self-Review

- **Spec coverage:** 恢复默认列表 → Task 1;移除直播列表 → 前端已由并入的 `feature/kiosk-go-live` 删掉(`c87cf747`),后端尾巴 → Task 2;先改设计稿 → 已完成(`d3c67394f`,artifact 第 34 版),进度回写 → Task 3。
- **Placeholder scan:** Task 1 Step 3 里两处 `/* 原样保留 */` 指的是现有 `KifuPage.tsx` 中 `listError` 分支与结果行 + `.kpager` 分支,原文不动,不是待补。
- **Type consistency:** `getAlbums` 参数形状 `{ q, page, page_size }` 在测试与实现一致;`PAGE_SIZE = 6`。
- **Review Focus:** 五条各落在 Task 1 / Task 2 的具体用例或闸上。
- **不做:** `KifuPage` 的「最近摆过」首帧读默认 store(`listRecent()` 不带身份)是 develop 上既有的缺口,与本次无关,登记不修。
