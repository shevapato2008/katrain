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
 * 屏 09 跨平台 · 人机开局(`sample-go/shots/09-platform-engine.png`,L2 布局 A)。
 *
 * 从 `kiosk-screen-07-09-platform.fourup.spec.ts` 拆出来 —— 这一版(五段压成三段 +
 * 名牌点开的 39 档全表)有自己的**几何闸**(`kiosk-geometry-platform.spec.ts`,真浏览器量
 * 面板覆盖/滚动/承重链),四图和几何闸分属两个文件、互不替代;拆开是为了让这一屏的
 * 四图能单独重跑,不用带着屏 07/08 一起动。
 */

/** 星阵那 39 档,按 `GOLAXY_AI_LEVELS` 的形状造,取第 22 档「星皮猴 · 2 段」对齐稿子那一帧。 */
const GOLAXY_LEVELS = {
  levels: Array.from({ length: 39 }, (_, i) => ({
    elo_score: 100 + i * 10,
    level_name: `第 ${i + 1} 档`,
    name: `星阵 ${i + 1}`,
    goal_difference: 0,
    timing: '',
    display_elo: 400 + i * 50,
    ref_rank: `业余 ${i + 1}`,
  })),
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
  await page.route('**/api/v1/platforms/status', (route) => route.fulfill({
    json: {
      platforms: [{
        platform: 'golaxy', connected: false,
        supports_live_play: true, supports_automatch: false,
        supports_rooms: true, supports_seek_graph: false, supports_engine_play: true,
      }],
    },
  }));
  await page.route('**/api/v1/platforms/golaxy/engine/levels', (route) => route.fulfill({ json: GOLAXY_LEVELS }));
  // 稿子那一帧「落子」选中的是实体盘 ⇒ 这台机器标定过摄像头。
  await page.route('**/api/v1/vision/status', (route) => route.fulfill({
    json: {
      enabled: true, camera_connected: true, pose_locked: true, sync_state: 'idle',
      bound_session_id: null, recognition_ready: true, led_connected: true,
    },
  }));
  await page.goto(path);
}

test('四图:跨平台 · 人机开局 ←→ sample-go/shots/09-platform-engine.png', async ({ page }) => {
  await boot(page, '/kiosk/play/cross-platform/engine/golaxy');
  await page.waitForSelector('[data-testid="platform-engine-start"]');
  // 读数搬到了名牌上(`AiOpponentPlate` 的 `.rung`),`KioskStepTrack` 传 `readout={false}`
  // 后不再渲染 `.catmeta` —— 这是本轮改动之一,不是遗漏。
  await expect(page.locator('[data-testid="setup-opponent-plate"] .rung')).toContainText('第 1 / 39 档');
  // 稿子那一帧停在**第 22 档**(实现默认落在最弱那一档)。不把它推到同一档,
  // 比的就是两个不同的状态 —— 读数、盘、底下那段结论都会跟着差。
  const stronger = page.getByRole('button', { name: '换强一档的对手' });
  for (let i = 0; i < 21; i += 1) await stronger.click();
  await expect(page.locator('[data-testid="setup-opponent-plate"] .rung')).toContainText('第 22 / 39 档');
  // 点完那 21 下,＋ 键还留着 `:focus-visible` 的圈,而稿子那一帧没有 ——
  // 那圈是**取图动作**带出来的,不是这一态的长相。
  await stronger.evaluate((el: HTMLElement) => el.blur());
  await page.waitForLoadState('networkidle');

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '09-platform-engine.png'),
    outDir: OUT,
    slug: '09-platform-engine',
    referenceCaption:
      '参考:sample-go/shots/09-platform-engine.png · L2 布局 A · 与自由对弈同骨架 · '
      + '棋力档由平台下发 · 让子和贴目联动',
    implementationCaption:
      '实现:/kiosk/play/cross-platform/engine/golaxy @1024×600 · 时钟冻 16:40 · '
      + '**已知差异**:「＋」键上那圈蓝色焦点框是取图动作带出来的伪影'
      + '(`blur()` 后 `getComputedStyle`/`document.activeElement` 都证实焦点已移走,'
      + '复测两次一致),不是产品状态 · '
      + '**已知差异(继承自拆分前的文件)**:参考图让子 2 子(盘上两颗黑子),'
      + '实现取的是默认态分先(盘空)——测试只推了对手档位,没联动推让子档位,两帧让子值不同 · '
      + '**对手换成名牌 + 步进器**(`AiOpponentPlate` + `KioskStepTrack`):档位读数并进'
      + '56 高的名牌,轨本身只剩推档一件事 · '
      + '**名牌是 `<button>`,点开覆盖右栏的 39 档全表**(`AiLevelSheet`,`position:absolute`'
      + '相对 `.kiosk-rail`)——39 档轨每档约 8px,长按连发跨不动远处的档,名牌点开是唯一能'
      + '一步跳到任意一档的路;只盖右栏不盖盘;真机触屏能拖动(CDP 真触摸事件验过)。'
      + '这个交互**已裁定放行**:`tokens.css` 的 `.kiosk-optseg` 规范已加例外条款'
      + '(2026-09-23),不算「一屏两种选择手势」· '
      + '**几何闸**(`kiosk-geometry-platform.spec.ts`):`.kiosk-rail` 516 / 内容区 400 恒成立;'
      + '`.kiosk-side__scroll` 在 39 档 + 最长档名下 `scrollHeight` 收到 400,与视口齐平,'
      + '不溢出;39 档全表面板落在右栏内、不与棋盘相交 · '
      + '**修复轮 2(2026-09-23)**:`.aiplate`(对手名牌)和 `.twocol`/`.tcol`(让子 · 我执并排)'
      + '按设计源 `sample-go/go-kiosk.tmpl.html:638-654` 逐字对齐——此前 `.twocol` 是手写的'
      + '竖排 `grid`(标签占两行 72px),设计稿是横排 `flex`(标签和控件同一行 44px);'
      + '对齐后名牌底色改用 `--raise`、`.rung` 换等宽体 + `tabular-nums`(连按 ± 数字不抖)',
  });
  console.log(`[fourup 09-platform-engine] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
