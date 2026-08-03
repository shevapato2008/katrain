import { describe, expect, it } from 'vitest';
import { isRankedGameType } from './gameType';

describe('isRankedGameType', () => {
  it.each(['ranked', 'rated', 'ai_ladder_ranked'])('treats %s as ranked', (gameType) => {
    expect(isRankedGameType(gameType)).toBe(true);
  });

  it('keeps free play unrestricted', () => {
    expect(isRankedGameType('free')).toBe(false);
  });
});
