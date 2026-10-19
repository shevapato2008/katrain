import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useLocalMoveConfirmation } from './useLocalMoveConfirmation';

const options = () => ({
  scope: 'session|game|33|B', input: 'screen' as const, enabled: true, recognizing: false,
  submit: vi.fn().mockResolvedValue({ accepted: true }),
});

describe('local screen move confirmation', () => {
  it('keeps only the last selection and does not submit before confirmation', () => {
    const props = options();
    const { result } = renderHook(() => useLocalMoveConfirmation(props));
    act(() => result.current.select(3, 3));
    act(() => result.current.select(4, 5));
    expect(result.current.point).toEqual({ x: 4, y: 5 });
    expect(props.submit).not.toHaveBeenCalled();
  });

  it('submits the last selection once and locks selection while sending', async () => {
    let complete!: (value: { accepted: boolean }) => void;
    const props = options();
    props.submit.mockImplementation(() => new Promise((resolve) => { complete = resolve; }));
    const { result } = renderHook(() => useLocalMoveConfirmation(props));
    act(() => result.current.select(4, 5));
    let request!: Promise<void>;
    act(() => { request = result.current.confirm(); void result.current.confirm(); result.current.select(6, 6); });
    expect(props.submit).toHaveBeenCalledTimes(1);
    expect(props.submit.mock.calls[0][0]).toMatchObject({ input: 'screen', action: 'move', coords: [4, 5] });
    expect(result.current.point).toEqual({ x: 4, y: 5 });
    expect(result.current.busy).toBe(true);
    await act(async () => { complete({ accepted: true }); await request; });
    expect(result.current.point).toBeNull();
    expect(result.current.busy).toBe(false);
  });

  it('keeps the selection after failure for retry', async () => {
    const props = options();
    props.submit.mockRejectedValue(new Error('unavailable'));
    const { result } = renderHook(() => useLocalMoveConfirmation(props));
    act(() => result.current.select(4, 5));
    await act(async () => { await result.current.confirm(); });
    expect(result.current.point).toEqual({ x: 4, y: 5 });
    expect(result.current.failed).toBe(true);
    expect(result.current.busy).toBe(false);
  });

  it('clears selection when the authoritative turn changes and ignores late completion', async () => {
    let complete!: (value: { accepted: boolean }) => void;
    const props = options();
    props.submit.mockImplementation(() => new Promise((resolve) => { complete = resolve; }));
    const { result, rerender } = renderHook((p) => useLocalMoveConfirmation(p), { initialProps: props });
    act(() => result.current.select(4, 5));
    let request!: Promise<void>;
    act(() => { request = result.current.confirm(); });
    rerender({ ...props, scope: 'other|game|0|B' });
    expect(result.current.point).toBeNull();
    act(() => result.current.select(2, 2));
    await act(async () => { complete({ accepted: true }); await request; });
    expect(result.current.point).toEqual({ x: 2, y: 2 });
  });

  it('requires a screen selection but allows physical confirmation without one', async () => {
    const props = options();
    const { result, rerender } = renderHook((p) => useLocalMoveConfirmation(p), { initialProps: { ...props, input: 'screen' as 'screen' | 'physical' } });
    await act(async () => { await result.current.confirm(); });
    expect(props.submit).not.toHaveBeenCalled();
    rerender({ ...props, input: 'physical' });
    await act(async () => { await result.current.confirm(); });
    expect(props.submit.mock.calls[0][0]).toMatchObject({ input: 'physical', action: 'move', coords: null });
  });

  it('reuses the request id after a lost reply', async () => {
    const props = options();
    props.submit.mockRejectedValueOnce(new Error('lost reply'));
    const { result } = renderHook(() => useLocalMoveConfirmation(props));
    act(() => result.current.select(4, 5));
    await act(async () => { await result.current.confirm(); });
    await act(async () => { await result.current.confirm(); });
    expect(props.submit.mock.calls[1][0].request_id).toBe(props.submit.mock.calls[0][0].request_id);
  });
});
