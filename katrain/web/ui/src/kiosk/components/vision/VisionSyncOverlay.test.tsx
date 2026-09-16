import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { VisionSyncEvent } from '../../hooks/useVisionSync';
import VisionSyncOverlay from './VisionSyncOverlay';

const mocks = vi.hoisted(() => ({
  playMove: vi.fn().mockResolvedValue(undefined),
  visionResetSync: vi.fn().mockResolvedValue(undefined),
}));

vi.mock('../../../api', () => ({ API: mocks }));
vi.mock('../../../hooks/useTranslation', () => ({
  useTranslation: () => ({ t: (_key: string, fallback?: string) => fallback ?? '' }),
}));

const event = (seq: number, type: VisionSyncEvent['type'], data: Record<string, unknown> = {}): VisionSyncEvent => ({
  seq, type, data,
});

const props = {
  onDismiss: vi.fn(),
  sessionId: 'session-1',
  boardSize: 19,
  playerToMove: 'B',
};

describe('VisionSyncOverlay ambiguous stone recovery', () => {
  beforeEach(() => vi.clearAllMocks());

  it('tells the user to straighten an unbacked stone without adopting it into the baseline', async () => {
    render(
      <VisionSyncOverlay
        {...props}
        syncEvents={[event(1, 'ambiguous_stone', { row: 3, col: 3, color: 1, unbacked: true })]}
      />,
    );

    expect(await screen.findByText('黑 子没放正')).toBeInTheDocument();
    expect(screen.getByText(/请把它挪到 D16/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '我挪一下' }));

    expect(mocks.visionResetSync).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: '我挪一下' })).toBeNull();
  });

  it('dismisses the stale ambiguous card when the board becomes synced', async () => {
    const ambiguous = event(1, 'ambiguous_stone', { row: 3, col: 3, unbacked: true });
    const { rerender } = render(<VisionSyncOverlay {...props} syncEvents={[ambiguous]} />);
    expect(await screen.findByRole('button', { name: '我挪一下' })).toBeInTheDocument();

    rerender(<VisionSyncOverlay {...props} syncEvents={[ambiguous, event(2, 'synced')]} />);

    await waitFor(() => expect(screen.queryByRole('button', { name: '我挪一下' })).toBeNull());
  });
});
