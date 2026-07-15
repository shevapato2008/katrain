import { beforeEach, describe, expect, it, vi } from 'vitest';

import { UserGamesAPI } from './userGamesApi';

const okJson = <T>(body: T) => ({
  ok: true,
  json: vi.fn().mockResolvedValue(body),
});

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe('UserGamesAPI', () => {
  it('lists games with the full filter contract and bearer authentication', async () => {
    const response = { items: [], total: 0, page: 2, page_size: 12 };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(okJson(response)));

    await expect(UserGamesAPI.list('token', {
      page: 2,
      page_size: 12,
      category: 'review',
      source: 'play_local',
      sort: '-created_at',
      q: 'Lee',
    })).resolves.toEqual(response);

    expect(fetch).toHaveBeenCalledWith(
      '/api/v1/user-games/?page=2&page_size=12&category=review&source=play_local&sort=-created_at&q=Lee',
      {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer token',
        },
      },
    );
  });

  it('gets game detail by id', async () => {
    const detail = { id: 'game-1', sgf_content: '(;GM[1])' };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(okJson(detail)));

    await expect(UserGamesAPI.get('token', 'game-1')).resolves.toEqual(detail);

    expect(fetch).toHaveBeenCalledWith('/api/v1/user-games/game-1', expect.objectContaining({
      headers: expect.objectContaining({ 'Authorization': 'Bearer token' }),
    }));
  });

  it('creates a game with a JSON request body', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(okJson({ id: 'game-1' })));
    const params = {
      sgf_content: '(;GM[1])',
      source: 'import',
      title: 'Teaching game',
    };

    await UserGamesAPI.create('token', params);

    expect(fetch).toHaveBeenCalledWith('/api/v1/user-games/', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify(params),
      headers: expect.objectContaining({
        'Content-Type': 'application/json',
        'Authorization': 'Bearer token',
      }),
    }));
  });

  it('updates a game with a JSON request body', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(okJson({ id: 'game-1' })));
    const params = { title: 'Renamed game', move_count: 42 };

    await UserGamesAPI.update('token', 'game-1', params);

    expect(fetch).toHaveBeenCalledWith('/api/v1/user-games/game-1', expect.objectContaining({
      method: 'PUT',
      body: JSON.stringify(params),
      headers: expect.objectContaining({ 'Authorization': 'Bearer token' }),
    }));
  });

  it('deletes a game by id', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(okJson({ status: 'deleted' })));

    await UserGamesAPI.delete('token', 'game-1');

    expect(fetch).toHaveBeenCalledWith('/api/v1/user-games/game-1', expect.objectContaining({
      method: 'DELETE',
      headers: expect.objectContaining({ 'Authorization': 'Bearer token' }),
    }));
  });

  it('gets a range of analysis moves', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(okJson([])));

    await UserGamesAPI.getAnalysis('token', 'game-1', 3, 20);

    expect(fetch).toHaveBeenCalledWith(
      '/api/v1/user-games/game-1/analysis?start_move=3&limit=20',
      expect.objectContaining({ headers: expect.objectContaining({ 'Authorization': 'Bearer token' }) }),
    );
  });

  it('gets analysis for one move', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(okJson({ move_number: 3 })));

    await UserGamesAPI.getMoveAnalysis('token', 'game-1', 3);

    expect(fetch).toHaveBeenCalledWith(
      '/api/v1/user-games/game-1/analysis/3',
      expect.objectContaining({ headers: expect.objectContaining({ 'Authorization': 'Bearer token' }) }),
    );
  });

  it('saves session analysis with the existing JSON body', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(okJson({ game_id: 'game-1', saved_moves: 20, total_moves: 20 })));

    await UserGamesAPI.saveAnalysisFromSession('token', 'game-1', 'session-2');

    expect(fetch).toHaveBeenCalledWith('/api/v1/user-games/game-1/analysis/save', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ session_id: 'session-2', game_id: 'game-1' }),
      headers: expect.objectContaining({ 'Authorization': 'Bearer token' }),
    }));
  });

  it('surfaces non-success response text', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      text: vi.fn().mockResolvedValue('invalid game'),
    }));

    await expect(UserGamesAPI.get('token', 'game-1'))
      .rejects.toThrow('Request failed 422: invalid game');
  });
});
