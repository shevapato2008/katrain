import { expect, test, type Page } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });   // 合成要读刚写出的 PNG,而 config 是 fullyParallel

const SHOTS = resolve(process.cwd(),
  '../../../../smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots');
const OUT = resolve(process.cwd(),
  '../../../superpowers/tracks/kiosk-go-shell-align/visual/07-09-platform/1024x600');

/**
 * 跨平台两屏(07 连接 · 08 大厅)。
 *
 * 屏 09(人机开局)2026-09-23 拆去了独立文件 `kiosk-screen-09-setup.fourup.spec.ts` ——
 * 它多了一条真浏览器几何闸(`kiosk-geometry-platform.spec.ts`),拆开是为了这一屏的
 * 四图能单独重跑,不用带着 07/08 一起动。
 *
 * 共同的一条预期差异:稿子里那枚琥珀 / 蓝色的 `.wip` 标(「对弈未接后端」「后端已有 ·
 * 界面未接」)**是说给读稿人听的进度标注,不上屏** —— 屏 15、屏 19 重画时已按这条处理过,
 * 稿子自己在 `.wip` 上面的注释里也是这么定义它的。
 */

const PLATFORMS = {
  platforms: [
    {
      platform: 'ogs', connected: true, saved_username: 'stellabox',
      supports_live_play: true, supports_automatch: true,
      supports_rooms: false, supports_seek_graph: true, supports_engine_play: false,
    },
    {
      platform: 'golaxy', connected: false,
      supports_live_play: true, supports_automatch: false,
      supports_rooms: true, supports_seek_graph: false, supports_engine_play: true,
    },
    {
      platform: 'fox', connected: false,
      supports_live_play: false, supports_automatch: false,
      supports_rooms: true, supports_seek_graph: false, supports_engine_play: false,
    },
  ],
};

/** 稿子那三个人,逐字对上(`shots/08a-platform-lobby.png`)。 */
const OGS_USERS = {
  users: [
    { user_id: '1', username: 'stone_walker', rank: '4d', status: 'idle' },
    { user_id: '2', username: 'mokuhazushi', rank: '1k', status: 'seeking' },
    { user_id: '3', username: 'tenuki_now', rank: '2d', status: 'playing' },
  ],
};

async function boot(page: Page, path: string) {
  await freezeClock(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'fourup');
    localStorage.setItem('katrain_language', 'cn');
  });
  await stubBackendStatics(page);
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, username: '访客', rank: '20k', credits: 0 },
  }));
  await page.route('**/api/v1/platforms/status', (route) => route.fulfill({ json: PLATFORMS }));
  await page.route('**/api/v1/platforms/ogs/users*', (route) => route.fulfill({ json: OGS_USERS }));
  // 稿子那一帧「落子」选中的是实体盘 ⇒ 这台机器标定过摄像头。
  await page.route('**/api/v1/vision/status', (route) => route.fulfill({
    json: {
      enabled: true, camera_connected: true, pose_locked: true, sync_state: 'idle',
      bound_session_id: null, recognition_ready: true, led_connected: true,
    },
  }));
  await page.goto(path);
}

test('四图:跨平台 · 连接 ←→ sample-go/shots/07-platform.png', async ({ page }) => {
  await boot(page, '/kiosk/play/cross-platform');
  await page.waitForSelector('[data-testid="platform-connect-page"]');
  await expect(page.locator('[data-testid="platform-row"]')).toHaveCount(3);
  // 登录段的目标是**推出来的**:OGS 已连、野狐 comingSoon ⇒ 只剩星阵。
  await expect(page.locator('[data-testid="platform-login-section"]')).toContainText('登录 · 星阵围棋');
  await page.waitForLoadState('networkidle');

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '07-platform.png'),
    outDir: OUT,
    slug: '07-platform',
    referenceCaption:
      '参考:sample-go/shots/07-platform.png · L2 布局 B · '
      + '能力标由 /platforms 下发 · 登录表单跟着平台换字段',
    implementationCaption:
      '实现:/kiosk/play/cross-platform @1024×600 · 时钟冻 16:40 · '
      + '**登录是页内一段不是弹层**(判例:屏 04 那两颗「点此输入」药丸 —— 真页面上它必须真能输入,'
      + '不做「点药丸弹一层」);目标是**推出来的**:显示顺序里第一个「可登录且未连接」的家 —— '
      + 'OGS 已连、野狐 comingSoon ⇒ 星阵,标题正是稿子那句 · '
      + '**野狐行尾换成「暂不能对弈」**:稿子那枚 `.wip`「对弈未接后端」是给读稿人看的进度标注、不上屏'
      + '(屏 15/19 同例),但它编码的产品事实今天仍成立,得换成屏上自己的词;'
      + '**不写「即将上线」** —— 挡路的是 protobuf 客户端要重建,没人给过日期,那是预测不是状态 · '
      + '**OGS 行尾多一颗「登出」**(实现反过来纠正稿子):登出是业务动作,规范 §11 不许它上页控条;'
      + '收进登录段也不行 —— 三家全连上时那段不渲染,而那正是最需要登出的时候。'
      + '行尾不挤(通栏 992,能力标右缘到行尾之间空 545px),「进入大厅」外接矩形一个像素没动 · '
      + '「已连接」标带上账号名 —— 共用终端上「现在连的是谁的号」是按下登出之前必须看得见的事实',
  });
  console.log(`[fourup 07-platform] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});

test('四图:跨平台 · 大厅 ←→ sample-go/shots/08a-platform-lobby.png', async ({ page }) => {
  await boot(page, '/kiosk/play/cross-platform/lobby?platform=ogs');
  await page.waitForSelector('[data-testid="platform-lobby-page"]');
  await expect(page.locator('[data-testid="platform-user"]')).toHaveCount(3);
  await page.waitForSelector('[data-testid="platform-automatch"]');
  await page.waitForLoadState('networkidle');

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '08a-platform-lobby.png'),
    outDir: OUT,
    slug: '08a-platform-lobby',
    referenceCaption:
      '参考:sample-go/shots/08a-platform-lobby.png · L2 布局 B · '
      + '分段选的是平台不是筛法 · 段位是平台那边的,不是盒子的',
    implementationCaption:
      '实现:/kiosk/play/cross-platform/lobby?platform=ogs @1024×600 · 时钟冻 16:40 · '
      + '**顶上那排平台分段没画**(照稿):星阵的 `get_online_users` / `get_rooms` 都 return [],'
      + '切过去只会是一张空列表,而空列表和「这儿本来就没有」长得一模一样 · '
      + '**挑战条件是只读读数**:`platformSendChallenge` 那三项实现里写死,画成可选项等于'
      + '承诺一个不存在的开关 · '
      + '**「输入之后回车」是真按回车**:旧实现 400ms 防抖,每敲一个字向外部平台发一次搜索 · '
      + '**对局中那一行不摆灰按钮**,摆状态标 —— 那个人现在收不到挑战,灰按钮会让人一直按',
  });
  console.log(`[fourup 08a-platform-lobby] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
