import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import KioskLayout from './KioskLayout';
import { DOCK_TABS } from '../../shell/dockRoutes';
import { EngineReadinessContext } from '../../context/EngineReadinessContext';

// Dock renders the 对弈 label; assert its presence/absence by route.
function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<KioskLayout username="友" />}>
          <Route path="/kiosk/*" element={<div>page</div>} />
          <Route path="/kiosk/settings" element={<div>settings</div>} />
          <Route path="/kiosk/play/ai/setup/:mode" element={<div>setup</div>} />
          <Route path="/kiosk/play/cross-platform/engine/:platform" element={<div>platform-setup</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

// EngineReadinessContext 默认值是 'ready'(banner 不渲染任何东西),要看到 banner 本身
// 得手动喂一个 'warming'/'unavailable'。
function renderAtWithReadiness(path: string, readiness: 'warming' | 'unavailable' | 'ready') {
  return render(
    <EngineReadinessContext.Provider value={readiness}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route element={<KioskLayout username="友" />}>
            <Route path="/kiosk/*" element={<div>page</div>} />
            <Route path="/kiosk/play/cross-platform/engine/:platform" element={<div>platform-setup</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </EngineReadinessContext.Provider>,
  );
}

// Task 4.6:EngineWarmupBanner 报的是本地引擎,跨平台屏(`/kiosk/play/cross-platform/**`)
// 打的是远端平台的 bot,和本地引擎无关 —— 判据只写在 KioskLayout 一处。
test('引擎准备中提示条在跨平台子树整个不出现,别的一级页正常出', () => {
  const play = renderAtWithReadiness('/kiosk/play', 'warming');
  expect(play.getByRole('status')).toBeInTheDocument();
  play.unmount();

  const crossPlatform = renderAtWithReadiness('/kiosk/play/cross-platform/engine/golaxy', 'warming');
  expect(crossPlatform.queryByRole('status')).not.toBeInTheDocument();
  crossPlatform.unmount();
});

test('Dock shows on L1 play', () => {
  renderAt('/kiosk/play');
  expect(screen.getByText('对弈')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '返回智星盒主页' })).toBeInTheDocument();
});

// L1 = Dock 词典里的六条,不是「路由表里排在前面的那几条」。Task 4 之前这份名单
// (navTabs 的 L1_PATHS)有 8 条且不含 settings —— 两处名单会漂,所以现在只留一份。
test.each(DOCK_TABS.map((t) => t.path))('home action shows on L1 route %s', (path) => {
  renderAt(path);
  expect(screen.getByRole('button', { name: '返回智星盒主页' })).toBeInTheDocument();
});

test('Dock hidden on deeper setup page', () => {
  renderAt('/kiosk/play/ai/setup/free');
  expect(screen.queryByText('对弈')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: '返回智星盒主页' })).not.toBeInTheDocument();
});

// ⚠️ 这条断言 Task 4 **翻了面**:设置现在是 Dock 上的第六项(规范 §1),所以它是 L1,
// 有 Dock、有主页键。旧版本断言「设置没有 Dock」,那是顶栏还有齿轮时代的分工。
test('Dock shows on L1 Report AND on L1 Settings —— 设置进了 Dock(§1 / D9)', () => {
  const report = renderAt('/kiosk/report');
  expect(screen.getByText('复盘')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '返回智星盒主页' })).toBeInTheDocument();
  report.unmount();
  renderAt('/kiosk/settings');
  expect(screen.getByText('复盘')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '设置' })).toHaveAttribute('aria-current', 'page');
  expect(screen.getByRole('button', { name: '返回智星盒主页' })).toBeInTheDocument();
});

// 对局屏 Task 4 挪进了 KioskLayout:**有顶栏、没 Dock**。
// 挪之前它连顶栏都没有 —— 撞规范 §5 防跳铁律 1。
test('对局屏有顶栏、没 Dock', () => {
  renderAt('/kiosk/play/ai/game/abc');
  expect(screen.getByTestId('kiosk-brand-zh')).toBeInTheDocument();
  expect(screen.queryByRole('navigation', { name: '主导航' })).not.toBeInTheDocument();
});
