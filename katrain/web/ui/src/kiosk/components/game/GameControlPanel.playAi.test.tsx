import { act, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import GameControlPanel from './GameControlPanel';
import type { GameState } from '../../../api';

/** 对弈·AI/升降级赛道的右栏行为测试。只证 DOM 结构与文案;几何在 tests/kiosk-screen-05-play-ai.spec.ts。 */

const seat = (type: string, name: string, over: Record<string, number> = {}) => ({
  player_type: type, player_subtype: '', name, calculated_rank: null, periods_used: 0, main_time_used: 0, ...over,
});

const base = (over: Partial<GameState> = {}): GameState => ({
  game_id: 'g', board_size: [19, 19], komi: 7.5, handicap: 0, ruleset: 'chinese',
  current_node_id: 7, current_node_index: 7, history: [{ node_id: 0, score: null, winrate: null }],
  player_to_move: 'B', stones: [], last_move: null, prisoner_count: { B: 0, W: 0 }, analysis: null, commentary: '',
  is_root: false, is_pass: false, end_result: null, children: [], ghost_stones: [], note: '',
  game_type: 'free', count_min_moves: 100,
  ui_state: {
    show_children: false, show_dots: false, show_hints: false, show_policy: false,
    show_ownership: false, show_move_numbers: false, show_coordinates: true, zen_mode: false,
  },
  players_info: { B: seat('player:human', '我'), W: seat('player:ai', 'KataGo') },
  ...over,
} as GameState);

const timer = (settings: { main_time: number; byo_length: number; byo_periods: number }, configured = true) => ({
  paused: false, main_time_used: 0, current_node_time_used: 0, next_player_periods_used: 0, configured,
  settings: { minimal_use: 0, sound: false, ...settings },
});

const panel = (gs: GameState, props: Record<string, unknown> = {}) => render(
  <GameControlPanel
    gameState={gs}
    onAction={() => {}}
    onNavigate={() => {}}
    analysisToggles={{}}
    onToggleAnalysis={() => {}}
    {...props}
  />,
);

const clockOf = (color: 'B' | 'W') => {
  const card = screen.getByTestId(`player-card-${color}`);
  return { value: card.querySelector('.clock b')?.textContent, label: card.querySelector('.clock span')?.textContent };
};

describe('A18 · 玩家卡时钟', () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  test('主时间阶段:两张卡都写剩余,只有轮到的一方在走', () => {
    panel(base({
      timer: timer({ main_time: 5, byo_length: 30, byo_periods: 3 }),
      players_info: { B: seat('player:human', '我', { main_time_used: 12 }), W: seat('player:ai', 'KataGo', { main_time_used: 30 }) },
    }));
    expect(clockOf('B')).toEqual({ value: '4:48', label: '剩余' });
    expect(clockOf('W')).toEqual({ value: '4:30', label: '剩余' });
    act(() => { vi.advanceTimersByTime(2000); });
    expect(clockOf('B').value).toBe('4:46');
    expect(clockOf('W').value).toBe('4:30');
  });

  test('仅读秒:写本次读秒剩余与剩几次', () => {
    panel(base({
      timer: timer({ main_time: 0, byo_length: 30, byo_periods: 3 }),
      players_info: { B: seat('player:human', '我', { periods_used: 1 }), W: seat('player:ai', 'KataGo') },
    }));
    expect(clockOf('B')).toEqual({ value: '0:30', label: '读秒 · 剩 2 次' });
    expect(clockOf('W')).toEqual({ value: '0:30', label: '读秒 · 剩 3 次' });
  });

  test('耗尽:写「超时」,并对轮到的那一方回调一次 onTimeout', () => {
    const onTimeout = vi.fn();
    panel(base({ timer: timer({ main_time: 0, byo_length: 30, byo_periods: 1 }) }), { onTimeout });
    act(() => { vi.advanceTimersByTime(31_000); });
    expect(clockOf('B')).toEqual({ value: '0:00', label: '超时' });
    expect(onTimeout).toHaveBeenCalledTimes(1);
    expect(onTimeout).toHaveBeenCalledWith('B');
  });

  test('没配过时限的局(星阵 / 大厅)不倒计时,仍写「第 N 手 · 不限时」', () => {
    panel(base({ timer: timer({ main_time: 20, byo_length: 30, byo_periods: 5 }, false) }));
    expect(clockOf('B')).toEqual({ value: '第 8 手', label: '不限时' });
  });

  test.each([{ children: [['W', [3, 3]]] }, { terminal_result: 'W+R' }])('r1 S6:非叶子或终局时不走钟、不回调 %j', (over) => {
    const onTimeout = vi.fn();
    panel(base({ timer: timer({ main_time: 0, byo_length: 30, byo_periods: 1 }), ...over } as Partial<GameState>), { onTimeout });
    act(() => { vi.advanceTimersByTime(31_000); });
    expect(clockOf('B').value).toBe('0:30');
    expect(onTimeout).not.toHaveBeenCalled();
  });

  test('r1 C1:换了一手、仍然耗尽 —— 再回调一次(服务端判轮次过期后,前端重同步到新的一手要能再核)', () => {
    const onTimeout = vi.fn();
    const timed = timer({ main_time: 0, byo_length: 30, byo_periods: 1 });
    const props = { onAction: () => {}, onNavigate: () => {}, analysisToggles: {}, onToggleAnalysis: () => {}, onTimeout };
    const exhausted = { B: seat('player:human', '我', { periods_used: 1 }), W: seat('player:ai', 'KataGo') };
    const { rerender } = render(<GameControlPanel gameState={base({ timer: timed, players_info: exhausted })} {...props} />);
    expect(onTimeout).toHaveBeenCalledTimes(1);
    rerender(<GameControlPanel gameState={base({ timer: timed, players_info: exhausted, current_node_id: 9 })} {...props} />);
    expect(onTimeout).toHaveBeenCalledTimes(2);
  });
});

