import { render, screen } from '@testing-library/react';
import { describe, test, expect } from 'vitest';
import GameControlPanel from './GameControlPanel';
import type { GameState } from '../../../api';

const mockGameState: GameState = {
  game_id: 'test-game',
  board_size: [19, 19],
  komi: 6.5,
  handicap: 0,
  ruleset: '日本',
  current_node_id: 0,
  current_node_index: 0,
  history: [{ node_id: 0, score: 0, winrate: 0.5 }],
  player_to_move: 'B',
  stones: [],
  last_move: null,
  prisoner_count: { B: 0, W: 0 },
  analysis: null,
  commentary: '',
  is_root: true,
  is_pass: false,
  end_result: null,
  children: [],
  ghost_stones: [],
  players_info: {
    B: { player_type: 'human', player_subtype: '', name: '张三', calculated_rank: '2D', periods_used: 0, main_time_used: 0 },
    W: { player_type: 'ai', player_subtype: 'katago', name: 'KataGo', calculated_rank: '5D', periods_used: 0, main_time_used: 0 },
  },
  note: '',
  ui_state: {
    show_children: false, show_dots: false, show_hints: false, show_policy: false,
    show_ownership: false, show_move_numbers: false, show_coordinates: true, zen_mode: false,
  },
} as GameState;

describe('GameControlPanel', () => {
  // The 3D board was removed from the kiosk on 2026-07-13 (freed ~321MB Mali GPU contending
  // with KataGo's OpenCL). Guard against reintroducing the toggle; core controls must remain.
  test('renders core controls and NO 3D toggle', () => {
    render(
      <GameControlPanel
        gameState={mockGameState}
        onAction={() => {}}
        onNavigate={() => {}}
        analysisToggles={{}}
        onToggleAnalysis={() => {}}
        isGameOver={false}
      />
    );
    expect(screen.queryByText('3D')).toBeNull();
    expect(screen.getByText('领地')).toBeInTheDocument();
    expect(screen.getByText('数子')).toBeInTheDocument();
  });

  // ── 悔棋按对弈方式判 ────────────────────────────────────────────────────────
  // Fan 2026-08-25 亲裁:「**只有人机对弈的自由对弈允许悔棋**;人机对弈的升降级对弈、
  // 人人对弈的对战大厅、跨平台对弈等都不允许,悔棋按钮可以撤销。」
  //
  // 五种对弈方式**逐个都要出现在这张表里** —— 少一行就等于那一种没被裁过。
  // 判据落在**屏上有没有这颗键**,不落在 `undoAllowed` 那个变量上:
  // 变量对「渲染那一支忘了引它」免疫,而那正是上一版的病(engineMode 和 playActions
  // 是两支各写一遍的代码,改一支漏一支不会有人红)。
  //
  // 这条留在 jsdom 里是对的:「按钮在不在 DOM 里」是**结构**不是布局,
  // 不经过浏览器的布局引擎;同一批里「三颗键还贴不贴右栏底」那种数在
  // `tests/kiosk-screen-05-game.spec.ts` 里用真浏览器量。
  //
  // **变异记录**(2026-08-25,五处逐个改坏、逐个跑过,不是推演):
  //   M1 `playActions` 无条件出悔棋      → 升降级×2 / 本地 / 大厅 / 灰键那条,红 5
  //   M2 engineMode 那一支把悔棋加回去    → 星阵那行,红 1
  //   M3 `undoAllowed = false`           → 自由对弈那行,红 1
  //   M4 `rankedGame` 只认 prop 不读 game_type → 「漏传 isRanked」那行,红 1
  //   M5 改成留一颗 `disabled` 的悔棋(稿子那个写法) → 红 5(同 M1)
  // 每一行都被至少一处变异单独点过名 —— 没有哪一行是靠别人红顺带绿的。
  const panel = (over: Partial<GameState>, props: Record<string, unknown> = {}) =>
    render(
      <GameControlPanel
        gameState={{ ...mockGameState, ...over }}
        onAction={() => {}}
        onNavigate={() => {}}
        analysisToggles={{}}
        onToggleAnalysis={() => {}}
        isGameOver={false}
        {...props}
      />
    );

  test.each([
    ['人机 · 自由对弈', { game_type: 'free' }, {}, true],
    ['人机 · 升降级对弈', { game_type: 'ai_ladder_ranked' }, { isRanked: true }, false],
    // `isRanked` **没传**:闸自己从 `game_type` 也读得出来。少传一次 prop 不该把闸打开。
    ['人机 · 升降级对弈(调用方漏传 isRanked)', { game_type: 'ai_ladder_ranked' }, {}, false],
    ['人人 · 本地对局', { game_type: 'pvp_local' }, {}, false],
    ['人人 · 对战大厅', { game_type: 'pvp_online' }, {}, false],
    ['跨平台 · 星阵人机', { game_type: 'free' }, { engineMode: true }, false],
  ] as const)('悔棋:%s → %s', (_name, over, props, expected) => {
    panel(over as Partial<GameState>, props as Record<string, unknown>);
    const undo = screen.queryByText('悔棋');
    expect(undo === null, '悔棋这颗键在不在').toBe(!expected);
    // 「认输」在五种里都在 —— 用它证这一排本身渲染了,
    // 否则整块没渲染时上面那句对「不该有」的四行会**全绿**。
    expect(screen.getByText('认输')).toBeInTheDocument();
  });

  // 撤掉不是灰着:这四种里悔棋是**开局就定死的没有**,不是过一会儿会回来的状态。
  // 判据「永久不可用 → 撤掉;暂时不可用 → 灰着」 —— 所以不许留一颗 `disabled` 的悔棋。
  test('不该有悔棋的局里,也不许留一颗灰着的悔棋', () => {
    panel({ game_type: 'pvp_online' });
    expect(screen.queryByRole('button', { name: /悔棋/ })).toBeNull();
  });
});
