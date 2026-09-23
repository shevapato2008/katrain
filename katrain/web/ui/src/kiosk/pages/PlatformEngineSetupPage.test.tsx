import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import PlatformEngineSetupPage from './PlatformEngineSetupPage';

/**
 * 屏 09 跨平台 · 人机开局的**行为**那一半。版式归
 * `tests/kiosk-screen-07-09-platform.fourup.spec.ts`(眼睛)和
 * `tests/kiosk-shell-scroll.spec.ts`(机器量),这里一条几何都不断言。
 *
 * ⚠️ 上一版这里有一条 `expect(getComputedStyle(panel).overflowY).not.toBe('auto')` ——
 * **删了**:它断的是布局结论,而 jsdom 没有布局引擎;而且这一屏改完之后右栏**本来就要滚**,
 * 那条断言连意图都反了。它换成的是真浏览器里那条
 * 「装不下时右栏自己滚,而『开始对局』怎么滚都还在」。
 *
 * 这里断言的五件事,每一件挂了都是一个产品缺陷:
 *   ① 对手只有**步进器一个**控件 —— 稿子那段 39 行名单按 2026-08-24 的裁定不做,
 *      理由在页面头注(一屏一种选择手势 / 屏 02 的 29 档已按同一条判过 / 摊开后 6.6 屏)。
 *   ② 档数、位次、展示 Elo、对标棋力**全部来自下发那份名单**,一个字面量都不许写死 ——
 *      名单撤掉之后「39」只剩步进器一处在说,写死了没有第二处会露馅。
 *   ③ 两头禁用**不回绕**:第 1 档再按「弱一档」不许绕到第 39 档。
 *   ④ **贴目跟着让子算**,不是另一个可选项。
 *   ⑤ 拉不到棋力档时**不给兜底表**:编出来的档次会让人选中星阵不认识的那一个。
 */

const { platformEngineLevels, platformEngineStart } = vi.hoisted(() => ({
  platformEngineLevels: vi.fn(),
  platformEngineStart: vi.fn(),
}));
vi.mock('../../api', () => ({ API: { platformEngineLevels, platformEngineStart } }));
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ token: 'tok', user: { id: 1, username: 'u' }, isAuthenticated: true }),
}));
// 默认没标定摄像头 —— 和这个 mock 之前的静态值一致。R-08 的两次渲染对比测试
// 把它改成 `true` 来看差异,别的用例都吃这个默认值。
let mockIsVisionEnabled = false;
vi.mock('../context/VisionContext', () => ({
  useVision: () => ({ visionStatus: { enabled: mockIsVisionEnabled }, isVisionEnabled: mockIsVisionEnabled, refreshStatus: vi.fn() }),
}));
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const LEVELS = Array.from({ length: 39 }, (_, i) => ({
  elo_score: 100 + i * 10,
  level_name: `第 ${i + 1} 档`,
  name: `星阵 ${i + 1}`,
  goal_difference: 0,
  timing: '',
  display_elo: 400 + i * 50,
  ref_rank: `业余 ${i + 1}`,
}));

const renderPage = () => render(
  <ThemeProvider theme={kioskTheme}>
    <MemoryRouter initialEntries={['/kiosk/play/cross-platform/engine/golaxy']}>
      <Routes>
        <Route path="/kiosk/play/cross-platform/engine/:platform" element={<PlatformEngineSetupPage />} />
      </Routes>
    </MemoryRouter>
  </ThemeProvider>,
);

/** 对手名牌 —— 读数搬到这里之后,「星阵 1 · 第 1 档」「第 1 / 39 档 · 展示 Elo … · 对标…」都在它身上。 */
const plate = () => screen.getByTestId('setup-opponent-plate');
/** 对手组标题右端(「星阵下发 39 档」)。 */
const opponentSecval = () => screen.getByTestId('setup-opponent').querySelector('.secval')!;
/** 让子 · 我执组标题右端(「让 2 子 · 黑贴 2 目」这类算出来的结果)。 */
const handicapSecval = () => screen.getByTestId('setup-handicap-side').querySelector('.secval')!;
/** 棋力档拉回来了 = 这一屏的控件全部就绪。 */
const ready = () => waitFor(() => expect(plate()).toHaveTextContent('第 1 档'));

