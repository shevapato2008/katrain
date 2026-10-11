import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { GameState } from '../../../api';
import LocalConfirmGame from './LocalConfirmGame';

vi.mock('../../../components/Board', () => ({ default: () => <div>BOARD</div> }));
vi.mock('../../hooks/useVoice', () => ({ useVoice: () => ({ speak: vi.fn(), stop: vi.fn() }) }));
const game = {
  game_id: 'g', current_node_id: 33, current_node_index: 33, player_to_move: 'B',
  board_size: [19, 19], children: [], end_result: null, game_type: 'pvp_local', count_min_moves: 100,
  players_info: { B: { name: '张三', main_time_used: 0, periods_used: 0 }, W: { name: '李四', main_time_used: 0, periods_used: 0 } },
  local_confirmation: { enabled: true, status: 'idle' },
} as GameState;
const props = () => ({ gameState: game, input: 'screen' as const, point: null, busy: false, failed: false,
  analysisToggles: { coords: true, numbers: false }, onToggle: vi.fn(), onSelect: vi.fn(), onConfirm: vi.fn(),
  onPass: vi.fn(), onCount: vi.fn(), onResign: vi.fn(), onExit: vi.fn(), onPaintedNode: vi.fn(), onExpired: vi.fn() });

describe('local confirmation panels', () => {
  it('requires a screen selection and makes the selected point explicit', () => {
    const p = props();
    const { rerender } = render(<LocalConfirmGame {...p} />);
    const black = within(screen.getByRole('region', { name: '黑方玩家面板' }));
    expect(black.getByRole('button', { name: /确认落子/ })).toBeDisabled();
    rerender(<LocalConfirmGame {...p} point={{ x: 3, y: 3 }} />);
    expect(black.getByText('已选 D4')).toBeInTheDocument();
    expect(black.getByRole('button', { name: /确认落子/ })).toBeEnabled();
  });
  it('lets the waiting side resign itself with a second confirmation', () => {
    const p = props();
    render(<LocalConfirmGame {...p} />);
    const white = within(screen.getByRole('region', { name: '白方玩家面板' }));
    fireEvent.click(white.getByRole('button', { name: '认输' }));
    expect(screen.getByText('白方认输？')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '确认白方认输' }));
    expect(p.onResign).toHaveBeenCalledWith('W');
  });
  it('locks all eight panel actions during confirmation', () => {
    render(<LocalConfirmGame {...props()} busy point={{ x: 3, y: 3 }} />);
    for (const side of ['黑', '白']) {
      const panel = within(screen.getByRole('region', { name: `${side}方玩家面板` }));
      expect(panel.getAllByRole('button')).toHaveLength(4);
      panel.getAllByRole('button').forEach((button) => expect(button).toBeDisabled());
      expect(panel.getByText('已暂停')).toBeInTheDocument();
    }
  });
});
