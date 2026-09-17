import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import { sequenceKey, UNIT_SIZE } from '../pages/tsumegoUnits';
import type { TsumegoProgressEntry } from '../../context/TsumegoProgressContext';
import { __resetKioskActivityStorageForTests, setKioskIdentity } from '../storage/kioskActivityStorage';

const TEST_UUID = 'tsumego-unit-list-test-user';

/**
 * 屏 13 · 题目列表。**2026-08-22 按稿子整屏换过**,所以和上一版对不上是预期的:
 * 上一版断的是「每题一张带缩略棋盘的 MUI 卡 + `?offset&limit=20` 取整题」,
 * 稿子上是「一格一题的 `.qgrid`(题号 + 试了几次)+ 数据条 3 格 + 换一批两行」。
 *
 * 留下来的是**契约**,不是文案:
 *   · 顺序表在 `sessionStorage` 里就直接用,**一次接口都不取**;没有才自己取一次并回填;
 *   · 点一格进那一道题;
 *   · 「试了几次」= `attempts + (做对了 ? 1 : 0)` —— `attempts` 数的是**失败**的那几次。
 */

const { mockNavigate, mockRefresh, progressMap, progressFlags } = vi.hoisted(() => ({
  mockNavigate: vi.fn(),
  mockRefresh: vi.fn(),
  progressMap: {} as Record<string, TsumegoProgressEntry>,
  progressFlags: { failed: false },
}));

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock('../../context/TsumegoProgressContext', () => ({
  useTsumegoProgress: () => ({
    progress: progressMap,
    markProgress: vi.fn(),
    isCompleted: (id: string) => !!progressMap[id]?.completed,
    unitProgress: (ids: string[]) => ({
      completed: ids.filter((id) => progressMap[id]?.completed).length,
      total: ids.length,
    }),
    categoryProgress: () => ({ completed: 0, total: 0 }),
    serverLoadFailed: progressFlags.failed,
    refresh: mockRefresh,
  }),
}));

// 训练营的「上次」三样按账号存(N10)。盒上 token 恒为 null、身份在 user 上 —— 这里照盒上的样子造。
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ user: { id: 7, username: '甲', rank: '5段', credits: 0 }, isAuthenticated: true, token: null }),
}));

// 45 道题 → 3 个单元(20 / 20 / 5)。
const TOTAL = 45;
const allIds = Array.from({ length: TOTAL }, (_, i) => `q${i}`);

const installFetch = (ids: string[] = allIds) => {
  global.fetch = vi
    .fn()
    .mockResolvedValue({ ok: true, json: () => Promise.resolve(ids.map((id) => ({ id }))) }) as any;
};

/** 常路:屏 12 已经把顺序表写进 sessionStorage 了。 */
const seedSequence = (level = '15k', category = 'capturing', ids: string[] = allIds) =>
  sessionStorage.setItem(sequenceKey(level, category), JSON.stringify(ids));

beforeEach(() => {
  vi.clearAllMocks();
  for (const k of Object.keys(progressMap)) delete progressMap[k];
  progressFlags.failed = false;
  sessionStorage.clear();
  localStorage.clear();
  __resetKioskActivityStorageForTests();
  setKioskIdentity(TEST_UUID, false);
  installFetch();
});

import TsumegoUnitListPage from '../pages/TsumegoUnitListPage';

const renderPage = (level = '15k', category = 'capturing', unit = '1') =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[`/kiosk/tsumego/${level}/${category}/${unit}`]}>
        <Routes>
          <Route path="/kiosk/tsumego/:level/:category/:unit" element={<TsumegoUnitListPage />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );

/** 错题页。**两条路由都挂上**:顺带证明静态段 `wrong` 在 v6 的最佳匹配里赢过 `:unit`。
 *  树单独拿出来,是给「重读回来」那条用例 `rerender` 用的。 */
const wrongTree = (level = '15k', category = 'capturing') => (
  <ThemeProvider theme={kioskTheme}>
    <MemoryRouter initialEntries={[`/kiosk/tsumego/${level}/${category}/wrong`]}>
      <Routes>
        <Route path="/kiosk/tsumego/:level/:category/:unit" element={<TsumegoUnitListPage />} />
        <Route path="/kiosk/tsumego/:level/:category/wrong" element={<TsumegoUnitListPage set="wrong" />} />
      </Routes>
    </MemoryRouter>
  </ThemeProvider>
);
const renderWrong = (level = '15k', category = 'capturing') => render(wrongTree(level, category));

