import { test } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubShellAssets } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });

const SHOTS = resolve(process.cwd(),
  '../../../../smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots');
const OUT = resolve(process.cwd(),
  '../../../superpowers/tracks/kiosk-go-shell-align/visual/17-baipu/1024x600');

/**
 * 屏 17 摆谱 · 进行中(L2 布局 A:盘 516 + 16 + 右栏 460)。
 *
 * ⚠️ **稿子那一帧里有三处是错的,不是我没对齐**(2026-08-24 裁定,已回报稿子作者):
 *  ① 「绿灯 = 该放上 / 红灯 = 该拿走」—— **反了,而且漏了一色**。
 *    `constants/ledColors.ts` 定死 黑→红 `#ff3b30` / 白→绿 `#34c759` / 提子→蓝 `#2f6fff`,
 *    后端 `COLOR_RGB`、`ledColors.test.ts` 那条精确相等、两条 track 的 PRD 全一致。
 *    ⇒ 屏上换成三句真图例:红=放黑子 / 绿=放白子 / 蓝=该拿走。
 *  ② 盘上那个候选圈稿子画成**绿**的,而 C7 是**黑**棋 —— 规范(建议 E,已采纳)定死
 *    「屏上高亮色必须和灯同色」,所以实现里它是红的。
 *  ③ 稿子动作区四格,多一颗**虚手**。这一屏是在重放一份既有 SGF,而这条 track 的数据契约
 *    把 pass 定义成「无物理动作」(不产帧、`frames.length = 1 + 非 pass 落子数`)——
 *    一颗人能按的虚手要么破坏那条等式,要么什么都不干。⇒ 三格:确认落子 / 撤回上一手 / 完成。
 *
 * 其余预期差异:
 *  · 玩家卡两张删了 —— 摆谱**没有人在下棋**,一局早已结束的谱,屏前只有一个操作员;
 *    `data-active` 挂在申真谞那张卡上等于屏上写着「轮到申真谞了」。名字进页控条标题。
 *  · 通栏状态条(落子黑 / 手数 / 已采集 / 两颗健康点)整块删:前三样稿子本来就有落点,
 *    LED 那颗**由页控条右上角那颗「重新点灯」兼任**(它本来就是这个故障的补救动作),
 *    相机那颗**删** —— 唯一现成的数据源 `vision/status` 在摆谱专用部署(有相机、有采集、
 *    无 vision 模型)下恒返回 `camera_connected:false`,挂上去就是在好机器上画红点。
 *  · 「完成」常驻但摆完之前灰着 + 写明还剩几手(常驻是为了那颗按 250 次的键位置不跳)。
 */

/** 稿子那 12 手,换成后端 `steps[]`(row 从上往下数)。 */
const MOVES: [number, number, 'B' | 'W'][] = [
  [3, 15, 'B'], [3, 3, 'W'],      // Q16 D16
  [15, 3, 'B'], [15, 15, 'W'],    // D4  Q4
  [9, 15, 'B'], [5, 16, 'W'],     // Q10 R14
  [5, 2, 'B'], [2, 5, 'W'],       // C14 F17
  [12, 16, 'B'], [12, 15, 'W'],   // R7  Q7
  [2, 4, 'B'], [9, 3, 'W'],       // E17 D10
];

const STEPS = {
  board_size: 19,
  meta: { player_black: '申真谞', player_white: '柯洁', handicap: 0, komi: 6.5, ruleset: 'chinese' },
  steps: [
    ...MOVES.map(([row, col, color], i) => ({
      kind: 'move', move_index: i, property: color, row, col, color, removed: [], board_hash: `h${i}`,
    })),
    // 第 13 手 = 稿子那个待摆点 C7(row 12, col 2)
    { kind: 'move', move_index: 12, property: 'B', row: 12, col: 2, color: 'B', removed: [], board_hash: 'h12' },
    // 后面再补一批,好让「共 241」那类分母不是 13(这一屏的分母要真)
    ...Array.from({ length: 228 }, (_, i) => ({
      kind: 'move', move_index: 13 + i, property: i % 2 === 0 ? 'W' : 'B',
      row: 7 + (i % 5), col: 7 + Math.floor(i / 5) % 5, color: i % 2 === 0 ? 'W' : 'B',
      removed: [], board_hash: `t${i}`,
    })),
  ],
};

