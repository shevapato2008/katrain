import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ReportsAPI } from './reportApi';

/* 与 src/api/live.errorShape.test.ts 同一条理由：
 *
 * 402 的 `detail.free_weekly_blocked` 要被上层读到，前提是**这一层把它挂上去**。
 * 若只在 useReportTasks / ReportsPage 那层写用例、自己造一个已经带 `detail` 的错误对象，
 * 那条用例在本层坏掉时**照样绿** —— 夹具造在断点里面，堵点按定义在更外面。
 * 所以从全局 fetch 那一层进去走真的请求函数。
 */
describe('api/reportApi.ts 的失败对象形状', () => {
  const originalFetch = globalThis.fetch;
  beforeEach(() => { vi.restoreAllMocks(); });
  afterEach(() => { globalThis.fetch = originalFetch; });

  const respond = (status: number, body: string) => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false, status, text: async () => body, json: async () => JSON.parse(body),
    }) as never;
  };

  it('402 的 detail 被挂到错误对象上 —— 上层才分得出「没绑手机」和「真没钱」', async () => {
    const body = JSON.stringify({
      detail: { code: 'insufficient_credits', free_weekly_blocked: 'phone_unbound' },
    });
    respond(402, body);
    const err = await ReportsAPI.create('tok', { user_game_id: 'g1', report_type: 'normal' })
      .catch((e) => e);
    expect(err.status).toBe(402);
    expect(err.detail?.free_weekly_blocked).toBe('phone_unbound');
  });

  it('报错串一个字没改 —— reportApi.test.ts:118 正按文本断言', async () => {
    const body = 'report already exists';
    respond(409, body);
    const err = await ReportsAPI.create('tok', { user_game_id: 'g1', report_type: 'normal' })
      .catch((e) => e);
    expect(err.message).toBe(`Request failed 409: ${body}`);
  });

  it('非 JSON 的响应不把整件事搞崩，只是没有 detail', async () => {
    respond(502, '<html>Bad Gateway</html>');
    const err = await ReportsAPI.create('tok', { user_game_id: 'g1', report_type: 'normal' })
      .catch((e) => e);
    expect(err.status).toBe(502);
    expect(err.detail).toBeUndefined();
  });
});
