import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import type { GeometryStatus } from '../../api/geometryApi';
import { GeometryAPI } from '../../api/geometryApi';
import { kioskTheme } from '../theme';
import GeometryCalibrationScreen from '../components/vision/GeometryCalibrationScreen';

/**
 * 屏 26 棋盘标定。**2026-08-24 整份换口径**(文件也跟着组件从 `…Workspace` 改名)。
 *
 * 上一版 7 条断言的是 `phaseTitle` / `phaseHint` 那两块大字和一排 MUI Chip;
 * 这一轮它们**换成了四步清单 + 三格状态**(同一份信息,分辨率更高)。
 * 每一条的**被测意图都还在**,只是问法换了 —— 逐条在注释里点名换的是哪一句。
 *
 * 布局事实一律不在这儿断言(jsdom 没有布局引擎):
 * 「右栏 460 摆不摆得下」「中段会不会滚」归 `tests/kiosk-shell-geometry.spec.ts`。
 */

const startCalibration = vi.fn();
const cancelCalibration = vi.fn();
const confirmExisting = vi.fn();
let status: GeometryStatus;
let loaded = true;

vi.mock('../context/GeometryContext', () => ({
  useGeometry: () => ({ status, loaded, startCalibration, cancelCalibration, confirmExisting, refresh: vi.fn() }),
}));

vi.mock('../../api/geometryApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/geometryApi')>();
  return { ...actual, GeometryAPI: { ...actual.GeometryAPI, layout: vi.fn() } };
});

const renderScreen = () => render(
  <ThemeProvider theme={kioskTheme}>
    <MemoryRouter>
      <GeometryCalibrationScreen
        backLabel="设置" onBack={vi.fn()}
        title="棋盘标定" sub="先把棋盘清空 · 四角 + 九星共 13 个定位点"
      />
    </MemoryRouter>
  </ThemeProvider>,
);

const steps = () => screen.getAllByTestId('calib-step');
const acts = () => screen.getByTestId('calib-actions');
const cells = () => Array.from(document.querySelectorAll('.kiosk-status__cell'))
  .map((c) => c.textContent ?? '');