const cells = () => Array.from(document.querySelectorAll('.qgrid button')) as HTMLButtonElement[];
const cellText = () => cells().map((b) => [b.querySelector('b')?.textContent, b.querySelector('em')?.textContent]);
const statValues = () =>
  Array.from(document.querySelectorAll('.kiosk-stat')).map((s) => [
    s.querySelector('.kiosk-stat__v')?.textContent,
    s.querySelector('.kiosk-stat__k')?.textContent,
  ]);

describe('TsumegoUnitListPage · 屏 13 题目列表', () => {
  it('顺序表已经在了就直接用 —— 一次接口都不取', async () => {
    seedSequence();
    renderPage();
    await waitFor(() => expect(cells()).toHaveLength(UNIT_SIZE));
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('深链进来(没有顺序表)才自己取一次,并把整类题号按顺序回填', async () => {
    renderPage('15k', 'capturing', '2');
    await waitFor(() =>
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/v1/tsumego/levels/15k/categories/capturing?limit=1000',
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      ),
    );
    await waitFor(() => {
      const raw = sessionStorage.getItem(sequenceKey('15k', 'capturing'));
      expect(raw).not.toBeNull();
      expect(JSON.parse(raw!)).toEqual(allIds);
    });
    // 第 2 单元 = 全类第 21–40 题。
    expect(cellText()[0][0]).toBe('21');
    expect(cells()).toHaveLength(UNIT_SIZE);
  });

  it('最后一个单元只有剩下的那几题', async () => {
    seedSequence();
    renderPage('15k', 'capturing', '3');
    await waitFor(() => expect(cells()).toHaveLength(TOTAL % UNIT_SIZE));
    expect(screen.getByText('第 41-45 题 · 落子即判')).toBeInTheDocument();
    expect(screen.getByText('这 5 道题')).toBeInTheDocument();
  });

  it('页控条写「这一档 · 这一类 · 第几单元」,返回键回单元列表', async () => {
    seedSequence();
    renderPage('15k', 'capturing', '2');
    await waitFor(() => expect(screen.getByText(/15 级 · 吃子 · 第 2 单元/)).toBeInTheDocument());
    fireEvent.click(screen.getByText('单元'));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tsumego/15k/capturing');
  });

  it('点一格进那一道题', async () => {
    seedSequence();
    renderPage('15k', 'capturing', '2');
    await waitFor(() => expect(cells()).toHaveLength(UNIT_SIZE));
    fireEvent.click(cells()[2]);              // 第 2 单元第 3 格 = 全类第 23 题 = q22
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tsumego/problem/q22');
  });

  it('综合训练单元沿用同一题格，但做题路由保留 ?set=all 且不再显示换一批', async () => {
    seedSequence('15k', 'all');
    renderPage('15k', 'all', '2');
    await waitFor(() => expect(cells()).toHaveLength(UNIT_SIZE));
    expect(screen.getByText(/15 级 · 综合训练 · 第 2 单元/)).toBeInTheDocument();
    fireEvent.click(cells()[2]);
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tsumego/problem/q22?set=all');
    expect(screen.queryByText('换一批')).toBeNull();
  });

  it('综合训练深链缺少顺序表时，从整级接口恢复题序', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ items: allIds.map((id) => ({ id })), total: TOTAL, page: 1, page_size: 200 }),
    }) as any;
    renderPage('15k', 'all', '1');
    await waitFor(() => expect(cells()).toHaveLength(UNIT_SIZE));
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/tsumego/levels/15k/problems?page=1&page_size=200',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(JSON.parse(sessionStorage.getItem(sequenceKey('15k', 'all'))!)).toEqual(allIds);
  });

  /* ── 这一屏最容易讲错的一件事 ─────────────────────────────────────────
   * `attempts` 在 `useTsumegoProblem` 里**只在走错和重摆时 +1**,做对那一手不加。
   * 所以第一次就做对的题存下来是 `attempts: 0` —— 直接把它印成「0 次」既难看又不对,
   * 而印成「—」会把「做对了」说成「没做过」。判据:**试了几次 = 失败次数 + (做对了 ? 1 : 0)**。 */
  it('「N 次」= 失败次数 + 做对的那一次;没做过写「—」不写「0 次」', async () => {
    progressMap['q0'] = { completed: true, attempts: 0 };   // 一次就对 → 1 次
    progressMap['q1'] = { completed: true, attempts: 2 };   // 错两次才对 → 3 次
    progressMap['q2'] = { completed: false, attempts: 1 };  // 错一次,还没对 → 1 次
    seedSequence();
    renderPage();
    await waitFor(() => expect(cells()).toHaveLength(UNIT_SIZE));
    expect(cellText().slice(0, 4)).toEqual([
      ['1', '1 次'],
      ['2', '3 次'],
      // 第 3 格既是「下一道」又已经试过一次 ⇒ 小字写**试了几次**,不写「在这儿」:
      // 「在这儿」那句话边框已经在说了,而「错过一次」没有第二个地方说得出来。
      ['3', '1 次'],
      ['4', '—'],
    ]);
    // 一个「0 次」都不许出现。
    expect(cellText().some(([, em]) => em === '0 次')).toBe(false);
  });

  it('做对的格子是 ok,下一道要做的是 now,其余不带类', async () => {
    progressMap['q0'] = { completed: true, attempts: 0 };
    seedSequence();
    renderPage();
    await waitFor(() => expect(cells()).toHaveLength(UNIT_SIZE));
    expect(cells()[0].className).toBe('ok');
    expect(cells()[1].className).toBe('now');
    expect(cells()[1].getAttribute('aria-current')).toBe('step');
    // 一次没试过的「下一道」才写「在这儿」。
    expect(cells()[1].querySelector('em')?.textContent).toBe('在这儿');
    expect(cells()[2].className).toBe('');
    expect(document.querySelectorAll('.qgrid button.now')).toHaveLength(1);
  });

  it('整单元都做完了就一格 now 都不画 —— 不许随便指一格当「下一道」', async () => {
    for (let i = 0; i < UNIT_SIZE; i += 1) progressMap[`q${i}`] = { completed: true, attempts: 0 };
    seedSequence();
    renderPage();
    await waitFor(() => expect(cells()).toHaveLength(UNIT_SIZE));
    expect(document.querySelectorAll('.qgrid button.now')).toHaveLength(0);
    expect(document.querySelectorAll('.qgrid button.ok')).toHaveLength(UNIT_SIZE);
  });

  it('可及名把状态一起带上 —— 只报题号的话 20 格读起来一模一样', async () => {
    progressMap['q0'] = { completed: true, attempts: 2 };
    seedSequence();
    renderPage();
    await waitFor(() => expect(cells()).toHaveLength(UNIT_SIZE));
    expect(cells()[0].getAttribute('aria-label')).toBe('第 1 题，做对了，3 次');
    expect(cells()[1].getAttribute('aria-label')).toBe('第 2 题，下一道');
    expect(cells()[4].getAttribute('aria-label')).toBe('第 5 题，还没做过');
  });

  it('数据条三格:分母写在值里,平均值按同一个「试了几次」口径算', async () => {
    progressMap['q0'] = { completed: true, attempts: 0, lastDuration: 20 };   // 1 次 / 20 秒
    progressMap['q1'] = { completed: true, attempts: 2, lastDuration: 24 };   // 3 次 / 24 秒
    seedSequence();
    renderPage();
    await waitFor(() => expect(cells()).toHaveLength(UNIT_SIZE));
    expect(statValues()).toEqual([
      ['2 / 20', '本单元已做对'],
      ['2.0', '平均尝试次数'],
      ['22 秒', '平均用时'],
    ]);
  });

  it('一道都没试过时平均值写「—」,不写 0.0 秒 —— 那是在断言一件不知道的事', async () => {
    seedSequence();
    renderPage();
    await waitFor(() => expect(cells()).toHaveLength(UNIT_SIZE));
    expect(screen.getByTestId('stat-avg-tries').textContent).toBe('—');
    expect(screen.getByTestId('stat-avg-time').textContent).toBe('—');
  });

  it('平均用时过了一分钟就写「分 秒」', async () => {
    progressMap['q0'] = { completed: true, attempts: 0, lastDuration: 95 };
    seedSequence();
    renderPage();
    await waitFor(() => expect(cells()).toHaveLength(UNIT_SIZE));
    expect(screen.getByTestId('stat-avg-time').textContent).toBe('1 分 35 秒');
  });

  it('专项单元可以切到这一档的综合训练', async () => {
    seedSequence('3d', 'capturing');
    renderPage('3d', 'capturing', '1');
    await waitFor(() => expect(cells()).toHaveLength(UNIT_SIZE));
    expect(screen.getByText('混合当前难度全部题型，每 20 题一单元')).toBeInTheDocument();
    fireEvent.click(screen.getByText('综合训练').closest('.kiosk-row')!.querySelector('button')!);
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tsumego/3d/all');
  });

  it('「只做错过的」:数是整类的真数、点名了 scope,「开始」进这一类的错题页(T1)', async () => {
    progressMap['q0'] = { completed: false, attempts: 2 };   // 错过,还没对
    progressMap['q7'] = { completed: true, attempts: 3 };    // 做对了 ⇒ 不算
    progressMap['q9'] = { completed: false, attempts: 0 };   // 没试过 ⇒ 不算
    progressMap['q40'] = { completed: false, attempts: 1 };  // 第 3 单元的 —— 整类都算
    seedSequence();
    renderPage();
    await waitFor(() => expect(cells()).toHaveLength(UNIT_SIZE));
    const row = screen.getByTestId('row-wrong');
    expect(within(row).getByText(/把这一类做错的重来一遍 · 现在有 2 道/)).toBeInTheDocument();
    expect(within(row).queryByText('还没接')).toBeNull();
    fireEvent.click(within(row).getByRole('button', { name: '开始' }));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tsumego/15k/capturing/wrong');
  });

  it('一道错题都没有时错题那一行的「开始」灰着', async () => {
    seedSequence();
    renderPage();
    await waitFor(() => expect(cells()).toHaveLength(UNIT_SIZE));
    expect(within(screen.getByTestId('row-wrong')).getByRole('button', { name: '开始' })).toBeDisabled();
  });

  it('做题记录没读到时错题那一行不说「现在有 0 道」,「开始」也不灰 —— 错题页那边有重试', async () => {
    progressFlags.failed = true;
    seedSequence();
    renderPage();
    await waitFor(() => expect(cells()).toHaveLength(UNIT_SIZE));
    const row = screen.getByTestId('row-wrong');
    expect(within(row).getByText(/做题记录没读到/)).toBeInTheDocument();
    expect(within(row).queryByText(/现在有 0 道/)).toBeNull();
    expect(within(row).getByRole('button', { name: '开始' })).not.toBeDisabled();
  });

  it('加载中说的是加载中,不是「这一类没有题」', () => {
    renderPage();
    expect(screen.getByTestId('problems-loading')).toBeInTheDocument();
    expect(screen.queryByTestId('problems-empty')).toBeNull();
    expect(document.querySelector('.qgrid')).toBeNull();
  });

  it('读不到时写出原因,并且给得起一次重试', async () => {
    (global.fetch as any).mockResolvedValueOnce({ ok: false, status: 404, json: () => Promise.resolve({}) });
    renderPage();
    await waitFor(() => expect(screen.getByTestId('problems-error')).toBeInTheDocument());
    expect(within(screen.getByTestId('problems-error')).getByText(/HTTP 404/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    await waitFor(() => expect(cells()).toHaveLength(UNIT_SIZE));
  });

  it('这一类真的一道题都没有时,说的是「还没有题」', async () => {
    installFetch([]);
    renderPage();
    await waitFor(() => expect(screen.getByTestId('problems-empty')).toBeInTheDocument());
    expect(screen.queryByTestId('problems-error')).toBeNull();
    expect(screen.queryByText(/随云端同步/)).toBeNull();
  });

  it('连不上云端(503)时说「连不上云端题库」,不把状态码甩给人看', async () => {
    (global.fetch as any).mockResolvedValueOnce({ ok: false, status: 503, json: () => Promise.resolve({}) });
    renderPage();
    const box = await screen.findByTestId('problems-error');
    expect(within(box).getByText('连不上云端题库')).toBeInTheDocument();
    expect(within(box).queryByText(/HTTP 503/)).toBeNull();
    expect(within(box).getByRole('button', { name: '重试' })).toBeInTheDocument();
  });

  it('单元号越界时说清楚一共有几个单元,并给一条回去的路', async () => {
    seedSequence();
    renderPage('15k', 'capturing', '9');
    await waitFor(() => expect(screen.getByTestId('problems-out-of-range')).toBeInTheDocument());
    expect(screen.getByText('这一类一共 45 道题，只有 3 个单元。')).toBeInTheDocument();
    // 越界时页控条不许写「第 161-180 题」—— 那是一件不知道的事。
    expect(screen.queryByText(/第 \d+-\d+ 题/)).toBeNull();
    // 页控条的返回键也写着「单元」—— 要点的是空态里那一个。
    fireEvent.click(within(screen.getByTestId('problems-out-of-range')).getByRole('button', { name: '单元' }));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tsumego/15k/capturing');
  });

  it('深链进来也记下这一类 —— 训练营那一排的高亮靠它', async () => {
    seedSequence('15k', 'semeai');
    renderPage('15k', 'semeai', '1');
    await waitFor(() => expect(localStorage.getItem(`kiosk_tsumego_last_category:${TEST_UUID}`)).toBe('semeai'));
  });

  describe('错题页(T1)', () => {
    beforeEach(() => {
      progressMap['q3'] = { completed: false, attempts: 1 };
      progressMap['q7'] = { completed: true, attempts: 3 };    // 做对了 ⇒ 不在错题里
      progressMap['q9'] = { completed: false, attempts: 0 };   // 没试过 ⇒ 不在
      progressMap['q41'] = { completed: false, attempts: 2 };  // 第 3 单元的 —— 整类都算
      seedSequence();
    });

    it('页控条写「这一档 · 这一类 · 错题」;格子只有试过没做对的,格上是整类真题号', async () => {
      renderWrong();
      await waitFor(() => expect(cells()).toHaveLength(2));
      expect(screen.getByText(/15 级 · 吃子 · 错题/)).toBeInTheDocument();
      expect(cellText()).toEqual([['4', '1 次'], ['42', '2 次']]);
      expect(cells()[0].getAttribute('aria-label')).toBe('第 4 题，做错过，1 次');
      // 每一道都没做对,不许随便指一格当「下一道」。
      expect(document.querySelector('.qgrid button.now')).toBeNull();
    });

    it('数据条三格:现在有几道 / 平均尝试次数 / 这一类已做对', async () => {
      renderWrong();
      await waitFor(() => expect(cells()).toHaveLength(2));
      expect(screen.getByTestId('stat-wrong-count').textContent).toBe('2 道');
      expect(screen.getByTestId('stat-avg-tries').textContent).toBe('1.5');
      expect(screen.getByTestId('stat-solved-in-category').textContent).toBe('1 / 45');
    });

    it('点一格:先把这份题单存成**这个账号的**快照,再带着 ?set=wrong 进做题屏', async () => {
      renderWrong();
      await waitFor(() => expect(cells()).toHaveLength(2));
      fireEvent.click(cells()[1]);
      expect(JSON.parse(localStorage.getItem(`kiosk_problems_15k_capturing_wrong:${TEST_UUID}`)!)).toEqual(['q3', 'q41']);
      expect(localStorage.getItem('kiosk_problems_15k_capturing_wrong')).toBeNull();
      expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tsumego/problem/q41?set=wrong');
    });

    it('换一批只剩「整级」—— 错题那一行指向自己,不画', async () => {
      renderWrong();
      await waitFor(() => expect(cells()).toHaveLength(2));
      expect(screen.queryByTestId('row-wrong')).toBeNull();
      expect(screen.getByText('综合训练')).toBeInTheDocument();
    });

    it('这一类一道错题都没有时说清楚,并给回单元的路', async () => {
      for (const k of Object.keys(progressMap)) delete progressMap[k];
      renderWrong();
      await waitFor(() => expect(screen.getByTestId('problems-no-wrong')).toBeInTheDocument());
      fireEvent.click(within(screen.getByTestId('problems-no-wrong')).getByRole('button', { name: '单元' }));
      expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tsumego/15k/capturing');
    });

    it('题号读到了、做题记录没读到:不说「没有做错过的题」,给重试;重读回来就出格子', async () => {
      for (const k of Object.keys(progressMap)) delete progressMap[k];
      progressFlags.failed = true;
      const view = renderWrong();
      const box = await screen.findByTestId('problems-wrong-unknown');
      expect(within(box).getByText('做题记录没读到')).toBeInTheDocument();
      expect(screen.queryByTestId('problems-no-wrong')).toBeNull();
      fireEvent.click(within(box).getByRole('button', { name: '重试' }));
      expect(mockRefresh).toHaveBeenCalledTimes(1);

      // 重读回来了:Provider 合并进度、清掉失败标志、重渲(Provider 那一半在 TsumegoProgressContext.test.tsx 里守)。
      progressMap['q3'] = { completed: false, attempts: 1 };
      progressFlags.failed = false;
      view.rerender(wrongTree());
      await waitFor(() => expect(cells()).toHaveLength(1));
      expect(screen.queryByTestId('problems-wrong-unknown')).toBeNull();
    });
  });
});
