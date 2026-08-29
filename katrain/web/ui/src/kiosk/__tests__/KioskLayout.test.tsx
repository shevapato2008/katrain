import { describe, it, expect } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import KioskLayout from '../components/layout/KioskLayout';

const renderLayout = (route = '/kiosk/play') =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route element={<KioskLayout username="张三" />}>
            <Route path="/kiosk/play" element={<div>PLAY_CONTENT</div>} />
            <Route path="/kiosk/report" element={<div>REPORT_CONTENT</div>} />
            <Route path="/kiosk/settings" element={<div>SETTINGS_CONTENT</div>} />
            <Route path="/kiosk/report/x1" element={<div>DETAIL_CONTENT</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );

describe('KioskLayout', () => {
  it('renders header, dock, console, and outlet on /kiosk/play', () => {
    renderLayout('/kiosk/play');
    expect(screen.getByText('智星盒')).toBeInTheDocument();
    expect(screen.getByText('对弈')).toBeInTheDocument();
    expect(screen.getByText('复盘')).toBeInTheDocument();
    expect(screen.getByText('PLAY_CONTENT')).toBeInTheDocument();
    // Task 5:左栏从自造几何的 `SmartBoardConsole`(标题「智能棋盘」)换成共享外壳的
    // `.kiosk-console`,标题逐字取稿子 ——「实体棋盘 / Camera board」。
    expect(screen.getByText('实体棋盘')).toBeInTheDocument();
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

  it('gates the console rail to RAIL_ROUTES — hidden on /kiosk/settings', () => {
    renderLayout('/kiosk/settings');
    expect(screen.getByText('SETTINGS_CONTENT')).toBeInTheDocument();
    expect(screen.queryByText('实体棋盘')).toBeNull();
    // 判据是「这个模块的活动会不会发生在实体盘上」(§5)—— 改设置不会。
    expect(document.querySelector('.kiosk-layout-l1')).toBeNull();
  });

  // 顶栏**没有开关**。这里曾经有一个 `immersive`,它能把顶栏整块不渲染 ——
  // 而 `.kiosk-content` 的 `top` 是写死的 `var(--topbar-h)`(tokens.css:419),
  // **抽掉顶栏并不会把那 56px 还给内容**:换来的只是屏顶一条空黑带,
  // 代价是那一屏上没有身份、没有时钟、没有退出口。2026-08-26 连同 `ImmersiveContext` 一起删。
  //
  // 这条锁的是规范 §5 防跳铁律 1(「顶栏永远占 y 0–56,任何层级、任何模块都不变高、不隐藏」)
  // 里 jsdom 能作证的那一半 —— **在不在**。高度和位置归真浏览器几何闸
  // (`kiosk-shell-geometry.spec.ts`),那一条同一天补了「每一条路由上都在」。
  it('顶栏在 L1 和 L2 上都渲染 —— 页面无法把它抽掉', () => {
    renderLayout('/kiosk/play');           // L1
    expect(screen.getByText('智星盒')).toBeInTheDocument();
    cleanup();

    renderLayout('/kiosk/report/x1');      // L2:不在 dockRoutes 词典里 ⇒ 无 Dock
    expect(screen.getByText('智星盒')).toBeInTheDocument();
    expect(screen.queryByText('对弈')).toBeNull();   // Dock 确实没了,顶栏还在
  });
});
