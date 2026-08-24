import { test, expect, type Page } from '@playwright/test';

/**
 * 课程这条路的**整条走通**:分类 → 书目与目录 → 小节讲解 → 原路返回。
 *
 * 和两屏各自的单测分工明确:单测把 router 整个 mock 掉,断的是「这个组件收到这份数据
 * 画成什么」;**这一份断的是路由真的接上了** —— 路径长什么样、`?book=` / `?ch=` 有没有
 * 写进地址、返回键回不回得去。那几件事在 `MemoryRouter` 里全是自己和自己一致。
 *
 * ⚠️ **2026-08-24 整份重写。** 上一版写于 2026-06-29,三条**在 HEAD 上就是红的**,
 * 而且不是缺引擎缺数据 —— 是测试过期,断言的东西实现里早就没有了:
 *   · `<video src=…/section_10.mp4>` —— 断的是**节级**拼出来的 URL,
 *     而实现从很早以前就走**图级** `figure.video_asset`;
 *   · 「本**节**暂无视频」—— 实现出的是「本**图**」,这一轮又整个换成了三级阶梯;
 *   · 一个点缩略图弹出来的对话框 —— 那个对话框已经不存在。
 * 同一轮里 `tutorial/book/:bookId` 连同 `TutorialBookDetailPage` 一起删了,
 * 上一版那条「点书名进书详情页」的路径也没有了。⇒ 重写,不是修补。
 *
 * 数据全部走 route mock,**不需要真的教程库、MinIO 或 KataGo**。
 */

const CATEGORY = '入门';

const CATEGORIES = [
  { slug: CATEGORY, title: CATEGORY, summary: '规则与吃子', order: 1, book_count: 2 },
];

const BOOKS = [
  { id: 1, category: CATEGORY, subcategory: '', title: '围棋入门一本通', author: '吴老师', translator: null, slug: 'rumen', chapter_count: 2 },
  { id: 2, category: CATEGORY, subcategory: '', title: '吃子技巧图解', author: null, translator: null, slug: 'chizi', chapter_count: 1 },
];

const chapter = (id: number, bookId: number, n: string, title: string, secs: number) =>
  ({ id, book_id: bookId, chapter_number: n, title, order: id, section_count: secs });

const BOOK_DETAIL: Record<number, unknown> = {
  1: { ...BOOKS[0], chapters: [chapter(101, 1, '第 1 章', '棋盘与棋子', 2), chapter(102, 1, '第 2 章', '气与提子', 1)] },
  2: { ...BOOKS[1], chapters: [chapter(201, 2, '第 1 章', '门吃', 1)] },
};

const SECTIONS: Record<number, unknown[]> = {
  101: [
    { id: 1011, chapter_id: 101, section_number: '1', title: '十九路', order: 0, figure_count: 2, has_video: true },
    { id: 1012, chapter_id: 101, section_number: '2', title: '黑先白后', order: 1, figure_count: 1, has_video: false },
  ],
  102: [{ id: 1021, chapter_id: 102, section_number: '1', title: '数气', order: 0, figure_count: 1, has_video: false }],
  201: [{ id: 2011, chapter_id: 201, section_number: '1', title: '门吃', order: 0, figure_count: 1, has_video: false }],
};

const figure = (over: Record<string, unknown>) => ({
  id: 1, section_id: 1011, page: 1, figure_label: '图 1',
  book_text: null, page_context_text: null, bbox: null, page_image_path: null,
  board_payload: {
    size: 19,
    stones: { B: [[3, 15]], W: [[4, 15]] },
    labels: { '3,15': '1', '4,15': '2' },
    viewport: { col: 0, row: 9, size: 10 },
  },
  recognition_debug: null, narration: null, audio_asset: null, video_asset: null,
  video_duration_ms: null, video_size_bytes: null, order: 0, updated_at: null,
  ...over,
});

/** ⚠️ `has_video` 故意留 `false`:详情端点从不设这个字段(`tutorials/models.py:52` 的默认值)。
 *  这一节**有**视频 —— 靠的是图上的 `video_asset`。这一条就是上一版栽的那个坑。 */
const SECTION_1011 = {
  id: 1011, chapter_id: 101, section_number: '1', title: '十九路', order: 0,
  figure_count: 2, has_video: false,
  figures: [
    figure({ id: 11, figure_label: '图 1', narration: '十九路棋盘。', video_asset: 'tutorial_assets/rumen/video/fig_1.mp4', video_duration_ms: 18000 }),
    figure({ id: 12, figure_label: '图 2', narration: '黑先白后。' }),
  ],
};

