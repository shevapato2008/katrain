import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import KioskLayout from './KioskLayout';
import { L1_PATHS } from './navTabs';

// Dock renders the 对弈 label; assert its presence/absence by route.
function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<KioskLayout username="友" />}>
          <Route path="/kiosk/*" element={<div>page</div>} />
          <Route path="/kiosk/settings" element={<div>settings</div>} />
          <Route path="/kiosk/play/ai/setup/:mode" element={<div>setup</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

test('Dock shows on L1 play', () => {
  renderAt('/kiosk/play');
  expect(screen.getByText('对弈')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '返回智星盒主页' })).toBeInTheDocument();
});

test.each(L1_PATHS)('home action shows on L1 route %s', (path) => {
  renderAt(path);
  expect(screen.getByRole('button', { name: '返回智星盒主页' })).toBeInTheDocument();
});

test('Dock hidden on deeper setup page', () => {
  renderAt('/kiosk/play/ai/setup/free');
  expect(screen.queryByText('对弈')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: '返回智星盒主页' })).not.toBeInTheDocument();
});

test('Dock shows on L1 Report and is hidden on Settings', () => {
  const report = renderAt('/kiosk/report');
  expect(screen.getByText('复盘')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '返回智星盒主页' })).toBeInTheDocument();
  report.unmount();
  renderAt('/kiosk/settings');
  expect(screen.queryByText('复盘')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: '返回智星盒主页' })).not.toBeInTheDocument();
});
