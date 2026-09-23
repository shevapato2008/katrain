import { expect, test, type Page } from '@playwright/test';
import { freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT, hasTouch: true });

/**
 * 屏 09 的承重链 —— 右栏 516 = 页控条 44 + 12 + 内容 400 + 12 + 主按钮 48。
 *
 * 这条闸量的是**交互之后**对不对,四图对比看的是静止一帧对不对,互不替代。
 * 「能不能滚」永远归这一关。
 *
 * ⚠️ 造数据要造到**最坏**:39 档 + 最长档名 + 摄像头不可用(多一行提示)。
 * 装得下的数据量下量出来的数字一概不算。
 */

/**
 * 比真实最长的档名还长,守边界。真实最长的在 `GOLAXY_AI_LEVELS`
 * (`katrain/web/platforms/golaxy/engine_client.py:_GOLAXY_ROWS`)里 grep 出来对过:
 * `name` 最长 3 字(如「星猛虎」)、`level_name` 最长 3 字(「准9段」),
 * 组合展示(`{name} · {level_name}`)顶多 8 字 —— 这里的 12 字确实更长。
 */
const LONGEST = '星阵超级究极加强版机器人';

const LEVELS = {
  levels: Array.from({ length: 39 }, (_, i) => ({
    elo_score: 100 + i * 10, level_name: `第 ${i + 1} 档`, name: LONGEST,
    goal_difference: 0, timing: '', display_elo: 400 + i * 50, ref_rank: '职业 / 野狐 9D+',
  })),
};

/** 完整 boot —— 不许留「同 fourup spec」这种占位:占位会让下一个人自己编一套,两处量的不是同一个页面。
 * `lang` 默认 `cn`(既有测试不用改调用点);内容类断言要传别的语种量。 */
async function boot(page: Page, opts: { camera: boolean; lang?: string }) {
  const lang = opts.lang ?? 'cn';
  await freezeClock(page);
  await page.addInitScript((l) => {
    localStorage.setItem('token', 'geom');
    localStorage.setItem('katrain_language', l);
  }, lang);
  await stubBackendStatics(page, lang);
  await page.route('**/api/v1/auth/me', (r) => r.fulfill({ json: { id: 1, username: '访客', rank: '20k', credits: 0 } }));
  await page.route('**/api/v1/platforms/status', (r) => r.fulfill({
    json: { platforms: [{ platform: 'golaxy', connected: true, saved_username: 'fan',
      supports_live_play: true, supports_automatch: false, supports_rooms: true,
      supports_seek_graph: false, supports_engine_play: true }] },
  }));
  await page.route('**/api/v1/platforms/golaxy/engine/levels', (r) => r.fulfill({ json: LEVELS }));
  await page.route('**/api/v1/vision/status', (r) => r.fulfill({
    json: { enabled: opts.camera, camera_connected: opts.camera, pose_locked: opts.camera,
      sync_state: 'idle', bound_session_id: null, recognition_ready: opts.camera, led_connected: opts.camera },
  }));
  await page.goto('/kiosk/play/cross-platform/engine/golaxy');
  await page.waitForSelector('[data-testid="platform-engine-start"]');
  await page.waitForLoadState('networkidle');
}

/**
 * **2026-09-23 修复轮 3:按语种参数化。** 之前只在 `cn` 下量过 ——
 * `.kiosk-opthint` 是定高的(`tokens.css:720-722`,`height`/`line-height` 同一个
 * token),译文一折行,第二行被静默裁掉,屏上看不出来。`de`/`fr`/`ru` 的
 * `platform:engine_fixed_hint`/`setup:no_camera_hint` 字符数是中文的 3–5 倍
 * (量过,见 `task-3-report.md`「德文下的版面」一节)。至少覆盖 `cn`(基线)和
 * `de`(最长的那个语种)× 两态摄像头,四组。
 *
 * ⚠️ **德文那几组预期会红 —— 不要为了让它们变绿去改产品代码或放松断言。**
 * 这是一个语种维度的版面缺口,是产品决定(换两行高的提示行 / 缩短译文 / 别的),
 * 不是这条闸的作者能现场定的;闸的任务是把数字如实量出来,交给人裁。
 */
