import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import { describe, expect, it } from 'vitest';

import AiLadderStatusCard from '../../features/aiLadder/AiLadderStatusCard';
import { AI_LADDER_COPY, formatOutcomeLabel } from '../../features/aiLadder/copy';
import type { AiLadderReadyStatus, AiLadderStatus } from '../../features/aiLadder/types';
import { zenTheme } from '../../theme';
import KioskAiLadderRows from '../components/settings/KioskAiLadderRows';

/**
 * 设置屏的 AI 段位现在有**两份视图**:galaxy 那张 MUI 卡(`AiLadderStatusCard`,以前在这屏
 * 是点开之后的对话框)和 kiosk 这份外壳行(`KioskAiLadderRows`,摘要一行 + 就地展开)。
 *
 * 两份并行实现的风险只有一个:**它们会说不同的话。** 这不是假设 —— 改之前,这屏的摘要行
 * 自己写了一套词(「认证中」「本地对弈」),而共享卡说的是「暂定」「本机对弈」。
 *
 * ⇒ 逐状态断言:**展开之后,该说的那几句两边要么都说、要么都不说。**
 * 判据落在 `AI_LADDER_COPY` 的具体串上,不落在「渲染了几个元素」上。
 * 照 `KioskAiLadderOpponent.parity.test.tsx` 的写法。
 */

const opponent = {
  rung: 17, rank_name: '4级',
  certification_status: 'certified', availability: 'available', route: 'server',
} as const;

const base: AiLadderReadyStatus = {
  view_state: 'ready',
  placement_state: { phase: 'placement', completed_games: 3, total_games: 5 },
  current_opponent: { ...opponent },
  recent_ranked_results: [],
  net_score: 0,
  pending_settlement: false,
};

/**
 * ⚠️ `current_opponent` 和 `placement_state.rung` 在后端是**同一个对象**
 * (`ai_ladder.py`:`placement_state = {"phase": "placed", "rung": opponent}`)。
 * `isRungUnseatable` / `isProvisionalSeating` 读的是 `current_opponent` —— 造成 `null` 的话
 * 那两个判别位恒为 false,「不可挑战」「可以试下但不计入」两条用例全部空过
 * (`KioskAiLadderOpponent.parity.test.tsx` 2026-08-26 实测踩过)。
 */
const placed = (over: Partial<AiLadderReadyStatus['current_opponent'] & object> = {},
  extra: Partial<AiLadderReadyStatus> = {}): AiLadderReadyStatus => {
  const rung = { ...opponent, rung: 16, rank_name: '5级', ...over };
  return { ...base, placement_state: { phase: 'placed', rung }, current_opponent: rung, ...extra };
};

const CASES: [string, AiLadderStatus][] = [
  ['加载中', { view_state: 'loading' }],
  ['出错', { view_state: 'error', message: '' }],
  ['定级赛进行中', base],
  ['已定档 · 已认证', placed()],
  ['已定档 · 暂定档且不可挑战', placed({ certification_status: 'provisional', availability: 'unavailable' })],
  ['已定档 · 暂定但这台机器让坐', placed({ certification_status: 'provisional' }, { provisional_play_allowed: true })],
  ['已定档 · 成绩在途', placed({}, { pending_settlement: true })],
  ['本机对弈那一路', placed({ route: 'local' })],
  ['有最近几盘', placed({}, { recent_ranked_results: ['win', 'loss', 'win'], net_score: 1 })],
  ['净胜分为负', placed({}, { net_score: -2 })],
];

/** 这几句**不许走散**。 */
const MUST_MATCH = () => [
  AI_LADDER_COPY.loading,
  AI_LADDER_COPY.loadError,
  AI_LADDER_COPY.retry,
  AI_LADDER_COPY.pendingSettlement,
  AI_LADDER_COPY.unavailable,
  AI_LADDER_COPY.provisionalSeating,
  AI_LADDER_COPY.certification.certified,
  AI_LADDER_COPY.certification.provisional,
  AI_LADDER_COPY.route.local,
  AI_LADDER_COPY.route.server,
  AI_LADDER_COPY.currentOpponentPrefix,
  AI_LADDER_COPY.currentRankPrefix,
  AI_LADDER_COPY.netScorePrefix,
  AI_LADDER_COPY.demotionThreshold,
  AI_LADDER_COPY.promotionThreshold,
  AI_LADDER_COPY.recentResultsNote,
  AI_LADDER_COPY.noRecentResults,
  '定级进度 3/5',
  '累计净胜分：+1',
  '累计净胜分：-2',
];