beforeEach(() => {
  vi.clearAllMocks();
  mockIsVisionEnabled = false;
  platformEngineLevels.mockResolvedValue({ levels: LEVELS });
  platformEngineStart.mockResolvedValue({ session_id: 's1' });
});

describe('屏 09 跨平台 · 人机开局', () => {
  it('对手只有名牌 + 轨两个控件 —— 稿子那段 39 行名单不做', async () => {
    renderPage();
    await ready();
    expect(screen.queryAllByTestId('setup-level-row')).toHaveLength(0);
    expect(screen.getByTestId('setup-opponent').querySelectorAll('.kiosk-row')).toHaveLength(0);
    expect(plate()).toHaveTextContent('星阵 1 · 第 1 档');
  });

  it('按 ＋ 走一档,名牌上的读数跟着走;停在第 1 档时「弱一档」禁用,不回绕', async () => {
    renderPage();
    await ready();
    const weaker = screen.getByRole('button', { name: '换弱一档的对手' });
    expect(weaker, '停在第 1 档「弱一档」还能按 —— 一次误触会绕到第 39 档').toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: '换强一档的对手' }));
    expect(plate()).toHaveTextContent('星阵 2 · 第 2 档');
    expect(weaker).toBeEnabled();
  });

  /**
   * **反写死变异**:名单只有 5 条时屏上必须写「5 档」「第 n / 5 档」。
   * 名单那一段撤掉之后,「39」这个数只剩组标题 + 名牌两处在说 —— 写死它有一处会露馅。
   */
  it('档数来自下发那份名单,不是写死的 39', async () => {
    platformEngineLevels.mockResolvedValue({ levels: LEVELS.slice(0, 5) });
    renderPage();
    await ready();
    expect(opponentSecval()).toHaveTextContent('星阵围棋下发 5 档');
    expect(plate()).toHaveTextContent('第 1 / 5 档');
  });

  // `ref_rank` 是那份名单里唯一不在轨上的一列(顶上六档是「野狐 9D」「职业 / 野狐 9D+」)。
  // 名单不做了,它必须搬进名牌 —— 掉了就是掉事实。
  it('名牌带上展示 Elo 和「对标棋力」—— 名单撤了,那一列得有落点', async () => {
    renderPage();
    await ready();
    expect(plate()).toHaveTextContent('展示 Elo 400');
    expect(plate()).toHaveTextContent('对标业余 1');
  });

  it('贴目跟着让子算 —— 分先 7.5,让先不贴,让 2 子贴 2 子(写在组标题上,不再单占一段)', async () => {
    renderPage();
    await ready();
    expect(handicapSecval()).toHaveTextContent('分先 · 黑贴 7.5 目');

    const more = screen.getByRole('button', { name: '多让一子' });
    await userEvent.click(more);
    expect(handicapSecval()).toHaveTextContent('让先 · 不贴目');
    await userEvent.click(more);
    expect(handicapSecval()).toHaveTextContent('让 2 子 · 黑贴 2 子');
  });

  it('「开始对局」发的是当下这三项', async () => {
    renderPage();
    await ready();
    await userEvent.click(screen.getByRole('button', { name: '换强一档的对手' }));
    await userEvent.click(screen.getByRole('button', { name: '多让一子' }));
    await userEvent.click(screen.getByTestId('platform-engine-start'));
    await waitFor(() => expect(platformEngineStart).toHaveBeenCalledWith(
      'golaxy', { level: 110, human_color: 'nigiri', handicap: -1 }, 'tok',
    ));
    await waitFor(() => expect(mockNavigate)
      .toHaveBeenCalledWith('/kiosk/play/cross-platform/engine/game/s1', { state: { backTo: '/kiosk/play/cross-platform/engine/golaxy' } }));
  });

  it('我执三段:猜先 / 执黑 / 执白,选了执白就写进 payload', async () => {
    renderPage();
    await ready();
    const seg = screen.getByTestId('setup-side-seg');
    ['猜先', '执黑', '执白'].forEach((label) => {
      expect(within(seg).getByRole('button', { name: label })).toBeInTheDocument();
    });
    expect(within(seg).getByRole('button', { name: '猜先' })).toHaveAttribute('aria-pressed', 'true');
    await userEvent.click(within(seg).getByRole('button', { name: '执白' }));
    await userEvent.click(screen.getByTestId('platform-engine-start'));
    await waitFor(() => expect(platformEngineStart).toHaveBeenCalledWith(
      'golaxy', { level: 100, human_color: 'W', handicap: 0 }, 'tok',
    ));
  });

  it('返回键回跨平台连接页', async () => {
    renderPage();
    await ready();
    await userEvent.click(screen.getByRole('button', { name: /跨平台/ }));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/play/cross-platform');
  });

  it('拉不到棋力档:说出来,**不给兜底表**,也开不了局', async () => {
    platformEngineLevels.mockRejectedValue(new Error('golaxy 没回话'));
    renderPage();
    await screen.findByText('golaxy 没回话');
    expect(screen.getByTestId('setup-opponent').querySelector('.catpick'), '拉不到档还画着步进器')
      .toBeNull();
    expect(screen.getByTestId('platform-engine-start')).toBeDisabled();
  });

  it('路数不是控件 —— 星阵只开 19 路,屏上没有任何棋盘尺寸按钮', async () => {
    renderPage();
    await ready();
    expect(screen.queryByRole('button', { name: /路/ })).not.toBeInTheDocument();
  });

  // 这一屏之前**没有**这颗开关(屏 02/03/04 早就接了)——
  // 于是同一台盒子上自由对弈选得了屏幕、跨平台却选不了。
  it('「怎么落子」那颗开关在;没标定摄像头时「实体盘」灰掉并说明原因', async () => {
    renderPage();
    await ready();
    const seg = screen.getByTestId('setup-input');
    expect(within(seg).getByRole('button', { name: '屏幕' })).toBeEnabled();
    expect(within(seg).getByRole('button', { name: '实体盘' })).toBeDisabled();
    expect(screen.getByText(/还没标定摄像头/)).toBeInTheDocument();
  });

  // Review Focus #1:平台一档都没下发。
  it('平台一档都没下发时,开始键按不下去,也不画名牌', async () => {
    platformEngineLevels.mockResolvedValue({ levels: [] });
    renderPage();
    await screen.findByTestId('platform-engine-start');
    expect(screen.getByTestId('platform-engine-start')).toBeDisabled();
    expect(screen.queryByTestId('setup-opponent-plate')).toBeNull();
  });

  /**
   * R-08:brief 原 Step 11 要求「面板开着时派一个视觉事件,断言轨够不着」——
   * 不写。理由两条:① 这份 mock 把 `useVision` 做成静态返回值,没有事件总线可派事件;
   * ② 就算写了也不可能失败 —— 面板是同一棵 React 树里的子节点,「开着的面板吞掉一次
   * state 更新」在 React 里没有对应机制。面板盖没盖住轨是**布局**问题,归 Task 4 的
   * 真浏览器几何闸,不归这里。
   *
   * 这里改测**真实为真的行为**:摄像头能不能用,决定「实体盘」这一档选不选得了、
   * 提示行说的是哪一句 —— 这是屏 09 曾经真出过的缺陷(上线时压根没有「怎么落子」
   * 这颗开关),提示行是它唯一诚实的降级路径。
   */
  it('摄像头能不能用,决定「实体盘」选不选得了、提示行说哪一句', async () => {
    mockIsVisionEnabled = true;
    const available = renderPage();
    await waitFor(() => expect(within(available.getByTestId('setup-opponent-plate')).getByText(/第 1 档/)).toBeInTheDocument());
    expect(within(available.getByTestId('setup-input')).getByRole('button', { name: '实体盘' })).toBeEnabled();
    expect(available.getByTestId('setup-input-hint')).toHaveTextContent('屏幕和实体盘走同一条隧道');
    available.unmount();

    mockIsVisionEnabled = false;
    const unavailable = renderPage();
    await waitFor(() => expect(within(unavailable.getByTestId('setup-opponent-plate')).getByText(/第 1 档/)).toBeInTheDocument());
    expect(within(unavailable.getByTestId('setup-input')).getByRole('button', { name: '实体盘' })).toBeDisabled();
    expect(unavailable.getByTestId('setup-input-hint')).toHaveTextContent('还没标定摄像头');
  });
});
