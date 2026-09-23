import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { KifuAPI } from './kifuApi';

afterEach(() => vi.unstubAllGlobals());

describe('棋谱 HTTP 错误保留状态码，供列表和详情识别离线', () => {
  // 页面测试只桩 KifuAPI；这里经过真实客户端，防止 fixture 自己构造 ApiError 掩盖接线断路。
  it.each([
    ['列表', () => KifuAPI.getAlbums({ page: 1, page_size: 6 })],
    ['详情', () => KifuAPI.getAlbum(7)],
  ] as const)('%s 的 503 抛 ApiError，404 保持原状态和消息', async (_name, request) => {
    for (const status of [503, 404]) {
      const body = JSON.stringify({ detail: status === 503 ? 'Remote kifu service unavailable' : 'Not found' });
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, { status })));
      const error = await request().catch((reason: unknown) => reason);
      expect(error).toBeInstanceOf(ApiError);
      expect(error).toMatchObject({ status, message: `Request failed ${status}: ${body}` });
    }
  });
});
