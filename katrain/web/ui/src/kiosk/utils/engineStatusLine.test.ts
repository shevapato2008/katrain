import { describe, expect, it } from 'vitest';
import { engineStatusLine } from './engineStatusLine';

const t = (_key: string, fallback: string) => fallback;

describe('engineStatusLine —— /api/v1/health 的引擎状态翻成人话', () => {
  it('reachable → 可用', () => {
    expect(engineStatusLine('reachable', t)).toEqual({ text: '可用', ok: true });
  });

  it('unreachable → 连不上', () => {
    expect(engineStatusLine('unreachable', t)).toEqual({ text: '连不上', ok: false });
  });

  // 根本没配云端,说成「连不上」会让人去查网络。
  it('unconfigured → 没配置,不是连不上', () => {
    expect(engineStatusLine('unconfigured', t)).toEqual({ text: '没配置', ok: false });
  });

  // 屏上一行人话,副标一行证据 —— 码留给报修时念给客服听。
  it('error_502 → 连不上,副标里带着 502', () => {
    const line = engineStatusLine('error_502', t);
    expect(line.text).toBe('连不上');
    expect(line.ok).toBe(false);
    expect(line.sub).toContain('502');
  });

  it('认不出来的值不猜,原样写出来', () => {
    expect(engineStatusLine('weird', t)).toEqual({ text: 'weird', ok: false });
  });
});
