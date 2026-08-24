import { test } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubShellAssets } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });

const SHOTS = resolve(process.cwd(),
  '../../../../smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots');
const OUT = resolve(process.cwd(),
  '../../../superpowers/tracks/kiosk-go-shell-align/visual/25-section/1024x600');

/**
 * 屏 25 课程 · 小节讲解(L2 布局 A:盘 516 + 16 + 右栏 460)。
 *
 * ⚠️ **这一屏必然越过稿子,而且越出去的那部分没有参照物。**
 * 稿子那块盘用的是它自己的 `gosvg(black, white, last, ghost, atari, oak)` ——
 * 它**画不出手数号、字母、记号,也没有「只看一角」**。稿子那一帧写的是
 * `data-b="B5,C4,C6,D5" data-w="E4,E6,F3" data-ghost="C5"`:**七颗手编的子冒充一张教程图**。
 * 真数据(`board_payload`)带 `labels` / `letters` / `shapes` / `viewport`,而书正文的原句就是
 * 「白棋的外势向 **A** 方面……」—— 字母是正文的宾语,不画就是掉内容。
 * ⇒ 这一屏的盘按真数据画,和稿子那一帧对不上是**预期**。
 *   顺带:`ghost`(那个绿圈)在这一屏**不用** —— `board_payload` 里没有「正在讨论的那个点」
 *   这个字段,照抄就得由前端猜一个。书上真有记号时走 `shapes`(这份 fixture 就用了圆圈)。
 *
 * 取两帧,因为这一屏的盘有两种画法而稿子只画了一种:
 *   `25-section`      —— **默认态**(有 viewport ⇒ 落在「局部」)。这是盒上最常见的一屏。
 *   `25b-section-full` —— 切到「全盘」。**这一帧才是和稿子那块盘的同类比较。**
 *
 * 其余预期差异(全部是裁定):
 *  ① 手数那条**滑条换成档位轨**:规范把 `.kiosk-slider` 限定在连续量,手数是离散整数;
 *    稿子那个拇指 16px,远低于 44,而 `.catpick` 的 ± 是 44×44。
 *  ② 行尾标是**三级阶梯**(视频 / 语音 / 文字 / 暂无),稿子那对「有讲解 / 本图暂无视频」作废 ——
 *    它把「有没有旁白」和「有没有视频」两根轴当成一根二值轴用。
 *  ③ 行里那三态(已看过 / 正在看 / 还没看)**不做**:盒上没有可信的「谁看过什么」。
 *    「正在看」换成**当前行高亮**,那一个是真的。
 *  ④ 行首那格是**手数**不是「图 4」:规范给 `.kiosk-row__lead` 的定义就是等宽序号,
 *    而 `figure_label` 是名字、归标题位 —— 一个值不摆两处。后端**没有图名**这个字段,
 *    稿子那个「气的数法」在数据里没有出处,不编。
 *  ⑤ 「24 秒旁白」→「24 秒」,且**只在 `video_duration_ms` 非空时出**(音频没有对应列)。
 */

const CH = (n: string) => n;   // 只是让下面那张表读起来像坐标

/** 稿子那七颗子,换成 `[col,row]`(row = 19 − 数字)。 */
const STONES = {
  B: [[1, 14], [2, 15], [2, 13], [3, 14]],   // B5 C4 C6 D5
  W: [[4, 15], [4, 13], [5, 16]],            // E4 E6 F3
};

const figure = (over: Record<string, unknown>) => ({
  id: 1, section_id: 10, page: 33, figure_label: CH('图 4'),
  book_text: null, page_context_text: null, bbox: null, page_image_path: null,
  board_payload: {
    size: 19,
    stones: STONES,
    // 手数:D5 是第 1 手,白 E4 第 2,黑 C6 第 3,白 E6 第 4,白 F3 第 5。
    labels: { '3,14': '1', '4,15': '2', '2,13': '3', '4,13': '4', '5,16': '5' },
    // 书上给这个点标了个圈 —— 「白 C5 是禁入点」说的就是它。**不是稿子那个 ghost**:
    // `board_payload` 里没有「候选点」这个字段。
    shapes: { '2,14': 'circle' },
    letters: { '6,12': 'A' },
    highlights: [],
    viewport: { col: 0, row: 9, size: 10 },
  },
  recognition_debug: null, narration: null, audio_asset: null, video_asset: null,
  video_duration_ms: null, video_size_bytes: null, order: 0, updated_at: null,
  ...over,
});

