import { act, render, screen, waitFor } from '@testing-library/react';
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
): AiLadderReadyStatus => ({
  ...readyStatus,
  // 出路字段默认按「门已经开着」补齐 —— 服务端在那一格发的正是
  // `can_force_resign: true` + 时长 `null`(此刻就能按,没什么可数)。
  // 不补的话这些用例测的是一个服务端**不会发**的形状:一扇既按不动、又没有期限的门,
  // 而按契约那种门根本不该出现在屏上。用例覆盖的取值仍由各自的 fixture 覆写。
  blocking_game: {
    can_force_resign: blockingGame.state === 'active',
    takeover_eligible_in_seconds: null,
    can_release_abandoned_settlement: blockingGame.state === 'pending_settlement',
    abandoned_settlement_eligible_in_seconds: null,
    ...blockingGame,
  },
});

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

    await user.click(screen.getByRole('button', { name: '认输并结束' }));
    expect(props.onEndGame).not.toHaveBeenCalled();
    expect(screen.getByText('这一局将按你认输处理，计为本局负，并计入升降级。此操作不可撤销。')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '取消' })).toHaveFocus();

    await user.click(screen.getByRole('button', { name: '取消' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(props.onEndGame).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: '认输并结束' }));
    await user.click(screen.getByRole('button', { name: '确认认输' }));
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
    expect(screen.getByRole('button', { name: '认输并结束' })).toBeEnabled();
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
    await user.click(screen.getByRole('button', { name: '刷新状态' }));
    expect(props.onRetry).toHaveBeenCalledOnce();
    expect(props.onContinue).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: '认输并结束' })).toBeEnabled();
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
    expect(screen.queryByRole('button', { name: '认输并结束' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '继续对局' })).not.toBeInTheDocument();
  });

  it('supports the legacy pending-settlement flag without challenge controls', async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    renderSetup({ ...readyStatus, pending_settlement: true }, { onRetry });

    expect(screen.getByText('本局已经下完，成绩还没送到云端。系统会一直重试。')).toBeInTheDocument();
    const actions = screen.getAllByRole('button');
    expect(actions).toHaveLength(1);
    expect(actions[0]).toHaveAccessibleName('刷新状态');
    await user.click(actions[0]);
    expect(onRetry).toHaveBeenCalledOnce();
    expect(screen.queryByText('智星棋手')).not.toBeInTheDocument();
    expect(screen.queryByText('选择执子')).not.toBeInTheDocument();
    // 「刷新状态」不在禁列里 —— 这一格本来就该有它,上面第 172 行正断言它在。
    // (我做批量改名时顺手把它加进了禁列,于是同一条测试自相矛盾。)
    expect(screen.queryByRole('button', { name: /继续对局|认输并结束|放弃等待成绩/ })).not.toBeInTheDocument();
  });

  it('treats an explicit null blocking game as authoritative over a stale legacy flag', () => {
    renderSetup({ ...readyStatus, pending_settlement: true, blocking_game: null });

    expect(screen.queryByText('本局已经下完，成绩还没送到云端。系统会一直重试。')).not.toBeInTheDocument();
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
    expect(screen.getByRole('button', { name: '认输并结束' })).toBeDisabled();
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
    expect(screen.getByRole('button', { name: '认输并结束' })).toBeDisabled();
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
  });

  it('closes the end-game confirmation with Escape without ending the game', async () => {
    const user = userEvent.setup();
    const status = blockingStatus({
      game_id: 'game-7', state: 'active', ownership: 'current_device', session_id: 'session-7',
      user_color: 'B', opponent_rank_name: '1段',
    });
    const { props } = renderSetup(status);

    await user.click(screen.getByRole('button', { name: '认输并结束' }));
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

    await user.click(screen.getByRole('button', { name: '认输并结束' }));
    view.rerender(<AiLadderRatedSetup {...commonProps} status={gameB} />);
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(onEndGame).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: '认输并结束' }));
    view.rerender(<AiLadderRatedSetup {...commonProps} status={readyStatus} />);
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(onEndGame).not.toHaveBeenCalled();

    view.rerender(<AiLadderRatedSetup {...commonProps} status={gameB} />);
    await user.click(screen.getByRole('button', { name: '认输并结束' }));
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

  it('invalidates the end-game target when the same game starts settling', async () => {
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

    await user.click(screen.getByRole('button', { name: '认输并结束' }));
    rerender(<AiLadderRatedSetup {...props} status={pending} />);

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(onEndGame).not.toHaveBeenCalled();
  });

  it('没到点的门是禁用的，并且在下面走秒', async () => {
    // 服务端在这一格发的是 `can_force_resign:false` + 一个真时长。屏上必须给出期限，
    // 而不是一个按下去 409、也不说什么时候能按的按钮。
    const status = blockingStatus({
      game_id: 'game-a', state: 'active', ownership: 'other_device',
      user_color: 'B', opponent_rank_name: '1段',
      can_force_resign: false, takeover_eligible_in_seconds: 252,
    });
    renderSetup(status);

    expect(screen.getByRole('button', { name: '认输并结束' })).toBeDisabled();
    expect(screen.getByText('4:12 后可用')).toBeInTheDocument();
    // 后果那句在没到点的时候不该出现 —— 那一刻要说的是「还要等多久」。
    expect(screen.queryByText('按认输计入本局，段位会变')).not.toBeInTheDocument();
  });

  it('倒计时走完，按钮自己变成可用 —— 不用等下一次刷新', async () => {
    vi.useFakeTimers();
    try {
      const status = blockingStatus({
        game_id: 'game-a', state: 'active', ownership: 'other_device',
        user_color: 'B', opponent_rank_name: '1段',
        can_force_resign: false, takeover_eligible_in_seconds: 3,
      });
      renderSetup(status);
      expect(screen.getByRole('button', { name: '认输并结束' })).toBeDisabled();

      // 只推进时钟，**不重新渲染、不给新数据** —— 这正是要证的:门开不依赖任何一次往返。
      await act(async () => { vi.advanceTimersByTime(4000); });

      expect(screen.getByRole('button', { name: '认输并结束' })).toBeEnabled();
      expect(screen.getByText('按认输计入本局，段位会变')).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it('放弃等待是另一笔买卖：动词、后果、弹窗都跟认输不一样', async () => {
    const user = userEvent.setup();
    const onEndGame = vi.fn();
    const status = blockingStatus({
      game_id: 'game-a', state: 'pending_settlement', ownership: 'current_device',
      user_color: 'B', opponent_rank_name: '1段',
      can_release_abandoned_settlement: true, abandoned_settlement_eligible_in_seconds: null,
    });
    renderSetup(status, { onEndGame });

    // 认输那扇门在这一格不存在 —— 服务端会直接拒（结果已在投递中，认输会把它顶掉）。
    expect(screen.queryByRole('button', { name: '认输并结束' })).not.toBeInTheDocument();
    expect(screen.getByText('本局作废，不计入升降级，段位不变')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '放弃等待成绩' }));
    // 弹窗必须说清这一笔**什么都不记** —— 跟认输共用一句话，就等于把两笔买卖说成一笔。
    expect(screen.getByText(/本局作废、不计入升降级、段位不变/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '确认放弃等待' }));
    expect(onEndGame).toHaveBeenCalledWith('game-a');
  });

  it('这一格属于本机、却接不回来时，出路仍然露出来', async () => {
    // 盒子中途重启:局接不回来（没有 session_id），而服务端答的是「此刻就能认输」。
    const status = blockingStatus({
      game_id: 'game-a', state: 'active', ownership: 'current_device',
      user_color: 'B', opponent_rank_name: '1段',
      can_force_resign: true, takeover_eligible_in_seconds: null,
    });
    renderSetup(status);

    expect(screen.getByText('这一局在本机开始，但本机的对局进程已经不在了 —— 接不回来。')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '认输并结束' })).toBeEnabled();
    expect(screen.getByText('已中断')).toBeInTheDocument();
  });

  it('等不来的门根本不画出来 —— 不是画一个永远按不动的', async () => {
    const status = blockingStatus({
      game_id: 'game-a', state: 'active', ownership: 'other_device',
      user_color: 'B', opponent_rank_name: '1段',
      can_force_resign: false, takeover_eligible_in_seconds: null,
      can_release_abandoned_settlement: false, abandoned_settlement_eligible_in_seconds: null,
    });
    renderSetup(status);

    expect(screen.queryByRole('button', { name: '认输并结束' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '放弃等待成绩' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '刷新状态' })).toBeEnabled();
  });
});
