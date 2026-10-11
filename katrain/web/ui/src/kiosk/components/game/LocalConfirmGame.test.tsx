import { useState } from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { GameState } from '../../../api';
import { i18n } from '../../../i18n';
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
  it('shares visible display controls between both seats, including the waiting side', () => {
    const p = props();
    function DisplayControls() {
      const [toggles, setToggles] = useState<Record<string, boolean>>(p.analysisToggles);
      return <LocalConfirmGame {...p} analysisToggles={toggles} onToggle={(key) => {
        p.onToggle(key);
        setToggles(previous => ({ ...previous, [key]: !previous[key] }));
      }} />;
    }
    render(<DisplayControls />);
    const black = within(screen.getByRole('region', { name: '黑方玩家面板' }));
    const white = within(screen.getByRole('region', { name: '白方玩家面板' }));
    for (const panel of [black, white]) {
      expect(panel.getByRole('button', { name: /坐标/, pressed: true })).toHaveTextContent('坐标开');
      expect(panel.getByRole('button', { name: /手数/, pressed: false })).toHaveTextContent('手数关');
    }
    fireEvent.click(white.getByRole('button', { name: /手数/, pressed: false }));
    expect(p.onToggle).toHaveBeenLastCalledWith('numbers');
    for (const panel of [black, white]) {
      expect(panel.getByRole('button', { name: /手数/, pressed: true })).toHaveTextContent('手数开');
    }
    fireEvent.click(black.getByRole('button', { name: /坐标/, pressed: true }));
    expect(p.onToggle).toHaveBeenLastCalledWith('coords');
    for (const panel of [black, white]) {
      expect(panel.getByRole('button', { name: /坐标/, pressed: false })).toHaveTextContent('坐标关');
    }
  });
  it('uses the existing stop-a-turn translation instead of the generic Pass label', () => {
    const translation = vi.spyOn(i18n, 't').mockImplementation((key, fallback) => (
      key === 'Pass' ? '虚着' : key === 'game:pass' ? '停一手' : fallback ?? key
    ));
    try {
      render(<LocalConfirmGame {...props()} />);
      expect(screen.getAllByRole('button', { name: '停一手' })).toHaveLength(2);
      expect(screen.queryByRole('button', { name: '虚着' })).not.toBeInTheDocument();
    } finally {
      translation.mockRestore();
    }
  });
  it('locks the eight business actions during confirmation while display controls remain available', () => {
    render(<LocalConfirmGame {...props()} busy point={{ x: 3, y: 3 }} />);
    for (const side of ['黑', '白']) {
      const panel = within(screen.getByRole('region', { name: `${side}方玩家面板` }));
      const buttons = panel.getAllByRole('button');
      expect(buttons).toHaveLength(6);
      buttons.filter(button => !button.hasAttribute('aria-pressed')).forEach(button => expect(button).toBeDisabled());
      buttons.filter(button => button.hasAttribute('aria-pressed')).forEach(button => expect(button).toBeEnabled());
      expect(panel.getByText('已暂停')).toBeInTheDocument();
    }
  });
});
