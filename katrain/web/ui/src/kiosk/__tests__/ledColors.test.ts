import { describe, it, expect } from 'vitest';
import { LED_HEX, LED_LABEL, type LedIntent } from '../constants/ledColors';

const intents: LedIntent[] = ['black', 'white', 'remove', 'hint'];

describe('ledColors', () => {
  it('maps every intent to a 6-digit hex', () => {
    intents.forEach((i) => expect(LED_HEX[i]).toMatch(/^#[0-9a-f]{6}$/));
  });

  it('pins the fixed LED colour semantics', () => {
    expect(LED_HEX.black).toBe('#ff3b30');
    expect(LED_HEX.white).toBe('#34c759');
    expect(LED_HEX.remove).toBe('#2f6fff');
    expect(LED_HEX.hint).toBe('#ffffff');
  });

  it('labels are the Chinese colour names', () => {
    expect(LED_LABEL).toEqual({ black: '红', white: '绿', remove: '蓝', hint: '白' });
  });
});
