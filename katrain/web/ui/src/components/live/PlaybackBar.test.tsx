import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import PlaybackBar from './PlaybackBar';
afterEach(() => vi.useRealTimers());
it('separates automatic live catch-up from explicit navigation and autoplay', () => {
  vi.useFakeTimers();
  const replay = vi.fn(); const follow = vi.fn();
  render(<PlaybackBar currentMove={1} totalMoves={3} isLive onMoveChange={replay} onFollowMoveChange={follow} />);
  expect(follow).toHaveBeenCalledExactlyOnceWith(3);
  expect(replay).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'live:previous' }));
  expect(replay).toHaveBeenCalledWith(0);
  replay.mockClear(); follow.mockClear();
  fireEvent.click(screen.getByRole('button', { name: '播放' }));
  act(() => vi.advanceTimersByTime(1000));
  expect(replay).toHaveBeenCalledExactlyOnceWith(2);
  expect(follow).not.toHaveBeenCalled();
});