describe('屏 26 棋盘标定', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    loaded = true;
    status = {
      phase: 'required', session_calibrated: false, last_valid: false,
      capabilities: { camera_ready: true, led_ready: true, geometry_ready: false },
    };
    vi.mocked(GeometryAPI.layout).mockRejectedValue(new Error('geometry request failed 409'));
  });

  // ── 四步,不是五步 ─────────────────────────────────────────────────────────

  /**
   * 🔴 稿子画五步,第 2 步「采集熄灯参考帧」对应 `dark_reference` ——
   * **全仓没有任何地方写入这个 phase**(只在两处「哪些算进行中」的常量集合里当摆设)。
   * 那件事确实在做,但是**每个锚点各一次、13+ 次**,不是一个有头有尾的阶段。
   * 画成一行只能在两种假话里挑一种,所以删掉、机制写进第 2 步副行。
   */
  it('四步不是五步,而且没有「采集熄灯参考帧」这一行', () => {
    renderScreen();
    expect(steps()).toHaveLength(4);
    expect(steps().map((s) => s.querySelector('.kiosk-row__t b')?.textContent)).toEqual([
      '准备空盘标定', '定位棋盘四角', '定位九个星位', '生成空盘基线',
    ]);
    expect(screen.queryByText(/采集熄灯参考帧/)).toBeNull();
    // 那件事没被吞掉 —— 它写在旁注里(放行里会折成两行、把 52 高的行顶破,四图上量到过)
    expect(screen.getByTestId('geometry-led-advisory').closest('p'))
      .toHaveTextContent('先熄灯拍一张、亮灯再拍一张');
  });

  it('没在跑的时候第 1 步是「进行中」—— 清空棋盘本来就是按下之前要做的', () => {
    renderScreen();
    expect(steps()[0]).toHaveAttribute('data-state', 'now');
    expect(steps()[1]).toHaveAttribute('data-state', 'todo');
  });

  it('跑到星位时:前两步完成、第 3 步在跑,而且说得出正在点第几个', () => {
    status = {
      ...status, phase: 'verifying',
      progress: { current: 7, total: 13 },
      detected_anchors: Array.from({ length: 7 }, (_, i) => ({ row: i, col: i, x: 0, y: 0, color: 'green' })),
    };
    renderScreen();
    expect(steps().map((s) => s.getAttribute('data-state'))).toEqual(['done', 'done', 'now', 'todo']);
    expect(steps()[2]).toHaveTextContent('正在点第 4 个'); // 7 − 4 + 1
  });

  /**
   * 🔴 断在哪一步**由 `detected_anchors` 的长度判,不靠错误串** ——
   * 错误串只说明最后一下出了什么问题,它反推不出前面走了多远。
   */
  it('失败:断点由已定位的锚点数决定,之前的步骤保持「完成」', () => {
    status = {
      ...status, phase: 'failed', error: 'anchor_not_found:3,15',
      detected_anchors: Array.from({ length: 6 }, (_, i) => ({ row: i, col: i, x: 0, y: 0, color: 'green' })),
    };
    renderScreen();
    // 6 个 ⇒ 四角过了、断在星位那一步
    expect(steps().map((s) => s.getAttribute('data-state'))).toEqual(['done', 'done', 'bad', 'todo']);
  });

  // ── 诊断,不是「重试」 ─────────────────────────────────────────────────────

  /** 上一版这条测的是同一张卡,`data-testid` 一字未改。 */
  it('失败给的是点名到具体点位的诊断,不是一颗光秃秃的重试键', () => {
    status = { ...status, phase: 'failed', error: 'anchor_not_found:3,15' };
    renderScreen();
    const card = screen.getByTestId('geometry-diagnostic-card');
    expect(card).toHaveTextContent('没找到 Q16 这个点的灯');
    expect(card).toHaveTextContent('压着一颗子');
    // 屏上不许出现一颗只写「重试」的键
    expect(screen.queryByRole('button', { name: '重试' })).toBeNull();
    // 而那句「失败时给诊断不给重试」的预告在诊断真在场时会自我指涉 ⇒ 不再说
    expect(screen.queryByText(/失败时给/)).toBeNull();
  });

  it('几何失效(degraded)走同一张诊断卡,不另开一种形状', () => {
    status = { ...status, phase: 'degraded' };
    renderScreen();
    expect(screen.getByTestId('geometry-diagnostic-card')).toHaveTextContent('棋盘和上次标定的位置对不上了');
  });

  /** LED 那条硬规矩**永远在**,不因为屏上正在发生什么而消失。 */
  it('LED 只在按下之后才亮 —— 这句话在任何状态下都在', () => {
    renderScreen();
    expect(screen.getByTestId('geometry-led-advisory')).toHaveTextContent('不会自动点亮 LED');
    status = { ...status, phase: 'failed', error: 'x' };
    renderScreen();
    expect(screen.getAllByTestId('geometry-led-advisory')[1]).toHaveTextContent('不会自动点亮 LED');
  });

  // ── 三格状态 ───────────────────────────────────────────────────────────────

  /**
   * 🔴 `DEFAULT_STATUS` 的三个 capability 全是 `false` —— 还没问过服务端就画,
   * 会在「还没读到」的时候说「未连接」。**还没读到 ≠ 读到了没连上**(G8)。
   */
  it('还没读到状态时三格全是「—」,不说「未连接」', () => {
    loaded = false;
    status = { ...status, capabilities: { camera_ready: false, led_ready: false, geometry_ready: false } };
    renderScreen();
    expect(cells()).toEqual(['摄像头—', '标定—', 'LED—']);
    expect(screen.queryByText('未连接')).toBeNull();
  });

  it('读到了才说连没连上', () => {
    status = { ...status, capabilities: { camera_ready: true, led_ready: false, geometry_ready: false } };
    renderScreen();
    expect(cells()[0]).toContain('已连接');
    expect(cells()[2]).toContain('未连接');
  });

  // ── 标定质量:不许把「不知道」画成「满分」 ─────────────────────────────────

  /**
   * 🔴 上一版是 `metrics.inlier_count ?? 13` / `rms_residual ?? 0` ——
   * **后端没给这个数的时候它编一个满分出来**(13/13、0.000 px 读起来就是「完美」)。
   * 规范 §14:值写「—」不写 0。
   */
  it('后端整个没给 metrics:说「没拿到残差数据」,不编一个 13/13 出来', () => {
    status = { ...status, phase: 'ready', session_calibrated: true, last_valid: true };
    renderScreen();
    expect(steps()[3]).toHaveTextContent('没拿到这次的残差数据');
    expect(steps()[3]).not.toHaveTextContent('13 / 13');
    expect(steps()[3]).toHaveAttribute('data-state', 'plain'); // 中性,不是 done —— 不知道不是满分
  });

  it('给了 metrics 但字段是空的:逐项写「—」,一样不敢标绿', () => {
    status = {
      ...status, phase: 'ready', session_calibrated: true, last_valid: true,
      metrics: {} as Record<string, never>,
    };
    renderScreen();
    expect(steps()[3]).toHaveTextContent('— / 13 点 · RMS — px · 最大残差 — px');
    expect(steps()[3]).toHaveAttribute('data-state', 'plain');
  });

  it('拿到真数就写真数;不足 13 点时 tag 转琥珀并把数写出来', () => {
    status = {
      ...status, phase: 'ready', session_calibrated: true, last_valid: true,
      metrics: { inlier_count: 9, rms_residual: 0.4213, max_residual: 0.9077 },
    };
    renderScreen();
    expect(steps()[3]).toHaveTextContent('9 / 13 点 · RMS 0.421 px · 最大残差 0.908 px');
    expect(steps()[3]).toHaveAttribute('data-state', 'warn');
    expect(within(steps()[3]).getByText('完成 · 9 / 13')).toBeInTheDocument();
  });

  // ── 两颗键 ─────────────────────────────────────────────────────────────────

  it('从没标定过:不摆那颗永远按不亮的「沿用上次标定」,主行动独占一行', () => {
    renderScreen();
    expect(within(acts()).queryByRole('button', { name: '沿用上次标定' })).toBeNull();
    expect(within(acts()).getAllByRole('button')).toHaveLength(1);
  });

  it('有上一次可沿用:两颗都在,按下去走 confirmExisting', async () => {
    status = { ...status, last_valid: true };
    renderScreen();
    fireEvent.click(within(acts()).getByRole('button', { name: '沿用上次标定' }));
    await waitFor(() => expect(confirmExisting).toHaveBeenCalled());
  });

  /**
   * 🔴 运行中稿子那两颗键**一颗都不成立**:「沿用上次标定」服务端会 `ValueError`,
   * 「重新开始标定」会撞 409。而一次标定是分钟级的 —— 没有退出路径 = 卡死。
   */
  it('运行中整行只有一颗「取消标定」', () => {
    status = { ...status, phase: 'flashing_corners', last_valid: true };
    renderScreen();
    const buttons = within(acts()).getAllByRole('button');
    expect(buttons).toHaveLength(1);
    expect(buttons[0]).toHaveTextContent('取消标定');
    fireEvent.click(buttons[0]);
    expect(cancelCalibration).toHaveBeenCalled();
  });

  it('摄像头或 LED 掉线时按不了开始 —— 这条上一版就有,口径没变', () => {
    status = { ...status, capabilities: { camera_ready: false, led_ready: true, geometry_ready: false } };
    renderScreen();
    expect(within(acts()).getByRole('button', { name: '重新开始标定' })).toBeDisabled();
  });

  /** 标定好了要按两次:第一次是「我真的要作废现在这份」。上一版就有这条。 */
  it('已标定时重来要按两次,第一次只是改文案不发请求', async () => {
    status = { ...status, phase: 'ready', session_calibrated: true, last_valid: true };
    renderScreen();
    fireEvent.click(within(acts()).getByRole('button', { name: '重新标定棋盘' }));
    expect(startCalibration).not.toHaveBeenCalled();
    fireEvent.click(within(acts()).getByRole('button', { name: '已清空，确认重新标定' }));
    await waitFor(() => expect(startCalibration).toHaveBeenCalledWith('manual'));
  });

  it('第一次标定发的是 auto,不是 manual —— 这是既有行为,重画不该顺手改掉', async () => {
    renderScreen();
    fireEvent.click(within(acts()).getByRole('button', { name: '重新开始标定' }));
    await waitFor(() => expect(startCalibration).toHaveBeenCalledWith('auto'));
  });

  // ── 摄像头画面底下那条 ─────────────────────────────────────────────────────

  it('画面底下那条两个数都算得出来,不估', () => {
    status = {
      ...status, phase: 'verifying',
      detected_anchors: Array.from({ length: 12 }, (_, i) => ({ row: i, col: i, x: 0, y: 0, color: 'green' })),
    };
    renderScreen();
    const cap = screen.getByTestId('calib-cap');
    expect(cap).toHaveTextContent('四角已定位 · 九星 8 / 9');
    expect(cap).toHaveTextContent('第 3 / 4 步');
  });

  // ── 没有摄像头的盒子 ───────────────────────────────────────────────────────

  /**
   * 🔴 `/status` 404 ⇒ `disabled`。那台机器上 `/geometry/stream` 会 404、`/calibrate` 会 404、
   * 四步一步都不会走 —— **把这些控件摆出来全是假的**。但返回键必须在。
   */
  it('没配摄像头的盒子:整块换成一句实话,不摆一屏按不动的控件', () => {
    status = { ...status, phase: 'disabled' };
    renderScreen();
    expect(screen.getByTestId('calib-disabled')).toHaveTextContent('这台盒子没有配摄像头');
    expect(screen.queryByTestId('calib-steps')).toBeNull();
    expect(screen.queryByTestId('calib-actions')).toBeNull();
    // 返回**必须**还在:L2 无 Dock、顶栏不带返回,没有它这一屏就是死角
    expect(screen.getByRole('button', { name: /设置/ })).toBeInTheDocument();
  });

  // ── 视图切换 ───────────────────────────────────────────────────────────────

  it('两段常驻都能按,顺序照稿子;没标定时切过去那块自己说人话', () => {
    renderScreen();
    const bar = screen.getByTestId('calib-pagebar');
    const segs = within(bar).getAllByRole('radio');
    expect(segs.map((s) => s.textContent)).toEqual(['原始画面', '俯视矫正']);
    fireEvent.click(segs[1]);
    expect(screen.getByText('完成 LED 标定后生成俯视画面')).toBeInTheDocument();
  });

  it('运行中切到俯视:说的是「完成后重新生成」,不播上一次那份正在被作废的几何', () => {
    status = { ...status, phase: 'flashing_corners', last_valid: true };
    renderScreen();
    fireEvent.click(within(screen.getByTestId('calib-pagebar')).getAllByRole('radio')[1]);
    expect(screen.getByText('标定进行中，俯视画面在完成后重新生成')).toBeInTheDocument();
  });
});
