import { test, expect, type Page } from '@playwright/test';
import { freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

/**
 * 开局设置 r2 的**承重结构实测**。
 *
 * 这一版整个卖点是「右栏不再滚动」—— 那是一句**关于布局的断言**,而 jsdom 没有布局引擎,
 * 对它无权作证。所以这条闸只在真浏览器里跑,目标 viewport 1024×600。
 *
 * ## 清单(先写关系式,再读数;具体像素只记录,不作判据)
 *
 * | 量什么 | 判据 |
 * |---|---|
 * | 该滚的是谁 | `.kiosk-rail[data-su] .kiosk-side__scroll` —— 不是它的祖先 |
 * | 该不该滚 | 这三屏在**内容最满**的那一态下 `scrollHeight <= clientHeight` |
 * | 还滚不滚得动 | 塞一块撑高的元素进去,`scrollTop` 写得进去、读得回来非 0 |
 * | 弹层没被裁掉 | 弹层的 border box 完整落在 `.kiosk-rail` 的盒子里 |
 * | 弹层盖不盖盘 | 弹层左边缘 ≥ 左盘右边缘 —— 盘画的是「按下开始后的局面」,盖住它=挡了唯一的反馈 |
 * | ± 居中 | 字形盒中心与按钮盒中心的偏移 |x| < 1.5px,且两颗键的偏移**彼此相差** < 1px |
 *
 * 「内容最满」是造出来的,不是默认态:
 * 默认态右栏本来就空,**装得下的数据量下量到的数字一概不算**。
 */

test.use({ viewport: KIOSK_VIEWPORT });

const SCROLL = '.kiosk-rail[data-su] .kiosk-side__scroll';

async function bootKiosk(page: Page) {
  await freezeClock(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'geom');
    localStorage.setItem('katrain_language', 'cn');
  });
  await stubBackendStatics(page);
  await page.route('**/api/v1/auth/me', (r) => r.fulfill({
    json: { id: 1, username: '访客', rank: '5段', credits: 0 },
  }));
  // 没标定过摄像头 —— 这一态比标定过的**多一行说明**,所以它才是内容最满的那一边。
  await page.route('**/api/v1/vision/status', (r) => r.fulfill({
    json: {
      enabled: false, camera_connected: false, pose_locked: false, sync_state: 'idle',
      bound_session_id: null, recognition_ready: false, led_connected: null,
    },
  }));
  await page.route('**/api/v1/geometry/status', (r) => r.fulfill({
    json: {
      phase: 'disabled', session_calibrated: false, last_error: null,
      capabilities: { camera_ready: false, led_ready: false, geometry_ready: false, recognition_ready: false },
    },
  }));
  await page.route('**/api/v1/ai-ladder/status*', (r) => r.fulfill({
    json: {
      view_state: 'ready',
      placement_state: { phase: 'done', completed_games: 5, total_games: 5 },
      current_opponent: { rung: 16, rank_name: '5级', certification_status: 'certified', availability: 'available', route: 'server' },
      recent_ranked_results: [], net_score: 1, pending_settlement: false, blocking_game: null,
    },
  }));
}

/** 把右栏推到**内容最满**的那一态:让子局(推导条改口)+ 自定贴目那一步走一遍。 */
async function fillToMax(page: Page) {
  const pick = async (id: string, k: string) => {
    await page.getByTestId(id).click();
    await page.locator(`[data-testid="${id}-pop"] [data-k="${k}"]`).click();
  };
  await pick('setup-handicap', '9');           // 让子最多的那一档
  await pick('setup-rules', 'button');          // 规则里最长的那个名字
  await page.waitForTimeout(120);
}

const SCREENS = [
  { route: '/kiosk/play/ai/setup/free', name: '自由对弈', max: true },
  { route: '/kiosk/play/ai/setup/ranked', name: '升降级对弈', max: false },
  { route: '/kiosk/play/pvp/setup', name: '本地对局', max: true },
];

for (const s of SCREENS) {
  test(`右栏不该滚:${s.name}`, async ({ page }) => {
    await bootKiosk(page);
    await page.goto(s.route);
    await page.waitForSelector(SCROLL);
    if (s.max) await fillToMax(page);

    const m = await page.evaluate((sel) => {
      const sc = document.querySelector(sel) as HTMLElement;
      /* `scrollHeight` 装得下时**恒等于** `clientHeight`,所以它只答「溢没溢出」,
         答不了「还剩多少」。余量要拿最后一个子元素的底边算 —— 记录用,不作判据。 */
      const kids = [...sc.children] as HTMLElement[];
      const top = sc.getBoundingClientRect().top;
      const contentBottom = kids.length
        ? Math.max(...kids.map((k) => k.getBoundingClientRect().bottom)) - top
        : 0;
      return {
        scrollHeight: sc.scrollHeight,
        clientHeight: sc.clientHeight,
        contentHeight: +contentBottom.toFixed(1),
      };
    }, SCROLL);
    // 关系式:内容最满时也装得下。具体像素只记录。
    expect.soft(m, `${s.name} 实测 ${m.scrollHeight}/${m.clientHeight}`).toBeTruthy();
    expect(m.scrollHeight, `${s.name} 右栏溢出了 ${m.scrollHeight - m.clientHeight}px`)
      .toBeLessThanOrEqual(m.clientHeight);
    console.log(`[不滚] ${s.name} 内容=${m.contentHeight} 可视=${m.clientHeight} 余量=${(m.clientHeight - m.contentHeight).toFixed(1)}`);
  });
}

