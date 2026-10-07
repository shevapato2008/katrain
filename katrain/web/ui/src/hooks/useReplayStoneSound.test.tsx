import { renderHook } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { useReplayStoneSound } from './useReplayStoneSound';

const play = vi.hoisted(() => vi.fn());
vi.mock('./useSound', () => ({ useSound: () => ({ play }) }));
beforeEach(() => play.mockClear());

it('plays only for a selected cursor change with a stone, including backward navigation', () => {
  const props = { identity: 7, cursor: 0, move: undefined as string | undefined, ready: false, selected: false };
  const { rerender } = renderHook(p => useReplayStoneSound(p), { initialProps: props });
  rerender({ ...props, ready: true, cursor: 2, move: 'D4' }); // async SGF + analysis frontier
  expect(play).not.toHaveBeenCalled();
  rerender({ ...props, ready: true, selected: true, cursor: 1, move: 'Q16' });
  expect(play).toHaveBeenCalledExactlyOnceWith('stone');
  rerender({ ...props, ready: true, selected: true, cursor: 1, move: 'Q16' }); // theme/filter/update
  rerender({ ...props, ready: true, selected: true, cursor: 2, move: 'pass' });
  rerender({ ...props, ready: true, selected: true, cursor: 3, move: undefined });
  rerender({ ...props, ready: true, selected: true, cursor: 0, move: 'D4' });
  expect(play).toHaveBeenCalledTimes(1);
  rerender({ ...props, ready: true, selected: true, cursor: 4, move: 'K10' });
  expect(play).toHaveBeenCalledTimes(2);
  rerender({ ...props, identity: 8, ready: true, selected: true, cursor: 2, move: 'D4' });
  expect(play).toHaveBeenCalledTimes(2);
});