/** 屏上出现了哪几句。用 `textContent` 整片找,免得被标记切成两半骗过去。 */
const spoken = (container: HTMLElement) => {
  const text = container.textContent ?? '';
  return MUST_MATCH().filter((phrase) => text.includes(phrase));
};

/** 每一盘的读法(「第1盘：胜」)在 aria-label 上 —— 屏上只写「胜」,单个字没法在全文里比。 */
const outcomeLabels = (container: HTMLElement) =>
  [...container.querySelectorAll('[aria-label]')]
    .map((el) => el.getAttribute('aria-label') ?? '')
    .filter((label) => /^第\d+盘：/.test(label));

const renderKioskExpanded = (status: AiLadderStatus) => {
  const kiosk = render(<KioskAiLadderRows status={status} onRetry={() => {}} />);
  const toggle = screen.queryByRole('button', { name: /段位详情/ });
  if (toggle) fireEvent.click(toggle);
  return kiosk;
};

describe('设置屏 AI 段位:展开之后和共享卡说的是同一套话', () => {
  for (const [name, status] of CASES) {
    it(name, () => {
      const shared = render(
        <ThemeProvider theme={zenTheme}><AiLadderStatusCard status={status} onRetry={() => {}} compact /></ThemeProvider>,
      );
      const sharedSaid = spoken(shared.container);
      const sharedOutcomes = outcomeLabels(shared.container);
      cleanup();

      const kiosk = renderKioskExpanded(status);
      const kioskSaid = spoken(kiosk.container);
      const kioskOutcomes = outcomeLabels(kiosk.container);
      cleanup();

      expect(kioskSaid, `${name}:两边说的不是同一套`).toEqual(sharedSaid);
      expect(kioskOutcomes, `${name}:最近几盘读出来不一样`).toEqual(sharedOutcomes);
      // 空集相等是**假通过**:两边都没渲染出来时这条也会绿。
      expect(sharedSaid.length, `${name}:这一态两边都一句没说,用例本身是空的`).toBeGreaterThan(0);
    });
  }

  it('「有最近几盘」那一态确实读出了每一盘(否则上面那条比的是两个空集)', () => {
    const kiosk = renderKioskExpanded(placed({}, { recent_ranked_results: ['win', 'loss'] }));
    expect(outcomeLabels(kiosk.container)).toEqual([formatOutcomeLabel(0, 'win'), formatOutcomeLabel(1, 'loss')]);
  });
});

describe('登记在案的不同 —— 必须是这一处', () => {
  it('外壳那份不画「AI升降级对弈」那行卡片标题:它在「账号与平台」组里,那一行自己就说了是段位', () => {
    const shared = render(
      <ThemeProvider theme={zenTheme}><AiLadderStatusCard status={placed()} compact /></ThemeProvider>,
    );
    expect(shared.container.textContent).toContain(AI_LADDER_COPY.title);
    cleanup();
    const kiosk = renderKioskExpanded(placed());
    expect(kiosk.container.textContent).not.toContain(AI_LADDER_COPY.title);
  });
});

describe('外壳那份自己的规矩', () => {
  it('整份里没有 MUI 类名', () => {
    for (const [, status] of CASES) {
      const { container } = renderKioskExpanded(status);
      expect(container.querySelectorAll('[class*="Mui"]')).toHaveLength(0);
      cleanup();
    }
  });

  it('出错时「重试」永远画得出来:拿不到 onRetry 就灰着,不是撤掉', () => {
    render(<KioskAiLadderRows status={{ view_state: 'error', message: '' }} />);
    expect(screen.getByRole('button', { name: AI_LADDER_COPY.retry })).toBeDisabled();
  });
});