const boot = async (page: import('@playwright/test').Page) => {
  await freezeClock(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'fourup');
    localStorage.setItem('katrain_language', 'cn');
    localStorage.setItem('baipu:sgf:s1', JSON.stringify({
      id: 's1', name: '摆谱 · 三星杯半决赛', sgf: '(;SZ[19];B[pd])', savedAt: 1,
    }));
  });
  await stubShellAssets(page);
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, username: '访客', rank: '5段', credits: 0 },
  }));
  await page.route('**/api/v1/baipu/load', (route) => route.fulfill({ json: STEPS }));
  await page.route('**/api/v1/led/**', (route) => route.fulfill({
    json: { ok: true, connected: true, shown_at: null, errors: [] },
  }));
  // 采集在这台机器上是通的:回一份成功,好让「已采集 N 帧 / 最近保存」有真数。
  await page.route('**/api/v1/baipu/capture', (route) => route.fulfill({
    json: { path: '/data/baipu/s1/move_012.jpg', geometry_correction: null },
  }));
  await page.goto('/kiosk/baipu/session/s1');
  await page.waitForSelector('[data-testid="baipu-pcard"]');
};

test('四图:摆谱 · 进行中 ←→ sample-go/shots/17-baipu.png', async ({ page }) => {
  await boot(page);
  // 摆到第 13 手(稿子那一帧)—— 前 12 手逐手确认,和真人做的事一样。
  for (let i = 0; i < 12; i += 1) {
    await page.getByRole('button', { name: '确认落子' }).click();
    await page.waitForFunction((n) => {
      const el = document.querySelector('[data-testid="baipu-pagebar"]');
      return !!el && el.textContent!.includes(`第 ${n} / 241 手`);
    }, i + 2);
  }
  await page.waitForLoadState('networkidle');
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '17-baipu.png'),
    outDir: OUT,
    slug: '17-baipu',
    referenceCaption:
      '参考:sample-go/shots/17-baipu.png · L2 布局 A(盘 516 + 16 + 右栏 460)· '
      + '主角在盘上不在屏上:灯指下一手，摄像头认，人负责摆',
    implementationCaption:
      '实现:/kiosk/baipu/session/s1 @1024×600 · 时钟冻 16:40 · 摆到第 13 手 · '
      + '**稿子那两行 LED 图例是错的**:黑→红 / 白→绿 / 提子→蓝(ledColors.ts 四处独立来源一致)，'
      + '稿子写「绿灯=该放上 / 红灯=该拿走」会让人去拿一颗刚该放下的子 ⇒ 换成三句真图例 · '
      + '**盘上那个圈是红的不是绿的**:C7 是黑棋，规范定死「屏上高亮色必须和灯同色」 · '
      + '**动作区三格不是四格**:稿子多的那颗「虚手」不做——这一屏在重放既有 SGF，'
      + '而 pass 按数据契约不产帧，一颗能按的虚手要么破坏 frames 等式要么什么都不干 · '
      + '**玩家卡两张删了**:摆谱没有人在下棋，名字进页控条标题 · '
      + '**通栏状态条删了**:LED 那颗健康点由右上角「重新点灯」兼任(它就是这个故障的补救)，'
      + '相机那颗删——唯一数据源在摆谱专用部署下恒报 false，挂上去就是在好机器上画红点 · '
      + '「完成」常驻但摆完前灰着(常驻是为了那颗按 250 次的键位置不跳)· '
      + '**「已采集 13 帧」比稿子多一帧,是稿子少算了**:数据契约写着 '
      + '`frames.length = 1(开局空盘那帧) + 非 pass 落子数`，摆到第 13 手 = 1 + 12 = 13 · '
      + '「最近保存」印的是**文件名**不是稿子那句「第 12 手」——盘前的人要拿它去磁盘上对，'
      + '而手数在同一块账的第一行已经有了',
  });
  console.log(`[fourup 17-baipu] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
