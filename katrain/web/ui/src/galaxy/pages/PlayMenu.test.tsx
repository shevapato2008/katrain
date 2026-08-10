import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { MemoryRouter, useLocation } from 'react-router-dom';
import PlayMenu from './PlayMenu';

vi.mock('../../context/SettingsContext', () => ({
  useSettings: () => ({ language: 'cn', setLanguage: vi.fn(), languages: [] }),
}));

vi.mock('../../i18n', () => ({
  i18n: {
    t: (key: string, fallback?: string) => key === 'play:game_records' ? 'Game Records' : (fallback ?? key),
  },
}));

const CurrentLocation = () => {
  const location = useLocation();
  return <output data-testid="current-location">{`${location.pathname}${location.search}`}</output>;
};

const renderPlayMenu = () => render(
  <MemoryRouter initialEntries={['/galaxy/play']}>
    <PlayMenu />
    <CurrentLocation />
  </MemoryRouter>,
);

describe('PlayMenu', () => {
  it('navigates to the shared game report from the page-header secondary action', async () => {
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
