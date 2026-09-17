import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { VisionSyncEvent } from '../../hooks/useVisionSync';
import VisionSyncOverlay from './VisionSyncOverlay';

const mocks = vi.hoisted(() => ({
  playMove: vi.fn().mockResolvedValue(undefined),
  visionResetSync: vi.fn().mockResolvedValue(undefined),
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
  boardSize: 19,
  playerToMove: 'B',
  currentNodeId: 10,
};

const dialogCount = () => screen.queryAllByRole('dialog').length;

describe('VisionSyncOverlay recovery presentation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.translate.mockImplementation((_key: string, fallback?: string) => fallback ?? '');
  });
  afterEach(() => vi.useRealTimers());

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
    expect(mocks.visionResetSync).not.toHaveBeenCalled();
    await waitFor(() => expect(screen.queryByRole('button', { name: '我挪一下' })).toBeNull());
  });

  it('keeps the low-confidence wording and adopts the physical baseline when ignored', async () => {
    render(
      <VisionSyncOverlay
        {...props}
        syncEvents={[event(1, 'ambiguous_stone', { row: 3, col: 3, color: 1, unbacked: false })]}
      />,
    );

    expect(await screen.findByText(/检测到疑似落子/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '忽略' }));
    expect(mocks.visionResetSync).toHaveBeenCalledWith('physical');
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
    ['initial generic mismatch', event(1, 'illegal_change', { positions: [[5, 5, 1]], missing: [] })],
    ['toast', event(1, 'degraded')],
  ])('keeps %s silent', (_name, syncEvent) => {
    render(<VisionSyncOverlay {...props} syncEvents={[syncEvent]} />);

    expect(mocks.voiceSpeak).not.toHaveBeenCalled();
  });

  it('keeps persistent board loss silent', () => {
    vi.useFakeTimers();
    render(<VisionSyncOverlay {...props} syncEvents={[event(1, 'board_lost')]} />);
    act(() => vi.advanceTimersByTime(10_000));

    expect(screen.getByText('棋盘检测异常')).toBeInTheDocument();
    expect(mocks.voiceSpeak).not.toHaveBeenCalled();
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

  it('synced clears blocking recovery and a persistent board-loss dialog', () => {
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
    act(() => vi.advanceTimersByTime(300));

    expect(screen.queryByText('棋盘检测异常')).toBeNull();
    expect(screen.queryByText('盘面与对局不一致')).toBeNull();
    expect(dialogCount()).toBe(0);
  });
});