test('撑破了仍然滚得动 —— 「装得下」不等于「滚坏了也看不出来」', async ({ page }) => {
  await bootKiosk(page);
  await page.goto('/kiosk/play/ai/setup/free');
  await page.waitForSelector(SCROLL);
  const moved = await page.evaluate((sel) => {
    const sc = document.querySelector(sel) as HTMLElement;
    const filler = document.createElement('div');
    /* ⚠️ `flex: 0 0` 不能省。`.kiosk-side__scroll` 是 flex 列,子项默认 `flex-shrink: 1`,
       只写 `height: 1200px` 会被压扁 —— 第一版就是这么假绿的:塞了 1200px 进去,
       `scrollTop` 只能写到 3。**探针自己被布局改掉了,而它在断言布局。** */
    filler.style.flex = '0 0 1200px';
    sc.appendChild(filler);
    sc.scrollTop = 500;
    const got = sc.scrollTop;
    filler.remove();
    return got;
  }, SCROLL);
  // 关系式:塞进去 1200px 之后至少能滚到 500(而不是「大于 0」——
  // 「大于 0」连被压扁剩 3px 都算通过,那正是第一版的假绿)。
  expect(moved, '塞高之后 scrollTop 写不进去 —— 承重链断了').toBeGreaterThanOrEqual(500);
  console.log(`[能滚] 撑高后 scrollTop=${moved}`);
});

test('弹层留在右栏里,盖不到左边那块盘', async ({ page }) => {
  await bootKiosk(page);
  await page.goto('/kiosk/play/ai/setup/free');
  await page.waitForSelector(SCROLL);

  for (const [id, label] of [['setup-handicap', '让子(11 档,两列)'], ['setup-clock', '用时(7 档)']] as const) {
    await page.getByTestId(id).click();
    await page.waitForSelector(`[data-testid="${id}-pop"]`);
    const g = await page.evaluate((testId) => {
      const pop = document.querySelector(`[data-testid="${testId}-pop"]`) as HTMLElement;
      const rail = document.querySelector('.kiosk-rail[data-su]') as HTMLElement;
      const board = document.querySelector('.kiosk-board') as HTMLElement;
      const p = pop.getBoundingClientRect(), r = rail.getBoundingClientRect(), b = board.getBoundingClientRect();
      return {
        popLeft: p.left, popRight: p.right, popTop: p.top, popBottom: p.bottom,
        railLeft: r.left, railRight: r.right, railTop: r.top, railBottom: r.bottom,
        boardRight: b.right,
      };
    }, id);
    // 判据一:完整落在 rail 的盒子里(祖先没裁它,它也没伸出去)
    expect(g.popLeft, `${label} 左边伸出右栏`).toBeGreaterThanOrEqual(g.railLeft - 0.5);
    expect(g.popRight, `${label} 右边伸出右栏`).toBeLessThanOrEqual(g.railRight + 0.5);
    expect(g.popTop, `${label} 顶出右栏`).toBeGreaterThanOrEqual(g.railTop - 0.5);
    expect(g.popBottom, `${label} 底出右栏`).toBeLessThanOrEqual(g.railBottom + 0.5);
    // 判据二:盖不到盘。原版设计稿拒绝下拉的理由就是这一条。
    expect(g.popLeft, `${label} 盖住了左边那块盘`).toBeGreaterThanOrEqual(g.boardRight);
    console.log(`[弹层] ${label} left=${g.popLeft.toFixed(1)} boardRight=${g.boardRight.toFixed(1)} 高=${(g.popBottom - g.popTop).toFixed(0)}`);
    await page.keyboard.press('Escape');
  }
});

test('棋力那两颗 ± 键居中,而且彼此对齐', async ({ page }) => {
  await bootKiosk(page);
  await page.goto('/kiosk/play/ai/setup/free');
  await page.waitForSelector('[data-testid="setup-strength"]');
  const off = await page.evaluate(() => {
    const keys = [...document.querySelectorAll('[data-testid="setup-strength"] button.su-step')] as HTMLElement[];
    return keys.map((b) => {
      const br = b.getBoundingClientRect();
      const g = (b.querySelector('svg') as SVGElement).getBoundingClientRect();
      return {
        label: b.getAttribute('aria-label'),
        w: +br.width.toFixed(2),
        dx: +((g.x + g.width / 2) - (br.x + br.width / 2)).toFixed(2),
        dy: +((g.y + g.height / 2) - (br.y + br.height / 2)).toFixed(2),
      };
    });
  });
  console.log('[±] ' + JSON.stringify(off));
  /* 改版前这两颗是文本 `−`(U+2212)和 `＋`(U+FF0B):量出来 dx 分别是 +5.66 和 +10,
     按钮被 `button{padding:.6em 1.2em}` 从 44 撑成 50。两层原因见 `SetupStepper.tsx`。 */
  for (const k of off) {
    expect(Math.abs(k.dx), `${k.label} 水平不居中(${k.dx}px)`).toBeLessThan(1.5);
    expect(Math.abs(k.dy), `${k.label} 垂直不居中(${k.dy}px)`).toBeLessThan(1.5);
  }
  expect(Math.abs(off[0].dx - off[1].dx), '两颗键彼此对不齐').toBeLessThan(1);
  expect(off[0].w, '按钮宽度被 padding 撑走了').toBeCloseTo(46, 0);
});
