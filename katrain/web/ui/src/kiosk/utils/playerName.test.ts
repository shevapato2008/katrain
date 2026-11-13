import { describe, expect, it } from 'vitest';
import type { GameState } from '../../api';
import { seatName } from './playerName';

const engineState = (over: Partial<GameState> = {}) => ({
  platform_engine_color: 'B',
  players_info: { B: { name: '[golaxy] 星皮猴' }, W: { name: 'Me' } },
  ...over,
} as unknown as GameState);

describe('星阵引擎局席位名称', () => {
  it.each(['B', 'W'] as const)('真人执%s时使用公开显示名', (color) => {
    const state = engineState({ platform_engine_color: color === 'B' ? 'W' : 'B' });
    expect(seatName(state, color, true, ' shuangmei ')).toBe('shuangmei');
  });

  it.each([undefined, '', '   '])('公开显示名为 %s 时回落我', (name) => {
    expect(seatName(engineState(), 'W', true, name)).toBe('我');
  });

  it.each([
    ['[golaxy] 星皮猴', '星阵·星皮猴'],
    ['[GoLaXy] 星猛虎', '星阵·星猛虎'],
  ])('去除 %s 的协议前缀并保留真实机器人名称', (raw, expected) => {
    const state = engineState({ players_info: { B: { name: raw }, W: { name: 'Me' } } as GameState['players_info'] });
    expect(seatName(state, 'B', true)).toBe(expected);
  });

  it('复用机器人名称翻译，并翻译品牌和真人回落文案', () => {
    const words: Record<string, string> = { Golaxy: 'Golaxy', 星皮猴: 'Star Monkey', 'game:me': 'Me' };
    const t = (key: string, fallback?: string) => words[key] ?? fallback ?? key;
    expect(seatName(engineState(), 'B', true, undefined, t)).toBe('Golaxy·Star Monkey');
    expect(seatName(engineState(), 'W', true, undefined, t)).toBe('Me');
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
    expect(seatName(state, 'B', engineMode, 'shuangmei')).toBe('Alice');
    expect(seatName(state, 'W', engineMode, 'shuangmei')).toBe('Me');
  });
});
