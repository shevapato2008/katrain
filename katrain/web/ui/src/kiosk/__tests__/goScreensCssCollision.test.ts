import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

/**
 * `go-screens.css` 里**不许有两条裸单类选择器同名**。
 *
 * ## 这条闸是被一个真缺陷换来的(2026-08-25)
 *
 * 屏 22 成长把右栏写成 `.gside { display:flex; flex-direction:column; gap:12px }`,
 * 而屏 06 在线大厅早就有一个 `.gside`(对局卡里那枚「执黑 / 执白」标,
 * `display:flex; align-items:center; gap:6px`)。两条**同特异度**,后面那条赢了
 * `display` / `gap` / `font-size`,可它**没设 `flex-direction`** ——
 * 于是 `column` 从屏 22 那条漏了过去,把屏 06 的标变成竖排、撑破了对局卡。
 *
 * ⚠️ **两屏的测试当时全绿。** 屏 22 的几何闸量的是屏 22,屏 06 的单测量的是屏 06,
 * 没有任何一条同时看得见这两个选择器 —— 这正是「闸量错了对象」那一族:
 * 逐屏断言对「跨屏互相污染」免疫。它最后是**四图重取**时露出来的,
 * 而四图只有在有人恰好回去重拍那一屏时才会露。
 *
 * ⇒ 判据落在**样式表本身**上:同一个类名在这份文件里只许有一处裸定义。
 * 带上下文的写法(`.a .b`、`.a.is-x`、`.a > .b`)不在此列 —— 那是有意的分支,
 * 不是两个屏各写各的。
 *
 * **变异实测**:把 `.gcol` 改回 `.gside` ⇒ 本条当场红,并把两处行号都printed出来。
 */

const CSS = resolve(__dirname, '../../kiosk-shell/go-screens.css');

/**
 * 去掉注释后,收集所有**顶层裸单类**选择器(`.foo {`)及其出现的行号。
 *
 * ⚠️ `@media` / `@supports` / `@container` **块内的重声明不算碰撞** —— 那是同一个类
 * 对同一屏的条件覆盖(`prefers-reduced-motion` 就必须这么写),不是两屏各写各的。
 * 这一条是被一次误报换来的(2026-09-20:`.game-win-trophy` 的 reduced-motion 覆盖被判成碰撞)。
 * 按「误报=判据选错了对象,不是再加一个例外」处理:改的是判据(补上 at-rule 嵌套),不是加白名单。
 */
export function bareClassSelectors(css: string): Map<string, number[]> {
  // 先整体去注释,但保留换行以便行号仍然准。
  let stripped = '';
  let i = 0;
  while (i < css.length) {
    if (css[i] === '/' && css[i + 1] === '*') {
      const end = css.indexOf('*/', i + 2);
      const chunk = css.slice(i, end === -1 ? css.length : end + 2);
      stripped += chunk.replace(/[^\n]/g, '');   // 注释整体换成等量换行
      i = end === -1 ? css.length : end + 2;
    } else {
      stripped += css[i];
      i += 1;
    }
  }

  const out = new Map<string, number[]>();
  let depth = 0;
  const atRuleDepths: number[] = [];
  let buf = '';
  let line = 1;
  for (const ch of stripped) {
    if (ch === '\n') { line += 1; buf += ch; continue; }
    if (ch === '{') {
      const selector = buf.trim();
      if (selector.startsWith('@')) {
        atRuleDepths.push(depth);
      } else if (atRuleDepths.length === 0) {
        for (const part of selector.split(',')) {
          const p = part.trim();
          if (/^\.[A-Za-z0-9_-]+$/.test(p)) out.set(p, [...(out.get(p) ?? []), line]);
        }
      }
      depth += 1;
      buf = '';
    } else if (ch === '}') {
      depth -= 1;
      while (atRuleDepths.length && atRuleDepths[atRuleDepths.length - 1] >= depth) atRuleDepths.pop();
      buf = '';
    } else {
      buf += ch;
    }
  }
  return out;
}

describe('go-screens.css 跨屏类名碰撞', () => {
  it('同一个裸单类选择器只许定义一次', () => {
    const found = bareClassSelectors(readFileSync(CSS, 'utf8'));
    const dupes = [...found.entries()]
      .filter(([, lines]) => lines.length > 1)
      .map(([name, lines]) => `${name} 在 ${lines.join(' / ')} 行各定义了一次`);
    expect(dupes, '两屏各写各的同名类 —— 后一条不会覆盖前一条没写的属性,漏过去的那几个会跨屏生效').toEqual([]);
  });

  it('判据本身:顶层同名要抓,@media 里的条件覆盖不算碰撞', () => {
    // 收窄之后最该担心的是「漏掉真碰撞」,所以这两格必须一起在场。
    const collision = bareClassSelectors(`
      .gside { display: flex; gap: 6px; }
      .gcard { color: red; }
      .gside { flex-direction: column; }
    `);
    expect(collision.get('.gside')?.length).toBe(2);

    const mediaOverride = bareClassSelectors(`
      .game-win-trophy { animation: spin 1.6s; }
      @media (prefers-reduced-motion: reduce) {
        .game-win-trophy { animation: none; }
      }
    `);
    expect(mediaOverride.get('.game-win-trophy')?.length).toBe(1);

    // at-rule 出来之后照常再抓 —— 别把嵌套状态漏在栈里。
    const afterAtRule = bareClassSelectors(`
      .gcol { color: red; }
      @media (min-width: 1px) { .gcol { color: blue; } }
      .gcol { color: green; }
    `);
    expect(afterAtRule.get('.gcol')?.length).toBe(2);
  });

  it('这份扫描确实扫到了东西 —— 不是空过', () => {
    // 没有这一条的话,正则写错(比如永远匹配不到)也会让上面那条永远绿。
    const found = bareClassSelectors(readFileSync(CSS, 'utf8'));
    expect(found.size).toBeGreaterThan(80);
    expect(found.has('.gcard')).toBe(true);
    expect(found.has('.gcol')).toBe(true);
  });
});
