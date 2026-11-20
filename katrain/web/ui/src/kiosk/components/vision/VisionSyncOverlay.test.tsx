import { StrictMode } from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { VisionSyncEvent } from '../../hooks/useVisionSync';
import VisionSyncOverlay from './VisionSyncOverlay';

const mocks = vi.hoisted(() => ({
  playMove: vi.fn().mockResolvedValue(undefined),
  visionResetSync: vi.fn().mockResolvedValue(undefined),
  visionVerifySync: vi.fn(),
  refreshState: vi.fn(),
  visionDenyStone: vi.fn().mockResolvedValue(undefined),
  translate: vi.fn((_key: string, fallback?: string) => fallback ?? ''),
  voiceSpeak: vi.fn(),
  voiceStop: vi.fn(),
}));

vi.mock('../../../api', () => ({ API: mocks }));
vi.mock('../../../hooks/useTranslation', () => ({
  useTranslation: () => ({ t: mocks.translate }),
}));
vi.mock('../../hooks/useVoice', () => ({
  useVoice: () => ({ speak: mocks.voiceSpeak, stop: mocks.voiceStop }),
}));

const event = (seq: number, type: VisionSyncEvent['type'], data: Record<string, unknown> = {}): VisionSyncEvent => ({
  seq, type, data,
});

const props = {
  onDismiss: vi.fn(),
  sessionId: 'session-1',
  gameId: 'game-1',
  onRefreshState: mocks.refreshState,
  boardSize: 19,
  playerToMove: 'B',
  currentNodeId: 10,
};

const dialogCount = () => screen.queryAllByRole('dialog').length;

