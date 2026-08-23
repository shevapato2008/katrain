import { test } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubShellAssets } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });   // 合成要读刚写出的 PNG,而 config 是 fullyParallel

const SHOTS = resolve(process.cwd(),
  '../../../../smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots');
const OUT = resolve(process.cwd(),
  '../../../superpowers/tracks/kiosk-go-shell-align/visual/03-setup-ranked/1024x600');

/**
 * 屏 03 升降级对弈 · 开局设置(L2 布局 A,右栏整栏滚)。
 *
 * 和屏 02 **同一个组件**(`pages/AiSetupPage.tsx`,`:mode` 分岔),所以外壳那一层
 * 两屏一起对齐;不同的只有右栏那几组。
 *
 * ## 这一轮**没做完**的一块:「对手」
 *
 * 稿子把它画成一段 `.setexplain`。实现里那块还是 `AiLadderSetupOpponent`(MUI 框),
 * **故意留着** —— 它手上是六种诚实状态:加载 / 出错重试 / 定级赛进度条 / 已定档 /
 * 档位不可挑战 / 未认证档试坐 / 成绩在途。稿子只画了「已定档」那一种。
 * 换壳要把六种都搬过来,而它同时是 galaxy 那屏的消费者
 * (`galaxy/pages/AiSetupPage.tsx:557`),在原地改样式会把另一家一起改了。
 * ⇒ 四图上这一块会明显不一致,**那是登记过的欠账,不是没看见**。
 *
 * ## 稿子这一屏有一处**已经被上一轮更正、但没改到**
 *
 * 那行提示写「提示、形势判断、**复盘**一律封掉」。2026-08-23 查过:
 * 后端那道闸是 `interface.py:877` 的 `ANALYSIS_ACTIONS`,里面全是**对局中那棵树上的动作**
 * (`analyze_extra` / `analyze_all` / `analyze_current` / `show_pv` / `find_mistake`);
 * 离线报告走 `POST /api/v1/reports/` → cron,只查「这局是不是你的」。
 * 那一轮「规范、围棋稿、计划书三处一并更正」只改到了复盘那两处,**这一屏漏了**。
 * 实现按更正后的口径写「提示、形势判断、变化图」。
 *
 * ## 其余预期差异
 *
 *  · **「落子」是两段可选**(2026-08-23 按稿子改回来的,同屏 02)。这一帧把摄像头 stub 成
 *    **已标定** ⇒ 和稿子那一帧一样选中「实体盘」。
 *    ⚠️ 这一组**没有说明行** —— 稿子 03 屏到「路数」那行就结束了。自由对弈那屏有一行,
 *    照抄过来会把下面每一组都推下去一行(实测四图 refOnly 当场涨 1900)。
 *    计分局只在**实体盘那段灰掉时**才说话:灰而不说原因是另一条更硬的规矩。
 *  · **赌注那两格按净胜分说话。** 稿子写「胜 · 升到 4 级」「负 · 退到 6 级」——
 *    那是净胜分正好 ±2 的特例;真规则 `core/ai_ladder_ranked.py:1503-1506` 是每局 ±1、
 *    到 ±3 才动档。而且「升到几级」这块屏拿不到(状态里只有当前档和对手档,没有整份阶梯目录)。
 *    这一帧造的是 `net_score = 2` —— 稿子那一态,于是胜那一格写「升一档」。
 *  · Dock 少「成长」(D6)。
 */

const LADDER_STATUS = {
  view_state: 'ready',
  placement_state: {
    phase: 'placed',
    rung: {
      rung: 16, rank_name: '5级', certification_status: 'certified',
      availability: 'available', route: 'server',
    },
  },
  current_opponent: {
    rung: 16, rank_name: '5级', certification_status: 'certified',
    availability: 'available', route: 'server',
  },
  recent_ranked_results: ['win', 'win'],
  net_score: 2,
  pending_settlement: false,
  blocking_game: null,
};

test('四图:升降级开局设置 ←→ sample-go/shots/03-setup-ranked.png', async ({ page }) => {
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
  await page.route('**/api/v1/ai-ladder/status', (route) => route.fulfill({ json: LADDER_STATUS }));

  await page.goto('/kiosk/play/ai/setup/ranked');
  await page.waitForSelector('[data-testid="setup-stakes"]');
  await page.waitForLoadState('networkidle');

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '03-setup-ranked.png'),
    outDir: OUT,
    slug: '03-setup-ranked',
    referenceCaption:
      '参考:sample-go/shots/03-setup-ranked.png · L2 布局 A(盘 516 + 16 + 右栏 460,右栏整栏滚)· '
      + '和屏 02 同一副骨架,右栏只回答三件事:你是谁、对手是谁、这一局赌多少',
    implementationCaption:
      '实现:/kiosk/play/ai/setup/ranked @1024×600 · 时钟冻 16:40 · 摄像头 stub 成已标定(和稿子同一态)· '
      + '⚠️ **「对手」那一块还没换壳**:实现用的仍是 `AiLadderSetupOpponent`,它手上是六种诚实状态'
      + '(加载 / 出错重试 / 定级赛进度 / 已定档 / 档位不可挑战 / 成绩在途),而稿子只画了「已定档」那一种;'
      + '它同时是 galaxy 那屏的消费者,在原地改样式会把另一家一起改了 —— **登记过的欠账,不是没看见** · '
      + '**「落子」是两段可选**(同屏 02,已标定 ⇒ 选中「实体盘」);这一组**没有说明行**,'
      + '因为稿子 03 屏到「路数」就结束了 —— 照抄自由对弈那行会把下面每一组都推下去一行 · '
      + '**赌注按净胜分说话**:稿子那两格「升到 4 级 / 退到 6 级」是净胜分 ±2 的特例,真规则是每局 ±1、'
      + '到 ±3 才动档;「升到几级」这块屏也拿不到(状态里没有整份阶梯目录),所以到点那格写「升一档」· '
      + '**那行提示写的是「变化图」不是「复盘」**:2026-08-23 查明后端那道闸(`interface.py:877` '
      + '`ANALYSIS_ACTIONS`)关的是对局中那棵树上的动作,离线报告不在里面;那一轮三处更正漏了这一屏 · '
      + 'Dock 少「成长」(D6)',
  });
  console.log(`[fourup 03-setup-ranked] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