const SECTION = {
  id: 10, chapter_id: 11, section_number: '2', title: '禁入点', order: 0,
  figure_count: 3, has_video: false,
  figures: [
    figure({
      id: 1, figure_label: '图 4', order: 0,
      narration: '白 C5 是禁入点。它的四口气 B5、D5、C4、C6 全被黑占着，下上去自己一口气都没有，'
        + '又提不掉黑棋——按规则不能下。但如果下上去能提掉黑子，那就不是禁入点了：先提子，再数气。',
      video_asset: 'tutorial_assets/rumen/video/fig_4.mp4',
      video_duration_ms: 24000,
    }),
    figure({ id: 2, figure_label: '图 5', order: 1, audio_asset: 'tutorial_assets/rumen/audio/fig_5.mp3', narration: '什么是禁入点。' }),
    figure({ id: 3, figure_label: '图 6', order: 2, narration: '能提子就不是禁入点。' }),
  ],
};

const NAV = {
  bookId: 1, bookTitle: '围棋入门一本通', bookSlug: 'rumen', category: '入门',
  chapterId: 100, chapterNumber: '第 3 章', chapterTitle: '禁入点与打劫',
  sectionTitle: '禁入点', hasVideo: true,
};

const boot = async (page: import('@playwright/test').Page) => {
  await freezeClock(page);
  await page.addInitScript((nav) => {
    localStorage.setItem('token', 'fourup');
    localStorage.setItem('katrain_language', 'cn');
    // 页面靠 router state 拿章号和返回去向 —— 直接 goto 是没有 state 的,
    // 所以把它塞进 history。这是**输入**,不是被断言的结论。
    history.replaceState({ usr: nav }, '');
  }, NAV);
  await stubShellAssets(page);
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, username: '访客', rank: '5段', credits: 0 },
  }));
  await page.route('**/api/v1/tutorials/sections/10', (route) => route.fulfill({ json: SECTION }));
  await page.goto('/kiosk/tutorial/section/10');
  await page.waitForSelector('[data-testid="tutorial-figure-row"]');
  await page.waitForLoadState('networkidle');
};

test('四图:课程 · 小节讲解(默认「局部」)←→ sample-go/shots/25-section.png', async ({ page }) => {
  await boot(page);
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '25-section.png'),
    outDir: OUT,
    slug: '25-section',
    referenceCaption:
      '参考:sample-go/shots/25-section.png · L2 布局 A(盘 516 + 16 + 右栏 460)· '
      + '稿子那块盘是**手编的七颗子**,它自己的渲染器画不出手数号 / 字母 / 记号 / 只看一角',
    implementationCaption:
      '实现:/kiosk/tutorial/section/10 @1024×600 · 时钟冻 16:40 · **默认态**(有 viewport ⇒ 落在「局部」)· '
      + '盘按真 board_payload 画:手数号在子上、书正文里那个「A」在空点上、圆圈是书上的记号 · '
      + '刻度带写的是**这个窗口里的坐标**(A–K 跳 I / 10–1),节距 = 落子区 / max(cols,rows) · '
      + '「局部」是默认:入门书的图大多只画一角,全盘会把那一角缩成指甲盖(稿子自己的话)· '
      + '手数**滑条换档位轨**(规范把滑条限定在连续量;稿子那个拇指 16px < 44)· '
      + '行尾是**三级阶梯**(视频 / 语音 / 文字 / 暂无),稿子那对「有讲解 / 本图暂无视频」把两根轴当一根用 · '
      + '行里三态不做(盒上没有可信的「谁看过什么」),「正在看」换成当前行高亮 · '
      + '行首那格是**手数**(规范给 lead 的定义就是等宽序号),图名归标题位;后端没有图名字段,'
      + '稿子那个「气的数法」在数据里没有出处,不编 · 「24 秒旁白」→「24 秒」,只在有视频时长时出',
  });
  console.log(`[fourup 25-section] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});

test('四图:课程 · 小节讲解(切到「全盘」)←→ sample-go/shots/25-section.png', async ({ page }) => {
  await boot(page);
  await page.getByRole('radio', { name: '全盘' }).click();
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '25-section.png'),
    outDir: OUT,
    slug: '25b-section-full',
    referenceCaption:
      '参考:sample-go/shots/25-section.png(同一张)· 稿子那一帧「全盘」是按下的,'
      + '所以**这一帧才是和它那块盘的同类比较**',
    implementationCaption:
      '实现:同一屏按了「全盘」· 19 路整盘 + 19 个刻度字,子的位置和稿子那七颗一一对上 · '
      + '差在稿子没有的那三样:手数号(1–5)、空点上的字母 A、书上那个圆圈记号 · '
      + '稿子那个绿色 ghost 圈**不做**:board_payload 里没有「候选点」这个字段,照抄就得前端猜',
  });
  console.log(`[fourup 25b-section-full] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
