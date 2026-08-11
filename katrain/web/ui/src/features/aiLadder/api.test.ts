import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  AiLadderApiError,
  endAiLadderGame,
  getAiLadderGameStatus,
  getAiLadderSettlementReceipt,
  getAiLadderStatus,
  startAiLadderGame,
} from './api';

afterEach(() => vi.unstubAllGlobals());

describe('ai ladder API', () => {
  it.each([
    { state: 'active', game_id: 'game-1' },
    { state: 'pending_settlement', game_id: 'game-1' },
    { state: 'settled', game_id: 'game-1', receipt: { counted: true, reason: null } },
  ])('loads a strict per-game lifecycle: %j', async (body) => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(getAiLadderGameStatus('game-1', 'galaxy-token')).resolves.toEqual(body);
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/ai-ladder/games/game-1/status', expect.objectContaining({
      headers: { Authorization: 'Bearer galaxy-token' }, credentials: 'same-origin',
    }));
  });

  it('rejects a malformed or failed per-game lifecycle response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: 'Ranked game not found' }),
      { status: 404, headers: { 'Content-Type': 'application/json' } },
    )));

    await expect(getAiLadderGameStatus('missing')).rejects.toEqual(expect.objectContaining({
      status: 404, message: 'Ranked game not found',
    }));
  });

  it('loads status with bearer authentication when a token exists', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ view_state: 'ready' }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    await getAiLadderStatus('galaxy-token');

    expect(fetchMock).toHaveBeenCalledWith('/api/v1/ai-ladder/status', expect.objectContaining({
      headers: { Authorization: 'Bearer galaxy-token' },
    }));
  });

  it('loads status cookie-only when no JavaScript token exists', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ view_state: 'ready' }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    await getAiLadderStatus();

    expect(fetchMock).toHaveBeenCalledWith('/api/v1/ai-ladder/status', expect.objectContaining({
      credentials: 'same-origin',
      headers: {},
    }));
  });

  it('loads the authenticated receipt for one server-issued game id', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      state: 'settled', game_id: 'g1', counted: false, reason: 'engine_unavailable',
    }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    await getAiLadderSettlementReceipt('g1', 'galaxy-token');

    expect(fetchMock).toHaveBeenCalledWith('/api/v1/ai-ladder/settlements/g1', expect.objectContaining({
      headers: { Authorization: 'Bearer galaxy-token' }, credentials: 'same-origin',
    }));
  });

  it('preserves backend detail for an unavailable opponent', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: 'AI rung is provisional and unavailable' }),
      { status: 409, headers: { 'Content-Type': 'application/json' } },
    )));

    await expect(startAiLadderGame({ board_size: 19, rules: 'chinese', komi: 7.5, handicap: 0,
      color: 'black', time_enabled: false, main_time: 0, byo_length: 30, byo_periods: 3 }))
      .rejects.toEqual(expect.objectContaining<Partial<AiLadderApiError>>({
        status: 409,
        message: 'AI rung is provisional and unavailable',
      }));
  });

  it('starts cookie-only without an Authorization header', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ session_id: 's1' }), { status: 201 }));
    vi.stubGlobal('fetch', fetchMock);
    await startAiLadderGame({ board_size: 19, rules: 'chinese', komi: 7.5, handicap: 0,
      color: 'black', time_enabled: false, main_time: 0, byo_length: 30, byo_periods: 3 });
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/ai-ladder/start', expect.objectContaining({
      credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
    }));
  });

  it('ends a game as a user resignation with bearer authentication', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      state: 'pending_settlement', game_id: 'game-1',
    }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(endAiLadderGame('game-1', 'galaxy-token')).resolves.toEqual({
      state: 'pending_settlement', game_id: 'game-1',
    });
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/ai-ladder/games/game-1/end', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer galaxy-token' },
      credentials: 'same-origin',
      body: JSON.stringify({ reason: 'user_resigned' }),
    });
  });

  it('returns a settled lifecycle with its receipt from a successful end request', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      state: 'settled',
      game_id: 'game-1',
      receipt: { counted: true, reason: null },
    }), { status: 200 })));

    await expect(endAiLadderGame('game-1')).resolves.toEqual({
      state: 'settled',
      game_id: 'game-1',
      receipt: { counted: true, reason: null },
    });
  });

  it('treats a released reservation as the success it is, not as a failed request', async () => {
    // 载荷逐字取自 `ai_ladder.py` 里 `end_ranked_game` 的 released 分支 —— 不是照类型想象出来的。
    // 象棋踩过这一格:后端成功,而界面的解码器认不出这个形状,于是屏上告诉用户「失败了」。
    // 围棋这边形状不同、结局一样:让掉**没有 receipt**(它不写账本 —— 那一局根本没开始过),
    // 于是少了这条分支,守卫把 200 当成畸形响应,`createApiError` 拿着 `response.ok === true`
    // 造出一个 `Request failed 200`,用户看到「结束对局失败，请重试」—— 而那一刻预约已经
    // 删掉了、账号已经放开了。
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      state: 'released', game_id: 'game-1', counted: false,
    }), { status: 200 })));

    await expect(endAiLadderGame('game-1')).resolves.toEqual({
      state: 'released', game_id: 'game-1', counted: false,
    });
  });

  it.each([
    { state: 'released', game_id: 'another-game', counted: false },
    { state: 'released', game_id: 'game-1', counted: true },
    { state: 'released', game_id: 'game-1' },
  ])('still rejects a malformed released lifecycle: %j', async (body) => {
    // `counted` 必须是**假**:让掉的全部意义就是什么都不计。一个说自己计了分的让掉
    // 是个矛盾的响应,放它过去等于让界面替后端编一个结果。
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 200 })));

    await expect(endAiLadderGame('game-1')).rejects.toEqual(expect.objectContaining<Partial<AiLadderApiError>>({
      status: 200,
    }));
  });

  it('URL-encodes the server-issued game id when ending a game', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      state: 'pending_settlement', game_id: 'game/1',
    }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    await endAiLadderGame('game/1');

    expect(fetchMock).toHaveBeenCalledWith('/api/v1/ai-ladder/games/game%2F1/end', expect.any(Object));
  });

  it('returns an already-effective 409 settled lifecycle instead of an API error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      state: 'settled',
      game_id: 'game-1',
      receipt: { counted: false, reason: 'inconclusive' },
    }), { status: 409 })));

    await expect(endAiLadderGame('game-1')).resolves.toEqual({
      state: 'settled',
      game_id: 'game-1',
      receipt: { counted: false, reason: 'inconclusive' },
    });
  });

  it('returns a matching pending lifecycle from a 409 response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      state: 'pending_settlement', game_id: 'game-1',
    }), { status: 409 })));

    await expect(endAiLadderGame('game-1')).resolves.toEqual({
      state: 'pending_settlement', game_id: 'game-1',
    });
  });

  it('keeps API error mapping for a 409 that is not a settled lifecycle', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: 'game is still active' }),
      { status: 409, headers: { 'Content-Type': 'application/json' } },
    )));

    await expect(endAiLadderGame('game-1')).rejects.toEqual(expect.objectContaining<Partial<AiLadderApiError>>({
      status: 409,
      message: 'game is still active',
    }));
  });

  it.each([
    { state: 'settled' },
    { state: 'settled', game_id: 'another-game', receipt: { counted: true, reason: null } },
    { state: 'settled', game_id: 'game-1', receipt: null },
    { state: 'settled', game_id: 'game-1', receipt: { counted: 'yes', reason: null } },
    { state: 'settled', game_id: 'game-1', receipt: { counted: false, reason: 'unexpected_reason' } },
  ])('keeps API error mapping for a malformed 409 settled lifecycle: %j', async (body) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 409 })));

    await expect(endAiLadderGame('game-1')).rejects.toEqual(expect.objectContaining<Partial<AiLadderApiError>>({
      status: 409,
    }));
  });

  it.each([
    { state: 'pending_settlement', game_id: 'another-game' },
    { state: 'settled', game_id: 'game-1' },
    { state: 'settled', game_id: 'game-1', receipt: { counted: true, reason: 'unexpected_reason' } },
  ])('maps a malformed successful lifecycle to an API error: %j', async (body) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 200 })));

    await expect(endAiLadderGame('game-1')).rejects.toEqual(expect.objectContaining<Partial<AiLadderApiError>>({
      status: 200,
    }));
  });

  it.each([200, 409])('maps an active end-game lifecycle with status %i to an API error', async (status) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      state: 'active', game_id: 'game-1',
    }), { status })));

    await expect(endAiLadderGame('game-1')).rejects.toEqual(expect.objectContaining<Partial<AiLadderApiError>>({
      status,
    }));
  });

  it('keeps the existing API error mapping for other failed end requests', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: 'game is not owned by this user' }),
      { status: 403, headers: { 'Content-Type': 'application/json' } },
    )));

    await expect(endAiLadderGame('game-1')).rejects.toEqual(expect.objectContaining<Partial<AiLadderApiError>>({
      status: 403,
      message: 'game is not owned by this user',
    }));
  });
});
