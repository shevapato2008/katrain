import { test } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });
test.describe.configure({ mode: 'serial' });   // 合成要读刚写出的 PNG,而 config 是 fullyParallel

const SHOTS = resolve(process.cwd(),
  '../../../../smartbox-software/superpowers/shared/kiosk-shell/sample-go/shots');
const OUT = resolve(process.cwd(),
  '../../../superpowers/tracks/kiosk-go-shell-align/visual/23-courses/1024x600');

/**
 * 屏 23 课程(L1 布局 A,形态 1 整栏滚)。
 *
 * ⚠️ **稿子这一屏自己是不自洽的**,所以没有哪一份数据能和它逐像素对上:
 * 它同时画着「三张分类卡」和「现在能练的」,而**那两块按定义不共存** ——
 * 环里写「—」说明这台盒子还没跟云端对过账,可三张卡又说分类拿到了。
 * 稿子自己的注释解释了这一点:那三张卡是**形状不是清单**。
 *
 * 这份对照取的是**有课的那一面**(三个分类从接口来),因为那是盒子上的常态;
 * 于是「现在能练的」按计划的裁定**不渲染** —— 有课的时候它就成了一排永远在的杂物。
 * 另一面(一类都没有 ⇒ 空态 + 现在能练的)由单测两个方向各钉一条。
 *
 * 其余预期差异:
 *  ① 组标题右端稿子写「每类几本，由接口返回」——那是说给读稿人听的,而那一格按规范放**数据**。
 *  ② 左栏那块盘稿子画了几颗示意子,实现照旧是压暗的空盘 —— 那一栏是实体盘镜像,
 *    摆一盘不是这一局的子就是拿装饰冒充状态(D11)。同步行那句话已经把意思说清楚了。
 */

const CATEGORIES = [
  { slug: 'basics', title: '入门', summary: '规则与吃子', order: 1, book_count: 4 },
  { slug: 'shape', title: '基本功', summary: '死活 · 手筋', order: 2, book_count: 7 },
  { slug: 'fuseki', title: '布局与定式', summary: '开局怎么走', order: 3, book_count: 2 },
];

test('四图:课程 ←→ sample-go/shots/23-courses.png', async ({ page }) => {
  await freezeClock(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'fourup');
    localStorage.setItem('katrain_language', 'cn');
  });
  await stubBackendStatics(page);
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, username: '访客', rank: '5段', credits: 0 },
  }));
  await page.route('**/api/v1/tutorials/categories', (route) => route.fulfill({ json: CATEGORIES }));

  await page.goto('/kiosk/tutorial');
  await page.waitForSelector('[data-testid="tutorial-categories"] .kiosk-card:nth-child(3)');
  await page.waitForLoadState('networkidle');

  const r = await captureFourUp({
    page,
    referencePng: resolve(SHOTS, '23-courses.png'),
    outDir: OUT,
    slug: '23-courses',
    referenceCaption:
      '参考:sample-go/shots/23-courses.png · L1 布局 A(镜像栏 296 + 16 + 右栏 680,整栏滚)· '
      + '左栏和对弈屏逐像素相同,差别只在同步行那句话',
    implementationCaption:
      '实现:/kiosk/tutorial @1024×600 · 时钟冻 16:40 · 三个分类是 fixture,**名字和本数全从接口来** · '
      + '**「现在能练的」这一组不在**:计划裁定它只在一类都没有的时候出现 —— 有课的时候它就成了一排'
      + '永远在的杂物;稿子把它和三张分类卡画在一起,而那两块按定义不共存(环里的「—」说明还没对过账)· '
      + '环恒是「—」:接口只给本数不给进度,拿本数画进度环会画出一条读不懂的弧;本数写在副标和组标题右端 · '
      + '组标题右端写真数「3 类 · 共 13 本」,不是稿子那句「由接口返回」 · '
      + '左栏是压暗的空盘不是示意子(D11:实体盘镜像里摆装饰=拿装饰冒充状态)· '
      + 'Dock 七项(2026-08-25 起补了「成长」,围棋独有)',
  });
  console.log(`[fourup 23-courses] both=${r.both} refOnly=${r.refOnly} implOnly=${r.implOnly}`);
});
