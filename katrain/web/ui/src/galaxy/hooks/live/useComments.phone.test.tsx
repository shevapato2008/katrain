import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { LiveAPI } from '../../../api/live';
import { useComments } from './useComments';

vi.mock('../../../context/AuthContext', () => ({
  useAuth: () => ({ token: 'tok', isAuthenticated: true }),
}));

describe('useComments 未绑手机被拒', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(LiveAPI, 'getComments').mockResolvedValue({ comments: [], total: 0 } as never);
  });

  const mount = async () => {
    const hook = renderHook(() => useComments('m1', true, { pollInterval: 0 }));
    await waitFor(() => expect(hook.result.current.loading).toBe(false));
    return hook;
  };

  it('403 comment_requires_phone → 一句能照着做的中文，不是裸的 Request failed 403', async () => {
    /* 今天这条路是静默的同族形状：后端 server.py 早就在发 chat_requires_identity，
       前端一个读者都没有。评论这条至少会把原始报错串糊到 Alert 里 ——
       用户看到 `Request failed 403: {"detail":{"code":"comment_requires_phone"}}`。 */
    vi.spyOn(LiveAPI, 'createComment').mockRejectedValue(
      Object.assign(new Error('Request failed 403: {"detail":{"code":"comment_requires_phone"}}'),
        { status: 403, code: 'comment_requires_phone' }));
    const { result } = await mount();
    await act(async () => { await result.current.postComment('hi'); });
    expect(result.current.error).toMatch(/绑定手机号/);
    expect(result.current.error).not.toMatch(/Request failed/);
  });

  it('别的失败不被误伤，仍然原样报出来', async () => {
    vi.spyOn(LiveAPI, 'createComment').mockRejectedValue(
      Object.assign(new Error('Request failed 500: boom'), { status: 500 }));
    const { result } = await mount();
    await act(async () => { await result.current.postComment('hi'); });
    expect(result.current.error).toMatch(/Request failed 500/);
  });
});
