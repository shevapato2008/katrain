import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { API, ApiError, apiPost } from './api';

const fetchMock = vi.fn();
beforeEach(() => { fetchMock.mockReset(); vi.stubGlobal('fetch', fetchMock); });
afterEach(() => { vi.unstubAllGlobals(); });

const reply = (status: number, body: string) =>
  ({ ok: status >= 200 && status < 300, status, text: async () => body, json: async () => JSON.parse(body) });

describe('ApiError.detail', () => {
  it.each([
    ['对象 detail 原样挂上', '{"detail":{"code":"analysis_pending","message":"x"}}', { code: 'analysis_pending', message: 'x' }],
    ['字符串 detail 原样挂上', '{"detail":"Game is already over"}', 'Game is already over'],
    ['不是 JSON(网关页) ⇒ undefined', '<html>502</html>', undefined],
    ['JSON 是 null ⇒ undefined', 'null', undefined],
  ])('%s', async (_n, body, detail) => {
    fetchMock.mockResolvedValue(reply(400, body));
    const err = await apiPost('/api/count/request', { session_id: 's' }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(400);
    expect(err.detail).toEqual(detail);
    expect(err.message).toBe(`Request failed 400: ${body}`); // message 格式不变
  });
});

describe('API.resign', () => {
  const bodyOf = () => JSON.parse(fetchMock.mock.calls[0][1].body);
  it('给了 color ⇒ body 带 color', async () => {
    fetchMock.mockResolvedValue(reply(200, '{"session_id":"s","state":{}}'));
    await API.resign('s', undefined, 'W');
    expect(bodyOf()).toEqual({ session_id: 's', color: 'W' });
  });
  it('没给 color ⇒ body 里连这个键都没有(其它模式带了会 400)', async () => {
    fetchMock.mockResolvedValue(reply(200, '{"session_id":"s","state":{}}'));
    await API.resign('s');
    expect(Object.keys(bodyOf())).toEqual(['session_id']);
  });
});

describe('API.deleteSession', () => {
  it('DELETE /api/session/{id}', async () => {
    fetchMock.mockResolvedValue(reply(200, '{"status":"deleted"}'));
    await API.deleteSession('a/b');
    expect(fetchMock.mock.calls[0][0]).toBe('/api/session/a%2Fb');
    expect(fetchMock.mock.calls[0][1].method).toBe('DELETE');
  });
  it('失败必须抛 —— 不能装作已退出', async () => {
    fetchMock.mockResolvedValue(reply(500, 'boom'));
    await expect(API.deleteSession('s')).rejects.toBeInstanceOf(ApiError);
  });
});
