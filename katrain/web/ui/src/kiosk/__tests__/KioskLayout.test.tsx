import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { useEffect } from 'react';
import { kioskTheme } from '../theme';
import KioskLayout from '../components/layout/KioskLayout';
import { useImmersive } from '../context/ImmersiveContext';

const renderLayout = (route = '/kiosk/play') =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route element={<KioskLayout username="张三" />}>
            <Route path="/kiosk/play" element={<div>PLAY_CONTENT</div>} />
            <Route path="/kiosk/report" element={<div>REPORT_CONTENT</div>} />
            <Route path="/kiosk/settings" element={<div>SETTINGS_CONTENT</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );

/** Outlet child that flips the real ImmersiveContext (mounted by KioskLayout) to
 * immersive mode on mount — proves the A6→A10 immersive mechanism end to end. */
const ImmersiveTrigger = () => {
  const { setImmersive } = useImmersive();
  useEffect(() => {
    setImmersive(true);
  }, [setImmersive]);
  return <div>IMMERSIVE_CONTENT</div>;
};

describe('KioskLayout', () => {
  it('renders header, dock, console, and outlet on /kiosk/play', () => {
    renderLayout('/kiosk/play');
    expect(screen.getByText('智星盒')).toBeInTheDocument();
    expect(screen.getByText('对弈')).toBeInTheDocument();
    expect(screen.getByText('复盘')).toBeInTheDocument();
    expect(screen.getByText('PLAY_CONTENT')).toBeInTheDocument();
    expect(screen.getByText('智能棋盘')).toBeInTheDocument();
  });

  // ⚠️ 后半句 Task 4 **翻了面**:设置是 Dock 的第六项(规范 §1),所以它有 Dock。
  // 旧断言「设置没有 Dock」属于顶栏还挂着齿轮的那套分工。
  it('shows topbar and Dock on both L1 Report and L1 Settings', () => {
    const report = renderLayout('/kiosk/report');
    expect(screen.getByText('REPORT_CONTENT')).toBeInTheDocument();
    expect(screen.getByText('智星盒')).toBeInTheDocument();
    expect(screen.getByText('复盘')).toBeInTheDocument();
    report.unmount();

    renderLayout('/kiosk/settings');
    expect(screen.getByText('智星盒')).toBeInTheDocument();
    expect(screen.getByText('复盘')).toBeInTheDocument();
  });

  it('gates the SmartBoardConsole to CONSOLE_ROUTES — hidden on /kiosk/settings', () => {
    renderLayout('/kiosk/settings');
    expect(screen.getByText('SETTINGS_CONTENT')).toBeInTheDocument();
    expect(screen.queryByText('智能棋盘')).toBeNull();
  });

  // Task 4 把 Dock 的出没**只**交给 `dockLevelOf`,`immersive` 不再参与:
  // 今天五个设 immersive 的页面(研究/复盘详情/摆谱对局/做题/直播)**全在 L2**,
  // `level === 1` 已经把它们挡住了,再叠一个条件只是多一条永远不走的分支。
  // 所以这条测试现在断言的是 immersive 仅存的那一半作用 —— 抽顶栏。
  //
  // ⚠️ **抽顶栏本身和规范 §5 防跳铁律 1 冲突**(「顶栏永远占 y 0–56,任何层级、
  // 任何模块都不变高、不隐藏」)。这条冲突已登记,归 Task 18 的 §12 差异清单处理,
  // 不在本 Task 范围内 —— 这条测试锁的是**现状**,不是终态。
  it('immersive 抽掉顶栏;Dock 归 level 管,L1 上照旧在(已登记的 §5 冲突)', () => {
    render(
      <ThemeProvider theme={kioskTheme}>
        <MemoryRouter initialEntries={['/kiosk/play']}>
          <Routes>
            <Route element={<KioskLayout username="张三" />}>
              <Route path="/kiosk/play" element={<ImmersiveTrigger />} />
            </Route>
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    );

    expect(screen.getByText('IMMERSIVE_CONTENT')).toBeInTheDocument();
    expect(screen.queryByText('智星盒')).toBeNull();
    expect(screen.getByText('对弈')).toBeInTheDocument();
  });
});
