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

/** 去掉注释后,收集所有**裸单类**选择器(`.foo {`)及其出现的行号。 */
function bareClassSelectors(css: string): Map<string, number[]> {
  const lines = css.split('\n');
  const out = new Map<string, number[]>();
  let inComment = false;
  lines.forEach((raw, i) => {
    let line = raw;
    if (inComment) {
      const end = line.indexOf('*/');
      if (end === -1) return;
      line = line.slice(end + 2);
      inComment = false;
    }
    // 同一行里可能开一段注释
    for (;;) {
      const start = line.indexOf('/*');
      if (start === -1) break;
      const end = line.indexOf('*/', start + 2);
      if (end === -1) { line = line.slice(0, start); inComment = true; break; }
      line = line.slice(0, start) + line.slice(end + 2);
    }
    const brace = line.indexOf('{');
    if (brace === -1) return;
    const selector = line.slice(0, brace).trim();
    if (!selector || selector.startsWith('@')) return;
    for (const part of selector.split(',')) {
      const p = part.trim();
      if (/^\.[A-Za-z0-9_-]+$/.test(p)) {
        out.set(p, [...(out.get(p) ?? []), i + 1]);
      }
    }
  });
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

  it('这份扫描确实扫到了东西 —— 不是空过', () => {
    // 没有这一条的话,正则写错(比如永远匹配不到)也会让上面那条永远绿。
    const found = bareClassSelectors(readFileSync(CSS, 'utf8'));
    expect(found.size).toBeGreaterThan(80);
    expect(found.has('.gcard')).toBe(true);
    expect(found.has('.gcol')).toBe(true);
  });
});
