import { afterEach, describe, expect, it, vi } from 'vitest';
import { API } from './api';

// 严格盒端 SSO（kiosk 构建 + VITE_BOX_SSO_STRICT）里 `authHeaders()` 第一行就 `return {}`：
// 身份只在 HttpOnly `sb_go_token` cookie 里，前端**绝不能**自己造 Bearer 头。
// 所以「带 token 就发 Bearer」这条契约只在非严格档成立 —— 旧版本无条件断言它，
// 在 `VITE_BOX_SSO_STRICT=true` 下跑整套测试时必红（2026-09-13 第一次跑那一档才发现，
// 因为仓里没有任何 CI 跑严格档）。
const isStrictBoxKiosk = __KIOSK_2D_ONLY__ && import.meta.env.VITE_BOX_SSO_STRICT === 'true';

describe('API.quickAnalyze authentication', () => {
  afterEach(() => vi.restoreAllMocks());

  it(isStrictBoxKiosk
    ? 'never sends Bearer in strict box mode, even when a token is passed'
    : 'sends Bearer when an access token is available', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status: 200 }));
    await API.quickAnalyze({ moves: [] }, 'access-token');
    if (isStrictBoxKiosk) {
      const options = fetchMock.mock.calls[0][1] as RequestInit;
      expect(options.headers).not.toHaveProperty('Authorization');
    } else {
      expect(fetchMock).toHaveBeenCalledWith('/api/v1/analysis/quick-analyze', expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer access-token' }),
      }));
    }
  });

  it('omits Authorization for the cookie-only path', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status: 200 }));
    await API.quickAnalyze({ moves: [] }, undefined);
    const options = fetchMock.mock.calls[0][1] as RequestInit;
    expect(options.headers).not.toHaveProperty('Authorization');
  });
});
