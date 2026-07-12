import { describe, it, expect, vi, beforeEach } from 'vitest';
import { UserGamesAPI } from './userGamesApi';

beforeEach(() => { vi.restoreAllMocks(); });

describe('UserGamesAPI', () => {
  it('list sends bearer token + source filter', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ items: [], total: 0, page: 1, page_size: 20 }) });
    vi.stubGlobal('fetch', fetchMock);
    await UserGamesAPI.list('tok123', { source: 'play_local', page: 2 });
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toContain('/api/v1/user-games/');
    expect(url).toContain('source=play_local');
    expect(url).toContain('page=2');
    expect(opts.headers.Authorization).toBe('Bearer tok123');
  });

  it('get fetches detail by id', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: 'g1', sgf_content: '(;GM[1])' }) });
    vi.stubGlobal('fetch', fetchMock);
    const g = await UserGamesAPI.get('tok', 'g1');
    expect(g.sgf_content).toBe('(;GM[1])');
    expect(fetchMock.mock.calls[0][0]).toContain('/api/v1/user-games/g1');
  });
});
