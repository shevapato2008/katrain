import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { KifuAPI } from './kifuApi';

afterEach(() => { delete window.__kifuListRequest; vi.unstubAllGlobals(); });

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

it('首条棋谱直接复用列表 preview，不再串行请求详情', async () => {
  const preview = { id: 24171, sgf_content: '(;SZ[19];B[dd])' };
  const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ items: [preview], preview, total: 1 }), { status: 200 })));
  vi.stubGlobal('fetch', fetchMock);
  await KifuAPI.getAlbums({ page: 1, page_size: 20, lang: 'cn' });
  expect(await KifuAPI.getAlbum(24171, 'cn')).toEqual(preview);
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

it('首次预加载网络失败后重试发起新的请求', async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response('{"items":[],"total":0}'));
  vi.stubGlobal('fetch', fetchMock);
  window.__kifuListRequest = {
    path: '/api/v1/kifu/albums?page=1&page_size=20&lang=cn',
    response: Promise.reject(new Error('offline')),
  };
  const request = () => KifuAPI.getAlbums({ page: 1, page_size: 20, lang: 'cn' });
  await expect(request()).rejects.toThrow('offline');
  expect(await request()).toEqual({ items: [], total: 0 });
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

it('列表与详情将AbortSignal透传给fetch', async () => {
  const signal = new AbortController().signal;
  const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response('{}')));
  vi.stubGlobal('fetch', fetchMock);
  await KifuAPI.getAlbums({ q: 'signal', signal });
  await KifuAPI.getAlbum(81291, 'cn', signal);
  expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/v1/kifu/albums?q=signal', { signal });
  expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/v1/kifu/albums/81291?lang=cn', { signal });
});

it('旧列表晚到不能清空或替换新列表的preview缓存', async () => {
  let resolveOld!: (response: Response) => void;
  const old = new Promise<Response>((resolve) => { resolveOld = resolve; });
  const preview = { id: 81292, sgf_content: '(;SZ[19];B[dd])' };
  const fetchMock = vi.fn().mockReturnValueOnce(old)
    .mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ preview }))));
  vi.stubGlobal('fetch', fetchMock);
  const first = KifuAPI.getAlbums({ q: 'old', lang: 'cn' });
  await KifuAPI.getAlbums({ q: 'current', lang: 'cn' });
  resolveOld(new Response(JSON.stringify({ preview: { id: 81293, sgf_content: '(;SZ[19];B[aa])' } })));
  await first;
  expect(await KifuAPI.getAlbum(preview.id, 'cn')).toEqual(preview);
  expect(fetchMock).toHaveBeenCalledTimes(2);
});

it('已取消的列表在JSON晚到时不发布preview，详情也不接受已取消的缓存读取', async () => {
  const controller = new AbortController();
  const preview = { id: 81294, sgf_content: '(;SZ[19];B[dd])' };
  let resolveJson!: (value: unknown) => void;
  const json = new Promise((resolve) => { resolveJson = resolve; });
  const fetchMock = vi.fn().mockResolvedValueOnce({ ok: true, json: () => json })
    .mockImplementation(() => Promise.resolve(new Response('{}')));
  vi.stubGlobal('fetch', fetchMock);
  const pending = KifuAPI.getAlbums({ q: 'cancelled', lang: 'cn', signal: controller.signal });
  await Promise.resolve();
  controller.abort();
  resolveJson({ preview });
  await expect(pending).rejects.toMatchObject({ name: 'AbortError' });
  await KifuAPI.getAlbum(preview.id, 'cn');
  expect(fetchMock).toHaveBeenCalledTimes(2);

  fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ preview })));
  await KifuAPI.getAlbums({ lang: 'cn' });
  await expect(KifuAPI.getAlbum(preview.id, 'cn', controller.signal)).rejects.toMatchObject({ name: 'AbortError' });
});
