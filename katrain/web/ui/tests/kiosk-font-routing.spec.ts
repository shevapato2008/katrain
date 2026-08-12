import { expect, test, type Page } from '@playwright/test';

/**
 * 字体路由闸 —— 问浏览器「这段字你最后用哪个字体画的」,不看 CSS 写得对不对。
 *
 * 规范 §9(`kiosk-shell-spec.md:609/634/1141`)把字族定死:「智星盒」三字 = 龙藏行楷、
 * **其余所有中文 = 霞鹜文楷**、拉丁与数字 = Geist / Newsreader、等宽 = JetBrains Mono。
 * 中西文靠**栈的回退**分开:拉丁面带显式 latin `unicode-range`,中文码点在那儿匹配不到面,
 * 自然落到下一族 "SmartBox Kai"。
 *
 * ⚠️ **为什么不直接接上游的 `scripts/check-fonts.mjs`。**
 * 那个脚本(第 33-35 行)把一张探针页写进 `assets/` 再量 —— 它量的是**资产包自己**,
 * 不是我们的 React 页面。抄过来跑只能证明「抄来的这份资产包内部自洽」,而我们真正要答的是
 * 「**我们屏上那些中文,最后由谁画的**」。这两个问题的差别不是理论上的:
 * MUI 组件的字体走 `typography.fontFamily`(emotion 类),**根本不读 `var(--font-*)`**,
 * 所以资产包全对、`tokens.css` 全对,屏上照样可以一个字都没走楷体。
 * ⇒ **照抄它的方法(CDP `CSS.getPlatformFontsForNode`),不照抄它的作用域。**
 *
 * 判据全部落在 `document.body` 上:CDP 这个命令报的是该节点**及其子文本节点**实际命中的
 * platform font 和覆盖字符数,所以在 body 上问一次 = 问「整屏用了哪些字体」。
 * 屏级的负向断言比逐个探针结实:它连**我没想到要探的那一块**一起管。
 */

test.use({ viewport: { width: 1024, height: 600 } });

/** 最小登录桩 —— 这条闸只关心字体,不关心业务数据长什么样。 */
const stubAuth = async (page: Page) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'kiosk-font-gate-token');
    localStorage.setItem('katrain_language', 'cn');
  });
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, username: 'tester', rank: '5段', credits: 0 },
  }));
};

type PlatformFont = { familyName: string; glyphCount: number };

/**
 * 整屏实际命中的 platform font,按覆盖字符数从多到少。
 *
 * ⚠️ **不能在 `body` 上问一次了事,我先这么写过,它报「一个都没有」。**
 * `CSS.getPlatformFontsForNode` 只统计该节点**自己的直接子文本节点**,不往下递归 ——
 * 而 `body` 底下全是元素、一个直接文本节点都没有。那次的红是**这条闸自己写错了**,
 * 不是页面有问题(同一次跑里「真 Bold 面已加载」是绿的,说明楷体明明在用)。
 * ⇒ 改成把屏上真正带文字的叶子元素逐个问一遍再合并。
 */
const platformFonts = async (page: Page): Promise<{ fonts: PlatformFont[]; probed: number }> => {
  // 等字体真的落地再量:@font-face 是异步的,早一步量到的是回退字体,而那正是这条闸要抓的东西
  // —— 于是它会在**没有缺陷**的时候红。
  await page.evaluate(() => document.fonts.ready);

  // 屏上每一个「自己带可见文字」的元素都打上标记。**上限 120** 是为了让 CDP 往返有个头,
  // 探了几个会打进失败信息里 —— 报绿必须带范围。
  const probed: number = await page.evaluate(() => {
    let index = 0;
    for (const el of Array.from(document.querySelectorAll<HTMLElement>('body *'))) {
      if (index >= 120) break;
      const own = Array.from(el.childNodes)
        .filter((n) => n.nodeType === Node.TEXT_NODE)
        .map((n) => n.textContent ?? '')
        .join('')
        .trim();
      if (!own) continue;
      const box = el.getBoundingClientRect();
      if (box.width === 0 || box.height === 0) continue; // 画不出来的不算
      el.setAttribute('data-fontprobe', String(index));
      index += 1;
    }
    return index;
  });

  const cdp = await page.context().newCDPSession(page);
  await cdp.send('DOM.enable');
  await cdp.send('CSS.enable');
  const { root } = await cdp.send('DOM.getDocument', { depth: -1 });

  const total = new Map<string, number>();
  for (let i = 0; i < probed; i += 1) {
    const { nodeId } = await cdp.send('DOM.querySelector', {
      nodeId: root.nodeId, selector: `[data-fontprobe="${i}"]`,
    });
    if (!nodeId) continue;
    const { fonts } = await cdp.send('CSS.getPlatformFontsForNode', { nodeId });
    for (const font of fonts as PlatformFont[]) {
      total.set(font.familyName, (total.get(font.familyName) ?? 0) + font.glyphCount);
    }
  }

  const merged = [...total.entries()]
    .map(([familyName, glyphCount]) => ({ familyName, glyphCount }))
    .sort((a, b) => b.glyphCount - a.glyphCount);
  return { fonts: merged, probed };
};