describe('VisionSyncOverlay recovery presentation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.visionVerifySync.mockResolvedValue({ ok: true, recovery_id: 'r1', session_id: 'session-1', game_id: 'game-1', current_node_id: 16 });
    mocks.refreshState.mockResolvedValue('applied');
    mocks.translate.mockImplementation((_key: string, fallback?: string) => fallback ?? '');
  });
  afterEach(() => vi.useRealTimers());

  it('refreshes open board-loss and capture copy without replaying recovery actions', () => {
    vi.useFakeTimers();
    const en: Record<string, string> = {
      '棋盘检测异常': 'Board detection issue',
      '请提走棋子': 'Remove captured stones',
      '请提走 {stones}': 'Remove {stones}',
      '{count} 颗黑子': '{count} black stones',
    };
    const ko: Record<string, string> = {
      '棋盘检测异常': '바둑판 인식 오류',
      '请提走棋子': '잡은 돌을 치우세요',
      '请提走 {stones}': '{stones} 치우세요',
      '{count} 颗黑子': '흑돌 {count}개',
    };
    mocks.translate.mockImplementation((key, fallback) => en[key] ?? fallback ?? key);
    const lost = event(1, 'board_lost');
    const { rerender } = render(<VisionSyncOverlay {...props} syncEvents={[lost]} />);
    act(() => vi.advanceTimersByTime(10_000));
    expect(screen.getByText('Board detection issue')).toBeInTheDocument();
    mocks.translate.mockImplementation((key, fallback) => ko[key] ?? fallback ?? key);
    rerender(<VisionSyncOverlay {...props} syncEvents={[lost]} />);
    expect(screen.getByText('바둑판 인식 오류')).toBeInTheDocument();
    const captured = event(2, 'capture_pending', { positions: [[7, 7, 1], [8, 8, 1]] });
    rerender(<VisionSyncOverlay {...props} syncEvents={[lost, captured]} />);
    expect(screen.getByText('잡은 돌을 치우세요')).toBeInTheDocument();
    expect(screen.getByText('흑돌 2개 치우세요')).toBeInTheDocument();
    expect(mocks.playMove).not.toHaveBeenCalled();
    expect(mocks.visionResetSync).not.toHaveBeenCalled();
  });

  it('does not re-prompt for the stone already submitted to a waiting platform', async () => {
    const mismatch = event(1, 'illegal_change', { positions: [[4, 5, 1]], missing: [] });
    const { rerender } = render(
      <VisionSyncOverlay {...props} syncEvents={[mismatch]}
        platformPendingStone={{ row: 4, col: 5, color: 1 }} />,
    );
    expect(screen.queryByText('盘面与对局不一致')).toBeNull();

    rerender(<VisionSyncOverlay {...props} syncEvents={[mismatch, { ...mismatch, seq: 2 }]}
      platformPendingStone={null} />);
    expect(await screen.findByText('盘面与对局不一致')).toBeInTheDocument();
  });

  it('shows an off-centre prompt as the only dialog and does not adopt it when dismissed', async () => {
    render(
      <VisionSyncOverlay
        {...props}
        syncEvents={[
          event(1, 'illegal_change', { positions: [[1, 1, 1]], missing: [] }),
          event(2, 'ambiguous_stone', { row: 3, col: 3, color: 1, unbacked: true }),
        ]}
      />,
    );

    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('黑 子没放正')).toBeInTheDocument();
    expect(screen.queryByText('盘面与对局不一致')).toBeNull();
    expect(dialogCount()).toBe(1);

    fireEvent.click(screen.getByRole('button', { name: '我挪一下' }));
    // 摆偏的那一颗**确实是子**,只是没放正。把它记成「这儿没有子」会在用户挪正之后
    // 反过来压住那颗真子 —— 所以这一档不许发否认。
    expect(mocks.visionDenyStone).not.toHaveBeenCalled();
    expect(mocks.visionResetSync).not.toHaveBeenCalled();
    await waitFor(() => expect(screen.queryByRole('button', { name: '我挪一下' })).toBeNull());
  });

  it('低置信度那一档说「不是落子」,而且按下去发的是否认、不是「把现状收进基线」', async () => {
    render(
      <VisionSyncOverlay
        {...props}
        syncEvents={[event(1, 'ambiguous_stone', { row: 3, col: 3, color: 1, unbacked: false })]}
      />,
    );

    expect(await screen.findByText(/检测到疑似落子/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '不是落子' }));
    expect(mocks.visionDenyStone).toHaveBeenCalledWith(3, 3);
    // adopt='physical' 会把假阳性收进基线当成现实,而且 RESET_SYNC 顺手销毁参考帧 ——
    // 用户每按一次就把唯一能按像素否决反光的证据毁掉一次。这条路必须不再被走。
    expect(mocks.visionResetSync).not.toHaveBeenCalled();
  });

  it('uses the shared denial feedback for a single extra stone in a mismatch', async () => {
    const mismatch = event(1, 'illegal_change', { positions: [[2, 10, 1]], missing: [] });
    const { rerender } = render(<VisionSyncOverlay {...props} syncEvents={[mismatch]} />);

    fireEvent.click(await screen.findByRole('button', { name: '不是落子' }));
    expect(mocks.visionDenyStone).toHaveBeenCalledWith(2, 10);
    expect(mocks.visionResetSync).not.toHaveBeenCalled();

    rerender(<VisionSyncOverlay {...props} syncEvents={[mismatch, { ...mismatch, seq: 2 }]} />);
    expect(screen.queryByText('盘面与对局不一致')).toBeNull();

    rerender(<VisionSyncOverlay {...props} syncEvents={[mismatch, { ...mismatch, seq: 2 },
      event(3, 'illegal_change', { positions: [[3, 10, 1]], missing: [] })]} />);
    expect(await screen.findByText('盘面与对局不一致')).toBeInTheDocument();
  });

  it('reports mismatch points to the digital board and clears them on sync', async () => {
    const onAttentionChange = vi.fn();
    const mismatch = event(1, 'illegal_change', {
      positions: [[2, 10, 1]], missing: [[4, 6, 2]],
    });
    const { rerender } = render(<VisionSyncOverlay {...props} onAttentionChange={onAttentionChange} syncEvents={[mismatch]} />);
    await waitFor(() => expect(onAttentionChange).toHaveBeenCalledWith([{ row: 2, col: 10 }, { row: 4, col: 6 }]));

    rerender(<VisionSyncOverlay {...props} onAttentionChange={onAttentionChange}
      syncEvents={[mismatch, event(2, 'synced')]} />);
    await waitFor(() => expect(onAttentionChange).toHaveBeenLastCalledWith([]));
  });

  it('announces an off-centre stone once across unchanged and unrelated rerenders', async () => {
    const stone = event(1, 'ambiguous_stone', { row: 3, col: 3, color: 1, unbacked: true });
    const { rerender } = render(<VisionSyncOverlay {...props} syncEvents={[stone]} />);

    await waitFor(() => expect(mocks.voiceSpeak).toHaveBeenCalledWith('stone_offcenter'));
    expect(mocks.voiceSpeak).toHaveBeenCalledTimes(1);

    rerender(<VisionSyncOverlay {...props} syncEvents={[stone]} />);
    expect(mocks.voiceSpeak).toHaveBeenCalledTimes(1);

    rerender(<VisionSyncOverlay {...props} syncEvents={[stone, event(2, 'degraded')]} />);
    expect(mocks.voiceSpeak).toHaveBeenCalledTimes(1);
  });

  it('announces a suspected move once', async () => {
    render(
      <VisionSyncOverlay
        {...props}
        syncEvents={[event(1, 'ambiguous_stone', { row: 3, col: 3, color: 1, unbacked: false })]}
      />,
    );

    await waitFor(() => expect(mocks.voiceSpeak).toHaveBeenCalledWith('suspected_move'));
    expect(mocks.voiceSpeak).toHaveBeenCalledTimes(1);
  });

  it('announces another stone target even when it uses the same voice line', async () => {
    const first = event(1, 'ambiguous_stone', { row: 3, col: 3, color: 1, unbacked: false });
    const { rerender } = render(<VisionSyncOverlay {...props} syncEvents={[first]} />);
    await waitFor(() => expect(mocks.voiceSpeak).toHaveBeenCalledTimes(1));

    rerender(
      <VisionSyncOverlay
        {...props}
        syncEvents={[first, event(2, 'ambiguous_stone', { row: 4, col: 5, color: 1, unbacked: false })]}
      />,
    );

    await waitFor(() => expect(mocks.voiceSpeak).toHaveBeenCalledTimes(2));
    expect(mocks.voiceSpeak).toHaveBeenNthCalledWith(2, 'suspected_move');
  });

  it('stops a cleared prompt and allows the same target to be announced again', async () => {
    const stone = event(1, 'ambiguous_stone', { row: 3, col: 3, color: 1, unbacked: true });
    const { rerender } = render(<VisionSyncOverlay {...props} syncEvents={[stone]} />);
    await waitFor(() => expect(mocks.voiceSpeak).toHaveBeenCalledTimes(1));

    rerender(<VisionSyncOverlay {...props} syncEvents={[stone, event(2, 'synced')]} />);
    await waitFor(() => expect(mocks.voiceStop).toHaveBeenCalledTimes(1));

    rerender(
      <VisionSyncOverlay
        {...props}
        syncEvents={[stone, event(2, 'synced'), { ...stone, seq: 3 }]}
      />,
    );
    await waitFor(() => expect(mocks.voiceSpeak).toHaveBeenCalledTimes(2));
    expect(mocks.voiceSpeak).toHaveBeenNthCalledWith(2, 'stone_offcenter');
  });

  it.each([
    ['capture recovery', event(1, 'capture_pending', { positions: [[7, 7, 2]] })],
    ['toast', event(1, 'degraded')],
  ])('keeps %s silent', (_name, syncEvent) => {
    render(<VisionSyncOverlay {...props} syncEvents={[syncEvent]} />);

    expect(mocks.voiceSpeak).not.toHaveBeenCalled();
  });

  it('announces a mismatch once while the same recovery stays visible', async () => {
    const mismatch = event(1, 'illegal_change', { positions: [[5, 5, 1]], missing: [] });
    const { rerender } = render(<VisionSyncOverlay {...props} syncEvents={[mismatch]} />);
    await waitFor(() => expect(mocks.voiceSpeak).toHaveBeenCalledWith('board_mismatch'));
    rerender(<VisionSyncOverlay {...props} syncEvents={[mismatch, { ...mismatch, seq: 2 }]} />);
    expect(mocks.voiceSpeak).toHaveBeenCalledTimes(1);
  });

  it('keeps persistent board loss silent', () => {
    vi.useFakeTimers();
    render(<VisionSyncOverlay {...props} syncEvents={[event(1, 'board_lost')]} />);
    act(() => vi.advanceTimersByTime(10_000));

    expect(screen.getByText('棋盘检测异常')).toBeInTheDocument();
    expect(mocks.voiceSpeak).not.toHaveBeenCalled();
  });

  it('silently recovers brief board-loss episodes during ordinary play', () => {
    vi.useFakeTimers();
    const history: VisionSyncEvent[] = [];
    const { rerender } = render(<VisionSyncOverlay {...props} syncEvents={[]} />);

    for (let index = 0; index < 3; index += 1) {
      history.push(event(index * 2 + 1, 'board_lost'));
      rerender(<VisionSyncOverlay {...props} syncEvents={[...history]} />);
      act(() => vi.advanceTimersByTime(500));
      history.push(event(index * 2 + 2, 'board_reacquired'));
      rerender(<VisionSyncOverlay {...props} syncEvents={[...history]} />);
      expect(screen.queryByText('棋盘已重新检测到')).toBeNull();
      expect(screen.queryByText('棋盘检测异常')).toBeNull();
    }
    act(() => vi.advanceTimersByTime(10_000));
    expect(screen.queryByText('棋盘检测异常')).toBeNull();
  });

  it('confirms recovery once after persistent board loss', () => {
    vi.useFakeTimers();
    const lost = event(1, 'board_lost');
    const recovered = event(2, 'board_reacquired');
    const { rerender } = render(<VisionSyncOverlay {...props} syncEvents={[lost]} />);
    act(() => vi.advanceTimersByTime(10_000));
    expect(screen.getByText('棋盘检测异常')).toBeInTheDocument();

    rerender(<VisionSyncOverlay {...props} syncEvents={[lost, recovered]} />);
    expect(screen.getByText('棋盘已重新检测到')).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(5_000));
    act(() => vi.advanceTimersByTime(500));
    expect(screen.queryByText('棋盘已重新检测到')).toBeNull();
    expect(screen.queryByText('棋盘检测异常')).toBeNull();

    rerender(<VisionSyncOverlay {...props} syncEvents={[lost, recovered, event(3, 'board_reacquired')]} />);
    expect(screen.queryByText('棋盘已重新检测到')).toBeNull();
  });

  it('keeps the loss episode active when an unrelated move candidate arrives', () => {
    vi.useFakeTimers();
    const lost = event(1, 'board_lost');
    const pending = event(2, 'move_pending', { row: 3, col: 3, color: 1 });
    const { rerender } = render(<VisionSyncOverlay {...props} syncEvents={[lost]} />);
    act(() => vi.advanceTimersByTime(5_000));
    rerender(<VisionSyncOverlay {...props} syncEvents={[lost, pending]} />);
    act(() => vi.advanceTimersByTime(5_000));
    expect(screen.getByText('棋盘检测异常')).toBeInTheDocument();

    rerender(<VisionSyncOverlay {...props} syncEvents={[lost, pending, event(3, 'board_reacquired')]} />);
    expect(screen.getByText('棋盘已重新检测到')).toBeInTheDocument();
  });

  it('stops the stone prompt when capture recovery takes over', async () => {
    const stone = event(1, 'ambiguous_stone', { row: 3, col: 3, color: 1, unbacked: true });
    const { rerender } = render(<VisionSyncOverlay {...props} syncEvents={[stone]} />);
    await waitFor(() => expect(mocks.voiceSpeak).toHaveBeenCalledTimes(1));

    rerender(
      <VisionSyncOverlay
        {...props}
        syncEvents={[stone, event(2, 'capture_pending', { positions: [[7, 7, 2]] })]}
      />,
    );

    await waitFor(() => expect(mocks.voiceStop).toHaveBeenCalledTimes(1));
    expect(mocks.voiceSpeak).toHaveBeenCalledTimes(1);
  });

  it('suppresses the exact pending mismatch for four seconds, then allows a later occurrence', () => {
    vi.useFakeTimers();
    const pending = event(1, 'move_pending', { row: 3, col: 4, color: 1 });
    const mismatch = event(2, 'illegal_change', { positions: [[3, 4, 1]], missing: [] });
    const { rerender } = render(<VisionSyncOverlay {...props} syncEvents={[pending, mismatch]} />);

    expect(screen.queryByText('盘面与对局不一致')).toBeNull();
    act(() => vi.advanceTimersByTime(4_000));
    rerender(<VisionSyncOverlay {...props} syncEvents={[pending, mismatch, { ...mismatch, seq: 3 }]} />);

    expect(screen.getByText('盘面与对局不一致')).toBeInTheDocument();
  });

  it('clears pending suppression when the current node changes', () => {
    const pending = event(1, 'move_pending', { row: 3, col: 4, color: 1 });
    const { rerender } = render(<VisionSyncOverlay {...props} syncEvents={[pending]} />);

    rerender(<VisionSyncOverlay {...props} currentNodeId={11} syncEvents={[pending]} />);
    rerender(
      <VisionSyncOverlay
        {...props}
        currentNodeId={11}
        syncEvents={[pending, event(2, 'illegal_change', { positions: [[3, 4, 1]], missing: [] })]}
      />,
    );

    expect(screen.getByText('盘面与对局不一致')).toBeInTheDocument();
  });

  it('turns an adjacent same-colour mismatch into a targeted relocation dialog', () => {
    render(
      <VisionSyncOverlay
        {...props}
        syncEvents={[event(1, 'illegal_change', { positions: [[18, 4, 2]], missing: [[18, 5, 2]] })]}
      />,
    );

    expect(screen.getByText('白子没放正，请从 E1 挪到 F1')).toBeInTheDocument();
    expect(screen.queryByText('盘面与对局不一致')).toBeNull();
    expect(dialogCount()).toBe(1);
    fireEvent.click(screen.getByRole('button', { name: '就下在 F1' }));
    expect(mocks.playMove).toHaveBeenCalledWith('session-1', { x: 5, y: 0 });
  });

  it('uses the localized stone label rather than appending 子 to 白棋', () => {
    mocks.translate.mockImplementation((key: string, fallback?: string) => {
      if (key === 'White') return '白棋';
      if (key === 'White Stone') return '○ 白';
      return fallback ?? '';
    });
    render(
      <VisionSyncOverlay
        {...props}
        syncEvents={[event(1, 'illegal_change', { positions: [[18, 4, 2]], missing: [[18, 5, 2]] })]}
      />,
    );

    expect(screen.getByText('白子没放正，请从 E1 挪到 F1')).toBeInTheDocument();
    expect(screen.queryByText(/白棋子没放正/)).toBeNull();
  });

  it.each([
    ['different colours', [[18, 4, 1]], [[18, 5, 2]]],
    ['non-adjacent points', [[18, 4, 2]], [[18, 6, 2]]],
    ['multiple stones', [[18, 4, 2], [17, 4, 2]], [[18, 5, 2]]],
  ])('keeps %s as a generic mismatch', (_name, positions, missing) => {
    render(<VisionSyncOverlay {...props} syncEvents={[event(1, 'illegal_change', { positions, missing })]} />);
    expect(screen.getByText('盘面与对局不一致')).toBeInTheDocument();
    expect(dialogCount()).toBe(1);
  });

  it('keeps at most one blocking dialog as higher-priority events arrive', () => {
    vi.useFakeTimers();
    const lost = event(1, 'board_lost');
    const mismatch = event(2, 'illegal_change', { positions: [[5, 5, 1]], missing: [] });
    const ambiguous = event(3, 'ambiguous_stone', { row: 5, col: 5, color: 1 });
    const capture = event(4, 'capture_pending', { positions: [[7, 7, 2]] });
    const { rerender } = render(<VisionSyncOverlay {...props} syncEvents={[lost]} />);
    act(() => vi.advanceTimersByTime(10_000));

    expect(screen.getByText('棋盘检测异常')).toBeInTheDocument();
    expect(dialogCount()).toBe(1);
    rerender(<VisionSyncOverlay {...props} syncEvents={[lost, mismatch]} />);
    expect(screen.getByText('盘面与对局不一致')).toBeInTheDocument();
    expect(dialogCount()).toBe(1);
    rerender(<VisionSyncOverlay {...props} syncEvents={[lost, mismatch, ambiguous]} />);
    expect(screen.getByText(/检测到疑似落子/)).toBeInTheDocument();
    expect(dialogCount()).toBe(1);
    rerender(<VisionSyncOverlay {...props} syncEvents={[lost, mismatch, ambiguous, capture]} />);
    expect(screen.getByText('请提走棋子')).toBeInTheDocument();
    expect(dialogCount()).toBe(1);
  });

  it('processes newly appended events after the event history has been trimmed past 100', () => {
    const history = Array.from({ length: 100 }, (_, index) => event(index + 1, 'move_confirmed'));
    const { rerender } = render(<VisionSyncOverlay {...props} syncEvents={history} />);
    const trimmed = [
      ...history.slice(1),
      event(101, 'illegal_change', { positions: [[2, 2, 1]], missing: [] }),
    ];
    rerender(<VisionSyncOverlay {...props} syncEvents={trimmed} />);

    expect(screen.getByText('盘面与对局不一致')).toBeInTheDocument();
  });

  it('keeps capture ownership after 30 seconds with no manual skip until captures clear', () => {
    vi.useFakeTimers();
    const capture = event(1, 'capture_pending', { positions: [[7, 7, 2]] });
    const { rerender } = render(<VisionSyncOverlay {...props} syncEvents={[capture]} />);
    act(() => vi.advanceTimersByTime(30_000));

    expect(screen.getByText('请提走棋子')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '跳过' })).toBeNull();
    rerender(<VisionSyncOverlay {...props} syncEvents={[capture, event(2, 'captures_cleared')]} />);
    expect(screen.queryByText('请提走棋子')).toBeNull();
  });

  it('synced verifies recovery and clears a persistent board-loss dialog', async () => {
    vi.useFakeTimers();
    const lost = event(1, 'board_lost');
    const { rerender } = render(<VisionSyncOverlay {...props} syncEvents={[lost]} />);
    act(() => vi.advanceTimersByTime(10_000));
    expect(screen.getByText('棋盘检测异常')).toBeInTheDocument();

    rerender(
      <VisionSyncOverlay
        {...props}
        syncEvents={[lost, event(2, 'illegal_change', { positions: [[2, 2, 1]], missing: [] }), event(3, 'synced')]}
      />,
    );
    await act(async () => { await vi.advanceTimersByTimeAsync(300); });

    expect(screen.queryByText('棋盘检测异常')).toBeNull();
    expect(screen.queryByText('盘面与对局不一致')).toBeNull();
    expect(dialogCount()).toBe(0);
  });

  it('shows the actionable shared mismatch while the platform still holds an uncertain send', async () => {
    const pending = event(1, 'move_pending', { row: 4, col: 5, color: 1 });
    const mismatch = event(2, 'illegal_change', { actionable: true, positions: [[4, 5, 1]], missing: [] });
    const { rerender } = render(
      <VisionSyncOverlay {...props} syncEvents={[pending, mismatch]}
        platformPendingStone={{ row: 4, col: 5, color: 1 }} />,
    );
    expect(await screen.findByText('盘面与对局不一致')).toBeInTheDocument();
    rerender(<VisionSyncOverlay {...props} currentNodeId={11} syncEvents={[pending, mismatch]}
      platformPendingStone={{ row: 4, col: 5, color: 1 }} />);
    expect(screen.getByText('盘面与对局不一致')).toBeInTheDocument();
    rerender(<VisionSyncOverlay {...props} currentNodeId={11} syncEvents={[pending, mismatch, event(3, 'synced')]}
      platformPendingStone={null} />);
    await waitFor(() => expect(screen.queryByText('盘面与对局不一致')).toBeNull());
  });
});


