import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import SettingsPage from '../pages/SettingsPage';
import { readAudioPref } from '../../utils/audioPrefs';

// B6: SettingsPage pulls in useSettings/useAuth/useGeometry (via AccountSection +
// PhysicalBoardStatus). Mock each context module directly — same idiom as
// src/kiosk/__tests__/KioskAuth.test.tsx (AuthContext) and
// src/kiosk/__tests__/PhysicalBoardStatus.test.tsx (GeometryContext) — rather
// than mounting the real providers, which would require faking network calls
// (SettingsProvider's i18n.loadTranslations, GeometryProvider's status poll).
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => ({
  ...(await importOriginal<typeof import('react-router-dom')>()),
  useNavigate: () => mockNavigate,
}));

const mockSetLanguage = vi.fn();
vi.mock('../../context/SettingsContext', () => ({
  useSettings: () => ({
    language: 'cn',
    setLanguage: mockSetLanguage,
    // Shares galaxy's full catalog; a small subset is enough to exercise the Select.
    languages: [
      { code: 'en', name: 'English' },
      { code: 'cn', name: '中文' },
      { code: 'jp', name: '日本語' },
    ],
  }),
}));

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 1, username: '张三', rank: '2D', credits: 0 },
    isAuthenticated: true,
    login: vi.fn(),
    logout: vi.fn(),
    token: 'mock-token',
  }),
}));

vi.mock('../context/GeometryContext', () => ({
  useGeometry: () => ({
    status: {
      phase: 'required',
      session_calibrated: false,
      last_valid: false,
      capabilities: { camera_ready: false, led_ready: false, geometry_ready: false },
    },
  }),
}));

const renderPage = () =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>
    </ThemeProvider>
  );

/**
 * 屏 27 设置(L1-B)。
 *
 * ⚠️ **上一版那六条「从 location.state.from 退回去」的用例删了。** 它们测的是**死码**:
 * 全仓只有 Dock 会跳到这一屏,而 Dock 不带 `state`。设置是 Dock 项 ⇒ L1 ⇒ **没有返回键**
 * (要退的是「回哪儿」,而 Dock 一直在)。那条页控条是它还是 L2 时留下的。
 *
 * ⚠️ 几何不在这儿断言:左栏 296、导航项高 44、整栏滚、高亮跟着滚动走,
 * 判据在 `tests/kiosk-shell-geometry.spec.ts` 和 `kiosk-shell-scroll.spec.ts`(真浏览器量)。
 */
describe('屏 27 设置 · 分组与导航', () => {
  beforeEach(() => vi.clearAllMocks());

  // **导航项数 = 分组数,且词一一对应** —— 两套词等于两套心智模型。
  it('导航五项,和右边五组的标题一个字不差', () => {
    renderPage();
    const nav = screen.getByTestId('settings-nav');
    const labels = [...nav.querySelectorAll('button')].map((b) => b.textContent);
    expect(labels).toEqual(['账号与平台', '实体棋盘', '落子与提示', '声音', '语言']);

    const groups = [...document.querySelectorAll('[data-group]')].map(
      (g) => g.querySelector('.kiosk-seclabel h2')?.textContent,
    );
    expect(groups).toEqual(labels);
  });

  // 稿子摆了七组,这台盒子上五组没有内容。**只做有内容的**(计划 D10 方案 a):
  // 挂「未接后端」是用错标 —— 那五组大部分不是「后端没有」,是「这个设置项还没做」。
  it('没有内容的那几组一个都不摆,也不挂「未接后端」', () => {
    renderPage();
    for (const absent of ['棋盘外观', '对局默认值', '关于']) {
      expect(screen.queryByText(absent)).toBeNull();
    }
    // 「声音」这一组 2026-08-26 补上了 —— 它**有内容**:落子音效和实体盘引导语一直在响,
    // 而这台盒子上原来一个关掉它们的地方都没有。
    // 但屏上写的是「声音」不是稿子那句「声音与报着」:**盒子不报着**(`useVoice` 说的是
    // 摆子引导那七句,不是手数)。多写两个字就是承诺一个不存在的功能。
    expect(screen.queryByText('声音与报着')).toBeNull();
    expect(screen.queryByText(/未接后端/)).toBeNull();
    expect(screen.queryByText(/即将上线/)).toBeNull();
  });

  it('一开始高亮在第一项', () => {
    renderPage();
    const nav = screen.getByTestId('settings-nav');
    const current = [...nav.querySelectorAll('button')].filter((b) => b.getAttribute('aria-current') === 'true');
    expect(current).toHaveLength(1);
    expect(current[0].textContent).toBe('账号与平台');
  });

  // 设置是 Dock 项 ⇒ L1 ⇒ 没有返回键。
  it('没有页控条、没有返回键', () => {
    renderPage();
    expect(document.querySelector('.kiosk-pagebar')).toBeNull();
    expect(screen.queryByRole('button', { name: '返回' })).toBeNull();
  });
});