const setup = async (page: Page) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'tutorial-e2e');
    localStorage.setItem('katrain_language', 'cn');
  });
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, username: 'tester', rank: '5段', credits: 0 },
  }));
  await page.route('**/api/v1/tutorials/categories', (route) => route.fulfill({ json: CATEGORIES }));
  await page.route('**/api/v1/tutorials/categories/*/books', (route) => route.fulfill({ json: BOOKS }));
  await page.route('**/api/v1/tutorials/books/*', (route) => {
    const id = Number(/books\/(\d+)/.exec(route.request().url())?.[1] ?? 1);
    route.fulfill({ json: BOOK_DETAIL[id] });
  });
  await page.route('**/api/v1/tutorials/chapters/*/sections', (route) => {
    const id = Number(/chapters\/(\d+)\/sections/.exec(route.request().url())?.[1] ?? 101);
    route.fulfill({ json: SECTIONS[id] ?? [] });
  });
  await page.route('**/api/v1/tutorials/sections/*', (route) => route.fulfill({ json: SECTION_1011 }));
  // 媒体网关:200 就行,`<video>` 是 preload=none,不会真去拉。
  await page.route('**/api/v1/tutorials/assets/**', (route) => route.fulfill({ status: 200, body: '' }));
};

test.describe('课程(只读镜像)', () => {
  test('分类 → 书目与目录 → 小节讲解 → 原路返回,四段路径都在地址里', async ({ page }) => {
    await setup(page);
    await page.goto('/kiosk/tutorial');

    // 屏 23:分类
    await page.getByRole('button', { name: /入门/ }).click();

    // 屏 24:选中的书**自动写进地址**(replace),下半屏是它的目录
    await expect(page).toHaveURL(/\/kiosk\/tutorial\/%E5%85%A5%E9%97%A8\?book=1$/);
    await expect(page.getByText('围棋入门一本通 · 目录')).toBeVisible();
    await expect(page.getByTestId('tutorial-chapter-row')).toHaveCount(2);

    // 章行本身是展开控件,摊开哪一章也进地址
    await page.getByTestId('tutorial-chapter-row').first().click();
    await expect(page).toHaveURL(/book=1&ch=101$/);
    await expect(page.getByTestId('tutorial-section-row')).toHaveCount(2);

    // 屏 25:小节讲解
    await page.getByTestId('tutorial-section-row').first().click();
    await expect(page).toHaveURL(/\/kiosk\/tutorial\/section\/1011$/);
    await expect(page.getByTestId('tutorial-figure-board')).toBeVisible();
    // 页控条按稿子写「章 · 节」,而且**不许出现 undefined**
    await expect(page.getByTestId('tutorial-section-pagebar')).toContainText('第 1 章 · 第 1 节 十九路');
    await expect(page.getByText('undefined')).toHaveCount(0);

    // 「← 目录」回得到**离开时那一屏**:书 + 摊开的那一章
    await page.getByRole('button', { name: /目录/ }).click();
    await expect(page).toHaveURL(/\/kiosk\/tutorial\/%E5%85%A5%E9%97%A8\?book=1&ch=101$/);
    await expect(page.getByTestId('tutorial-section-row')).toHaveCount(2);
  });

  test('有没有视频看图上的 video_asset,不看那一节的 has_video(它恒是 false)', async ({ page }) => {
    await setup(page);
    await page.goto('/kiosk/tutorial/section/1011');
    await expect(page.getByTestId('tutorial-figure-board')).toBeVisible();

    // 一进来是棋图,不是视频
    await expect(page.locator('video')).toHaveCount(0);

    // 这一节的 `has_video` 是 false,而图 1 有 `video_asset` ⇒ 这颗键必须是「看视频讲解」
    await page.getByRole('button', { name: '看视频讲解' }).click();
    await expect(page.locator('video')).toHaveAttribute(
      'src', '/api/v1/tutorials/assets/tutorial_assets/rumen/video/fig_1.mp4',
    );
    await expect(page.getByTestId('tutorial-figure-board')).toHaveCount(0);
  });

  test('第二张图只有文字讲解:键灰掉,行尾标也换一个词', async ({ page }) => {
    await setup(page);
    await page.goto('/kiosk/tutorial/section/1011');
    await expect(page.getByTestId('tutorial-figure-row')).toHaveCount(2);

    const rows = page.getByTestId('tutorial-figure-row');
    await expect(rows.nth(0)).toContainText('视频讲解');
    await expect(rows.nth(1)).toContainText('文字讲解');

    await page.getByRole('button', { name: '下一图' }).click();
    await expect(page.getByRole('button', { name: '只有文字讲解' })).toBeDisabled();
    await expect(page.locator('video')).toHaveCount(0);
  });

  test('深链进小节(没有 router state):照样画得出,「← 目录」退回课程首页', async ({ page }) => {
    await setup(page);
    await page.goto('/kiosk/tutorial/section/1011');
    await expect(page.getByTestId('tutorial-figure-board')).toBeVisible();
    // 没有 state ⇒ 标题只有节,**不猜一个章号**
    await expect(page.getByText('undefined')).toHaveCount(0);

    await page.getByRole('button', { name: /目录/ }).click();
    await expect(page).toHaveURL(/\/kiosk\/tutorial$/);
  });
});
