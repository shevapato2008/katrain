import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import TrendChart from './TrendChart';
import type { MoveAnalysis } from '../../types/live';

vi.mock('../../hooks/useTranslation', () => ({
  useTranslation: () => ({ t: (_k: string, fallback: string) => fallback }),
}));

/**
 * `TrendChart` 在 2026-09-01 之前**一条单测都没有** —— 五个分析 tab 全靠 e2e 截图守着。
 * 这次五个 tab 一起重做（去掉计数、换分段控件、换黑白编码、去掉列表、加分布图），
 * 全量单测 1682 条一条没红，正是因为没人守。
 *
 * 这里守的是 jsdom **有权作证**的那些：控件在不在、文案对不对、点击换不换视图。
 * 图形几何（缩放比、柱高、连续段框在哪）jsdom 无权作证，判据在
 * `tests/galaxy-report-tabs-visual.spec.ts` 的真浏览器量测里。
 */
const CAND = ['A1', 'B2', 'C3', 'D4', 'E5', 'F6', 'G7', 'H8', 'J9', 'K10'];
const topMoves = () =>
  CAND.map((m) => ({ move: m, visits: 10, winrate: 0.5, score_lead: 0, prior: 0.1, pv: [] }));

function game(n = 40): Record<number, MoveAnalysis> {
  const out: Record<number, MoveAnalysis> = {};
  for (let i = 0; i <= n; i += 1) {
    const player = i % 2 === 1 ? 'B' : 'W';
    // 让每一档都出现，这样七档柱、妙手、失误三个 tab 都有内容可画。
    const grade =
      i % 11 === 3 ? 'blunder' : i % 7 === 2 ? 'mistake' : i % 5 === 1 ? 'inaccuracy'
        : i % 13 === 4 ? 'brilliant' : i % 3 === 0 ? 'best' : 'very_good';
    out[i] = {
      match_id: 'g', move_number: i, move: CAND[i % CAND.length], player,
      winrate: 0.5, score_lead: 0, top_moves: topMoves(), ownership: null,
      is_brilliant: false, is_mistake: false, is_questionable: false,
      delta_score: 0, delta_winrate: 0,
      grade, points_lost: grade === 'blunder' ? 7.7 : 2.0,
      is_top_move: i % 3 === 0, top_prior: 0.05,
      brilliance: grade === 'brilliant' ? 2 : null,
    } as MoveAnalysis;
  }
  return out;
}

const renderChart = (props: Partial<React.ComponentProps<typeof TrendChart>> = {}) =>
  render(<TrendChart analysis={game()} totalMoves={40} currentMove={20} {...props} />);

const tabs = () => screen.getAllByRole('tab');

