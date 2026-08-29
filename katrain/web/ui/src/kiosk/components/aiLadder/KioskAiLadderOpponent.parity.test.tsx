import { render, screen, cleanup } from '@testing-library/react';
import { ThemeProvider } from '@mui/material/styles';
import { describe, expect, it } from 'vitest';

import AiLadderSetupOpponent from '../../../features/aiLadder/AiLadderSetupOpponent';
import { AI_LADDER_COPY } from '../../../features/aiLadder/copy';
import type { AiLadderReadyStatus, AiLadderStatus } from '../../../features/aiLadder/types';
import { zenTheme } from '../../../theme';
import KioskAiLadderOpponent from './KioskAiLadderOpponent';

/**
 * 「对手」那一格现在有**两份视图**:galaxy 那份(MUI)和 kiosk 这份(外壳)。
 *
 * 两份并行实现的风险只有一个,而且是致命的那一个:**它们会说不同的话。**
 * 屏 03 上写着「可以试下但不计入升降级」,而同一个状态在网页上什么都不说 ——
 * 用户按下去之后才发现这一局白下了,而两边的单测都是绿的(各测各的)。
 *
 * ⇒ 这条闸逐状态断言:**该说的那几句,两边要么都说、要么都不说。**
 * 判据落在 `AI_LADDER_COPY` 的具体串上,不落在「渲染了几个元素」上。
 *
 * 两处**登记在案的不同**在文件末尾单独钉住 —— 不同本身是裁定,
 * 但它必须是**这两处**,多一处少一处都要在这儿变红。
 */

const base: AiLadderReadyStatus = {
  view_state: 'ready',
  placement_state: { phase: 'placement', completed_games: 3, total_games: 5 },
  current_opponent: {
    rung: 17, rank_name: '4级',
    certification_status: 'certified', availability: 'available', route: 'server',
  },
  recent_ranked_results: [],
  net_score: 0,
  pending_settlement: false,
};

/**
 * ⚠️ **`current_opponent` 和 `placement_state.rung` 是同一个对象** ——
 * 后端 `ai_ladder.py:474` 写的是 `placement_state = {"phase": "placed", "rung": opponent}`,
 * 而 `current_opponent = dict(opponent)`。
 *
 * 这一条不是细节:`isRungUnseatable` / `isProvisionalSeating` 读的都是
 * **`current_opponent`**(`startGate.ts:29,74`)。把它造成 `null`(共享件那份现成的用例
 * 就是这么写的),两个判别位恒为 false ⇒「不可挑战」和「可以试下但不计入」那两条**永远不渲染**,
 * 而断言它们的用例全部**空过**。
 * 2026-08-26 实测:第一版这么写的时候,把 kiosk 那份的 `provisionalSeating` 整块删掉,
 * 这份闸**一条都没红**。
 */
const placed = (over: Partial<AiLadderReadyStatus['current_opponent'] & object> = {},
  extra: Partial<AiLadderReadyStatus> = {}): AiLadderReadyStatus => {
  const rung = { ...base.current_opponent!, rung: 16, rank_name: '5级', ...over };
  return { ...base, placement_state: { phase: 'placed', rung }, current_opponent: rung, ...extra };
};

const CASES: [string, AiLadderStatus][] = [
  ['加载中', { view_state: 'loading' }],
  ['出错', { view_state: 'error', message: '升降级对弈状态加载失败' }],
  ['定级赛进行中', base],
  ['已定档 · 已认证', placed()],
  ['已定档 · 暂定档且不可挑战', placed({ certification_status: 'provisional', availability: 'unavailable' })],
  // 这一台开了「暂定也让坐」(`KATRAIN_LADDER_ALLOW_PROVISIONAL`):坐得下,但这一局不计入。
  // **屏上不说这句话的代价是用户白下一局**,所以两边必须都说。
  ['已定档 · 暂定但这台机器让坐', placed(
    { certification_status: 'provisional' }, { provisional_play_allowed: true },
  )],
  ['已定档 · 成绩在途', placed({}, { pending_settlement: true })],
  ['本机对弈那一路', placed({ route: 'local' })],
];

/** 这几句**不许走散** —— 每一句都是「用户按下去之前必须知道」的一件事。 */
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
  AI_LADDER_COPY.placementOpponentPrefix,
  '定级进度 3/5',
];

/** 屏上出现了哪几句。用 `textContent` 整片找,免得被标记切成两半骗过去。 */
function spoken(container: HTMLElement): string[] {
  const text = container.textContent ?? '';
  return MUST_MATCH().filter((phrase) => text.includes(phrase));
}

describe('两份视图说的是同一套话', () => {
  for (const [name, status] of CASES) {
    it(name, () => {
      const shared = render(
        <ThemeProvider theme={zenTheme}>
          <AiLadderSetupOpponent status={status} onRetry={() => {}} />
        </ThemeProvider>,
      );
      const sharedSaid = spoken(shared.container);
      cleanup();

      const kiosk = render(<KioskAiLadderOpponent status={status} onRetry={() => {}} />);
      const kioskSaid = spoken(kiosk.container);
      cleanup();

      expect(kioskSaid, `${name}:两边说的不是同一套`).toEqual(sharedSaid);
      // 空集相等是**假通过**:两边都没渲染出来时这条也会绿。
      expect(sharedSaid.length, `${name}:这一态两边都一句没说,用例本身是空的`).toBeGreaterThan(0);
    });
  }
});

describe('登记在案的两处不同 —— 必须是这两处', () => {
  it('外壳那份不画「41档升降级AI」那行标题:它正上方就是「对手」那条组标签', () => {
    const shared = render(
      <ThemeProvider theme={zenTheme}><AiLadderSetupOpponent status={placed()} /></ThemeProvider>,
    );
    expect(shared.container.textContent).toContain(AI_LADDER_COPY.setupTitle);
    cleanup();

    const kiosk = render(<KioskAiLadderOpponent status={placed()} />);
    expect(kiosk.container.textContent).not.toContain(AI_LADDER_COPY.setupTitle);
  });

  it('已定档那一句照稿子写:「你是 X,配到 第 N 档 —— 为什么不给挑」', () => {
    render(<KioskAiLadderOpponent status={placed()} />);
    const said = screen.getByTestId('ladder-opponent').textContent ?? '';
    expect(said).toContain('你是');
    expect(said).toContain('5级');
    expect(said).toContain('第 16 档');
    expect(said).toContain(AI_LADDER_COPY.boxPicksReason);
    // 两个数出自**同一份** `rung` —— 升降级里你的档就是你的对手
    // (`ai_ladder_ranked.py:178` `if rung is not None: return rung`)。
    // 所以这不是「你的段位」和「对手的档」两件事,是同一件事的两种写法。
  });
});
