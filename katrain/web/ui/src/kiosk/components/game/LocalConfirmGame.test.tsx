import { useState } from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { GameState } from '../../../api';
import { i18n } from '../../../i18n';
import LocalConfirmGame from './LocalConfirmGame';

vi.mock('../../../components/Board', () => ({ default: () => <div>BOARD</div> }));
const voice = vi.hoisted(() => ({ speak: vi.fn(), stop: vi.fn() }));
vi.mock('../../hooks/useVoice', () => ({ useVoice: () => voice }));
const game = {
  game_id: 'g', current_node_id: 33, current_node_index: 33, handicap: 0, player_to_move: 'B',
  board_size: [19, 19], children: [], end_result: null, game_type: 'pvp_local', count_min_moves: 100,
  players_info: { B: { name: '张三', main_time_used: 0, periods_used: 0 }, W: { name: '李四', main_time_used: 0, periods_used: 0 } },
  local_confirmation: { enabled: true, status: 'idle' },
} as GameState;
const props = () => ({ gameState: game, input: 'screen' as const, point: null, busy: false, failed: false,
  analysisToggles: { coords: true, numbers: false }, onToggle: vi.fn(), onSelect: vi.fn(), onConfirm: vi.fn(),
  onPass: vi.fn(), onCount: vi.fn(), onResign: vi.fn(), onExit: vi.fn(), onPaintedNode: vi.fn(), onExpired: vi.fn() });

describe('local confirmation panels', () => {
  beforeEach(() => { vi.clearAllMocks(); sessionStorage.clear(); });

  it('physical preparation disables confirmation and delays the opening voice until readiness', () => {
    const p = props();
    const opening = { ...game, current_node_index: 0 };
    const view = render(<LocalConfirmGame {...p} input="physical" gameState={opening} physicalPreparation="preparing" />);
    expect(screen.getByText('正在准备实体盘')).toBeInTheDocument();
    expect(screen.getByText('请先清空棋盘并移开双手，准备好后再落子。')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /准备中/ })).toBeDisabled();
    expect(voice.speak).not.toHaveBeenCalled();
    view.rerender(<LocalConfirmGame {...p} input="physical" gameState={opening} physicalPreparation="ready" />);
    expect(voice.speak).toHaveBeenCalledWith('local_confirm_physical');
    expect(screen.getByRole('button', { name: /确认落子/ })).toBeEnabled();
  });


  it('preparation in an existing game asks for the electronic position without clearing confirmed stones', () => {
    render(<LocalConfirmGame {...props()} input="physical" physicalPreparation="preparing" />);
    expect(screen.getByText('对齐电子棋谱，拿回未确认棋子，再移开双手。')).toBeInTheDocument();
    expect(screen.queryByText(/清空棋盘/)).not.toBeInTheDocument();
    expect(voice.speak).not.toHaveBeenCalled();
  });
  it('failed preparation has a separate retry even while pose blocks confirmation', () => {
    const p = props();
    const retry = vi.fn();
    const failedGame = { ...game, current_node_index: 0, local_confirmation: { enabled: true, status: 'idle' as const, reason: 'unavailable' as const } };
    const view = render(<LocalConfirmGame {...p} input="physical" gameState={failedGame}
      blocked physicalPreparation="error" onRetryPreparation={retry} />);
    expect(screen.getByText('先拿回尚未确认的棋子，再移开双手，重新准备实体盘。')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /重新准备实体盘/ }));
    expect(retry).toHaveBeenCalledTimes(1);
    expect(p.onConfirm).not.toHaveBeenCalled();
    expect(p.onPass).not.toHaveBeenCalled();
    view.rerender(<LocalConfirmGame {...p} input="physical" gameState={game} physicalPreparation="ready" />);
    expect(screen.queryByText('实体盘准备失败')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /确认落子/ })).toBeEnabled();
  });
  it('严重光照提示使用同一语音实例打断开局引导，关闭后停止，不触发对局动作', () => {
    const p = props();
    const opening = { ...game, current_node_index: 0, handicap: 0 };
    const view = render(<LocalConfirmGame {...p} input="physical" gameState={opening} />);
    expect(voice.speak).toHaveBeenLastCalledWith('local_confirm_physical');
    view.rerender(<LocalConfirmGame {...p} input="physical" gameState={{ ...opening,
      local_confirmation: { enabled: true, status: 'idle', reason: 'frame_overexposed' } }} />);
    expect(screen.getByRole('dialog')).toHaveTextContent('画面过亮，暂时无法可靠识别');
    expect(voice.speak).toHaveBeenLastCalledWith('lighting_overexposed');
    fireEvent.click(screen.getByRole('button', { name: '知道了' }));
    expect(voice.stop).toHaveBeenCalledTimes(1);
    for (const action of [p.onConfirm, p.onPass, p.onCount, p.onResign, p.onExit]) expect(action).not.toHaveBeenCalled();
  });
  it('同一节点识别中的空reason不会重置提示，成功换节点后允许再提示', async () => {
    const p = props();
    const severe = { ...game, local_confirmation: { enabled: true, status: 'idle' as const, reason: 'frame_underexposed' as const } };
    const view = render(<LocalConfirmGame {...p} input="physical" gameState={severe} />);
    expect(voice.speak).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole('button', { name: '知道了' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    view.rerender(<LocalConfirmGame {...p} input="physical" busy gameState={{ ...game,
      local_confirmation: { enabled: true, status: 'recognizing', reason: null } }} />);
    view.rerender(<LocalConfirmGame {...p} input="physical" gameState={severe} />);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(voice.speak).toHaveBeenCalledTimes(1);
    expect(screen.getByText('画面过暗')).toBeInTheDocument();
    expect(screen.getByText('移开遮挡；仍有提示请换个位置。')).toBeInTheDocument();
    view.rerender(<LocalConfirmGame {...p} input="physical" gameState={{ ...game, current_node_id: 34 }} />);
    view.rerender(<LocalConfirmGame {...p} input="physical" gameState={{ ...severe, current_node_id: 34 }} />);
    expect(screen.getByRole('dialog')).toHaveTextContent('画面过暗，暂时无法可靠识别');
    expect(voice.speak).toHaveBeenCalledTimes(2);
  });
  it('普通超时不给严重光照提示', () => {
    render(<LocalConfirmGame {...props()} input="physical" gameState={{ ...game,
      local_confirmation: { enabled: true, status: 'idle', reason: 'timeout' } }} />);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(voice.speak).not.toHaveBeenCalled();
  });
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
