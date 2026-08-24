import { test } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubShellAssets } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });   // 合成要读刚写出的 PNG,而 config 是 fullyParallel

const SHOTS = resolve(process.cwd(),
  '../../../../smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots');
const OUT = resolve(process.cwd(),
  '../../../superpowers/tracks/kiosk-go-shell-align/visual/24-books/1024x600');

/**
 * 屏 24 课程 · 书目与章节(L2 布局 B,通栏整栏滚)。
 *
 * **两屏合一**:原来的 `tutorial/book/:bookId` + `TutorialBookDetailPage.tsx` 一起删了,
 * 稿子自己写的判据 —— 选完书之后下面那半屏才有内容,分成两屏第一屏只有三张卡、剩下 350px 全空。
 *
 * 与稿子的预期差异,全部是**裁定**不是没对齐:
 *  ① **进度那一层一处不上**:环恒「—」(稿子第一张卡是 35%)、副标不写「已看到第 3 章」、
 *    章行行尾那三个键(已看完 / 接着看 / 开始)整个没有。盒上没有可信的「谁看过什么」——
 *    `UserTutorialProgress` 已废弃、V1 字符串键与 V2 整数 id 无映射、零端点。
 *  ② **章行行尾换成一颗 caret**:行本身就是展开控件,caret 说的是「这一行现在是开是合」,
 *    那个屏上为真;三态说的是「你看过没有」,那个盒上问不出来。
 *  ③ **两处组标题右端换成真数**:稿子写「书目由云端下发」和「点到『节』才有讲解」——
 *    那是说给读稿人听的,而那一格按规范放**数据**。本数已在页控条副标(一个数不摆两处)
 *    ⇒ 上面那格留空;下面那格写「{c} 章 · {s} 节」。
 *  ④ 分类名是 `入门` 不是稿子的 `入门篇` —— 四类的 slug 就是它们的中文名
 *    (`db_queries.py:22` 写死的四条:入门 / 布局 / 中盘 / 官子),屏上不许现编一个后缀。
 *  ⑤ 章行默认**全收起**,和稿子同形。摊开哪一章进 URL(`?ch=`),所以屏 25 按「← 目录」
 *    回得到离开时那一屏 —— 上一版是「每一章都摊开」,回来时全收起会让人重新找一遍自己在哪。
 */

const CATEGORY = '入门';

const BOOKS = [
  { id: 1, category: CATEGORY, subcategory: '', title: '围棋入门一本通', author: null, translator: null, slug: 'rumen', chapter_count: 8 },
  { id: 2, category: CATEGORY, subcategory: '', title: '吃子技巧图解', author: null, translator: null, slug: 'chizi', chapter_count: 6 },
  { id: 3, category: CATEGORY, subcategory: '', title: '死活初步', author: null, translator: null, slug: 'sihuo', chapter_count: 5 },
];

/** 章:照稿子那六行的节数与图数。 */
const CHAPTERS: [string, string, number, number][] = [
  ['第 1 章', '棋盘与棋子', 4, 27],
  ['第 2 章', '气与提子', 5, 41],
  ['第 3 章', '禁入点与打劫', 4, 33],
  ['第 4 章', '连接与分断', 5, 38],
  ['第 5 章', '做眼与做活', 6, 52],
  ['第 6 章', '征子与枷吃', 4, 31],
];

const BOOK_DETAIL = {
  ...BOOKS[0],
  chapters: CHAPTERS.map(([n, title, secs], i) => ({
    id: 100 + i, book_id: 1, chapter_number: n, title, order: i, section_count: secs,
  })),
};

/** 每章的节:节数照稿子,图数摊开之后**加起来正好是稿子那个数**(最后一节兜余数)。 */
const sectionsFor = (chapterIdx: number) => {
  const [, , secs, figs] = CHAPTERS[chapterIdx];
  const base = Math.floor(figs / secs);
  return Array.from({ length: secs }, (_, i) => ({
    id: (100 + chapterIdx) * 100 + i,
    chapter_id: 100 + chapterIdx,
    section_number: String(i + 1),
    title: `第 ${i + 1} 节`,
    order: i,
    figure_count: i === secs - 1 ? figs - base * (secs - 1) : base,
    has_video: i === 0,
  }));
};

test('四图:课程 · 书目与章节 ←→ sample-go/shots/24-books.png', async ({ page }) => {
  await freezeClock(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'fourup');
    localStorage.setItem('katrain_language', 'cn');
  });
  await stubShellAssets(page);
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, username: '访客', rank: '5段', credits: 0 },
  }));
  await page.route('**/api/v1/tutorials/categories/*/books', (route) => route.fulfill({ json: BOOKS }));
  await page.route('**/api/v1/tutorials/books/1', (route) => route.fulfill({ json: BOOK_DETAIL }));
  await page.route('**/api/v1/tutorials/chapters/*/sections', (route) => {
    const id = Number(/chapters\/(\d+)\/sections/.exec(route.request().url())?.[1] ?? 100);
    route.fulfill({ json: sectionsFor(id - 100) });
  });

  await page.goto(`/kiosk/tutorial/${encodeURIComponent(CATEGORY)}`);
  await page.waitForSelector('[data-testid="tutorial-chapter-row"]:nth-child(1)');
  await page.waitForLoadState('networkidle');
  // 焦点环不进图 —— 自动选第一本是 `replace` 回写,没有焦点;这一下是保险。
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '24-books.png'),
    outDir: OUT,
    slug: '24-books',
    referenceCaption:
      '参考:sample-go/shots/24-books.png · L2 布局 B(页控条 44 + 12 + 滚动区 460 = 516,通栏 992)· '
      + '上半屏三张书卡、下半屏那本书的目录',
    implementationCaption:
      '实现:/kiosk/tutorial/入门 @1024×600 · 时钟冻 16:40 · 三本书和六章全从接口来 · '
      + '**两屏合一**:`tutorial/book/:bookId` 连同 TutorialBookDetailPage 一起删了,'
      + '选中的书进 URL(`?book=1`)—— 页内 state 会让屏 25 的「← 目录」回到一本都没选的空半屏 · '
      + '**进度一处不上**:环恒「—」(稿子第一张卡 35%)、副标不写「已看到第 3 章」、'
      + '章行行尾那三个键(已看完 / 接着看 / 开始)整个没有 —— 盒上没有可信的「谁看过什么」'
      + '(UserTutorialProgress 已废弃 / V1 字符串键与 V2 整数 id 无映射 / 零端点),'
      + 'localStorage 顶替更坏:这台盒子有账号,按机器存会把甲的进度显示成乙的 · '
      + '**行尾换成一颗 caret**:行本身就是展开控件,caret 说的是「这一行现在是开是合」,那个为真 · '
      + '**两处组标题右端换真数**:稿子那两句是说给读稿人听的,而那一格按规范放数据;'
      + '本数已在页控条副标(一个数不摆两处)⇒ 上格留空,下格写「6 章 · 28 节」 · '
      + '分类名是「入门」不是「入门篇」:四类的 slug 就是中文名(db_queries.py:22)',
  });
  console.log(`[fourup 24-books] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
