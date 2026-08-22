import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { MemoryRouter, useLocation } from 'react-router-dom';
import PlayMenu from './PlayMenu';
import { GameNavigationProvider } from '../context/GameNavigationContext';

vi.mock('../../context/SettingsContext', () => ({
  useSettings: () => ({ language: 'cn', setLanguage: vi.fn(), languages: [] }),
}));

vi.mock('../../i18n', () => ({
  i18n: {
    t: (key: string, fallback?: string) => key === 'play:game_records' ? 'Game Records' : (fallback ?? key),
    // `GameNavigationProvider` 走 `useTranslation`，它订阅 i18n 的语言变化。
    // 这个 mock 原来只有 `t`，补上订阅面才装得起 provider。
    lang: 'cn',
    subscribe: () => () => {},
  },
}));

const CurrentLocation = () => {
  const location = useLocation();
  return <output data-testid="current-location">{`${location.pathname}${location.search}`}</output>;
};

const renderPlayMenu = () => render(
  <MemoryRouter initialEntries={['/galaxy/play']}>
    <GameNavigationProvider>
      <PlayMenu />
      <CurrentLocation />
    </GameNavigationProvider>
  </MemoryRouter>,
);

// 页头改用共享的 `ContentPageHeader`（spec §2.4：左上角箭头图标键 + 标题），它经由
// `ModulePlate` 读 `GameNavigationContext`。生产里 provider 挂在 `MainLayout` 上、
// 覆盖全部 galaxy 路由，所以这里补的是**测试的装配**，不是生产缺口。
describe('PlayMenu', () => {
  it('navigates to the shared game report from the secondary action below the header', async () => {
    const user = userEvent.setup();
    renderPlayMenu();

    await user.click(screen.getByRole('button', { name: 'Game Records' }));

    expect(screen.getByTestId('current-location')).toHaveTextContent('/galaxy/report');
  });

  it.each([
    [/Play vs AI \(Free\)/, '/galaxy/play/ai?mode=free'],
    [/Rated Game vs AI/, '/galaxy/play/ai?mode=rated'],
    [/Human vs Human/, '/galaxy/play/human'],
  ])('keeps the %s mode card navigation', async (mode, destination) => {
    const user = userEvent.setup();
    renderPlayMenu();

    await user.click(screen.getByRole('button', { name: mode }));

    expect(screen.getByTestId('current-location')).toHaveTextContent(destination);
  });
});