describe('TrendChart 的五个分析 tab', () => {
  /* tab 标签**不带括号计数**（Fan 2026-09-01）：计数随筛选变 ⇒ 标签宽度变 ⇒ 整条 tab 抖动。
     变异验证：把 `<Tab label={t('live:brilliant','Brilliant')} />` 改回
     ``label={`${...} (${countLabel(brilliants)})`}``，本条红。 */
  it('五个 tab 按顺序排列，标签里没有计数', () => {
    renderChart();
    expect(tabs().map((el) => el.textContent)).toEqual([
      'Trend', 'Brilliant', 'Mistakes', '发挥水准', 'AI吻合度',
    ]);
    for (const el of tabs()) expect(el.textContent).not.toMatch(/[()（）]/);
  });

  /* 走势 tab **没有**阶段筛选：那张图画的是整局曲线，截一段等于把上下文砍掉。
     其余四个 tab 必须有。 */
  it('走势没有筛选条，其余四个 tab 有', async () => {
    const user = userEvent.setup();
    renderChart();
    expect(screen.queryByRole('radiogroup', { name: '阶段' })).not.toBeInTheDocument();
    for (const i of [1, 2, 3, 4]) {
      await user.click(tabs()[i]);
      expect(screen.getByRole('radiogroup', { name: '阶段' })).toBeInTheDocument();
    }
  });

  /* 阶段与棋手是**两组互不相干**的筛选，做成两条分段控件而不是七个并排的胶囊 ——
     胶囊排一行看不出「这是两组」也看不出「一组里只能选一个」。
     发挥水准与 AI吻合度只筛阶段（两张图本来就同时画黑白）。 */
  it('妙手/失误有阶段+棋手两条；发挥水准只有阶段', async () => {
    const user = userEvent.setup();
    renderChart();
    await user.click(tabs()[1]);
    expect(screen.getByRole('radiogroup', { name: '棋手' })).toBeInTheDocument();
    await user.click(tabs()[3]);
    expect(screen.queryByRole('radiogroup', { name: '棋手' })).not.toBeInTheDocument();
  });

  it('分段控件是单选：选中的那一格 aria-checked 为真，且只有一格', async () => {
    const user = userEvent.setup();
    renderChart();
    await user.click(tabs()[1]);
    const group = screen.getByRole('radiogroup', { name: '阶段' });
    const radios = within(group).getAllByRole('radio');
    expect(radios.filter((r) => r.getAttribute('aria-checked') === 'true')).toHaveLength(1);
    await user.click(radios[2]);
    expect(radios[2]).toHaveAttribute('aria-checked', 'true');
    expect(radios[0]).toHaveAttribute('aria-checked', 'false');
  });

  /* 妙手/失误**不再用列表罗列**（Fan：「尽量用上面的图表展示所有信息」）。
     但数量不能跟着消失 —— 每方最多画 5 条，不说清楚用户会以为整局就这些问题。 */
  it('妙手/失误只出图不出列表，数量在图下说明里报', async () => {
    const user = userEvent.setup();
    renderChart();
    await user.click(tabs()[2]);
    expect(document.querySelector('[data-testid="trend-lollipop-chart"]')).toBeInTheDocument();
    expect(screen.getByText(/本阶段共 \d+ 处/)).toBeInTheDocument();
  });

  it('发挥水准画的是纵向柱图，并常驻七档的量化定义', async () => {
    const user = userEvent.setup();
    renderChart();
    await user.click(tabs()[3]);
    expect(document.querySelector('[data-testid="trend-histogram-chart"]')).toBeInTheDocument();
    // 阈值必须来自生成产物 GRADE_LADDER_POINTS，不在文案里写死。
    expect(screen.getByText('目损 < 0.5 目')).toBeInTheDocument();
    expect(screen.getByText('目损 ≥ 6 目')).toBeInTheDocument();
  });

  /* AI吻合度的两个视图。分布图是 Fan 点名要的：看出连续吻合段。 */
  it('AI吻合度可在统计与分布之间切换', async () => {
    const user = userEvent.setup();
    renderChart();
    await user.click(tabs()[4]);
    const view = screen.getByRole('radiogroup', { name: '视图' });
    expect(document.querySelector('[data-testid="trend-match-timeline"]')).not.toBeInTheDocument();
    await user.click(within(view).getByRole('radio', { name: '分布' }));
    expect(document.querySelector('[data-testid="trend-match-timeline"]')).toBeInTheDocument();
  });

  /* 这句话是**硬性**的：分布图会让连续吻合段一眼可见，但一致率高低本来就取决于
     局面难度。界面上不能暗示我们有判作弊的证据 —— 我们一份都没有。 */
  it('两个视图都必须带着「不能当作作弊证据」那句话', async () => {
    const user = userEvent.setup();
    renderChart();
    await user.click(tabs()[4]);
    const caveat = /不能单独当作棋力或作弊的证据/;
    expect(screen.getByText(caveat)).toBeInTheDocument();
    await user.click(within(screen.getByRole('radiogroup', { name: '视图' })).getByRole('radio', { name: '分布' }));
    expect(screen.getByText(caveat)).toBeInTheDocument();
  });
});
