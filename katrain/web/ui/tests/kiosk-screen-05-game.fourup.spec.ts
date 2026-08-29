import { test } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });   // 合成要读刚写出的 PNG,而 config 是 fullyParallel

const SHOTS = resolve(process.cwd(),
  '../../../../smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots');
const OUT = resolve(process.cwd(),
  '../../../superpowers/tracks/kiosk-go-shell-align/visual/05-game/1024x600');

/**
 * ⚠️ **屏号是 05 不是 02。** 计划书里这一屏写作「屏 02」,那是 2026-08-20 那份**十屏**稿的编号;
 * 稿子 2026-08-21 扩到 27 屏之后,对局中变成第 5 屏(`sample-go/shots/05-game.png`,
 * 稿子里 `<span class="idx">05</span>`)。参考图的文件名是唯一不会漂的锚,所以 slug 跟它走。
 */

const COLS = 'ABCDEFGHJKLMNOPQRST';
const xy = (c: string): [number, number] => [COLS.indexOf(c[0]), Number(c.slice(1)) - 1];

// 稿子 `:847` 那一局,逐子照搬 —— 参考图和实现图画的必须是**同一个局面**,
// 否则四图对比看到的差异有一半是「两边摆的子不一样」。
const BLACK = ['Q16', 'Q4', 'C14', 'C11', 'Q6', 'Q10', 'K17', 'C7', 'C5', 'D8', 'R14', 'M16'];
const WHITE = ['D4', 'D16', 'C16', 'O3', 'L3', 'F17', 'G3', 'D6', 'C4', 'F5', 'N17', 'P17'];

// 稿子那条曲线:开局十来手贴着中线,第 17 手黑走坏,两条线一起掉,当前 黑 37.4% / 白 +4.8 目。
const HISTORY = Array.from({ length: 25 }, (_, i) => ({
  node_id: i,
  winrate: i < 17 ? 0.5 - i * 0.0035 : 0.5 - 17 * 0.0035 - (i - 16) * 0.0105,
  score: i < 17 ? -i * 0.1 : -17 * 0.1 - (i - 16) * 0.39,
}));

const STATE = {
  game_id: 'fourup-05', board_size: [19, 19], komi: 6.5, handicap: 0, ruleset: 'chinese',
  game_type: 'free', count_min_moves: 100, current_node_id: 24, current_node_index: 24,
  history: HISTORY, player_to_move: 'B',
  stones: [
    ...BLACK.map((c, i) => ['B', xy(c), null, i * 2 + 1]),
    ...WHITE.map((c, i) => ['W', xy(c), null, i * 2 + 2]),
  ],
  last_move: xy('P17'), prisoner_count: { B: 0, W: 0 },
  analysis: null, commentary: '', is_root: false, is_pass: false, end_result: null,
  children: [], ghost_stones: [],
  players_info: {
    B: { player_type: 'player:human', player_subtype: '', name: '访客（你）', calculated_rank: '', periods_used: 0, main_time_used: 0 },
    W: { player_type: 'player:ai', player_subtype: 'katago', name: 'KataGo', calculated_rank: -4, periods_used: 0, main_time_used: 0 },
  },
  note: '',
  ui_state: { show_children: false, show_dots: false, show_hints: false, show_policy: false,
    show_ownership: false, show_move_numbers: false, show_coordinates: true, zen_mode: false },
};

test('四图:对局中 ←→ sample-go/shots/05-game.png', async ({ page }) => {
  await freezeClock(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'fourup');
    localStorage.setItem('katrain_language', 'cn');
  });
  /**
   * 对局 WS 也要接住。造的 token 是假的,服务端会 `close(1008, "Invalid token")`,
   * 而 `dc55f32e` 之后那条拒绝**会在屏上说出来** —— 稿子这一帧画的是正常对局,
   * 不接的话四图右半永远盖着一条红色的「实时连接被拒绝」。
   * 接住之后什么都不发:这一帧的局面本来就来自 `/api/state`,WS 只负责后续推送。
   * (它占不占流内高度是另一回事,归 `kiosk-screen-05-game.spec.ts` 那条几何闸 ——
   *  那一条**故意不 stub**,量的就是报错态。)
   */
  await page.routeWebSocket('**/ws/**', () => { /* 连上就行,不推任何东西 */ });
  // 后端没起时 logo 会 502,取出来的图左上角是碎图标 —— 钉在仓里那份真字节上。
  await stubBackendStatics(page);
  await page.route('**/api/state**', (route) => route.fulfill({ json: { state: STATE } }));
  await page.route('**/api/v1/**', (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/auth/me') {
      return route.fulfill({ json: { id: 1, username: '访客', rank: '5段', credits: 0 } });
    }
    // 摄像头三格在这一屏上**没有位置**(§5 状态显示归 L1 镜像栏)。这里把实体识别整条关掉,
    // 取图机器上本来也没有摄像头 —— 开着只会让「重置识别」那个页级图标键出现在一台
    // 根本没有实体盘的机器上。**那个键在真盒子上是有的**,标签带里写明了。
    if (path === '/api/v1/vision/status') {
      return route.fulfill({ json: { enabled: false, camera_connected: false, pose_locked: false,
        sync_state: 'unbound', recognition_ready: false, led_connected: null, bound_session_id: null } });
    }
    if (path === '/api/v1/geometry/status') {
      return route.fulfill({ status: 404, json: { detail: 'geometry disabled' } });
    }
    return route.fulfill({ json: {} });
  });
  await page.goto('/kiosk/play/ai/game/fourup-05');
  // 等的是**盘真的画出来了**:canvas 在 DOM 里不等于画过一笔,所以等到七个动作键都在
  // (它们和盘同一次渲染)再等网络静默。
  await page.waitForSelector('[data-testid="game-actions"] button:nth-child(7)');
  await page.waitForLoadState('networkidle');

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '05-game.png'),
    outDir: OUT,
    slug: '05-game',
    referenceCaption: '参考:sample-go/shots/05-game.png · 稿子上解释「为什么不画胜率曲线」那段是旁注(已作废)·.note 一律不上线',
    implementationCaption:
      '实现:/kiosk/play/ai/game @1024×600 · 局面/胜率曲线是 fixture(照搬稿子那一局)· 实体识别关着 ⇒ 页控条右端那个「重置识别」键在真盒子上才出现 · 盘是共享 Board(canvas)+ externalRulers',
  });
  console.log('[fourup 05-game]', JSON.stringify(r));
});
