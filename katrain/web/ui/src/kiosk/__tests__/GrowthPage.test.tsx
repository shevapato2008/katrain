import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { GrowthDiagnosis, GrowthSummary } from '../api/growthApi';
import type { AiLadderStatus } from '../../features/aiLadder/types';

/**
 * 屏 22 成长。这里守的全是**口径**,不是数字长什么样:
 *
 *  · 未定级时写「未定级」,**绝不写 20 级** —— 那是出厂值,当成实力显示出来就是在编。
 *  · 数没取到时写 `—` 并说一句,**绝不退回 0** —— 「一局没下」和「没读到」是两句话。
 *  · 胜率分母为 0 时写 `—`,不是 `0%`。
 *  · 盒子上这几个数出自本机缓存 ⇒ 屏上必须说「本机记录」。
 *  · 「按对手强度」只列打过的档 —— 后端 GROUP BY 的结果,前端不补零。
 *
 * 布局那一半(两块诊断会不会顶破右栏、档位列表能不能滚)在
 * `tests/kiosk-screen-22-growth.spec.ts` 里用真浏览器量 —— jsdom 对布局无权作证。
 */

const { mocks } = vi.hoisted(() => ({
  mocks: {
    ladder: { view_state: 'loading' } as AiLadderStatus,
    summary: null as GrowthSummary | null,
    summaryError: null as Error | null,
    diagnosis: null as GrowthDiagnosis | null,
    diagnosisError: null as Error | null,
    progress: {} as Record<string, { completed: boolean }>,
    progressFailed: false,
  },
}));

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ token: 'tok', isAuthenticated: true, user: { id: 1, username: 't' } }),
}));
vi.mock('../../context/TsumegoProgressContext', () => ({
  useTsumegoProgress: () => ({ progress: mocks.progress, serverLoadFailed: mocks.progressFailed }),
}));
vi.mock('../../features/aiLadder/useAiLadderStatus', () => ({
  useAiLadderStatus: () => ({ status: mocks.ladder }),
}));
vi.mock('../api/growthApi', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api/growthApi')>()),
  getGrowthSummary: () => (mocks.summaryError ? Promise.reject(mocks.summaryError) : Promise.resolve(mocks.summary)),
  getGrowthDiagnosis: () => (mocks.diagnosisError
    ? Promise.reject(mocks.diagnosisError) : Promise.resolve(mocks.diagnosis)),
}));

import GrowthPage from '../pages/GrowthPage';

const READY = (over: Partial<Extract<AiLadderStatus, { view_state: 'ready' }>> = {}): AiLadderStatus => ({
  view_state: 'ready',
  placement_state: { phase: 'placement', completed_games: 2, total_games: 5 },
  current_opponent: null,
  recent_ranked_results: [],
  net_score: 0,
  pending_settlement: false,
  ...over,
});

const SUMMARY = (over: Partial<GrowthSummary> = {}): GrowthSummary => ({
  window_days: 30,
  games_in_window: 12,
  ranked_total: 7,
  ranked_wins_in_window: 3,
  ranked_losses_in_window: 1,
  by_opponent_rung: [],
  authority: 'this_node',
  ...over,
});

const DIAGNOSIS = (over: Partial<GrowthDiagnosis> = {}): GrowthDiagnosis => ({
  window_days: 90,
  reports: 6,
  skipped_without_color: 0,
  graded_moves: 420,
  phases: [
    { phase: 'opening', graded: 150, bad: 15 },
    { phase: 'midgame', graded: 200, bad: 60 },
    { phase: 'endgame', graded: 70, bad: 7 },
  ],
  authority: 'this_node',
  ...over,
});

/** 「去复盘」要真的落到复盘那条路由上 —— 所以这一屏挂在路由里渲染,复盘那一屏用个桩。 */
const renderGrowth = () => render(
  <MemoryRouter initialEntries={['/kiosk/growth']}>
    <Routes>
      <Route path="/kiosk/growth" element={<GrowthPage />} />
      <Route path="/kiosk/report" element={<div data-testid="report-page-stub" />} />
    </Routes>
  </MemoryRouter>,
);

const statValues = () =>
  Array.from(document.querySelectorAll('[data-testid="growth-stats"] .kiosk-stat__v'))
    .map((n) => n.textContent);

