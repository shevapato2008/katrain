import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { resolve } from 'node:path';

import { LIVE_SOURCE_META, liveSourceLabel, liveSourceMeta } from './liveSources';

/**
 * 直播 / 预告平台的名字**只许有一处**。
 *
 * ## 这条闸也是被一个真缺陷换来的(2026-08-26)
 *
 * 同一张表在五个文件里各写了一遍,而它们**已经走散了**:
 * `pandanet` 在屏 15 棋谱上是「PandaNet」,在屏 18 直播和另外两处是「IGS」——
 * 同一个平台在两屏上是两个名字,用户没有任何办法知道那是同一家。
 *
 * 逐屏的单测对这个免疫:每一屏都在验证**自己那一份**表,而每一份都自洽。
 * ⇒ 判据必须落在**源码本身**上,和 `goScreensCssCollision` 是同一族。
 */

const SRC = resolve(__dirname, '..');
/**
 * 一份「平台名表」长什么样:**把这几个 id 当键,后面跟一个字符串或对象**。
 * `{ xingzhen: '星阵' }` / `{ pandanet: { label: 'IGS' } }` 都算。
 *
 * ⚠️ **判据是表的形状,不是那几个词。** 第一版扫「星阵 / 弈客 / 幽玄」这几个字,
 * 结果命中六处全是正当用法 —— 注释在讲「星阵是引擎直连」,
 * `t('game:golaxy_ai', '星阵围棋 · 人机')` 是这一屏的标题,充值那句话里也有它。
 * **闸报的每一条都必须是真违规**,否则下一个人学会的是给它加白名单,
 * 而白名单一长,这条闸就再也拦不住真的那一份。
 */
const TABLE_SHAPE = /\b(xingzhen|yike|pandanet|foxwq|yugen|nihonkiin)\s*:\s*[{'"`]/;

/**
 * 去掉注释再扫。注释里出现 `yike:` 这种写法虽然少见,但去掉它零成本。
 */
function stripComments(text: string): string {
  return text.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1');
}

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    if (name === 'node_modules' || name === 'kiosk-shell') continue;
    const full = resolve(dir, name);
    if (statSync(full).isDirectory()) walk(full, out);
    else if (/\.(ts|tsx)$/.test(name) && !/\.test\.tsx?$/.test(name)) out.push(full);
  }
  return out;
}

describe('平台名只有一处', () => {
  it('没有第二份表 —— 全仓只有 liveSources.ts 拿这些 id 当键配名字', () => {
    const offenders = walk(SRC)
      .filter((f) => !f.endsWith('/utils/liveSources.ts'))
      .filter((f) => TABLE_SHAPE.test(stripComments(readFileSync(f, 'utf8'))))
      .map((f) => f.slice(SRC.length + 1));
    expect(offenders, '又有人在别处写了一份平台名表').toEqual([]);
  });

  it('pandanet 在全仓只有一个名字', () => {
    expect(LIVE_SOURCE_META.pandanet.label).toBe('IGS');
    // 走散那次就是这个词:四处里三处写 IGS,棋谱屏写 PandaNet。
    const offenders = walk(SRC)
      .filter((f) => !f.endsWith('/utils/liveSources.ts'))
      .filter((f) => stripComments(readFileSync(f, 'utf8')).includes('PandaNet'))
      .map((f) => f.slice(SRC.length + 1));
    expect(offenders).toEqual([]);
  });
});

describe('认不出来的 id', () => {
  it('原样吐出去,不写「未知来源」—— 那个 id 用户还能拿去搜', () => {
    expect(liveSourceLabel('sgf_archive')).toBe('sgf_archive');
    expect(liveSourceMeta('sgf_archive')).toBeNull();
  });

  it('两条枚举的每一个值都有名字', () => {
    for (const id of ['xingzhen', 'yike', 'pandanet', 'foxwq', 'yugen', 'nihonkiin']) {
      expect(liveSourceMeta(id), id).not.toBeNull();
    }
  });
});
