import { render, screen } from '@testing-library/react';
import { describe, test, expect, vi } from 'vitest';
import GameControlPanel from './GameControlPanel';
import type { GameState } from '../../../api';

/**
 * 本地对局玩家卡上的钟(spec §3.3)。只断言**文字和回调**,不断言布局 ——
 * 布局归 tests/kiosk-screen-05-local-clock.spec.ts 那条真浏览器承重实测。
 * 客户端流逝恒为 0(没有推进定时器):每一格的读数完全由快照决定。
 */
const timer = (over: Partial<NonNullable<GameState['timer']>> = {}): NonNullable<GameState['timer']> => ({
  paused: false, main_time_used: 0, current_node_time_used: 0, next_player_periods_used: 0,
  settings: { main_time: 10, byo_length: 30, byo_periods: 3, minimal_use: 0, sound: false },
  ...over,
});
const state = (over: {
  game_type?: GameState['game_type']; timer?: GameState['timer']; B?: { main_time_used: number; periods_used: number };
}): GameState => ({
  game_id: 'clock', board_size: [19, 19], komi: 7.5, handicap: 0, ruleset: 'chinese',
  game_type: over.game_type ?? 'pvp_local', count_min_moves: 100,
  current_node_id: 0, current_node_index: 0, history: [{ node_id: 0, score: 0, winrate: 0.5 }],
  player_to_move: 'B', stones: [], last_move: null, prisoner_count: { B: 0, W: 0 }, analysis: null,
  commentary: '', is_root: true, is_pass: false, end_result: null, children: [], ghost_stones: [],
  players_info: {
    B: { player_type: 'player:human', player_subtype: '', name: '小明', calculated_rank: '', periods_used: 0, main_time_used: 0, ...over.B },
    W: { player_type: 'player:human', player_subtype: '', name: '小红', calculated_rank: '', periods_used: 0, main_time_used: 0 },
  },
  note: '', timer: over.timer,
  ui_state: { show_children: false, show_dots: false, show_hints: false, show_policy: false,
    show_ownership: false, show_move_numbers: false, show_coordinates: true, zen_mode: false },
} as GameState);
const panel = (gs: GameState, onTimeExpired = vi.fn(), isGameOver = false) => (
  <GameControlPanel gameState={gs} onAction={() => {}} onNavigate={() => {}} analysisToggles={{}}
    onToggleAnalysis={() => {}} isGameOver={isGameOver} onTimeExpired={onTimeExpired} />
);

describe('本地对局玩家卡上的钟', () => {
  test('主时间阶段:大字剩余主时间,副标读秒规格', () => {
    render(panel(state({ timer: timer(), B: { main_time_used: 18, periods_used: 0 } })));
    expect(screen.getByText('09:42')).toBeInTheDocument();
    expect(screen.getAllByText('读秒 30秒×3')).toHaveLength(2);   // 两张卡都有钟
  });

  test('读秒阶段:大字本次读秒剩余,副标剩几次', () => {
    render(panel(state({
      timer: timer({ current_node_time_used: 6 }), B: { main_time_used: 600, periods_used: 1 },
    })));
    expect(screen.getByText('00:24')).toBeInTheDocument();
    expect(screen.getByText('读秒 · 剩 2 次')).toBeInTheDocument();
  });

  test('用尽:00:00 · 超时,并且只调一次 onTimeExpired', () => {
    const onTimeExpired = vi.fn();
    const exhausted = () => state({ timer: timer(), B: { main_time_used: 600, periods_used: 3 } });
    const { rerender } = render(panel(exhausted(), onTimeExpired));
    expect(screen.getByText('00:00')).toBeInTheDocument();
    expect(screen.getByText('超时')).toBeInTheDocument();
    rerender(panel(exhausted(), onTimeExpired));          // 钟停在 0:不连调
    expect(onTimeExpired).toHaveBeenCalledTimes(1);
  });

  test('409 带回的新状态让钟回到读秒 ⇒ 再走到 0 会再调一次', () => {
    const onTimeExpired = vi.fn();
    const { rerender } = render(panel(state({ timer: timer(), B: { main_time_used: 600, periods_used: 3 } }), onTimeExpired));
    rerender(panel(state({ timer: timer({ current_node_time_used: 20 }), B: { main_time_used: 600, periods_used: 2 } }), onTimeExpired));
    expect(screen.getByText('00:10')).toBeInTheDocument();
    rerender(panel(state({ timer: timer(), B: { main_time_used: 600, periods_used: 3 } }), onTimeExpired));
    expect(onTimeExpired).toHaveBeenCalledTimes(2);
  });

  test('已终局:不调 onTimeExpired', () => {
    const onTimeExpired = vi.fn();
    render(panel(state({ timer: timer(), B: { main_time_used: 600, periods_used: 3 } }), onTimeExpired, true));
    expect(onTimeExpired).not.toHaveBeenCalled();
  });

  test('不限时的本地对局(main 0 · byo 0 · paused):仍是「第 N 手 / 不限时」', () => {
    render(panel(state({ timer: timer({ paused: true, settings: { main_time: 0, byo_length: 0, byo_periods: 3, minimal_use: 0, sound: false } }) })));
    expect(screen.getByText('第 1 手')).toBeInTheDocument();
    expect(screen.getByText('不限时')).toBeInTheDocument();
    expect(screen.queryByText('00:00')).toBeNull();
  });

  test('自由对弈即使带了用时也不走新钟、不调 onTimeExpired(非 pvp_local 一字不改)', () => {
    const onTimeExpired = vi.fn();
    render(panel(state({ game_type: 'free', timer: timer(), B: { main_time_used: 600, periods_used: 3 } }), onTimeExpired));
    expect(screen.queryByText('超时')).toBeNull();
    expect(screen.getByText('本局已下')).toBeInTheDocument();   // 旧分支:main_time_used>0 ⇒ 「10:00 本局已下」
    expect(onTimeExpired).not.toHaveBeenCalled();
  });
});