beforeEach(() => {
  mocks.ladder = READY();
  mocks.summary = SUMMARY();
  mocks.summaryError = null;
  mocks.diagnosis = DIAGNOSIS();
  mocks.diagnosisError = null;
  mocks.progress = {};
  mocks.progressFailed = false;
});

describe('屏 22 成长', () => {
  it('未定级时写「未定级」——**不写 20 级**(那是出厂值,不是实力)', async () => {
    renderGrowth();
    expect(screen.getByTestId('growth-rank-value')).toHaveTextContent('未定级');
    // ⚠️ 断言落在**那个大字**上,不落在整个左栏上:左栏里还有一条规矩写着
    // 「下封 20 级」,拿整栏去断言 `not.toHaveTextContent('20 级')` 是**量错了对象**
    //(第一版就是这么写的,当场红)。
    expect(screen.getByTestId('growth-rank-value')).not.toHaveTextContent('20 级');
    expect(screen.getByTestId('growth-rank')).toHaveTextContent('2 / 5');
  });

  it('定级完成后写真档名', async () => {
    mocks.ladder = READY({
      placement_state: {
        phase: 'placed',
        rung: { rung: 18, rank_name: '3级', certification_status: 'certified', availability: 'available', route: 'local' },
      },
    });
    renderGrowth();
    expect(screen.getByTestId('growth-rank-value')).toHaveTextContent('3级');
  });

  // 稿子写的是「下封 20 级 · 上封 **12 段**」,而 `katrain/core/ladder.py` 的 41 档里
  // 根本没有「12 段」这个词。屏上写实际的上下界。
  it('升降规矩写的是真的上下界,不是稿子那个不存在的「12 段」', () => {
    renderGrowth();
    const rank = screen.getByTestId('growth-rank');
    expect(rank).toHaveTextContent('净胜 3 盘升一档');
    expect(rank).toHaveTextContent('下封 20 级');
    expect(rank).toHaveTextContent('超越人类');
    expect(rank).not.toHaveTextContent('12 段');
  });

  // 大字底下那条进度**两态都要有**:稿子只画了未定级那一态,定级之后它那儿是空的 ——
  // 而空的那块正是四图上左栏那道缝。定级后填「净胜分 n/3」,规矩就写在这一屏自己身上。
  it('未定级时那条进度写「定级局 2 / 5」', () => {
    renderGrowth();
    expect(screen.getByTestId('growth-metric')).toHaveTextContent('定级局');
    expect(screen.getByTestId('growth-metric')).toHaveTextContent('2 / 5');
  });

  it('定级之后换成「净胜分」,**正负号要写出来**', () => {
    mocks.ladder = READY({
      placement_state: {
        phase: 'placed',
        rung: { rung: 18, rank_name: '3级', certification_status: 'certified', availability: 'available', route: 'local' },
      },
      net_score: -2,
    });
    renderGrowth();
    const m = screen.getByTestId('growth-metric');
    expect(m).toHaveTextContent('净胜分');
    // `-2` 和 `2` 是两件事(一个朝降级、一个朝升级)。只写 `2` 就把方向丢了。
    expect(m).toHaveTextContent('-2 / 3');
  });

  it('已解题从做题进度里数,不从后端那几个数里拿', () => {
    mocks.progress = { a: { completed: true }, b: { completed: false }, c: { completed: true } };
    renderGrowth();
    expect(statValues()).toContain('2');
  });

  it('四个数按口径显示,胜率那格标签写明「升降级」', async () => {
    renderGrowth();
    await waitFor(() => expect(statValues()[0]).toBe('12'));
    // 3 胜 1 负 = 75%
    expect(statValues()[1]).toBe('75%');
    expect(statValues()[3]).toBe('7');
    // **标签承重**:只有升降级局的胜负是从这个用户视角记下来的,写成光秃秃的「胜率」就是在扩大口径。
    expect(screen.getByTestId('growth-stats')).toHaveTextContent('升降级胜率 · 近 30 天');
  });

  // 2026-09 起 `user_games` 记下了「用户坐哪一方」⇒ 云端给得出全部算得出执色的局。
  it('有算得出胜负的局时,那一格是百分比、标签是「胜率 · 近 30 天」', async () => {
    mocks.summary = SUMMARY({ games_in_window: 10, decided_games_in_window: 8, wins_in_window: 6, losses_in_window: 2 });
    renderGrowth();
    await waitFor(() => expect(statValues()[0]).toBe('10'));
    expect(statValues()[1]).toBe('75%');
    expect(screen.getByTestId('growth-stats')).toHaveTextContent('胜率 · 近 30 天');
    expect(screen.getByTestId('growth-stats')).not.toHaveTextContent('升降级胜率');
  });

  it('一局都算不出执色时写 —,并说清有几局没算进去', async () => {
    mocks.summary = SUMMARY({ games_in_window: 5, decided_games_in_window: 0, wins_in_window: 0, losses_in_window: 0 });
    renderGrowth();
    await waitFor(() => expect(statValues()[0]).toBe('5'));
    expect(statValues()[1]).toBe('—');
    expect(screen.getByTestId('growth-unknown-seat')).toHaveTextContent('5');
  });

  it('每一局都算得出执色时不说那句话 —— 没话说就不占地方', async () => {
    mocks.summary = SUMMARY({ games_in_window: 3, decided_games_in_window: 3, wins_in_window: 2, losses_in_window: 1 });
    renderGrowth();
    await waitFor(() => expect(statValues()[0]).toBe('3'));
    expect(screen.queryByTestId('growth-unknown-seat')).toBeNull();
  });

  // 云端还没部署这一版时,老响应里没有那三个键:数退回升降级口径,**标签也跟着退**,
  // 也不说「没算进去」那句 —— 老口径下那个差额不是「没记执色」,是「不是升降级局」。
  it('老云端没给新字段时,标签退回「升降级胜率」,也不说没算进去那句', async () => {
    renderGrowth();
    await waitFor(() => expect(statValues()[0]).toBe('12'));
    expect(screen.getByTestId('growth-stats')).toHaveTextContent('升降级胜率 · 近 30 天');
    expect(screen.queryByTestId('growth-unknown-seat')).toBeNull();
  });

  it('一局升降级都没下时胜率是「—」,不是 0%', async () => {
    mocks.summary = SUMMARY({ ranked_wins_in_window: 0, ranked_losses_in_window: 0 });
    renderGrowth();
    await waitFor(() => expect(statValues()[0]).toBe('12'));
    expect(statValues()[1]).toBe('—');
    expect(statValues()[1]).not.toBe('0%');
  });

  /**
   * 四个格里这一格最容易漏:另外三格的数来自 `summary`,取不到时是 `undefined`
   * ⇒ `num()` 自己会写 `—`;而「已解题」是**本地 `.length` 算出来的,永远是个数字**,
   * 读失败也照样是 0 ——「一题没做过」和「没读到」在屏上成了同一句话。
   */
  it('做题进度没读到、本机也是空的:已解题写「—」不写 0', async () => {
    mocks.progressFailed = true;
    renderGrowth();
    await waitFor(() => expect(statValues()[0]).toBe('12'));
    expect(statValues()[2]).toBe('—');
    expect(statValues()[2]).not.toBe('0');
  });

  it('读失败但本机有数:照常显示 —— 那至少是个真实下界,不是猜的', async () => {
    mocks.progressFailed = true;
    mocks.progress = { a: { completed: true }, b: { completed: true }, c: { completed: false } };
    renderGrowth();
    await waitFor(() => expect(statValues()[0]).toBe('12'));
    expect(statValues()[2]).toBe('2');
  });

  it('数没取到时写「—」并说一句,**不退回 0**', async () => {
    mocks.summaryError = new Error('boom');
    renderGrowth();
    await waitFor(() => expect(screen.getByTestId('growth-summary-error')).toBeInTheDocument());
    // 「近 30 天对局」和「升降级局累计」两格都没有来源了 ⇒ 都是 `—`,不是 `0`。
    expect(statValues()[0]).toBe('—');
    expect(statValues()[3]).toBe('—');
    // 已解题那格来源不同(做题进度),不受影响 —— 0 在这儿是真的 0。
    expect(statValues()[2]).toBe('0');
  });

  it('盒子上这几个数出自本机缓存时,屏上说「本机记录」', async () => {
    mocks.summary = SUMMARY({ authority: 'local_cache' });
    renderGrowth();
    await waitFor(() => expect(screen.getByTestId('growth-local-note')).toBeInTheDocument());
    expect(screen.getByTestId('growth-local-note')).toHaveTextContent('本机记录');
  });

  it('权威在本机时不说那句话 —— 没话说就不占地方', async () => {
    renderGrowth();
    await waitFor(() => expect(statValues()[0]).toBe('12'));
    expect(screen.queryByTestId('growth-local-note')).toBeNull();
  });

  /**
   * 2026-08-26 补的第三档。在此之前盒子上**从来不问云端**,永远数本机、永远标
   * `local_cache` ⇒ 同一台盒子上复盘屏那张列表来自云端、成长屏这几个数来自本机,
   * **两屏对不上,而两边都没说自己从哪儿数的**。
   * 现在拿到云端那份时这几个数是跨设备完整的 ⇒ 那句「本机记录」不该再出现,
   * 它出现就是在给一份完整账本挂免责声明。
   */
  it('数来自云端时不说「本机记录」—— 那一份是全的', async () => {
    mocks.summary = SUMMARY({ authority: 'cloud' });
    renderGrowth();
    await waitFor(() => expect(statValues()[0]).toBe('12'));
    expect(screen.queryByTestId('growth-local-note')).toBeNull();
  });

  it('「按对手强度」只列打过的档,不补一排 0 胜 0 负', async () => {
    mocks.summary = SUMMARY({
      by_opponent_rung: [
        { rung: 21, rank_name: '准1段', wins: 1, losses: 0 },
        { rung: 18, rank_name: '3级', wins: 2, losses: 3 },
      ],
    });
    renderGrowth();
    const box = screen.getByTestId('growth-by-rung');
    await waitFor(() => expect(box.querySelectorAll('.grung')).toHaveLength(2));
    expect(box).toHaveTextContent('准1段');
    expect(box).toHaveTextContent('2 胜 · 3 负');
    expect(box).not.toHaveTextContent('还没有战绩');
  });

  it('一档都没打过时说「还没有战绩」', async () => {
    renderGrowth();
    await waitFor(() => expect(statValues()[0]).toBe('12'));
    expect(screen.getByTestId('growth-by-rung')).toHaveTextContent('还没有战绩');
  });

  // ── 能力诊断(G1)──────────────────────────────────────────────────────
  // 口径:最近 N 份已完成报告里**你执的那一方**的手,按布局 / 中盘 / 官子三段数问题手
  //(报告七档里的小亏 · 失误 · 恶手)。段名与复盘屏同一套词(`grade:phase_*`)。

  it('三段各一行,最弱那段有标记,样本量写出来', async () => {
    renderGrowth();
    const rows = await screen.findAllByTestId('diag-row');
    expect(rows).toHaveLength(3);
    expect(rows.map((r) => r.getAttribute('data-phase'))).toEqual(['opening', 'midgame', 'endgame']);
    // 中盘 60/200 = 30%,另两段 10% —— 分得开,标出来。
    expect(screen.getByTestId('diag-weakest')).toHaveTextContent('中盘');
    expect(screen.getByTestId('diag-weakest')).toHaveTextContent('60 / 200');
    expect(screen.getByTestId('diag-sample')).toHaveTextContent('6');
    expect(screen.getByTestId('diag-sample')).toHaveTextContent('420');
    expect(screen.queryByTestId('diag-thin')).toBeNull();
  });

  // 两段只差一个百分点就说「你中盘最弱」,是拿噪声给人下结论。
  it('段与段分不开时不标最弱', async () => {
    mocks.diagnosis = DIAGNOSIS({ phases: [
      { phase: 'opening', graded: 200, bad: 20 },
      { phase: 'midgame', graded: 200, bad: 22 },
      { phase: 'endgame', graded: 100, bad: 10 },
    ] });
    renderGrowth();
    await screen.findAllByTestId('diag-row');
    expect(screen.queryByTestId('diag-weakest')).toBeNull();
  });

  it('样本不够时照显示,但多一句「结论会抖」', async () => {
    mocks.diagnosis = DIAGNOSIS({ reports: 1, graded_moves: 40, phases: [{ phase: 'opening', graded: 40, bad: 4 }] });
    renderGrowth();
    expect(await screen.findByTestId('diag-thin')).toBeInTheDocument();
    expect(screen.getAllByTestId('diag-row')).toHaveLength(1);
  });

  it('一份报告都没有时说「还没有复盘报告」并给出口,不说「样本 0 局」', async () => {
    mocks.diagnosis = DIAGNOSIS({ reports: 0, graded_moves: 0, phases: [] });
    renderGrowth();
    expect(await screen.findByTestId('diag-empty')).toHaveTextContent('还没有复盘报告');
    expect(screen.queryByText(/样本 0 局/)).toBeNull();
    await userEvent.click(screen.getByTestId('diag-go-report'));
    expect(screen.getByTestId('report-page-stub')).toBeInTheDocument();
  });

  // 报告是有的,只是那几局下的时候还没记执色 —— 这时说「还没有复盘报告」就是在撒谎。
  it('有报告但全都记不出执色时,说的是这件事,不是「还没有报告」', async () => {
    mocks.diagnosis = DIAGNOSIS({ reports: 0, skipped_without_color: 4, graded_moves: 0, phases: [] });
    renderGrowth();
    const empty = await screen.findByTestId('diag-empty');
    expect(empty).not.toHaveTextContent('还没有复盘报告');
    expect(empty).toHaveTextContent('4');
    expect(screen.getByTestId('diag-go-report')).toBeInTheDocument();
  });

  // 盒子上报告在云端,本机库里没有逐手数据 ⇒ 退回本机缓存时「0 份报告」说的是「这会儿没连上云端」,
  // 不是「你还没有报告」。说成后者就是在替用户断言一件我们不知道的事。
  it('盒上退回本机缓存且一份都没有时,不说「还没有复盘报告」', async () => {
    mocks.diagnosis = DIAGNOSIS({ reports: 0, graded_moves: 0, phases: [], authority: 'local_cache' });
    renderGrowth();
    const empty = await screen.findByTestId('diag-offline');
    expect(empty).toHaveTextContent('云端');
    expect(screen.queryByText('还没有复盘报告')).toBeNull();
  });

  it('盒上退回本机缓存但有数时,照显示并说明是本机记录', async () => {
    mocks.diagnosis = DIAGNOSIS({ authority: 'local_cache' });
    renderGrowth();
    expect(await screen.findByTestId('diag-sample')).toHaveTextContent('本机记录');
  });

  it('诊断请求失败时说「诊断没读到」,不退回空态', async () => {
    mocks.diagnosisError = new Error('boom');
    renderGrowth();
    expect(await screen.findByTestId('diag-error')).toBeInTheDocument();
    expect(screen.queryByTestId('diag-empty')).toBeNull();
    expect(screen.queryByText(/样本 0 局/)).toBeNull();
  });

  it('「后端已有 · 界面未接」那个蓝标去掉了 —— 接上了就不是「未接」', async () => {
    renderGrowth();
    await screen.findAllByTestId('diag-row');
    expect(screen.getByTestId('growth-diagnosis')).not.toHaveTextContent('界面未接');
  });

  // ── 近 30 天档位走势(G3,Fan 2026-09-21 裁定画档位)──────────────────────
  it('有走势数据时左栏画出折线,并标出最高档', async () => {
    mocks.summary = SUMMARY({ rung_trend: [
      { date: '2026-09-01', rung: 10, rank_name: '3级' },
      { date: '2026-09-05', rung: 12, rank_name: '1级' },
      { date: '2026-09-08', rung: 11, rank_name: '2级' },
    ] });
    renderGrowth();
    expect(await screen.findByTestId('growth-trend')).toBeInTheDocument();
    expect(screen.getByTestId('growth-trend-peak')).toHaveTextContent('1级');
  });

  it('老云端没给 rung_trend 时,左栏不出现走势块(也不出现空轴)', async () => {
    renderGrowth();
    await waitFor(() => expect(statValues()[0]).toBe('12'));
    expect(screen.queryByTestId('growth-trend-block')).toBeNull();
  });

  // 一个点画出来是一条没有斜率的线,会被读成「持平」—— 说一句话,不画。
  it('走势不到两个点时说一句话,不画线', async () => {
    mocks.summary = SUMMARY({ rung_trend: [{ date: '2026-09-01', rung: 10, rank_name: '3级' }] });
    renderGrowth();
    expect(await screen.findByTestId('growth-trend-empty')).toBeInTheDocument();
    expect(screen.queryByTestId('growth-trend')).toBeNull();
  });
});
