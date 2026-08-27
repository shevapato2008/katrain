import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { GameState } from '../../../api';
import RightSidebarPanel from './RightSidebarPanel';

vi.mock('../../../api', () => ({ API: { getFollowing: vi.fn().mockResolvedValue([]) } }));
vi.mock('../../../context/AuthContext', () => ({ useAuth: () => ({ user: null, token: null }) }));
vi.mock('../../../context/SettingsContext', () => ({ useSettings: () => ({ language: 'cn' }) }));
// 这个组件的文案全走 `t(key, 中文默认)`；测试里没有 catalog，取第二个参数就是屏上那句。
vi.mock('../../../hooks/useTranslation', () => ({ useTranslation: () => ({ t: (_k: string, zh?: string) => zh ?? _k }) }));
vi.mock('../../../components/ScoreGraph', () => ({ default: () => <div data-testid="score-graph" /> }));
vi.mock('../../../components/PlayerCard', () => ({ default: () => <div data-testid="player-card" /> }));

const seat = (name: string, type: string) => ({
  player_type: type, player_subtype: '', name, calculated_rank: null, periods_used: 0, main_time_used: 0,
});

const gameState = {
  game_id: 'g1', board_size: [19, 19], komi: 6.5, handicap: 0, ruleset: 'japanese', current_node_id: 1,
  current_node_index: 1, history: [], player_to_move: 'B', stones: [], last_move: null,
  prisoner_count: { B: 0, W: 0 }, analysis: null, commentary: '', is_root: false, is_pass: false,
  end_result: null, children: [], ghost_stones: [], note: '', language: 'cn', game_type: 'free',
  players_info: { B: seat('游客', 'player:human'), W: seat('AI', 'player:ai') },
  ui_state: {
    show_children: false, show_dots: false, show_hints: false, show_policy: false,
    show_ownership: false, show_move_numbers: false, show_coordinates: true, zen_mode: false,
  },
} as unknown as GameState;

const renderPanel = (props: Partial<React.ComponentProps<typeof RightSidebarPanel>> = {}) =>
  render(
    <RightSidebarPanel
      gameState={gameState}
      analysisToggles={{}}
      onToggleChange={vi.fn()}
      onNavigate={vi.fn()}
      {...props}
    />
  );

const tool = (name: string) => screen.getByRole('button', { name });

/**
 * 未登录游客的会话服务端不交付分析（`analysis_delivered === false`），于是三个分析键
 * 点了不会有任何反应。一个点了没反应的键和一个坏掉的键在用户那里是同一个东西 ——
 * 所以要置灰**并说出原因**。
 */
describe('RightSidebarPanel — 分析要登录', () => {
  it('三个分析键置灰并给出原因，其余键不受牵连', () => {
    renderPanel({ analysisRequiresLogin: true });

    expect(tool('Territory')).toBeDisabled();
    expect(tool('Advice')).toBeDisabled();
    expect(tool('Graph')).toBeDisabled();
    expect(screen.getByTestId('analysis-requires-login')).toHaveTextContent('登录后可用');

    // 悔棋/停一手/认输在未登录的自由对弈里是**通的**（服务端对无主会话放行）。
    // 与升降级那把锁分开，正是为了不为了关分析顺手关掉能用的功能。
    expect(tool('Undo')).toBeEnabled();
    expect(tool('Pass')).toBeEnabled();
    expect(tool('Resign')).toBeEnabled();
  });

  it('不传这个标志时一切照旧：三个分析键可点，也不出现那句解释', () => {
    renderPanel();

    expect(tool('Territory')).toBeEnabled();
    expect(tool('Advice')).toBeEnabled();
    expect(tool('Graph')).toBeEnabled();
    expect(screen.queryByTestId('analysis-requires-login')).not.toBeInTheDocument();
  });

  it('升降级那把锁仍然连悔棋一起锁 —— 两把锁的范围不同', () => {
    renderPanel({ isRated: true });

    expect(tool('Territory')).toBeDisabled();
    expect(tool('Undo')).toBeDisabled();
    // 说的是升降级那句，不是「登录后可用」。
    expect(screen.queryByTestId('analysis-requires-login')).not.toBeInTheDocument();
    expect(screen.getByText('Items disabled during Rated Game')).toBeInTheDocument();
  });
});
