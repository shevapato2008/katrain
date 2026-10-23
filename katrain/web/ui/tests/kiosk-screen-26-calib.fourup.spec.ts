import { expect, test } from '@playwright/test';
import { resolve } from 'node:path';
import { captureFourUp, freezeClock, KIOSK_VIEWPORT, stubBackendStatics } from './helpers/fourup';

test.use({ viewport: KIOSK_VIEWPORT });

const REFERENCE = resolve(process.cwd(), '../../../docs/previews/proposed-calib-2026-10-20/calib-proposed-1024x600.png');
const OUT = resolve(process.cwd(), '../../../docs/previews/implemented-calib-2026-10-20');

// No RK3562 camera or LED is attached to this development host. The status
// response is a fixture; the rendering and routing run in the real browser.
test('1024×600 calibration screen shows readiness, lighting pause, and failure', async ({ page }) => {
  await freezeClock(page);
  await page.addInitScript(() => {
    localStorage.setItem('token', 'fourup');
    localStorage.setItem('katrain_language', 'cn');
  });
  await stubBackendStatics(page);
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    json: { id: 1, username: '访客', rank: '5段', credits: 0 },
  }));
  const disconnected = {
    phase: 'required', session_calibrated: false, last_valid: false,
    progress: { current: 0, total: 5 }, detected_anchors: [],
    capabilities: { camera_ready: false, led_ready: false, geometry_ready: false, recognition_ready: false },
  };
  let status: Record<string, unknown> = disconnected;
  await page.route('**/api/v1/geometry/status', (route) => route.fulfill({ json: status }));
  await page.route('**/api/v1/geometry/snapshot*', (route) => route.fulfill({
    status: 503, json: { detail: 'camera_frame_not_available' },
  }));

  await page.goto('/kiosk/vision/setup');
  await expect(page.getByTestId('calib-pagebar').getByRole('button', { name: '返回设置' })).toBeVisible();
  await expect(page.getByTestId('calib-step')).toHaveCount(4);
  await expect(page.getByTestId('calib-cap')).toContainText('共 5 个定位点');
  await expect(page.getByTestId('calib-pagebar')).not.toContainText('13 个定位点');
  await expect(page.getByRole('button', { name: '重新开始标定 · 设备未连接' })).toBeDisabled();
  await page.getByRole('button', { name: '标定说明' }).click();
  await expect(page.getByRole('dialog')).toContainText('四角和天元共 5 个定位点');
  await page.getByRole('dialog').getByRole('button', { name: '知道了' }).click();
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());

  await captureFourUp({
    page,
    referencePng: REFERENCE,
    outDir: OUT,
    slug: '26-calib',
    localReference: true,
    referenceCaption: '参考：已确认的 #calib 设计稿，1024×600，设备未连接。',
    implementationCaption: '实现：真实 kiosk 页面与路由；摄像头和 LED 未连接状态由 API fixture 提供。',
  });

  const detected = Array.from({ length: 3 }, (_, i) => ({ row: i, col: i, x: 160 + i * 70, y: 140 + i * 50, color: 'green' }));
  status = {
    ...disconnected, phase: 'lighting_paused', pause_reason: 'frame_overexposed',
    progress: { current: 3, total: 5 }, detected_anchors: detected,
    capabilities: { camera_ready: true, led_ready: true, geometry_ready: false, recognition_ready: false },
  };
  await page.reload();
  await expect(page.getByRole('dialog')).toContainText('画面过亮');
  await expect(page.getByRole('dialog')).toContainText('已完成的 3 个点会保留');
  await page.screenshot({ path: resolve(OUT, '26-calib--lighting-paused.png'), animations: 'disabled' });

  status = { ...status, phase: 'failed', stopped_phase: 'verifying', error: 'anchor_not_found:9,9' };
  await page.reload();
  await expect(page.getByTestId('geometry-diagnostic-card')).toContainText('没找到 K10 这个点的灯');
  await expect(page.getByTestId('calib-cap')).toContainText('停在第 3 步');
  await page.screenshot({ path: resolve(OUT, '26-calib--failed.png'), animations: 'disabled' });
});
