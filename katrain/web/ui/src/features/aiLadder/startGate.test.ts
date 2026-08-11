import { describe, expect, it } from 'vitest';
import {
  aiLadderBlockingGame,
  aiLadderStartBlock,
  canStartAiLadderGame,
  isProvisionalSeating,
  isRungUnseatable,
} from './startGate';
import type { AiLadderCatalogEntry, AiLadderReadyStatus } from './types';

const rung = (overrides: Partial<AiLadderCatalogEntry> = {}): AiLadderCatalogEntry => ({
  rung: 16,
  rank_name: '5级',
  certification_status: 'certified',
  availability: 'available',
  route: 'server',
  ...overrides,
});

const ready = (overrides: Partial<AiLadderReadyStatus> = {}): AiLadderReadyStatus => ({
  view_state: 'ready',
  placement_state: { phase: 'placement', completed_games: 0, total_games: 5 },
  current_opponent: rung(),
  recent_ranked_results: [],
  net_score: 0,
  pending_settlement: false,
  ...overrides,
});

describe('aiLadderStartBlock', () => {
  it('lets a certified, available rung start', () => {
    expect(aiLadderStartBlock(ready())).toBeNull();
    expect(canStartAiLadderGame(ready())).toBe(true);
  });

  it('blocks while the status is loading or failed', () => {
    expect(aiLadderStartBlock({ view_state: 'loading' })).toBe('not_ready');
    expect(aiLadderStartBlock({ view_state: 'error', message: 'x' })).toBe('not_ready');
  });

  it('blocks while the previous game is still settling', () => {
    expect(aiLadderStartBlock(ready({ pending_settlement: true }))).toBe('pending_settlement');
  });

  it('另一台设备正在下的时候,开始按钮必须当场是灰的', () => {
    // 这一格从前**一个字都不看**:云端的 `pending_settlement` 只在「下完了、成绩在送」时
    // 为真,所以另一台设备正在下时它是假的,kiosk 的开始按钮是可点的 —— 点下去才被
    // 服务端一个 409 顶回来。屏上先答应、服务端再否决。
    const status = ready({
      blocking_game: {
        game_id: 'game-1', state: 'active', ownership: 'other_device',
        user_color: 'B', opponent_rank_name: '5段',
      },
    });
    expect(status.pending_settlement).toBe(false);
    expect(aiLadderStartBlock(status)).toBe('blocking_game');
    expect(canStartAiLadderGame(status)).toBe(false);
    expect(aiLadderBlockingGame(status)?.game_id).toBe('game-1');
  });

  it.each(['reserved', 'pending_settlement'] as const)('挡局的每一个状态都挡:%s', (state) => {
    // 三个状态代价不同(让掉 / 认输),但**都占着这个账号**,所以在这里一视同仁。
    const status = ready({
      pending_settlement: state === 'pending_settlement',
      blocking_game: {
        game_id: 'game-1', state, ownership: 'current_device',
        user_color: 'B', opponent_rank_name: '5段',
      },
    });
    expect(aiLadderStartBlock(status)).toBe('blocking_game');
  });

  it('把「哪一局挡着」带出来,而 pending_settlement 只够说一句「等着」', () => {
    // 两者同时成立时以 blocking_game 为准:它带着是哪一局,调用方据此才摆得出那一格
    // 真正的出路(立即重试 / 认输 / 让掉)。
    const status = ready({
      pending_settlement: true,
      blocking_game: {
        game_id: 'game-1', state: 'pending_settlement', ownership: 'current_device',
        user_color: 'B', opponent_rank_name: '5段',
        sync: { state: 'waiting', attempt: 2, max_attempts: 5, next_attempt_in_seconds: 18, last_http_status: null, last_error: null },
      },
    });
    expect(aiLadderStartBlock(status)).toBe('blocking_game');
    expect(aiLadderBlockingGame(status)?.sync?.state).toBe('waiting');
  });

  it('没有挡局的时候不凭空造一个', () => {
    expect(aiLadderBlockingGame(ready())).toBeNull();
    expect(aiLadderBlockingGame(ready({ blocking_game: null }))).toBeNull();
    expect(aiLadderBlockingGame({ view_state: 'loading' })).toBeNull();
  });

  it('挡局挡住开始按钮,但不改「这个档位能不能坐」这句事实', () => {
    // 两个问题分开问:一条与档位无关的原因,不许顺手吞掉一句关于档位的事实。
    const status = ready({
      current_opponent: rung({ certification_status: 'provisional' }),
      blocking_game: {
        game_id: 'game-1', state: 'active', ownership: 'other_device',
        user_color: 'B', opponent_rank_name: '5段',
      },
    });
    expect(aiLadderStartBlock(status)).toBe('blocking_game');
    expect(isRungUnseatable(status)).toBe(true);
  });

  it('blocks an uncertified rung on a node that will not seat one', () => {
    expect(aiLadderStartBlock(ready({ current_opponent: rung({ certification_status: 'provisional' }) })))
      .toBe('rung_not_certified');
    expect(aiLadderStartBlock(ready({ current_opponent: rung({ availability: 'unavailable' }) })))
      .toBe('rung_not_certified');
  });

  it('lets the same rung start where the server says it will seat one', () => {
    const status = ready({
      current_opponent: rung({ certification_status: 'provisional', availability: 'unavailable' }),
      provisional_play_allowed: true,
    });
    expect(aiLadderStartBlock(status)).toBeNull();
    // ...and the UI must say the rung is unmeasured, because it still is.
    expect(isProvisionalSeating(status)).toBe(true);
  });

  it('does not call a certified rung provisional just because the switch is on', () => {
    expect(isProvisionalSeating(ready({ provisional_play_allowed: true }))).toBe(false);
  });

  it('treats a server that never sends the field as one that will not seat an uncertified rung', () => {
    const status = ready({ current_opponent: rung({ certification_status: 'provisional' }) });
    expect(status.provisional_play_allowed).toBeUndefined();
    expect(aiLadderStartBlock(status)).toBe('rung_not_certified');
    expect(isProvisionalSeating(status)).toBe(false);
  });

  it('blocks when the server offered no opponent at all', () => {
    expect(aiLadderStartBlock(ready({ current_opponent: null }))).toBe('no_opponent');
  });
});
