import { expect, test, type Page } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubShellAssets } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });   // 合成要读刚写出的 PNG,而 config 是 fullyParallel

const SHOTS = resolve(process.cwd(),
  '../../../../smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots');
const OUT = resolve(process.cwd(),
  '../../../superpowers/tracks/kiosk-go-shell-align/visual/06-lobby/1024x600');

/**
 * 屏 06 在线大厅四帧(L2 两栏,没有棋盘 ⇒ 页控条通栏):
 * 06 主屏 · 06b 未登录 · 06c 匹配中 · 06d 收到邀请。
 *
 * 稿子 2026-08-23 照国际象棋 05L 那一组重做,理由和四处适配写在
 * `go-kiosk.tmpl.html` 各屏上面的注释里,以及 `LobbyPage.tsx` 的文件头。
 *
 * ## 预期差异,四条
 *
 *  ① **段位那一列没有实现。** 稿子按「接上之后」画了它并写死了契约:`/users/online`
 *    回的 `User.rank` / `elo_points` **全仓没有任何一处写**(`UPDATE users SET` 只出现在
 *    `core/billing.py`,改的是 credits;`models_db.py:75` 的默认值 `"20k"` 从注册那天起
 *    没人动过)。真段位在 `ai_ladder_ranked` 那张表里,缺的只是一个 join。
 *    今天照画,**定过级的人会被这一列说成没定过级** ⇒ 不上。位置和宽度稿子里定死了
 *    (`.rk`,62px,名字之后第一格),join 接上就补。
 *    差异图上它是每一行右半那一小截红边。
 *
 *  ② **06d 那行小字改了。** 稿子写「不接受就一直挂着 —— 邀请没有期限」,只说了一半:
 *    `/ws/lobby` 的 `invite` 只把一条消息转给对方(`server.py:2402`),**没有 TTL、没有
 *    撤回、也没有 decline** ⇒ 这颗「拒绝」只关掉本地这个窗,对面收不到任何东西。
 *    实现写成「拒绝只关掉这个窗 —— 对面收不到回音,邀请也没有期限」。
 *
 *  ③ **06d 的副行去掉了「业余 3 段 · 」。** `invitation` 里只有 `from_id` / `from_name` /
 *    `mode`,没有段位 —— 和 ① 同一个理由,不编。
 *
 *  ④ **06b 的 `fact` 小字改了。** 稿子写「段位来自『升降级对弈』,没打过定级赛就显示未定级」,
 *    那句话承诺的正是 ① 里没上的那一列。换成这一屏真做得到的事(名单只列此刻连着的人)。
 *
 *  另外 Dock 少「成长」:围棋没有 growth 路由/页面/后端(D6)。
 */

const ME = { id: 1, username: '访客' };

/** 稿子那五局,逐字对上(`shots/06-lobby.png` 左栏)。 */
const GAMES = [
  { session_id: '7f3a91c2', player_b: '小满', player_w: '云在青天', spectator_count: 3, move_count: 87 },
  { session_id: '22c1d8e4', player_b: '不系舟', player_w: '半日闲', spectator_count: 0, move_count: 12 },
  { session_id: '9e07b5a1', player_b: '棋逢对手', player_w: '一只鸽子', spectator_count: 1, move_count: 41 },
  { session_id: '4b8d2f60', player_b: '何砚', player_w: '木木', spectator_count: 0, move_count: 3 },
  { session_id: '15fa73cc', player_b: '秋水长天', player_w: '阿凯', spectator_count: 2, move_count: 66 },
];

/** 稿子那 14 人。前四个空闲、后十个正在上面那五局里 —— 状态是**算**出来的,不是喂进来的。 */
const USERS = [
  ME,
  { id: 2, username: '柳三石' }, { id: 3, username: '周不困' }, { id: 4, username: '大熊' },
  { id: 5, username: '小满' }, { id: 6, username: '云在青天' }, { id: 7, username: '不系舟' },
  { id: 8, username: '半日闲' }, { id: 9, username: '棋逢对手' }, { id: 10, username: '一只鸽子' },
  { id: 11, username: '何砚' }, { id: 12, username: '木木' }, { id: 13, username: '秋水长天' },
  { id: 14, username: '阿凯' },
];

/**
 * 假 WebSocket。**不是为了省事** —— 两条理由:
 *   · 「收到邀请」这一态没有任何用户可触发的入口,它只能由服务端推过来。
 *   · 真 WS 连的是 `:8002` 上那个 Python 进程,它对 `token=fourup` 会直接关掉连接 ⇒
 *     这几张图的绿会取决于另一个进程当时的脾气。这一条本 track 栽过(见 `stubShellAssets`)。
 * 顺带把 1 秒那条计时器停掉,让「已等 N 秒」停在 0 —— 稿子那一帧写的就是 0。
 */
