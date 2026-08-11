import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import AiLadderRatedSetup from './AiLadderRatedSetup';
import type { AiLadderReadyStatus, AiLadderStatus } from '../../../features/aiLadder/types';

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

const renderReceiptStatus = (
  status: AiLadderStatus,
  lifecycleReceipt: NonNullable<React.ComponentProps<typeof AiLadderRatedSetup>['lifecycleReceipt']>,
) => render(
  <AiLadderRatedSetup
    status={status}
    color="B"
    mainTime={10}
    byoLength={30}
    byoPeriods={3}
    startPending={false}
    lifecycleReceipt={lifecycleReceipt}
    onColorChange={vi.fn()}
    onRetry={vi.fn()}
    onStart={vi.fn()}
  />,
);

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

    await user.click(screen.getByRole('button', { name: '在这台机器上开新局' }));
    expect(props.onEndGame).not.toHaveBeenCalled();
    expect(screen.getByText(/它将计为本局负并计入升降级/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '取消' })).toHaveFocus();

    await user.click(screen.getByRole('button', { name: '取消' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(props.onEndGame).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: '在这台机器上开新局' }));
    await user.click(screen.getByRole('button', { name: '确认开新局' }));
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
    // 「刷新状态」不在这一格 —— 它做的事(重问一次 /status)本来就每 15 秒在自动发生,
    // 而棋盘随进程没了,刷多少次都刷不回来。
    expect(screen.queryByRole('button', { name: '刷新状态' })).not.toBeInTheDocument();
    expect(props.onRetry).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: '在这台机器上开新局' })).toBeEnabled();
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
    expect(props.onContinue).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: '在这台机器上开新局' })).toBeEnabled();
  });

  it('成绩还在送的那一局，也能当场把占位夺回来', async () => {
    const user = userEvent.setup();
    const status = blockingStatus({
      game_id: 'game-4', state: 'pending_settlement', ownership: 'current_device', session_id: 'session-4',
      user_color: 'W', opponent_rank_name: '2段',
    });
    renderSetup(status);

    expect(screen.getByRole('button', { name: '在这台机器上开新局' })).toBeEnabled();
    // 下完了的局没有「继续」可言。
    expect(screen.queryByRole('button', { name: '继续对局' })).not.toBeInTheDocument();
  });

  it('supports the legacy pending-settlement flag without challenge controls', async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    renderSetup({ ...readyStatus, pending_settlement: true }, { onRetry });

    expect(screen.getByText('这一局已经下完，成绩还没送到云端。')).toBeInTheDocument();
    const actions = screen.getAllByRole('button');
    expect(actions).toHaveLength(1);
    expect(actions[0]).toHaveAccessibleName('刷新状态');
    await user.click(actions[0]);
    expect(onRetry).toHaveBeenCalledOnce();
    expect(screen.queryByText('智星棋手')).not.toBeInTheDocument();
    expect(screen.queryByText('选择执子')).not.toBeInTheDocument();
    // 「刷新状态」不在禁列里 —— 这一格本来就该有它,上面正断言它在。
    expect(screen.queryByRole('button', { name: /继续对局|在这台机器上开新局|立即重试/ })).not.toBeInTheDocument();
  });

  it('treats an explicit null blocking game as authoritative over a stale legacy flag', () => {
    renderSetup({ ...readyStatus, pending_settlement: true, blocking_game: null });

    expect(screen.queryByText('这一局已经下完，成绩还没送到云端。')).not.toBeInTheDocument();
    expect(screen.getByText('本局挑战')).toBeInTheDocument();
    expect(screen.getByText('智星棋手')).toBeInTheDocument();
    expect(screen.getByText('选择执子')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '开始正式对局' })).toBeInTheDocument();
  });

  it('keeps the settlement receipt visible after the blocking game disappears', () => {
    renderSetup(
      { ...readyStatus, pending_settlement: true },
      { lifecycleReceipt: { counted: false, reason: 'engine_unavailable' } },
    );

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

  it('keeps a settlement receipt visible while status is loading', () => {
    renderReceiptStatus({ view_state: 'loading' }, { counted: true, reason: null });

    expect(screen.getByText('结算已完成')).toBeInTheDocument();
    expect(screen.getByText(/本局已计入升降级/)).toBeInTheDocument();
  });

  it('keeps a settlement receipt above an error status', () => {
    renderReceiptStatus(
      { view_state: 'error', message: '状态刷新失败' },
      { counted: false, reason: 'engine_unavailable' },
    );

    expect(screen.getByText('结算已完成')).toBeInTheDocument();
    expect(screen.getByText(/本局不计入升降级/)).toBeInTheDocument();
    expect(screen.queryByText('状态刷新失败')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '重试' })).not.toBeInTheDocument();
  });

  it('keeps lifecycle state visible and disables both actions while pending', () => {
    const status = blockingStatus({
      game_id: 'game-6', state: 'active', ownership: 'current_device', session_id: 'session-6',
      user_color: 'B', opponent_rank_name: '1段',
    });
    renderSetup(status, { lifecyclePending: true, lifecycleError: '结束对局失败，请稍后重试' });

    expect(screen.getByRole('alert')).toHaveTextContent('结束对局失败，请稍后重试');
    expect(screen.getByRole('button', { name: '继续对局' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '在这台机器上开新局' })).toBeDisabled();
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
    expect(screen.getByText('未完成对局')).toBeInTheDocument();
  });

  it('safely disables lifecycle actions when a legacy caller omits the new props', () => {
    const status = blockingStatus({
      game_id: 'game-legacy', state: 'active', ownership: 'current_device', session_id: 'session-legacy',
      user_color: 'B', opponent_rank_name: '1段',
    });

    render(
      <AiLadderRatedSetup
        status={status}
        color="B"
        mainTime={10}
        byoLength={30}
        byoPeriods={3}
        startPending={false}
        onColorChange={vi.fn()}
        onRetry={vi.fn()}
        onStart={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: '继续对局' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '在这台机器上开新局' })).toBeDisabled();
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  });

  it('closes the end-game confirmation with Escape without ending the game', async () => {
    const user = userEvent.setup();
    const status = blockingStatus({
      game_id: 'game-7', state: 'active', ownership: 'current_device', session_id: 'session-7',
      user_color: 'B', opponent_rank_name: '1段',
    });
    const { props } = renderSetup(status);

    await user.click(screen.getByRole('button', { name: '在这台机器上开新局' }));
    await user.keyboard('{Escape}');

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(props.onEndGame).not.toHaveBeenCalled();
  });

  it('invalidates the captured end-game target when authoritative lifecycle state changes', async () => {
    const user = userEvent.setup();
    const onEndGame = vi.fn();
    const commonProps = {
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
      onEndGame,
    };
    const gameA = blockingStatus({
      game_id: 'game-a', state: 'active', ownership: 'current_device', session_id: 'session-a',
      user_color: 'B', opponent_rank_name: '1段',
    });
    const gameB = blockingStatus({
      game_id: 'game-b', state: 'active', ownership: 'current_device', session_id: 'session-b',
      user_color: 'W', opponent_rank_name: '2段',
    });
    const view = render(<AiLadderRatedSetup {...commonProps} status={gameA} />);

    await user.click(screen.getByRole('button', { name: '在这台机器上开新局' }));
    view.rerender(<AiLadderRatedSetup {...commonProps} status={gameB} />);
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(onEndGame).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: '在这台机器上开新局' }));
    view.rerender(<AiLadderRatedSetup {...commonProps} status={readyStatus} />);
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(onEndGame).not.toHaveBeenCalled();

    view.rerender(<AiLadderRatedSetup {...commonProps} status={gameB} />);
    await user.click(screen.getByRole('button', { name: '在这台机器上开新局' }));
    view.rerender(
      <AiLadderRatedSetup
        {...commonProps}
        status={gameB}
        lifecycleReceipt={{ counted: true, reason: null }}
      />,
    );
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());

    view.rerender(<AiLadderRatedSetup {...commonProps} status={gameB} />);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(onEndGame).not.toHaveBeenCalled();
  });

  it('同一局在弹窗开着时转成「成绩未送达」，代价那句话当场改口', async () => {
    const user = userEvent.setup();
    const onEndGame = vi.fn();
    const active = blockingStatus({
      game_id: 'game-a', state: 'active', ownership: 'current_device', session_id: 'session-a',
      user_color: 'B', opponent_rank_name: '1段',
    });
    const pending = blockingStatus({
      game_id: 'game-a', state: 'pending_settlement', ownership: 'current_device', session_id: 'session-a',
      user_color: 'B', opponent_rank_name: '1段',
    });
    const { props, rerender } = renderSetup(active, { onEndGame });

    await user.click(screen.getByRole('button', { name: '在这台机器上开新局' }));
    expect(screen.getByText(/它将计为本局负并计入升降级/)).toBeInTheDocument();

    // 代价每次都从**当下**这份数据算,不在按下的那一刻抄一份存起来 —— 否则用户会
    // 照着一句已经不成立的话按下去。
    rerender(<AiLadderRatedSetup {...props} status={pending} />);
    await waitFor(() => expect(
      within(screen.getByRole('dialog')).getByText(/那一局不计入本次开局/),
    ).toBeInTheDocument());
    expect(screen.queryByText(/它将计为本局负并计入升降级/)).not.toBeInTheDocument();
    expect(onEndGame).not.toHaveBeenCalled();
  });

  it('成绩还在送：屏上说清第几次重试、下一次还有多久', () => {
    const status = blockingStatus({
      game_id: 'game-a', state: 'pending_settlement', ownership: 'current_device',
      user_color: 'B', opponent_rank_name: '1段',
      sync: {
        state: 'waiting', attempt: 2, max_attempts: 5, next_attempt_in_seconds: 252,
        last_http_status: null, last_error: 'timeout',
      },
    });
    renderSetup(status, { onRetrySettlement: vi.fn() });

    expect(screen.getByText('这一局已经下完，成绩还没送到云端。')).toBeInTheDocument();
    expect(screen.getByText('重试 2/5 · 4:12 后自动重试')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '立即重试' })).toBeEnabled();
  });

  it('倒计时走完就改口说「即将重试」，不停在一个 0:00 上', async () => {
    vi.useFakeTimers();
    try {
      const status = blockingStatus({
        game_id: 'game-a', state: 'pending_settlement', ownership: 'current_device',
        user_color: 'B', opponent_rank_name: '1段',
        sync: {
          state: 'waiting', attempt: 3, max_attempts: 5, next_attempt_in_seconds: 3,
          last_http_status: null, last_error: null,
        },
      });
      renderSetup(status, { onRetrySettlement: vi.fn() });
      expect(screen.getByText('重试 3/5 · 0:03 后自动重试')).toBeInTheDocument();

      // 只推进时钟，**不重新渲染、不给新数据** —— 走秒不依赖任何一次往返。
      await act(async () => { vi.advanceTimersByTime(4000); });

      // 队列每 60 秒排空一次,到期只保证「下一轮会带上它」,不保证此刻正在发。
      expect(screen.getByText('重试 3/5 · 即将重试…')).toBeInTheDocument();
      expect(screen.queryByText(/0:00/)).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it('立即重试把这一局报上去，等待期间按钮自己说明它在忙', async () => {
    const user = userEvent.setup();
    const onRetrySettlement = vi.fn();
    const status = blockingStatus({
      game_id: 'game-a', state: 'pending_settlement', ownership: 'current_device',
      user_color: 'B', opponent_rank_name: '1段',
      sync: {
        state: 'exhausted', attempt: 5, max_attempts: 5, next_attempt_in_seconds: null,
        last_http_status: null, last_error: 'connection refused',
      },
    });
    const { rerender, props } = renderSetup(status, { onRetrySettlement });

    expect(screen.getByText('连试 5 次都没送到。恢复联网后会自动继续送。')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '立即重试' }));
    expect(onRetrySettlement).toHaveBeenCalledWith('game-a');

    rerender(<AiLadderRatedSetup {...props} status={status} syncRetryPending />);
    expect(screen.getByRole('button', { name: '正在重试…' })).toBeDisabled();
  });

  it('云端在事实上拒收的成绩不给重试按钮，代价那句话也跟着改', () => {
    // 422 问一百遍还是 422。给一个按不出结果的按钮，比不给更坏；
    // 而「成绩送到了仍然算」对一份永远送不到的成绩是假话。
    const status = blockingStatus({
      game_id: 'game-a', state: 'pending_settlement', ownership: 'current_device',
      user_color: 'B', opponent_rank_name: '1段',
      sync: {
        state: 'refused', attempt: 1, max_attempts: 5, next_attempt_in_seconds: null,
        last_http_status: 422, last_error: 'HTTP 422',
      },
    });
    renderSetup(status, { onRetrySettlement: vi.fn() });

    expect(screen.queryByRole('button', { name: '立即重试' })).not.toBeInTheDocument();
    expect(screen.getByText('云端拒收了这一局的成绩（HTTP 422），再试也是同一个答复。')).toBeInTheDocument();
    expect(screen.getByText('那一局不计入升降级，段位不变')).toBeInTheDocument();
  });

  it('网页直连没有 outbox：不发 sync，就不摆重试按钮', () => {
    const status = blockingStatus({
      game_id: 'game-a', state: 'pending_settlement', ownership: 'other_device',
      user_color: 'B', opponent_rank_name: '1段',
    });
    renderSetup(status);

    expect(screen.queryByRole('button', { name: '立即重试' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '在这台机器上开新局' })).toBeEnabled();
    expect(screen.getByText('那一局不计入本次开局；成绩送到了仍按它真实的结果计算')).toBeInTheDocument();
  });

  it('这一格属于本机、却接不回来时，开新局仍然露出来', () => {
    // 盒子中途重启:局接不回来（没有 session_id）。
    const status = blockingStatus({
      game_id: 'game-a', state: 'active', ownership: 'current_device',
      user_color: 'B', opponent_rank_name: '1段',
    });
    renderSetup(status);

    expect(screen.getByText('这一局在本机开始，但本机的对局进程已经不在了 —— 接不回来。')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '在这台机器上开新局' })).toBeEnabled();
    expect(screen.getByText('那一局会记为本局负，并计入升降级')).toBeInTheDocument();
    expect(screen.getByText('已中断')).toBeInTheDocument();
  });
});
