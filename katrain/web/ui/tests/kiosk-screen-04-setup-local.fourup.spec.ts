import { test } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubShellAssets } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });   // 合成要读刚写出的 PNG,而 config 是 fullyParallel

const SHOTS = resolve(process.cwd(),
  '../../../../smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots');
const OUT = resolve(process.cwd(),
  '../../../superpowers/tracks/kiosk-go-shell-align/visual/04-setup-local/1024x600');

/**
 * 屏 04 本地对局 · 开局设置(L2 布局 A,右栏整栏滚)。
 *
 * 和屏 02/03 同一副骨架,少了引擎那三组(棋力 / AI 策略 / 我执),多了「对局双方」。
 *
 * ## 预期差异,五条,每条都是**实现对、稿子那一处不成立**
 *
 *  ① **「落子」是读数不是控件**(同屏 02):`isVisionEnabled` 由后端给,全仓没有任何
 *    地方能让用户切。这一屏尤其不能画成可选 —— 本地对局那条路由外面套着
 *    `<PhysicalBoardGuard requireRecognition>`,盘没标定过时进去的是标定工作台。
 *    这一帧把摄像头 stub 成**已标定**,和稿子那一帧(选中「实体盘」)说同一件事。
 *
 *  ② **「点此输入」是真输入框,不是药丸。** 静态稿只能画到药丸那一步;真页面上它必须
 *    真能打字。样子照搬(同高 26、同圆角、同描边、同字号),宽度放到 116 —— 药丸只装得下
 *    「点此输入」四个字,输入框还要装得下人名。**不做「点药丸弹一层输入」**:
 *    那是稿子上没有的一层流程,而且弹层正好盖住左边那块盘。
 *
 *  ③ **「白方 · 贴目的一方」反了。** 贴目是**黑方贴给白方**的(`core/game.py:372`
 *    黑棋分数减 komi),白方是**收**的那一方 ⇒ 实现写「后行 · 收下贴目的一方」。
 *
 *  ④ **`.setnote` 第一句改了。** 稿子写「不接引擎,没有提示也没有形势判断」——
 *    前半句对、后半句不对:`interface.py:253` 的 `SCORING_GAME_TYPES` 只有
 *    `rated / ranked / ai_ladder_ranked`,`pvp_local` 不在里面 ⇒ `analysis_allowed`
 *    为真,对局屏那颗「领地」照样能按,而领地就是形势判断。真正关掉的是
 *    **胜负走势图**(`GameControlPanel.tsx:113` 的 `evalAllowed` 排除了 `pvp_local`)
 *    和 **AI 支招**(`GamePage.tsx:451` 的 `hintVisible` 要求 `game_type === 'free'`)。
 *
 *  ⑤ **`.setnote` 第二句的后半改了。** 稿子写「段位只有**在线大厅的定级队列**会改」——
 *    定级赛不在在线大厅,在「升降级对弈」(`LobbyPage.tsx:151` 那句挡人的话就是这么说的);
 *    权威在 `interface.py:258`:`RANK_MOVING_GAME_TYPES = ("ai_ladder_ranked",)`,
 *    注释逐字写着「Exactly one, by design」。照稿子写会把人指去一个改不了段位的地方。
 *
 *  另外 Dock 少「成长」:围棋没有 growth 路由/页面/后端(D6)。
 */

test('四图:本地对局开局设置 ←→ sample-go/shots/04-setup-local.png', async ({ page }) => {
  await freezeClock(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'fourup');
    localStorage.setItem('katrain_language', 'cn');
  });
  await stubShellAssets(page);
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, username: '访客', rank: '5级', credits: 0 },
  }));
  // 稿子那一帧选中的是「实体盘」⇒ 这台机器标定过摄像头。
  await page.route('**/api/v1/vision/status', (route) => route.fulfill({
    json: {
      enabled: true, camera_connected: true, pose_locked: true, sync_state: 'idle',
      bound_session_id: null, recognition_ready: true, led_connected: true,
    },
  }));
  await page.route('**/api/v1/geometry/status', (route) => route.fulfill({
    json: {
      phase: 'ready', session_calibrated: true, last_error: null,
      capabilities: { camera_ready: true, led_ready: true, geometry_ready: true, recognition_ready: true },
    },
  }));

  await page.goto('/kiosk/play/pvp/setup');
  await page.waitForSelector('[data-testid="setup-sound"]');
  await page.waitForLoadState('networkidle');

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '04-setup-local.png'),
    outDir: OUT,
    slug: '04-setup-local',
    referenceCaption:
      '参考:sample-go/shots/04-setup-local.png · L2 布局 A(盘 516 + 16 + 右栏 460,右栏整栏滚)· '
      + '和屏 02/03 同一副骨架,少了引擎那三组(棋力 / AI 策略 / 我执),多了「对局双方」',
    implementationCaption:
      '实现:/kiosk/play/pvp/setup @1024×600 · 时钟冻 16:40 · 摄像头 stub 成已标定(和稿子同一态)· '
      + '**「落子」是读数不是控件**(虚线边):`isVisionEnabled` 由后端给,用户切不了;这一屏尤其不能画成'
      + '可选 —— 本地对局那条路由外面套着 `PhysicalBoardGuard`,盘没标定过时进去的是标定工作台 · '
      + '**「点此输入」是真输入框不是药丸**:静态稿只能画到药丸那一步,真页面上它必须真能打字'
      + '(同高同圆角同描边,宽 116 好装得下人名);不做「点药丸弹一层输入」—— 弹层正好盖住左边那块盘 · '
      + '**「白方 · 贴目的一方」反了**:贴目是黑方贴给白方的(`core/game.py:372` 黑棋分数减 komi),'
      + '白方是收的那一方 ⇒ 写「后行 · 收下贴目的一方」· '
      + '**底下那段说明两句都改了**:① 稿子说「没有提示也没有形势判断」,而 `pvp_local` 不在 '
      + '`interface.py:253` 的 `SCORING_GAME_TYPES` 里 ⇒ 对局屏那颗「领地」照样能按;真正关掉的是'
      + '胜负走势图和 AI 支招 · ② 稿子说「段位只有在线大厅的定级队列会改」,而定级赛在「升降级对弈」'
      + '(`LobbyPage.tsx:151`),权威是 `interface.py:258` 的 `RANK_MOVING_GAME_TYPES = ("ai_ladder_ranked",)` · '
      + 'Dock 少「成长」(D6)',
  });
  console.log(`[fourup 04-setup-local] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
