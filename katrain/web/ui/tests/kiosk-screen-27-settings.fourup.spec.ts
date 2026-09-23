import { expect, test, type Page } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });   // 合成要读刚写出的 PNG,而 config 是 fullyParallel

const SHOTS = resolve(process.cwd(),
  '../../../../smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots');
const OUT = resolve(process.cwd(),
  '../../../superpowers/tracks/kiosk-go-shell-align/visual/27-settings/1024x600');
// 「关于」那一组在 `27-settings.png` 里是折在下面看不见的。这张是**同一份稿子**
// (`sample-go/go-kiosk.html`,与 27-settings.png 登记的指纹同一版)滚到底拍的,
// 照 `screen-gate.mjs` 的取法:补 doctype、2×、截 `.kiosk-screen`,并回读过屏名与「关于」整组在视口里。
const ABOUT_REF = resolve(process.cwd(),
  '../../../superpowers/tracks/kiosk-go-settings/visual/reference/27-settings-about.png');

/**
 * 屏 27 设置(L1-B:左栏仍是 296 的 `.kiosk-console`,装的是导航不是盘)。
 *
 * ⚠️ **这一屏和稿子差得最多,而且是裁定不是遗漏**:
 * 稿子摆了七组,这台盒子上**两组没有内容**(棋盘外观、对局默认值整组不存在;
 * 实体棋盘只有标定和读数,没有 LED 开关和帧率滑条)。计划 D10 在三条路里选了
 * **只做有内容的组**:
 *   · 七组全摆、空的挂琥珀「未接后端」—— **用错标**:那五组大部分不是「后端没有」,
 *     是「这个设置项还没做」。两回事,两种颜色。
 *   · 七组全摆、空的做成真功能 —— 五个新 feature,远超一条表现层赛道。
 * ⇒ 导航项数 = 分组数,**词一一对应**。差异图上少那几组是这条裁定的后果。
 *
 * 🔵 **2026-08-26:「声音」从「没内容」那一堆里挪出来了。** 判据没变 —— 变的是事实:
 * 落子音效(`useSound`)和实体盘引导语(`useVoice`)一直在响,而这台盒子上**一个关掉它们
 * 的地方都没有**;`useSound` 那个 `setEnabled` 零调用点,而且它是 `useRef`、每个组件各一份,
 * 接上去也关不掉别人。⇒ 它一直是「有内容」的那一类,只是内容藏在代码里没有出口。
 * 屏上写的是**「声音」**不是稿子那句「声音与报着」:盒子不报着(`useVoice` 说的是摆子引导
 * 那七句,不是手数),多写两个字就是承诺一个不存在的功能。
 *
 * 其余预期差异:
 *  ① 稿子没有「语言」这一组,实现有 —— 规范 §12 说它该在设置中心,**可设置中心不在本仓**,
 *    搬走等于这台盒子上再没有语言开关。登记为已知偏差。
 *  ② 账号那两行 2026-08-23 从 MUI 卡片重排成了 `.kiosk-row`;2026-09 段位详情也换成了
 *    就地展开的外壳行(稿子没有 AI 段位这一行,所以展开态只能对着账号组那块看骨架)。
 *  ④ 「关于」2026-09-21 起有内容了(Fan 裁定:版本 + 两个引擎),对照的是稿子滚到底那一帧。
 *  ③ 平台那一行念的是**真能连的三家**(OGS / 野狐 / 星阵),不是上一版那四张死卡
 *    (99围棋 / 野狐 / 腾讯 / 新浪 —— 和真正能连的对不上)。
 */

/**
 * Playwright 的 `click()` 会让被点的键进 `:focus-visible`,画出一圈焦点环;盒子上是手指点,
 * Chromium 对触摸点按不画这一圈。拍之前把焦点拿走,拍到的才是用户看到的那一帧。
 */
const blurAfterClick = (page: Page) => page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());

async function stubSettings(page: Page) {
  await freezeClock(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'fourup');
    localStorage.setItem('katrain_language', 'cn');
  });
  await stubBackendStatics(page);
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, username: '访客', rank: '5段', credits: 0 },
  }));
  // 这台盒子接着摄像头、标定过了、LED 也在 —— 三格才有真读数可显示。
  await page.route('**/api/v1/geometry/status', (route) => route.fulfill({
    json: {
      phase: 'ready', session_calibrated: true, last_error: null,
      capabilities: { camera_ready: true, led_ready: true, geometry_ready: true, recognition_ready: true },
    },
  }));

  // 段位状态不 mock 的话这一行会显示「加载失败」—— 那是诚实的,但对照台要看的是常态。
  await page.route('**/api/v1/ai-ladder/**', (route) => route.fulfill({
    json: {
      view_state: 'ready',
      placement_state: { phase: 'placed', rung: { rung: 12, rank_name: '9 级', certification_status: 'certified', availability: 'available', route: 'local' } },
      current_opponent: { rung: 12, rank_name: '9 级', certification_status: 'certified', availability: 'available', route: 'local' },
      recent_ranked_results: [], net_score: 2, pending_settlement: false,
    },
  }));

  await page.route('**/api/v1/health', (route) => route.fulfill({
    json: { status: 'ok', version: '1.17.1', engines: { local: 'reachable', cloud: 'unconfigured' } },
  }));

  await page.goto('/kiosk/settings');
  await page.waitForSelector('[data-testid="settings-nav"] button');
  await page.waitForSelector('[data-testid="about-version"]');
  await page.waitForLoadState('networkidle');
}