for (const lang of ['cn', 'de'] as const) {
  for (const camera of [true, false] as const) {
    test(`屏 09 最坏内容量下,整条链上没有任何一层在滚(lang=${lang} camera=${camera})`, async ({ page }) => {
      await boot(page, { camera, lang });

      const m = await page.evaluate(() => {
        const scroll = document.querySelector('.kiosk-side__scroll') as HTMLElement;
        // 从滚动容器一路往上数到 .kiosk-screen —— 同一条链上可以有不止一处断点,
        // 只量最里面那一层,外面某一层在滚照样绿。
        const chain: { sel: string; sh: number; ch: number }[] = [];
        let el: HTMLElement | null = scroll;
        while (el && !el.classList.contains('kiosk-screen')) {
          chain.push({
            sel: el.className || el.tagName,
            sh: el.scrollHeight, ch: el.clientHeight,
          });
          el = el.parentElement;
        }
        const rail = document.querySelector('.kiosk-rail') as HTMLElement;
        return { chain, railH: rail.clientHeight, viewportH: scroll.clientHeight };
      });
      console.log(`[geom 09 chain lang=${lang} camera=${camera}]`, JSON.stringify(m, null, 1));

      expect(m.railH).toBe(516);          // tokens.css:69 --content-h-l2
      expect(m.viewportH).toBe(400);      // 516 − 44 页控条 − 12 − 12 − 48 主按钮
      for (const n of m.chain) {
        expect(n.sh, `${n.sel} 在滚(lang=${lang} camera=${camera})`).toBeLessThanOrEqual(n.ch);
      }
    });
  }
}

/**
 * 滚动条拇指没被 `.kiosk-rail { position: relative }` 挪走。
 *
 * `scrollSync.ts:38` 读 `scroll.offsetTop`,而 `offsetTop` 随 `offsetParent` 变 ——
 * `[data-testid="platform-engine-setup-page"] .kiosk-rail { position: relative }`
 * (`go-screens.css:1854`)给这一屏的滚动区换了 `offsetParent`。两态都要量:
 * 不溢出时条子该撤掉(`syncScrollbar` 早返回那一支),溢出时拇指顶边要贴着滚动区顶边。
 */
/**
 * 「不溢出撤条」这一支——**这条断言目前必然红**。上面那条「整条链上没有任何一层在滚」
 * 已经量出:摄像头可用态(三段,无提示行)`.kiosk-side__scroll` 仍然 `scrollHeight-clientHeight=59`,
 * 现在这条页面上**没有一种真实数据组合是不溢出的**——「不溢出」这个前提本身不成立,
 * 不是撤条逻辑坏了。留着这条断言,让它诚实地红,而不是删掉或放松到匹配现状。
 */
test('屏 09 滚动条:不溢出态应撤条(当前实现下这一态达不到,见上一条链测量)', async ({ page }) => {
  await boot(page, { camera: true });
  const m = await page.evaluate(() => {
    const scroll = document.querySelector('.kiosk-side__scroll') as HTMLElement;
    const bar = document.querySelector('.kiosk-scrollbar') as HTMLElement;
    return {
      overflow: scroll.scrollHeight - scroll.clientHeight,
      barDisplay: getComputedStyle(bar).display,
    };
  });
  console.log('[geom 09 scrollbar not-overflowing]', JSON.stringify(m));
  expect(m.overflow, '这一态本该不溢出 —— 见「整条链上没有任何一层在滚」那条的同一发现').toBeLessThan(1);
  expect(m.barDisplay).toBe('none');
});