const describeFonts = (fonts: PlatformFont[]) =>
  fonts.map((f) => `${f.familyName}(${f.glyphCount})`).join(', ') || '(一个都没有)';

const has = (fonts: PlatformFont[], fragment: string) =>
  fonts.some((f) => f.familyName.includes(fragment));

/**
 * 一屏之内可能被误用的中文字体。**分成两类,因为它们红起来的原因不同**:
 *   · 退役字库(`spec:648`)—— 说明有人又把它写回了某处 `fontFamily`;
 *   · 系统字 —— 说明霞鹜文楷**根本没加载成功**,浏览器往下掉到了开发机上碰巧有的那个。
 * 后一类在板子上根本不存在(`spec:628`:RK3562/Debian 11 上 PingFang / Songti / Kaiti SC
 * 一个都没有),所以它在开发机上红,恰恰是在替板子上的「中文没字可用」提前报警。
 */
const RETIRED_CJK = ['Noto Sans SC', 'Noto Serif SC', 'Hanken Grotesk', 'Instrument Sans', 'Source Serif'];
const SYSTEM_CJK = ['PingFang', 'Heiti', 'Songti', 'STSong', 'STHeiti', 'Hiragino', 'Kaiti', 'STKaiti'];

const assertFontRouting = async (page: Page, screen: string) => {
  const { fonts, probed } = await platformFonts(page);
  const shown = `${describeFonts(fonts)}(探了 ${probed} 个带字元素)`;
  // 一个都没探到 = 这一屏根本没渲染出来。没有这条,下面每一条都会以「没有违规」的姿态变绿。
  expect(probed, `${screen}:一个带文字的元素都没找到 —— 这屏没渲染`).toBeGreaterThan(0);

  // ① 中文必须落在霞鹜文楷上。这是这条闸的主判据,其余几条都是它的反面。
  expect(has(fonts, 'LXGW WenKai'), `${screen}:中文没走霞鹜文楷 —— 实际命中 ${shown}`).toBe(true);

  // ② 一个退役字库都不许出现。**这条比 ① 强**:①「楷体在场」和「所有中文都走楷体」
  //    是两回事 —— 半屏楷体半屏 Noto 也能让 ① 绿。
  for (const family of RETIRED_CJK) {
    expect(has(fonts, family), `${screen}:退役字库 ${family} 还在画字 —— 实际命中 ${shown}`).toBe(false);
  }
  for (const family of SYSTEM_CJK) {
    expect(has(fonts, family), `${screen}:掉到系统字 ${family} —— 板子上没有这个字,实际命中 ${shown}`).toBe(false);
  }

  // ③ 拉丁与数字走拉丁族。缺了它,「中文全对」可能是因为 Kai 被提到了栈首、连 ASCII 一起抢走。
  const latin = has(fonts, 'Geist') || has(fonts, 'Newsreader') || has(fonts, 'JetBrains');
  expect(latin, `${screen}:拉丁与数字没走 Geist / Newsreader / JetBrains —— 实际命中 ${shown}`).toBe(true);

  // ④ 龙藏只许盖「智星盒」三个字。它只有三个字形,漏出去整段会崩,而 `unicode-range` 一旦
  //    被人改宽就静默生效 —— 所以钉的是**覆盖字符数**,不是「在不在」。
  const longCang = fonts.find((f) => f.familyName.includes('Long Cang'));
  if (longCang) {
    expect(longCang.glyphCount, `${screen}:龙藏盖到了 ${longCang.glyphCount} 个字,它只有「智星盒」三个字形`).toBeLessThanOrEqual(3);
  }

  return shown;
};

test('kiosk 挡局屏:中文走霞鹜文楷,拉丁走拉丁族', async ({ page }) => {
  await stubAuth(page);
  await page.goto('/kiosk/play/ai/setup/ranked');
  await page.waitForLoadState('networkidle');
  const shown = await assertFontRouting(page, '挡局屏');
  console.log(`[字体] 挡局屏实际命中:${shown}`);
});

test('kiosk 对弈首页:同一套字族(这屏不共用挡局屏的任何组件)', async ({ page }) => {
  await stubAuth(page);
  await page.goto('/kiosk/play');
  await page.waitForLoadState('networkidle');
  const shown = await assertFontRouting(page, '对弈首页');
  console.log(`[字体] 对弈首页实际命中:${shown}`);
});

test('600 字重的中文命中真 Bold 面,不是浏览器合成的伪粗', async ({ page }) => {
  await stubAuth(page);
  await page.goto('/kiosk/play/ai/setup/ranked');
  await page.waitForLoadState('networkidle');
  await page.evaluate(() => document.fonts.ready);

  // `familyName` 分不出字重(粗细两个面同名),所以这一条只能问 `document.fonts`。
  // 楷体合成伪粗尤其难看,而屏上 600 字重到处都是。
  const loaded = await page.evaluate(() =>
    [...document.fonts].filter((f) => f.family === 'SmartBox Kai' && f.status === 'loaded')
      .map((f) => f.weight));
  expect(loaded.length, '一个楷体面都没加载 —— fonts.css 没进来').toBeGreaterThan(0);
  expect(loaded, `已加载的楷体字重:${loaded.join(', ')}`).toContain('700');
});
