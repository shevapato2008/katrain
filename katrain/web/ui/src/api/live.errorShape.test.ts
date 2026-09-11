import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { LiveAPI } from './live';

/* 为什么单独有这个文件：
 *
 * `useComments.phone.test.tsx` 把 `LiveAPI.createComment` 整个 mock 掉，并**自己造一个
 * 已经带 `.code` 的错误对象**。那条用例证明的是「hook 拿到 code 之后会翻译它」，
 * 它**从来没执行过** `api/live.ts` 里那行 `err.code = JSON.parse(body)?.detail?.code`。
 * 变异实测：把那一行删掉，`useComments.phone.test.tsx` 两条全绿 —— 而真实链路已经断了。
 *
 * 这就是「到达性测试给断路发通行证」：夹具造在断点**里面**，堵点按定义总在更外面。
 * 所以这里从**全局 fetch** 那一层进去，走真的 apiPostAuth。
 */
describe('api/live.ts 的失败对象形状', () => {
  const originalFetch = globalThis.fetch;
  beforeEach(() => { vi.restoreAllMocks(); });
  afterEach(() => { globalThis.fetch = originalFetch; });

  const respond = (status: number, body: string) => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false, status, text: async () => body, json: async () => JSON.parse(body),
    }) as never;
  };

  it('403 的 detail.code 被挂到错误对象上 —— 调用方才有得分支', async () => {
    respond(403, JSON.stringify({ detail: { code: 'comment_requires_phone', message: '发表评论需要先绑定手机号。' } }));
    const err = await LiveAPI.createComment('m1', 'tok', 'hi').catch((e) => e);
    expect(err.status).toBe(403);
    expect(err.code).toBe('comment_requires_phone');
  });

  it('报错串一个字没改 —— 别处按文本断言的用例照旧有效', async () => {
    const body = JSON.stringify({ detail: { code: 'comment_requires_phone' } });
    respond(403, body);
    const err = await LiveAPI.createComment('m1', 'tok', 'hi').catch((e) => e);
    expect(err.message).toBe(`Request failed 403: ${body}`);
  });

  it('非 JSON 的响应（网关 502 之类）不把整件事搞崩，只是没有 code', async () => {
    respond(502, '<html>Bad Gateway</html>');
    const err = await LiveAPI.createComment('m1', 'tok', 'hi').catch((e) => e);
    expect(err.status).toBe(502);
    expect(err.code).toBeUndefined();
    expect(err.message).toContain('Request failed 502');
  });
});