describe('scoped mismatch recovery', () => {
  const verified = { ok: true, recovery_id: 'r1', session_id: 'session-1', game_id: 'game-1', current_node_id: 16 };
  const mismatch = event(1, 'illegal_change', { positions: [], missing: [[1, 4, 2]] });
  const deferred = <T,>() => {
    let resolve!: (value: T) => void;
    const promise = new Promise<T>(done => { resolve = done; });
    return { promise, resolve };
  };
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.translate.mockImplementation((_key: string, fallback?: string) => fallback ?? '');
    mocks.visionVerifySync.mockResolvedValue(verified);
    mocks.refreshState.mockResolvedValue('applied');
  });
  afterEach(() => vi.useRealTimers());
  it('keeps one pending dialog until verification and refresh both complete; never adopts missing E18', async () => {
    const post = deferred<typeof verified>();
    const get = deferred<string>();
    mocks.visionVerifySync.mockReturnValue(post.promise);
    mocks.refreshState.mockReturnValue(get.promise);
    const { rerender } = render(<VisionSyncOverlay {...props} syncEvents={[mismatch]} />);
    fireEvent.click(screen.getByRole('button', { name: '已按提示调整' }));
    expect(screen.getByRole('button', { name: '正在核对盘面…' })).toBeDisabled();
    expect(mocks.refreshState).not.toHaveBeenCalled();
    rerender(<VisionSyncOverlay {...props} syncEvents={[mismatch, { ...mismatch, seq: 2 }, event(3, 'synced'), event(4, 'synced', { current_node_id: 15 })]} />);
    expect(dialogCount()).toBe(1);
    expect(mocks.visionVerifySync).toHaveBeenCalledTimes(1);
    await act(async () => { post.resolve(verified); });
    expect(mocks.refreshState).toHaveBeenCalledWith(verified);
    expect(screen.getByText('盘面与对局不一致')).toBeInTheDocument();
    await act(async () => { get.resolve('applied'); });
    await waitFor(() => expect(screen.queryByText('盘面与对局不一致')).toBeNull());
    expect(mocks.playMove).not.toHaveBeenCalled();
    rerender(<VisionSyncOverlay {...props} syncEvents={[mismatch, { ...mismatch, seq: 2 }, event(3, 'synced'), event(4, 'synced'), { ...mismatch, seq: 5 }]} />);
    expect(screen.queryByText('盘面与对局不一致')).toBeNull();
  });
  it('shows the same missing point after the successful recovery duplicate grace expires', async () => {
    vi.useFakeTimers();
    const { rerender } = render(<VisionSyncOverlay {...props} syncEvents={[mismatch]} />);
    fireEvent.click(screen.getByRole('button', { name: '已按提示调整' }));
    await act(async () => { await vi.advanceTimersByTimeAsync(300); });
    expect(screen.queryByText('盘面与对局不一致')).toBeNull();

    const immediateDuplicate = { ...mismatch, seq: 2 };
    rerender(<VisionSyncOverlay {...props} syncEvents={[mismatch, immediateDuplicate]} />);
    expect(screen.queryByText('盘面与对局不一致')).toBeNull();

    await act(async () => { await vi.advanceTimersByTimeAsync(7_000); });
    const laterLoss = { ...mismatch, seq: 3 };
    rerender(<VisionSyncOverlay {...props} syncEvents={[mismatch, immediateDuplicate, laterLoss]} />);
    expect(screen.getByText('盘面与对局不一致')).toBeInTheDocument();
    expect(dialogCount()).toBe(1);

    rerender(<VisionSyncOverlay {...props} syncEvents={[mismatch, immediateDuplicate, laterLoss, event(4, 'synced')]} />);
    await act(async () => { await vi.advanceTimersByTimeAsync(300); });
    expect(mocks.visionVerifySync).toHaveBeenCalledTimes(2);
    expect(screen.queryByText('盘面与对局不一致')).toBeNull();
    expect(mocks.playMove).not.toHaveBeenCalled();
  });
  it.each([{}, { current_node_id: 15 }, { game_id: 'old', current_node_id: 16 }])('treats synced %j only as a scoped verification trigger', async data => {
    const post = deferred<typeof verified>();
    mocks.visionVerifySync.mockReturnValue(post.promise);
    render(<VisionSyncOverlay {...props} syncEvents={[mismatch, event(2, 'synced', data)]} />);
    expect(mocks.visionVerifySync).toHaveBeenCalledWith('session-1', 'game-1');
    expect(mocks.refreshState).not.toHaveBeenCalled();
    expect(screen.getByText('盘面与对局不一致')).toBeInTheDocument();
    await act(async () => { post.resolve(verified); });
    await waitFor(() => expect(screen.queryByText('盘面与对局不一致')).toBeNull());
    expect(mocks.playMove).not.toHaveBeenCalled();
  });
  it('shows an explicit retry without looping automatically after failure', async () => {
    mocks.visionVerifySync.mockRejectedValueOnce(new Error('camera unavailable'));
    const { rerender } = render(<VisionSyncOverlay {...props} syncEvents={[mismatch, event(2, 'synced')]} />);
    expect(await screen.findByRole('alert')).toHaveTextContent(/重试/);
    rerender(<VisionSyncOverlay {...props} syncEvents={[mismatch, event(2, 'synced'), event(3, 'synced')]} />);
    expect(mocks.visionVerifySync).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole('button', { name: '重试核对' }));
    await waitFor(() => expect(screen.queryByText('盘面与对局不一致')).toBeNull());
    expect(mocks.visionVerifySync).toHaveBeenCalledTimes(2);
  });
  it.each([undefined, { ok: true }, { ...verified, ok: false }, { ...verified, recovery_id: '' },
    { ...verified, session_id: 'other' }, { ...verified, game_id: 'other' },
    { ...verified, current_node_id: -1 }, { ...verified, current_node_id: 1.5 },
  ])('does not refresh or complete for an incomplete response %j', async response => {
    mocks.visionVerifySync.mockResolvedValue(response);
    render(<VisionSyncOverlay {...props} syncEvents={[mismatch]} />);
    fireEvent.click(screen.getByRole('button', { name: '已按提示调整' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/重试/);
    expect(mocks.refreshState).not.toHaveBeenCalled();
    expect(screen.getByText('盘面与对局不一致')).toBeInTheDocument();
  });
  it.each(['superseded', 'error'])('keeps recovery retryable for a %s refresh', async outcome => {
    if (outcome === 'error') mocks.refreshState.mockRejectedValue(new Error('network'));
    else mocks.refreshState.mockResolvedValue(outcome);
    render(<VisionSyncOverlay {...props} syncEvents={[mismatch]} />);
    fireEvent.click(screen.getByRole('button', { name: '已按提示调整' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/重试/);
  });
  it.each(['session', 'game'])('ignores a late POST after %s changes', async kind => {
    const post = deferred<typeof verified>();
    mocks.visionVerifySync.mockReturnValue(post.promise);
    const { rerender } = render(<VisionSyncOverlay {...props} syncEvents={[mismatch]} />);
    fireEvent.click(screen.getByRole('button', { name: '已按提示调整' }));
    rerender(<VisionSyncOverlay {...props} sessionId={kind === 'session' ? 'session-2' : props.sessionId} gameId={kind === 'game' ? 'game-2' : props.gameId} syncEvents={[]} />);
    await act(async () => { post.resolve(verified); });
    expect(mocks.refreshState).not.toHaveBeenCalled();
    expect(screen.queryByText('盘面与对局不一致')).toBeNull();
  });
  it('keeps automatic recovery alive across effect cleanup/replay', async () => {
    const post = deferred<typeof verified>();
    mocks.visionVerifySync.mockReturnValue(post.promise);
    render(<StrictMode><VisionSyncOverlay {...props} syncEvents={[mismatch, event(2, 'synced')]} /></StrictMode>);
    await act(async () => { post.resolve(verified); });
    await waitFor(() => expect(screen.queryByText('盘面与对局不一致')).toBeNull());
    expect(mocks.refreshState).toHaveBeenCalledTimes(1);
  });
  it('shows a lost POST timeout, permits retry, and ignores the late original response', async () => {
    const { API: actual } = await vi.importActual<typeof import('../../../api')>('../../../api');
    const response = deferred<{ ok: boolean; json: () => Promise<typeof verified> }>();
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(response.promise));
    vi.useFakeTimers();
    mocks.visionVerifySync.mockImplementation(actual.visionVerifySync);
    render(<VisionSyncOverlay {...props} syncEvents={[mismatch]} />);
    fireEvent.click(screen.getByRole('button', { name: '已按提示调整' }));
    await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
    expect(screen.getByRole('alert')).toHaveTextContent(/超时.*重试/);
    await act(async () => { response.resolve({ ok: true, json: async () => verified }); });
    expect(mocks.refreshState).not.toHaveBeenCalled();
    mocks.visionVerifySync.mockResolvedValue(verified);
    fireEvent.click(screen.getByRole('button', { name: '重试核对' }));
    await act(async () => { await vi.advanceTimersByTimeAsync(300); });
    expect(screen.queryByText('盘面与对局不一致')).toBeNull();
    vi.unstubAllGlobals();
  });

});
