import { test, expect, type Page } from '@playwright/test';

/**
 * E2E for the read-only kiosk tutorial module.
 *
 * Uses Playwright route mocks for /api/v1/tutorials/** (fixed categories / books /
 * chapters / sections / figures) so the core flow is asserted deterministically —
 * NO "if visible then continue" smoke pattern, no silent skips. Auth is seeded the
 * same way as baipu.spec.ts (token in localStorage + mocked /auth/me).
 *
 * Requires the Playwright webServer (see playwright.config.ts) to serve the built
 * app; it does NOT require real tutorial data, MinIO, or KataGo.
 */

const CATEGORIES = [{ slug: 'rumen', title: '入门', summary: '围棋基础知识', order: 0, book_count: 1 }];

const BOOKS = [
  { id: 1, category: 'rumen', subcategory: '', title: '测试教程书', author: '测试作者', translator: null, slug: 'test-book', chapter_count: 1 },
];

const BOOK_DETAIL = { ...BOOKS[0], chapters: [{ id: 11, book_id: 1, chapter_number: '第1章', title: '基础', order: 0, section_count: 2 }] };

const SECTIONS_11 = [
  { id: 10, chapter_id: 11, section_number: '1', title: '第一节', order: 0, figure_count: 1, has_video: true },
  { id: 20, chapter_id: 11, section_number: '2', title: '无视频节', order: 1, figure_count: 1, has_video: false },
];

const figure = (over: Record<string, unknown>) => ({
  id: 101, section_id: 10, page: 1, figure_label: '图1', book_text: null, page_context_text: null,
  bbox: null, page_image_path: 'tutorial_assets/test-book/page/page_1.jpg',
  board_payload: { size: 19, stones: { B: [[3, 3]], W: [[15, 15]] }, labels: { '3,3': '1', '15,15': '2' }, viewport: { col: 0, row: 0, cols: 8, rows: 8 } },
  recognition_debug: null, narration: null, audio_asset: null, video_asset: null,
  video_duration_ms: null, video_size_bytes: null, order: 0, updated_at: null, ...over,
});

// Section 10: figures carry a parseable slug (tutorial_assets/test-book/...) → video should be attempted.
const SECTION_10 = { ...SECTIONS_11[0], figures: [figure({})] };
// Section 20: no parseable slug (all asset paths null) → must degrade to "本节暂无视频".
const SECTION_20 = { ...SECTIONS_11[1], figures: [figure({ id: 201, section_id: 20, figure_label: '图A', page_image_path: null })] };

const VIDEO_URL = '/api/v1/tutorials/assets/tutorial_assets/test-book/video/section_10.mp4';

async function setupTutorialMocks(page: Page) {
  await page.addInitScript(() => localStorage.setItem('token', 'test-token'));
  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({ json: { id: 1, username: 'tester', email: 't@example.com' } }),
  );
  await page.route('**/api/v1/tutorials/categories', (route) => route.fulfill({ json: CATEGORIES }));
  await page.route('**/api/v1/tutorials/categories/*/books', (route) => route.fulfill({ json: BOOKS }));
  await page.route('**/api/v1/tutorials/books/*', (route) => route.fulfill({ json: BOOK_DETAIL }));
  await page.route('**/api/v1/tutorials/chapters/*/sections', (route) => route.fulfill({ json: SECTIONS_11 }));
  await page.route('**/api/v1/tutorials/sections/10', (route) => route.fulfill({ json: SECTION_10 }));
  await page.route('**/api/v1/tutorials/sections/20', (route) => route.fulfill({ json: SECTION_20 }));
  // Media gateway: 200 so nothing errors (video has preload="none" so it won't fetch anyway).
  await page.route('**/api/v1/tutorials/assets/**', (route) => route.fulfill({ status: 200, body: '' }));
}

test.describe('kiosk tutorial (read-only)', () => {
  test('browses categories → book → section, plays video, opens figure dialog', async ({ page }) => {
    await setupTutorialMocks(page);
    await page.goto('/kiosk/tutorial');

    // Category landing
    await expect(page.getByText('入门')).toBeVisible({ timeout: 10000 });
    await page.getByText('入门').click();

    // Book list
    await expect(page.getByText('测试教程书')).toBeVisible({ timeout: 10000 });
    await page.getByText('测试教程书').click();

    // Chapter / section tree
    await expect(page.getByText('基础')).toBeVisible({ timeout: 10000 });
    await page.getByText('1. 第一节').click();

    // Section study page — full breadcrumb from router state
    await expect(page.getByText('测试教程书 ▸ 基础 ▸ 1. 第一节')).toBeVisible({ timeout: 10000 });

    // Video is attempted with the slug-derived URL (NOT gated on section has_video)
    await expect(page.locator('video')).toHaveAttribute('src', VIDEO_URL);

    // Figure thumbnail → enlarge dialog with move slider (labels present → maxStep > 0)
    await page.getByText('图1').first().click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(page.locator('.MuiSlider-root')).toBeVisible();
  });

  test('degrades gracefully when no video slug can be resolved', async ({ page }) => {
    await setupTutorialMocks(page);
    await page.goto('/kiosk/tutorial/section/20');

    await expect(page.getByText('本节暂无视频')).toBeVisible({ timeout: 10000 });
    // Board diagrams still render…
    await expect(page.getByText('图A')).toBeVisible();
    // …and no <video> element is mounted.
    await expect(page.locator('video')).toHaveCount(0);
  });

  test('deep-link resolves slug from figures and shows a clean breadcrumb', async ({ page }) => {
    await setupTutorialMocks(page);
    // Direct nav: no router state. Video must still be attempted (P0-1), breadcrumb must not contain "undefined".
    await page.goto('/kiosk/tutorial/section/10');

    await expect(page.locator('video')).toHaveAttribute('src', VIDEO_URL, { timeout: 10000 });
    await expect(page.getByText('教程 ▸ 1. 第一节')).toBeVisible();
    await expect(page.getByText('undefined')).toHaveCount(0);
  });
});