async function stubLobbySocket(page: Page) {
  await page.addInitScript(() => {
    class FakeWS {
      static readonly OPEN = 1;
      readyState = 1;
      onmessage: ((e: { data: string }) => void) | null = null;
      onerror: (() => void) | null = null;
      onclose: (() => void) | null = null;
      sent: string[] = [];

      constructor(public url: string) {
        (window as unknown as Record<string, unknown>).__lobbySent = this.sent;
        (window as unknown as Record<string, unknown>).__lobbyPush =
          (m: unknown) => this.onmessage?.({ data: JSON.stringify(m) });
      }

      send(s: string) { this.sent.push(s); }
      close() { this.readyState = 3; }
    }
    (window as unknown as Record<string, unknown>).WebSocket = FakeWS;

    const realSetInterval = window.setInterval.bind(window);
    // 只掐 1000ms 那一条(排队秒表)。10s 那条列表刷新照跑 —— 停掉它等于把「会自己刷新」
    // 这件事也一起测没了。
    (window as unknown as Record<string, unknown>).setInterval =
      (fn: TimerHandler, ms?: number, ...rest: unknown[]) =>
        (ms === 1000 ? 0 : realSetInterval(fn, ms, ...rest));
  });
}

async function bootLobby(page: Page, { token = true } = {}) {
  await freezeClock(page);
  await stubLobbySocket(page);
  await page.addInitScript((withToken) => {
    if (withToken) localStorage.setItem('token', 'fourup');
    else localStorage.removeItem('token');
    localStorage.setItem('katrain_language', 'cn');
  }, token);
  await stubShellAssets(page);
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { ...ME, rank: '20k', credits: 0 },
  }));
  await page.route('**/api/v1/users/online', (route) => route.fulfill({ json: USERS }));
  await page.route('**/api/v1/games/active/multiplayer', (route) => route.fulfill({ json: GAMES }));
  // 定级赛一局没打 ⇒ 排位那一段灰着,底下一行写「你还差 5 局」(稿子那一帧就是这个数)。
  await page.route('**/api/v1/ai-ladder/status', (route) => route.fulfill({
    json: {
      view_state: 'ready',
      placement_state: { phase: 'placement', completed_games: 0, total_games: 5 },
      current_opponent: null, recent_ranked_results: [], net_score: 0, pending_settlement: false,
    },
  }));
  await page.goto('/kiosk/play/pvp/lobby');
}

test('四图:在线大厅主屏 ←→ sample-go/shots/06-lobby.png', async ({ page }) => {
  await bootLobby(page);
  await page.waitForSelector('[data-testid="lobby-start-match"]');
  await expect(page.locator('[data-testid="lobby-game"]')).toHaveCount(5);
  await expect(page.locator('[data-testid="lobby-player"]')).toHaveCount(14);
  await page.waitForLoadState('networkidle');

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '06-lobby.png'),
    outDir: OUT,
    slug: '06-lobby',
    referenceCaption:
      '参考:sample-go/shots/06-lobby.png · L2 两栏(没有棋盘 ⇒ 页控条通栏)· '
      + '左栏是局、右栏是人,各自独立滚,主行动钉右栏底 · 照国象 05L 的骨架,拿围棋自己的真数据填',
    implementationCaption:
      '实现:/kiosk/play/pvp/lobby @1024×600 · 时钟冻 16:40 · 5 局 / 14 人的 fixture 与稿子逐字对上 · '
      + '**段位那一列没有实现**(唯一一处「实现比稿子少」):`/users/online` 回的 `User.rank`/`elo_points` '
      + '全仓没有任何一处写(`UPDATE users SET` 只在 `core/billing.py` 改 credits),真段位在 '
      + '`ai_ladder_ranked` 那张表里 —— 今天照画会**把定过级的人说成没定过级**;'
      + '位置和宽度稿子里定死了(`.rk` 62px,名字之后第一格),join 接上就补 · '
      + '**空闲 / 对局中是算出来的**:拿左栏那五局的名字比对右栏,不是后端喂的状态位 · '
      + '**名单按能不能邀请排序**(我 → 空闲 → 对局中),能点的那几个不该埋在十几行灰按钮下面 · '
      + '**观众数只在真有观众时出现**,恒挂一个 0 是拿一个空位置冒充一条信息 · '
      + '**一个字不写时限**:`create_multiplayer_session` 不带任何时钟参数,不是「不限时」是没有那个字段 · '
      + 'Dock 少「成长」(D6)',
  });
  console.log(`[fourup 06-lobby] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});

test('四图:在线大厅 · 未登录 ←→ sample-go/shots/06b-lobby-guest.png', async ({ page }) => {
  await bootLobby(page, { token: false });
  await page.waitForSelector('[data-testid="lobby-guest"]');
  await page.waitForLoadState('networkidle');

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '06b-lobby-guest.png'),
    outDir: OUT,
    slug: '06b-lobby-guest',
    referenceCaption:
      '参考:sample-go/shots/06b-lobby-guest.png · L2 · 页控条通栏 + 460 面板居中 · '
      + '说清**为什么这一条线要账号**,而不是只说「请先登录」',
    implementationCaption:
      '实现:/kiosk/play/pvp/lobby(无 token)@1024×600 · '
      + '旧版这一态是一句飘在屏幕上方的 MUI `Alert` 加一颗按钮,现在是稿子那道门 · '
      + '**`fact` 那行小字改了**:稿子写「段位来自升降级对弈,没打过定级赛就显示未定级」—— '
      + '那句话承诺的正是主屏上没上的段位列;换成这一屏真做得到的事(名单只列此刻连着的人)· '
      + '**顺手修掉一个 hooks 顺序错**:旧版把「没登录就早退」写在一部分 hooks 中间,'
      + '`/ws/lobby` 那个 `useEffect` 排在早退之后 —— 登录后同一个组件实例多注册一个 hook,'
      + 'React 当场抛 Rendered more hooks than during the previous render',
  });
  console.log(`[fourup 06b-lobby-guest] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});

