import { describe, expect, it } from 'vitest';
import type { GameState } from '../../api';
import { seatName } from './playerName';

const engineState = (over: Partial<GameState> = {}) => ({
  platform_engine_color: 'B',
  players_info: { B: { name: '[golaxy] 星皮猴' }, W: { name: 'Me' } },
  ...over,
} as unknown as GameState);

describe('星阵引擎局席位名称', () => {
  it.each(['B', 'W'] as const)('真人执%s时使用当前星阵昵称', (color) => {
    const state = engineState({
      platform_engine_color: color === 'B' ? 'W' : 'B',
      players_info: { B: { name: ' 星阵昵称 ' }, W: { name: ' 星阵昵称 ' } } as GameState['players_info'],
    });
    expect(seatName(state, color, true)).toBe('星阵昵称');
  });

  it.each(['Me', ' Me ', '', '   '])('真人名字为旧占位 %s 时回落星阵用户', (name) => {
    const state = engineState({ players_info: { B: { name: '[golaxy] 星皮猴' }, W: { name } } as GameState['players_info'] });
    expect(seatName(state, 'W', true)).toBe('星阵用户');
  });

  it.each([
    ['[golaxy] 星皮猴', '星阵·星皮猴'],
    ['[GoLaXy] 星猛虎', '星阵·星猛虎'],
  ])('去除 %s 的协议前缀并保留真实机器人名称', (raw, expected) => {
    const state = engineState({ players_info: { B: { name: raw }, W: { name: 'Me' } } as GameState['players_info'] });
    expect(seatName(state, 'B', true)).toBe(expected);
  });

  it('复用机器人名称翻译，并翻译品牌和真人回落文案', () => {
    const words: Record<string, string> = { Golaxy: 'Golaxy', 星皮猴: 'Star Monkey', '星阵用户': 'Golaxy player' };
    const t = (key: string, fallback?: string) => words[key] ?? fallback ?? key;
    expect(seatName(engineState(), 'B', true, t)).toBe('Golaxy·Star Monkey');
    expect(seatName(engineState(), 'W', true, t)).toBe('Golaxy player');
  });

  it.each(['', '[golaxy]   '])('机器人名称为空时只显示星阵 (%s)', (name) => {
    const state = engineState({ players_info: { B: { name }, W: { name: 'Me' } } as GameState['players_info'] });
    expect(seatName(state, 'B', true)).toBe('星阵');
  });

  it('保留未收录的机器人名称', () => {
    const state = engineState({ players_info: { B: { name: '[golaxy] CustomBot' }, W: { name: 'Me' } } as GameState['players_info'] });
    expect(seatName(state, 'B', true)).toBe('星阵·CustomBot');
  });

  it.each([
    [false, 'B'],
    [true, undefined],
    [true, null],
    [true, 'invalid'],
  ])('engineMode=%s 且引擎色为 %s 时保留原始名称', (engineMode, engineColor) => {
    const state = engineState({
      platform_engine_color: engineColor as GameState['platform_engine_color'],
      players_info: { B: { name: 'Alice' }, W: { name: 'Me' } } as GameState['players_info'],
    });
    expect(seatName(state, 'B', engineMode)).toBe('Alice');
    expect(seatName(state, 'W', engineMode)).toBe('Me');
  });
});
