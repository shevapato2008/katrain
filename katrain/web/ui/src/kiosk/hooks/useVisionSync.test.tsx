import { act, renderHook } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { useVisionSync } from './useVisionSync';
vi.mock('../../api', () => ({ API: { visionBind: vi.fn().mockResolvedValue(undefined), visionUnbind: vi.fn().mockResolvedValue(undefined) } }));
vi.mock('../../utils/websocketUrl', () => ({ websocketUrl: (path: string) => path }));
class Socket {
  static instances: Socket[] = [];
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror = null;
  close = vi.fn();
  constructor() { Socket.instances.push(this); }
}
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); Socket.instances = []; });
it('reconnects, preserves sequence, and cancels old socket handlers and timers', async () => {
  vi.useFakeTimers(); vi.stubGlobal('WebSocket', Socket);
  const { result, rerender, unmount } = renderHook(({ session }) => useVisionSync(session), { initialProps: { session: 'a' } });
  await act(async () => {});
  const first = Socket.instances[0];
  act(() => { first.onopen?.(); first.onmessage?.({ data: JSON.stringify({ type: 'setup_complete', data: {} }) }); });
  expect(result.current.connected).toBe(true);
  expect(result.current.latestEvent?.seq).toBe(0);
  act(() => first.onclose?.());
  expect(result.current.connected).toBe(false);
  await act(async () => { vi.advanceTimersByTime(1000); });
  expect(Socket.instances).toHaveLength(2);
  const second = Socket.instances[1];
  act(() => { second.onopen?.(); second.onmessage?.({ data: JSON.stringify({ type: 'setup_complete', data: {} }) }); });
  expect(result.current.latestEvent?.seq).toBe(1);
  act(() => second.onclose?.());
  rerender({ session: 'b' }); await act(async () => {});
  expect(second.onmessage).toBeNull();
  expect(result.current.connected).toBe(false);
  await act(async () => { vi.advanceTimersByTime(1000); });
  expect(Socket.instances).toHaveLength(3);
  const third = Socket.instances[2];
  act(() => third.onclose?.()); unmount();
  await act(async () => { vi.advanceTimersByTime(1000); });
  expect(Socket.instances).toHaveLength(3);
  expect(third.onclose).toBeNull();
});