test('四图:在线大厅 · 匹配中 ←→ sample-go/shots/06c-lobby-match.png', async ({ page }) => {
  await bootLobby(page);
  await page.waitForSelector('[data-testid="lobby-start-match"]');
  await expect(page.locator('[data-testid="lobby-game"]')).toHaveCount(5);
  await page.click('[data-testid="lobby-start-match"]');
  await page.waitForSelector('[data-testid="lobby-matching"]');
  // 点完那颗键还留着 `:focus-visible` 的蓝圈,而稿子那一帧没有 —— 那圈是**取图动作**
  // 带出来的,不是这一态的长相。取图前把焦点撤掉。
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
  // 稿子那一帧写的是 0 —— 1 秒那条计时器已经在 stub 里掐掉,这条是它真的掐住了的证据。
  await expect(page.locator('[data-testid="lobby-queue-secs"]')).toHaveText('0');
  await page.waitForLoadState('networkidle');

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '06c-lobby-match.png'),
    outDir: OUT,
    slug: '06c-lobby-match',
    referenceCaption:
      '参考:sample-go/shots/06c-lobby-match.png · ⑥ 的模态态 · '
      + '不定长进度条(等多久取决于队列里有没有第二个人,这个数产不出来)+ 真的已等秒数',
    implementationCaption:
      '实现:点了「开始匹配」之后 @1024×600 · '
      + '**弹层的定位原点是 `.kiosk-layout-a`**,不是 `.kiosk-content` —— 后者带 14px 上下内边距,'
      + '`inset:0` 一路找上去会让弹层高 544 而中间区只有 516,底边被画布裁掉(稿子那道闸报的就是超 14)· '
      + '**条子是不定长的**:队列里有没有第二个人这件事产不出秒数,画一条定长倒计时就是编一个不存在的承诺 · '
      + '已等秒数是真的(前端自己数),这一帧把 1 秒计时器掐住停在 0 · '
      + '**时限一个字不写**(见主屏)',
  });
  console.log(`[fourup 06c-lobby-match] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});

test('四图:在线大厅 · 收到邀请 ←→ sample-go/shots/06d-lobby-inbox.png', async ({ page }) => {
  await bootLobby(page);
  await page.waitForSelector('[data-testid="lobby-start-match"]');
  await expect(page.locator('[data-testid="lobby-game"]')).toHaveCount(5);
  await page.evaluate(() => {
    (window as unknown as { __lobbyPush: (m: unknown) => void })
      .__lobbyPush({ type: 'invitation', from_id: 2, from_name: '柳三石', mode: 'free' });
  });
  await page.waitForSelector('[data-testid="lobby-invitation"]');
  await page.waitForLoadState('networkidle');

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '06d-lobby-inbox.png'),
    outDir: OUT,
    slug: '06d-lobby-inbox',
    referenceCaption:
      '参考:sample-go/shots/06d-lobby-inbox.png · ⑥ 的模态态 · '
      + '**没有倒计时** —— 围棋的邀请没有期限,不画一个不存在的裁定',
    implementationCaption:
      '实现:服务端推来一条 `invitation` 之后 @1024×600 · '
      + '**没有倒计时**:国象 05S 那条 60 秒是他们服务端定的期限,围棋的 `invite` 只是把一条消息'
      + '转给对方(`server.py:2402`)—— 没有 TTL、没有撤回。画一条走完归零、而后端归零时什么都不做的条,'
      + '是拿动画伪造一个不存在的裁定 · '
      + '**那行小字改了**:稿子写「不接受就一直挂着 —— 邀请没有期限」只说了一半,后端连 decline 都没有,'
      + '这颗「拒绝」只关掉本地这个窗、对面收不到任何东西 ⇒ 写成「拒绝只关掉这个窗 —— 对面收不到回音,'
      + '邀请也没有期限」· '
      + '**副行去掉了「业余 3 段 · 」**:`invitation` 里只有 from_id / from_name / mode,没有段位,不编',
  });
  console.log(`[fourup 06d-lobby-inbox] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