describe('N14 + A11 · 右栏按对局类型', () => {
  const hist = [
    { node_id: 0, score: null, winrate: null, move: null, player: null },
    { node_id: 1, score: null, winrate: null, move: 'Q16', player: 'B' },
    { node_id: 2, score: null, winrate: null, move: 'D4', player: 'W' },
  ] as GameState['history'];
  const labels = () => Array.from(screen.getByTestId('game-actions').querySelectorAll('button'))
    .map((b) => b.textContent?.trim());

  test('升降级局:不渲染「领地」「AI支招」(规范 §8:禁的时候整块不渲染)', () => {
    panel(base({ game_type: 'ai_ladder_ranked' }), { isRanked: true });
    expect(labels()).toEqual(['数子', '停一手', '认输']);
  });

  test.each([
    ['升降级', { game_type: 'ai_ladder_ranked' }, { isRanked: true, analysisToggles: { score: true } }],
    ['本地对局', { game_type: 'pvp_local' }, { analysisToggles: { score: true } }],
    ['关掉图表的自由对弈', { game_type: 'free' }, { analysisToggles: { score: false } }],
  ])('%s:胜率块不在时,右栏中段是棋谱', (_name, over, props) => {
    panel(base({ ...(over as Partial<GameState>), history: hist, current_node_index: 2 }), props);
    expect(screen.getByTestId('game-moves-fold')).toBeInTheDocument();
    expect(document.querySelector('.kiosk-fold[data-fold="eval"]')).toBeNull();
  });

  test('开着图表的自由对弈:胜率块在、棋谱不在(屏 05 不变)', () => {
    panel(base({ history: hist, current_node_index: 2 }), { analysisToggles: { score: true } });
    expect(screen.queryByTestId('game-moves-fold')).toBeNull();
    expect(document.querySelector('.kiosk-fold[data-fold="eval"]')).not.toBeNull();
  });
});