test('四图:设置 ←→ sample-go/shots/27-settings.png', async ({ page }) => {
  await stubSettings(page);
  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '27-settings.png'),
    outDir: OUT,
    slug: '27-settings',
    referenceCaption:
      '参考:sample-go/shots/27-settings.png · L1-B(左栏仍是 296,装导航不是盘)· '
      + '稿子摆了七组:账号与平台 / 实体棋盘 / 棋盘外观 / 落子与提示 / 声音与报着 / 对局默认值 / 关于',
    implementationCaption:
      '实现:/kiosk/settings @1024×600 · 时钟冻 16:40 · 摄像头 / 标定 / LED 三格是 fixture · '
      + '**只做有内容的六组**(计划 D10):稿子里剩下那两组(棋盘外观 / 对局默认值)不是「后端没有」而是「这个设置项还没做」,'
      + '挂琥珀「未接后端」是用错标;做成真功能是五个新 feature,超出一条表现层赛道 —— **裁定不是遗漏** · '
      + '导航项数 = 分组数、词一一对应;高亮跟着**滚动位置**走,不跟着最后点过哪一项 · '
      + '尾部那段留白不是排版,是让最后一组也能滚到视口顶 —— 不然点第 3 项会被滚动事件弹回第 2 项 · '
      + '多一组「语言」:规范 §12 说它该在设置中心,可设置中心不在本仓,搬走等于这台盒子上再没有语言开关 · '
      + '**「关于」2026-09-21 补上**(版本 + 本机 / 云端引擎),导航六项 · '
      + '实体棋盘三格照标定屏的说法:摄像头 已连接、几何标定 已标定、LED 串口已连接(视觉赛道 V4:只说串口通了) · '
      + '**「声音」2026-08-26 补上**,它有内容:落子音效和实体盘引导语一直在响,而这台盒子上原来一个关掉它们的地方都没有;'
      + '屏上写的是「声音」不是稿子那句「声音与报着」—— 盒子不报着,多写两个字就是承诺一个不存在的功能 · '
      + '账号那两行也是 `.kiosk-row`;段位那一行的词换成共享那套(当前段位 / 已认证 / 本机对弈)· '
      + '平台那一行念的是真能连的三家,不是上一版那四张对不上的死卡',
  });
  console.log(`[fourup 27-settings] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});

test('四图:设置 · AI 段位详情展开 ←→ sample-go/shots/27-settings.png', async ({ page }) => {
  await stubSettings(page);
  await page.getByRole('button', { name: '查看AI段位详情' }).click();
  await page.waitForSelector('[data-testid="ladder-detail"]');
  await blurAfterClick(page);
  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '27-settings.png'),
    outDir: OUT,
    slug: '27-settings-ladder-open',
    referenceCaption:
      '参考:sample-go/shots/27-settings.png · 稿子的「账号与平台」没有 AI 段位这一行 —— 这一对只看骨架:'
      + '展开的几行是不是同一族 .kiosk-row、有没有撑破右栏',
    implementationCaption:
      '实现:点「查看AI段位详情」之后 · **就地展开**,不弹层(以前是装着 galaxy MUI 卡的对话框)· '
      + '往里缩一格 + 左边一条细线 = 上面那行「段位」的下一层 · 净胜分七格(-3…+3,中间那格是 0)· '
      + '最近 5 盘 · 每一句都取自 AI_LADDER_COPY,与 galaxy 那张卡逐状态同源(parity 测试)· 键变「收起」',
  });
  console.log(`[fourup 27-settings-ladder-open] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});

test('四图:设置 · 关于 ←→ 同一份稿子滚到底那一帧', async ({ page }) => {
  await stubSettings(page);
  await page.getByTestId('settings-nav').getByRole('button', { name: '关于' }).click();
  await expect.poll(() => page.evaluate(() =>
    document.querySelector('[data-testid="settings-nav"] [aria-current="true"]')?.textContent)).toBe('关于');
  await blurAfterClick(page);
  const r = await captureFourUp({
    page,
    referencePng: ABOUT_REF,
    localReference: true,
    outDir: OUT,
    slug: '27-settings-about',
    referenceCaption:
      '参考:sample-go/go-kiosk.html 屏 27 滚到底(与 27-settings.png 同一版稿子)· 「关于」三行:引擎 / 识盘 / 资源,'
      + '行首一列 lead 写类别 · 稿子没有尾部留白,所以「关于」停在视口顶下 236',
    implementationCaption:
      '实现:点导航「关于」· 只画 Fan 2026-09-21 裁定的三行:版本 / 本机 KataGo / 云端 KataGo,'
      + '行型照稿子(lead 列 + 正文 + 状态标)· 数据全来自 /api/v1/health,拿不到版本就不画那一行 · '
      + '**不画设备名**(DEVICE_ID 没配 env 时是每次启动自铸的 uuid4)· 尾部留白让最后一组也滚得到视口顶 —— '
      + '所以「关于」在顶上而稿子里它在下面,这是高亮说真话的前提,不是偏差',
  });
  console.log(`[fourup 27-settings-about] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
