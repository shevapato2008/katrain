import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { GameState } from '../../../api';
import LobbyGamePanel from './LobbyGamePanel';
const state = { board_size: [19, 19], current_node_index: 4, history: Array(5).fill({}), count_min_moves: 100,
  player_to_move: 'B', my_color: 'B', prisoner_count: { B: 3, W: 2 }, players_info: {
    B: { name: 'fan' }, W: { name: '在线棋友的长名字' },
  } } as unknown as GameState;
const props = () => ({ gameState: state, setupLine: '19 路 · 中国规则 · 贴目 7.5 · 分先', connected: true,
  isGameOver: false, blocked: false, counting: false, statusSlot: null, hardwareFault: null,
  analysisToggles: { coords: true, numbers: false }, onToggleAnalysis: vi.fn(), onAction: vi.fn(), onExit: vi.fn(),
  territory: { phase: 'idle' as const, visible: false, disabled: false, request: vi.fn() } });
describe('lobby game panel', () => {
  it('keeps both invited grades separate from long names and defaults missing labels to unknown', () => {
    const p = props();
    const { rerender } = render(<LobbyGamePanel {...p} sessionId="local" playerRanks={{ B: { label: '2段', title: '2段' }, W: { label: '20k', title: '20k' } }} />);
    const seats = screen.getAllByTestId('lobby-player');
    expect(within(seats[0]).getByText('20k')).toHaveClass('kiosk-player-rank');
    expect(within(seats[1]).getByText('2段')).toHaveClass('kiosk-player-rank');
    expect(within(seats[0]).getByTitle('在线棋友的长名字')).not.toContainElement(within(seats[0]).getByText('20k'));
    rerender(<LobbyGamePanel {...p} />);
    expect(screen.getAllByText('等级未知')).toHaveLength(2);
    expect(screen.queryByText('尚未定级')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '停一手' })); expect(p.onAction).toHaveBeenCalledWith('pass');
  });
  it('binds real seats, captures and turn with the four approved actions and equal toggles', () => {
    const p = props(); render(<LobbyGamePanel {...p} />);
    expect(screen.getByRole('heading', { name: '大厅对局' })).toBeInTheDocument();
    const seats = screen.getAllByTestId('lobby-player');
    expect(seats[0]).toHaveTextContent('白 · 在线棋友的长名字');
    expect(seats[0]).toHaveTextContent('提子 2');
    expect(seats[1]).toHaveTextContent('黑 · fan（你）');
    expect(seats[1]).toHaveTextContent('提子 3');
    expect(seats[1]).toHaveAttribute('data-turn', 'true');
    expect(screen.getByText('轮到你落子')).toBeInTheDocument();
    const actions = within(screen.getByTestId('game-actions')).getAllByRole('button');
    expect(actions.map(b => b.textContent)).toEqual(['领地', '数子', '停一手', '认输']);
    expect(actions[1]).toBeDisabled();
    expect(screen.getByText('满 100 手可数子')).toBeInTheDocument();
    fireEvent.click(actions[0]); expect(p.territory.request).toHaveBeenCalledOnce();
    fireEvent.click(actions[2]); expect(p.onAction).toHaveBeenCalledWith('pass');
    fireEvent.click(actions[3]); expect(p.onAction).toHaveBeenCalledWith('resign');
    fireEvent.click(screen.getByRole('button', { name: '退出对局' })); expect(p.onExit).toHaveBeenCalledOnce();
    expect(screen.getByRole('button', { name: '坐标' })).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(screen.getByRole('button', { name: '手数' })); expect(p.onToggleAnalysis).toHaveBeenCalledWith('numbers');
  });
  it('keeps legal pass and resign available when only the count identity is unavailable', () => {
    render(<LobbyGamePanel {...props()} countDisabled gameState={{ ...state, history: Array(100).fill({}) }} />);
    expect(screen.getByRole('button', { name: '数子' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '停一手' })).toBeEnabled();
    expect(screen.getByRole('button', { name: '认输' })).toBeEnabled();
  });
  it('gates pass by actual side and turn, permits threshold count and preserves urgent status over territory', () => {
    const p = props(); render(<LobbyGamePanel {...p} gameState={{ ...state, player_to_move: 'W', history: Array(100).fill({}) }}
      territory={{ ...p.territory, phase: 'error' }} statusSlot={<div role="alert">等待对方确认数子</div>} />);
    expect(screen.getByRole('button', { name: '停一手' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '数子' })).toBeEnabled();
    expect(within(screen.getByRole('region', { name: '在线对局状态' })).getByRole('alert')).toHaveTextContent('等待对方确认数子');
    expect(screen.getByText('领地未取得，请重试')).toBeInTheDocument();
    expect(screen.getByText('仅供参考，正式胜负以数子为准')).toBeInTheDocument();
  });
});
