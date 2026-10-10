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

  it('保留盒端的具体失败原因：云端服务报错不当成断网', async () => {
    const body = JSON.stringify({ detail: { code: 'kifu_cloud_error', message: 'Remote kifu service unavailable' } });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, { status: 503 })));
    const error = await KifuAPI.getAlbums().catch((reason: unknown) => reason);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 503, detail: { code: 'kifu_cloud_error' } });
  });
});

describe('棋谱展示语言', () => {
  it('列表与详情传 lang，旧详情调用仍保持原 URL', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response('{}', { status: 200 })));
    vi.stubGlobal('fetch', fetchMock);

    await KifuAPI.getAlbums({ q: '柯洁', page: 2, lang: 'jp' });
    await KifuAPI.getAlbum(7, 'en');
    await KifuAPI.getAlbum(7);

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      '/api/v1/kifu/albums?q=%E6%9F%AF%E6%B4%81&page=2&lang=jp',
      '/api/v1/kifu/albums/7?lang=en',
      '/api/v1/kifu/albums/7',
    ]);
  });
});
