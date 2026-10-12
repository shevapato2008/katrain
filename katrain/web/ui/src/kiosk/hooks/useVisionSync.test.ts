import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { API } from '../../api';
import { useVisionSync } from './useVisionSync';

const deferred = () => {
  let resolve!: () => void;
  const promise = new Promise<void>(r => { resolve = r; });
  return { promise, resolve };
};

describe('vision binding preparation', () => {
  beforeEach(() => {
    vi.stubGlobal('WebSocket', class { close() {} });
    vi.spyOn(API, 'visionUnbind').mockResolvedValue(undefined);
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });
  afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

  it('reports preparation until bind resolves and then invokes the completion callback', async () => {
    const binding = deferred();
    vi.spyOn(API, 'visionBind').mockReturnValue(binding.promise);
    const onBound = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() => useVisionSync('original', onBound));
    expect(result.current.bindState).toBe('preparing');
    expect(onBound).not.toHaveBeenCalled();
    await act(async () => binding.resolve());
    expect(result.current.bindState).toBe('ready');
    expect(onBound).toHaveBeenCalledWith('original');
  });

  it('a failed initial bind can be retried without submitting a move or duplicating a pending bind', async () => {
    const binding = deferred();
    const bind = vi.spyOn(API, 'visionBind').mockRejectedValueOnce(new Error('reference unavailable'))
      .mockReturnValueOnce(binding.promise);
    const confirm = vi.spyOn(API, 'confirmLocalMove');
    const { result } = renderHook(() => useVisionSync('original'));
    await waitFor(() => expect(result.current.bindState).toBe('error'));
    act(() => { result.current.retryBind(); result.current.retryBind(); });
    expect(result.current.bindState).toBe('preparing');
    expect(bind).toHaveBeenCalledTimes(2);
    expect(confirm).not.toHaveBeenCalled();
    await act(async () => binding.resolve());
    expect(result.current.bindState).toBe('ready');
  });

  it('a late bind from the previous session cannot complete the new session', async () => {
    const old = deferred();
    vi.spyOn(API, 'visionBind').mockReturnValueOnce(old.promise).mockResolvedValue(undefined);
    const onBound = vi.fn().mockResolvedValue(undefined);
    const { result, rerender } = renderHook(({ id }) => useVisionSync(id, onBound), { initialProps: { id: 'old' } });
    rerender({ id: 'new' });
    await waitFor(() => expect(result.current.bindState).toBe('ready'));
    await act(async () => old.resolve());
    expect(onBound).toHaveBeenCalledTimes(1);
    expect(onBound).toHaveBeenCalledWith('new');
  });
});