/**
 * 「溢出贴顶」这一支 —— **2026-09-23 修复轮 3 退役,不留代码,只留这段记录。**
 *
 * 退役理由三件事:
 *
 * ① **对象已经不存在。** 修复轮 1/2 把这一屏的留白按设计源收紧之后(`.inputgrp`
 *    padding、`.setgrp` 段间距、`.aiplate`/`.twocol` 逐字对齐设计稿),摄像头不可用态
 *    (39 档 + 最长档名 + 多一行提示 —— 这一屏能造出的最坏内容量)下
 *    `.kiosk-side__scroll` 的 `scrollHeight === clientHeight === 400`。这一屏**没有任何
 *    一种真实数据组合会溢出**了,「溢出态」这个前提本身不再成立,退役这条测的不是
 *    「功能坏了」,是「它要守的那个状态屏上到不了」。
 *
 * ② **它当初要守的风险已被证伪。** 这条测试存在的理由写在上面 `:98` 那条测试之前的
 *    注释里:`.kiosk-rail { position: relative }`(仅这一屏的作用域覆盖,`go-screens.css`)
 *    可能把滚动条拇指的定位祖先从 `.kiosk-side` 换成 `.kiosk-rail`,从而挪动拇指位置。
 *    Task 4 报告(`task-4-report.md` §3 变异②)实测推翻了这个前提:`.kiosk-side`
 *    (`tokens.css:510`)自己早就是 `position: relative`,是比 `.kiosk-rail` 更近的
 *    定位祖先,`scrollSync.ts:38` 读的 `scroll.offsetTop` 由它决定 ——
 *    `.kiosk-rail` 那条作用域覆盖对这一屏的拇指位置**不是决定性的**。理由没了,
 *    对象也没了,两条都站不住,没有理由再留着造数据去凑。
 *
 * ③ **如果以后要守「拇指贴顶」这个行为,该守在一个真会滚的屏上。** 屏 02(自由对弈
 *    · 开局设置)是这一屏的姊妹屏,右栏内容量比这一屏大,是真溢出的 —— 新的拇指贴顶
 *    测试应该长在那一屏的几何闸里,不是在这一屏人为造一个产品到不了的状态。
 *
 * **不允许的做法**:为了让这条断言变绿而放宽 `LEVELS`/档名去制造溢出 —— 那是在测
 * 一个产品实际达不到的状态,比没有这条闸更坏(闸会一直绿,却守着一件不会发生的事)。
 */

/** `.kiosk-opthint` 定高(`tokens.css:720-722` height/line-height 同一个 token),文案换行会被静默裁掉。 */
/**
 * 按语种参数化,理由和上面那组链测试同一段注释。cn/de × 摄像头可用/不可用,四组。
 *
 * **2026-09-23 修复轮 4:换轴。** 原来断的是 `scrollWidth <= clientWidth`(水平),
 * 而 `.kiosk-opthint` 是 `white-space: normal` —— **它永远不会横向溢出,只会折行**,
 * 那条断言在 cn/de 下都绿,却两边都没在量真正的东西(闸量错了对象的教科书形状)。
 * 折行超出的是**垂直**方向:`.kiosk-opthint` 定高一行(`tokens.css:720-722`,
 * `height`/`line-height` 同一个 token),德文实测 `clientHeight=16` 但内容要两行
 * `scrollHeight=32`,`overflow: visible` ⇒ 第二行不是被裁掉看不见,是画到盒子
 * 外面、压在下面的留白上 —— 换成量高度才是量它真正会不会出事的那个轴。
 *
 * 配套的产品修法:`go-screens.css` 给这一屏的 `.kiosk-opthint` 开了
 * `height: auto; min-height: var(--opthint-h)`(只在这一屏,`.kiosk-opthint` 是
 * 屏 02/03/04 共用的,那几屏本来就整栏滚,不在这轮处理范围内)。
 */
for (const lang of ['cn', 'de'] as const) {
  test(`屏 09 提示行不被裁切(lang=${lang})—— 摄像头可用/不可用两种文案都要测(更长的那句才是真边界)`, async ({ page }) => {
    for (const camera of [true, false]) {
      await boot(page, { camera, lang });
      const hint = await page.evaluate(() => {
        const el = document.querySelector('[data-testid="setup-input-hint"]') as HTMLElement;
        return { scrollHeight: el.scrollHeight, clientHeight: el.clientHeight, text: el.textContent };
      });
      console.log(`[geom 09 hint lang=${lang} camera=${camera}]`, JSON.stringify(hint));
      expect(hint.scrollHeight, `提示行被裁切(lang=${lang} camera=${camera}):「${hint.text}」`)
        .toBeLessThanOrEqual(hint.clientHeight);
    }
  });
}

/**
 * 「我执」分段按钮里的字不许折行(Task 4.6,Fan 裁定)。
 * `[data-testid="setup-side-seg"]` 里每个 `button` 断言 `scrollHeight <= clientHeight` ——
 * 折行不是被裁掉,是画到盒子外面压住下面的留白(同类型缺陷见上面 `.kiosk-opthint` 的注释)。
 * cn 和 de 都要量:cn 的猜先/执黑/执白从来不折,de 的 `Schwarz nehmen`(14 字母)在半栏(~200px)
 * 折成两行是这条闸要抓的真缺陷。
 */
