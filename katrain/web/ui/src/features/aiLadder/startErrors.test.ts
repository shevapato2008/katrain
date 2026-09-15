import { describe, expect, test } from 'vitest';
import {
  aiLadderStartUnavailableMessage,
  aiLadderStatusUnavailableMessage,
  aiLadderUnavailableReason,
} from './startErrors';

describe('升降级 503 按服务端 detail 分原因(A15 / A2)', () => {
  test.each([
    ['Remote server unavailable', 'offline'],
    ['Ranked AI ladder authority is unavailable on this node', 'not_authoritative'],
    ['Ranked engine cannot serve the seated rung', 'engine_cannot_serve'],
    ['Ranked game reservation is awaiting cloud expiry', 'cloud_unconfirmed'],
    ['Ranked game activation is awaiting cloud reconciliation', 'cloud_unconfirmed'],
    ['Request failed 503: {"detail":"Ranked engine cannot serve the seated rung"}', 'engine_cannot_serve'],
    ['Could not create game session', 'unknown'],
  ])('%s → %s', (detail, reason) => {
    expect(aiLadderUnavailableReason(detail)).toBe(reason);
  });

  test('断网时状态接口不再说「本机不记升降级成绩」', () => {
    const msg = aiLadderStatusUnavailableMessage('Remote server unavailable');
    expect(msg).toContain('连不上云端');
    expect(msg).not.toContain('本机不记');
  });

  test('节点确实不记成绩时原句不变', () => {
    expect(aiLadderStatusUnavailableMessage('Ranked AI ladder authority is unavailable on this node'))
      .toBe('本机不记升降级成绩，暂时无法开始升降级对弈');
  });

  test('引擎带不动这一档:说没开局、段位没动,不叫人「稍后再试」', () => {
    const msg = aiLadderStartUnavailableMessage('Ranked engine cannot serve the seated rung');
    expect(msg).toContain('本次没有开局');
    expect(msg).toContain('不影响你的段位');
    expect(msg).not.toContain('稍后再试');
  });

  test('云端未确认:不许说「本次没有开局」', () => {
    expect(aiLadderStartUnavailableMessage('Ranked game activation is awaiting cloud reconciliation'))
      .not.toContain('本次没有开局');
  });
});
