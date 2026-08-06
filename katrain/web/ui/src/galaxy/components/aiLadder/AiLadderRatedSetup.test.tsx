import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import AiLadderRatedSetup from './AiLadderRatedSetup';
import type { AiLadderReadyStatus } from '../../../features/aiLadder/types';

const readyStatus: AiLadderReadyStatus = {
  view_state: 'ready',
  placement_state: {
    phase: 'placed',
    rung: { rung: 30, rank_name: '5段', certification_status: 'certified', availability: 'available', route: 'server' },
  },
  current_opponent: { rung: 30, rank_name: '5段', certification_status: 'certified', availability: 'available', route: 'server' },
  recent_ranked_results: ['win', 'loss', 'win', 'win', 'loss'],
  net_score: 1,
  pending_settlement: false,
};

const renderSetup = (
  status: AiLadderReadyStatus = readyStatus,
  overrides: Partial<React.ComponentProps<typeof AiLadderRatedSetup>> = {},
) => {
  const props: React.ComponentProps<typeof AiLadderRatedSetup> = {
    status,
    color: 'B',
    mainTime: 10,
    byoLength: 30,
    byoPeriods: 3,
    startPending: false,
    lifecyclePending: false,
    onColorChange: vi.fn(),
    onRetry: vi.fn(),
    onStart: vi.fn(),
    onContinue: vi.fn(),
    onEndGame: vi.fn(),
    ...overrides,
  };
  return { ...render(<AiLadderRatedSetup {...props} />), props };
};

const blockingStatus = (
  blockingGame: NonNullable<AiLadderReadyStatus['blocking_game']>,
): AiLadderReadyStatus => ({ ...readyStatus, blocking_game: blockingGame });

describe('AiLadderRatedSetup', () => {
  it('shows the ready ranked journey without exposing the internal rung', () => {
    renderSetup();

    expect(screen.getByText('5段', { selector: '[data-testid="current-rank"]' })).toBeInTheDocument();
    expect(screen.getAllByText('+1').length).toBeGreaterThan(0);
    expect(screen.getByText('胜 负 胜 胜 负')).toBeInTheDocument();
    expect(screen.getByText('19路')).toBeInTheDocument();
    expect(screen.getByText('中国规则')).toBeInTheDocument();
    expect(screen.getByText('贴目 7.5')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '开始正式对局' })).toBeEnabled();
    expect(screen.queryByText('30')).not.toBeInTheDocument();
  });

  it('does not expose a ranked-game-specific history entry point', () => {
    renderSetup();

    expect(screen.queryByRole('button', { name: '查看正式对局记录' })).not.toBeInTheDocument();
  });

  it('continues a current-device active game with a session and can end it after confirmation', async () => {
    const user = userEvent.setup();
    const status = blockingStatus({
      game_id: 'game-1', state: 'active', ownership: 'current_device', session_id: 'session-1',
      user_color: 'B', opponent_rank_name: '5段',
    });
    const { props } = renderSetup(status);

    await user.click(screen.getByRole('button', { name: '继续对局' }));
    expect(props.onContinue).toHaveBeenCalledWith('session-1');

    await user.click(screen.getByRole('button', { name: '结束该对局' }));
    expect(props.onEndGame).not.toHaveBeenCalled();
    expect(screen.getByText('结束后将按你认输处理，并计为本局负。此操作不可撤销。')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '取消' })).toHaveFocus();

    await user.click(screen.getByRole('button', { name: '取消' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(props.onEndGame).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: '结束该对局' }));
    await user.click(screen.getByRole('button', { name: '确认结束' }));
    expect(props.onEndGame).toHaveBeenCalledWith('game-1');
  });

  it('refreshes a current-device active game without a session and still offers ending it', async () => {
    const user = userEvent.setup();
    const status = blockingStatus({
      game_id: 'game-2', state: 'active', ownership: 'current_device',
      user_color: 'W', opponent_rank_name: '4段',
    });
    const { props } = renderSetup(status);

    expect(screen.queryByRole('button', { name: '继续对局' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '刷新状态' }));
    expect(props.onRetry).toHaveBeenCalledOnce();
    expect(screen.getByRole('button', { name: '结束该对局' })).toBeEnabled();
  });

  it('never reveals or uses another-device session and waits for settlement instead', async () => {
    const user = userEvent.setup();
    const status = blockingStatus({
      game_id: 'game-3', state: 'active', ownership: 'other_device', session_id: 'private-session',
      user_color: 'B', opponent_rank_name: '3段',
    });
    const { props } = renderSetup(status);

    expect(screen.queryByText('private-session')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '继续对局' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '等待结算' }));
    expect(props.onRetry).toHaveBeenCalledOnce();
    expect(props.onContinue).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: '结束该对局' })).toBeEnabled();
  });

  it('only refreshes a game pending settlement', async () => {
    const user = userEvent.setup();
    const status = blockingStatus({
      game_id: 'game-4', state: 'pending_settlement', ownership: 'current_device', session_id: 'session-4',
      user_color: 'W', opponent_rank_name: '2段',
    });
    const { props } = renderSetup(status);

    await user.click(screen.getByRole('button', { name: '刷新状态' }));
    expect(props.onRetry).toHaveBeenCalledOnce();
    expect(screen.queryByRole('button', { name: '结束该对局' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '继续对局' })).not.toBeInTheDocument();
  });

  it('keeps the settlement receipt visible after the blocking game disappears', () => {
    renderSetup(readyStatus, { lifecycleReceipt: { counted: false, reason: 'engine_unavailable' } });

    expect(screen.getByText('结算已完成')).toBeInTheDocument();
    expect(screen.getByText(/本局不计入升降级/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '开始正式对局' })).not.toBeInTheDocument();
  });

  it('prioritizes a counted settlement receipt over a blocking game', () => {
    const status = blockingStatus({
      game_id: 'game-5', state: 'active', ownership: 'current_device', session_id: 'session-5',
      user_color: 'B', opponent_rank_name: '1段',
    });
    renderSetup(status, { lifecycleReceipt: { counted: true, reason: null } });

    expect(screen.getByText('结算已完成')).toBeInTheDocument();
    expect(screen.getByText(/本局已计入升降级/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '继续对局' })).not.toBeInTheDocument();
  });

  it('keeps lifecycle state visible and disables both actions while pending', () => {
    const status = blockingStatus({
      game_id: 'game-6', state: 'active', ownership: 'current_device', session_id: 'session-6',
      user_color: 'B', opponent_rank_name: '1段',
    });
    renderSetup(status, { lifecyclePending: true, lifecycleError: '结束对局失败，请稍后重试' });

    expect(screen.getByRole('alert')).toHaveTextContent('结束对局失败，请稍后重试');
    expect(screen.getByRole('button', { name: '继续对局' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '结束该对局' })).toBeDisabled();
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
    expect(screen.getByText('未完成对局')).toBeInTheDocument();
  });

  it('closes the end-game confirmation with Escape without ending the game', async () => {
    const user = userEvent.setup();
    const status = blockingStatus({
      game_id: 'game-7', state: 'active', ownership: 'current_device', session_id: 'session-7',
      user_color: 'B', opponent_rank_name: '1段',
    });
    const { props } = renderSetup(status);

    await user.click(screen.getByRole('button', { name: '结束该对局' }));
    await user.keyboard('{Escape}');

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(props.onEndGame).not.toHaveBeenCalled();
  });
});