for (const lang of ['cn', 'de'] as const) {
  test(`屏 09「我执」分段按钮不折行(lang=${lang})`, async ({ page }) => {
    await boot(page, { camera: true, lang });
    const buttons = await page.evaluate(() => {
      const seg = document.querySelector('[data-testid="setup-side-seg"]') as HTMLElement;
      return Array.from(seg.querySelectorAll('button')).map((b) => ({
        text: b.textContent,
        scrollHeight: b.scrollHeight,
        clientHeight: b.clientHeight,
      }));
    });
    console.log(`[geom 09 side-seg lang=${lang}]`, JSON.stringify(buttons));
    for (const b of buttons) {
      expect(b.scrollHeight, `「我执」按钮折行(lang=${lang}):「${b.text}」`)
        .toBeLessThanOrEqual(b.clientHeight);
    }
  });
}

test('39 档面板:完整落在右栏内、与棋盘无交集、轨的四角都被盖住、手指拨得动', async ({ page }) => {
  await boot(page, { camera: true });
  await page.click('[data-testid="setup-opponent-plate"]');
  const sheet = page.locator('[data-testid="setup-level-sheet"]');
  await expect(sheet).toBeVisible();

  const box = await page.evaluate(() => {
    const s = document.querySelector('[data-testid="setup-level-sheet"]')!.getBoundingClientRect();
    const rail = document.querySelector('.kiosk-rail')!.getBoundingClientRect();
    const b = document.querySelector('.kiosk-board')!.getBoundingClientRect();
    const trk = document.querySelector('[data-testid="setup-level"]')!.getBoundingClientRect();
    const sheetEl = document.querySelector('[data-testid="setup-level-sheet"]')!;
    // 轨的四角 + 中心,五个点都要命中面板 —— 只测中心一个点,局部露出照样绿。
    const pts: [number, number][] = [
      [trk.left + 2, trk.top + 2], [trk.right - 2, trk.top + 2],
      [trk.left + 2, trk.bottom - 2], [trk.right - 2, trk.bottom - 2],
      [trk.left + trk.width / 2, trk.top + trk.height / 2],
    ];
    return {
      // 完整包含于 rail(四条边都要,不能只比 left)
      inRail: s.left >= rail.left && s.right <= rail.right && s.top >= rail.top && s.bottom <= rail.bottom,
      // 与棋盘矩形无交集(两轴都判,只比 left/right 挡不住纵向压到盘上的情形)
      noOverlapBoard: !(s.left < b.right && s.right > b.left && s.top < b.bottom && s.bottom > b.top),
      hits: pts.map(([x, y]) => sheetEl.contains(document.elementFromPoint(x, y))),
    };
  });
  console.log('[geom sheet]', JSON.stringify(box));
  expect(box.inRail).toBe(true);
  expect(box.noOverlapBoard).toBe(true);
  expect(box.hits).toEqual([true, true, true, true, true]);

  // 能滚 + **手指**拨得动。鼠标滚轮拨得动 ≠ 触屏拨得动。
  const body = sheet.locator('.aisheet__body');
  const overflow = await body.evaluate((el) => { el.scrollTop = 0; return el.scrollHeight - el.clientHeight; });
  expect(overflow, '39 档没撑出溢出 ⇒ 这条闸量的不是滚动').toBeGreaterThan(0);

  // ⚠️ **不能用 page.evaluate 里 dispatchEvent 合成的 TouchEvent。**
  //    脚本造的事件是 untrusted,**不驱动 Chromium 的原生触摸滚动** ——
  //    实现完全正确时 scrollTop 照样是 0,这条会永久假红。
  //    `page.touchscreen` 在本仓这版 Playwright 里只有 tap(),没有 swipe。
  //    真正的手指拖动只能走 CDP。
  const r = (await body.boundingBox())!;
  const cx = Math.round(r.x + r.width / 2);
  const cdp = await page.context().newCDPSession(page);
  const pt = (y: number) => [{ x: cx, y: Math.round(y), radiusX: 8, radiusY: 8, force: 1 }];
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: pt(r.y + r.height - 20) });
  for (const y of [r.y + r.height - 80, r.y + r.height - 160, r.y + 20]) {
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: pt(y) });
  }
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
  await page.waitForTimeout(150);            // 触摸滚动由浏览器自己做,给它几帧

  const after = await body.evaluate((el) => el.scrollTop);
  console.log('[geom sheet scrollTop after swipe]', after);
  expect(after, '手指拨不动').toBeGreaterThan(0);
});