describe('屏 27 设置 · 每一组的内容都是真的', () => {
  beforeEach(() => vi.clearAllMocks());

  // 上一版那四张平台卡是 `pointer-events:none` 的死装饰,而且列的是
  // 99围棋/野狐/腾讯/新浪 —— **和真正能连的三家对不上**。
  it('平台那一行念的是真能连的三家,并且点得动', () => {
    renderPage();
    expect(screen.getByText(/OGS · 野狐围棋 · 星阵围棋/)).toBeInTheDocument();
    expect(screen.queryByText(/99围棋/)).toBeNull();
    expect(screen.queryByText(/腾讯围棋/)).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '去连接' }));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/play/cross-platform');
  });

  it('实体棋盘那一组给的是真读数和一条去标定的路', () => {
    renderPage();
    expect(screen.getByText('还没标定')).toBeInTheDocument();
    for (const key of ['camera', 'calib', 'led']) {
      expect(screen.getByTestId(`settings-cap-${key}`).textContent).toContain('未连接');
    }
    fireEvent.click(screen.getByRole('button', { name: '开始标定' }));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/vision/setup');
  });

  // 一屏之内所有选择组用**同一种控件**(规范 §12)—— 所以是分段不是 MUI 开关。
  it('「做对后自动进入下一题」是分段控件,拨了就存下来', () => {
    renderPage();
    const seg = screen.getByRole('group', { name: '做对后自动进入下一题' });
    const [on, off] = [...seg.querySelectorAll('button')];
    expect(document.querySelector('input[type="checkbox"]')).toBeNull();
    fireEvent.click(off);
    expect(off).toHaveAttribute('aria-pressed', 'true');
    expect(on).toHaveAttribute('aria-pressed', 'false');
    fireEvent.click(on);
    expect(on).toHaveAttribute('aria-pressed', 'true');
  });

  // 两把开关**分开**:音效是几十毫秒的一声,引导语是一整句话 ——
  // 教室里最先想关掉的往往是后者,合成一把就逼人连落子声一起丢掉。
  it('声音是两把开关,不是一把', () => {
    renderPage();
    expect(screen.getByRole('group', { name: '落子音效' })).toBeInTheDocument();
    expect(screen.getByRole('group', { name: '语音提示' })).toBeInTheDocument();
  });

  it('出厂两把都是开的 —— 读不到就当开,不是当关', () => {
    localStorage.clear();
    renderPage();
    for (const name of ['落子音效', '语音提示']) {
      const [on] = [...screen.getByRole('group', { name }).querySelectorAll('button')];
      expect(on, name).toHaveAttribute('aria-pressed', 'true');
    }
  });

  it('拨了就落盘,而且落的是**共享的那一份** —— 不是组件里另存的 state', () => {
    renderPage();
    const seg = screen.getByRole('group', { name: '落子音效' });
    const [on, off] = [...seg.querySelectorAll('button')];

    fireEvent.click(off);
    expect(off).toHaveAttribute('aria-pressed', 'true');
    // 判据落在**播放那一侧读的同一个出口**上,不落在 localStorage 的键名上:
    // 键名对了而 `useSound` 读的是别处,屏上照样写着「关」而喇叭还在响。
    expect(readAudioPref('sfx')).toBe(false);
    expect(readAudioPref('voice')).toBe(true);   // 另一把没跟着动

    fireEvent.click(on);
    expect(readAudioPref('sfx')).toBe(true);
  });

  it('语音那一行照实说它什么时候才会响', () => {
    renderPage();
    expect(screen.getByText(/只在用实体棋盘时会响/)).toBeInTheDocument();
  });

    it('换语言走的是会落盘的那个 setter,不是组件里的局部状态', () => {
    renderPage();
    fireEvent.change(screen.getByTestId('settings-language'), { target: { value: 'jp' } });
    expect(mockSetLanguage).toHaveBeenCalledWith('jp');
  });

  // 规范 §12 说语言该在设置中心,可**设置中心不在本仓** —— 搬走等于这台盒子上再没有语言开关。
  // 屏上照实说它将来会搬。
  it('语言这一组照实说它将来会搬走', () => {
    renderPage();
    expect(screen.getByText('这一项将来会搬到设置中心')).toBeInTheDocument();
  });

  it('账号那一块还在 —— 退出登录一个功能不少', () => {
    renderPage();
    expect(screen.getByTestId('settings-logout')).toBeInTheDocument();
    expect(screen.getByText('张三')).toBeInTheDocument();
  });
});
