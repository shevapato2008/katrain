import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { API } from '../api';
import { useGameSession } from './useGameSession';

vi.mock('../api', () => ({
  API: {
    getState: vi.fn().mockResolvedValue({ session_id: 'session-123', state: {} }),
    undo: vi.fn().mockRejectedValue(new Error('Request failed 409: {"detail":"nope"}')),
    resign: vi.fn(),
    newGame: vi.fn(),
    createSession: vi.fn(),
  },
}));

const sockets: MockWebSocket[] = [];
class MockWebSocket {
  static OPEN = 1;
  readyState = MockWebSocket.OPEN;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onopen: (() => void) | null = null;
  onclose: ((event: { code: number; reason: string; wasClean: boolean }) => void) | null = null;
  close = vi.fn();
  send = vi.fn();
  constructor(readonly url: string) { sockets.push(this); }
}

describe('useGameSession · 断线与一次性错误分开记(N25)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sockets.length = 0;
    vi.stubGlobal('WebSocket', MockWebSocket);
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
  });
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  const connected = async () => {
    const hook = renderHook(() => useGameSession());
    await act(async () => { hook.result.current.setSessionId('session-123'); });
    return hook;
  };

  it('意外断开: connectionLost = dropped，error 文案不变', async () => {
    const { result } = await connected();
    act(() => { sockets[0].onclose?.({ code: 1006, reason: '', wasClean: false }); });
    expect(result.current.connectionLost).toBe('dropped');
    expect(result.current.error).toBe('实时连接已断开，棋盘不会自动更新，请刷新页面');
  });

  it('服务端 1008 拒绝: connectionLost = rejected，保留原因和登录文案', async () => {
    const { result } = await connected();
    act(() => { sockets[0].onclose?.({ code: 1008, reason: 'Invalid token', wasClean: true }); });
    expect(result.current.connectionLost).toBe('rejected');
    expect(result.current.error).toBe('实时连接被拒绝（Invalid token），棋盘不会自动更新，请重新登录后重试');
  });

  it('一次性操作失败不算断线，clearError 清掉错误', async () => {
    const { result } = await connected();
    await act(async () => { await result.current.handleAction('undo').catch(() => undefined); });
    expect(result.current.connectionLost).toBeNull();
    expect(result.current.error).toContain('409');
    act(() => { result.current.clearError(); });
    expect(result.current.error).toBeNull();
  });

  it('新连接打开会清断线状态，旧连接事件不能覆盖新连接', async () => {
    const { result } = await connected();
    const first = sockets[0];
    act(() => { first.onclose?.({ code: 1006, reason: '', wasClean: false }); });
    expect(result.current.connectionLost).toBe('dropped');
    await act(async () => { result.current.setSessionId('session-456'); });
    act(() => { sockets[1].onopen?.(); });
    expect(result.current.connectionLost).toBeNull();
    act(() => { first.onclose?.({ code: 1008, reason: 'old socket', wasClean: true }); });
    expect(result.current.connectionLost).toBeNull();
  });

  it('断线后卸载再回到同一局，重新 GET 状态并建立第二条 WS，没有认输或新建局', async () => {
    const first = await connected();
    act(() => { sockets[0].onclose?.({ code: 1006, reason: '', wasClean: false }); });
    first.unmount();
    expect(sockets[0].close).toHaveBeenCalledOnce();
    const second = await connected();
    expect(API.getState).toHaveBeenCalledTimes(2);
    expect(API.getState).toHaveBeenNthCalledWith(1, 'session-123', undefined);
    expect(API.getState).toHaveBeenNthCalledWith(2, 'session-123', undefined);
    expect(sockets).toHaveLength(2);
    expect(sockets[1].url).toBe(sockets[0].url);
    expect(sockets[1].url).toContain('/ws/session-123');
    act(() => { sockets[1].onopen?.(); });
    expect(second.result.current.connectionLost).toBeNull();
    expect(API.resign).not.toHaveBeenCalled();
    expect(API.newGame).not.toHaveBeenCalled();
    expect(API.createSession).not.toHaveBeenCalled();
  });
});
