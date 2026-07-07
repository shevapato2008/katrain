import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import NavigationRail from '../components/layout/NavigationRail';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock('../context/OrientationContext', () => ({
  useOrientation: () => ({ rotation: 0, setRotation: vi.fn() }),
}));

const renderWithProviders = (ui: React.ReactElement, route = '/kiosk/play') =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </ThemeProvider>
  );

describe('NavigationRail', () => {
  it('renders all primary nav labels plus settings', () => {
    renderWithProviders(<NavigationRail />);
    ['对弈', '死活', '研究', '棋谱', '摆谱', '直播', '教程', '设置'].forEach((label) => {
      expect(screen.getByText(label)).toBeInTheDocument();
    });
  });

  it('highlights 教程 on a tutorial section deep-link route', () => {
    renderWithProviders(<NavigationRail />, '/kiosk/tutorial/section/123');
    expect(screen.getByText('教程').closest('button')).toHaveAttribute('data-active', 'true');
  });

  it('navigates to /kiosk/tutorial on 教程 click', () => {
    renderWithProviders(<NavigationRail />);
    fireEvent.click(screen.getByText('教程'));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tutorial');
  });

  it('highlights active item based on current route using matchPath', () => {
    renderWithProviders(<NavigationRail />, '/kiosk/tsumego/problem/123');
    const tsumegoItem = screen.getByText('死活').closest('button');
    expect(tsumegoItem).toHaveAttribute('data-active', 'true');
  });

  it('does not false-match similar route prefixes', () => {
    renderWithProviders(<NavigationRail />, '/kiosk/live');
    const liveItem = screen.getByText('直播').closest('button');
    expect(liveItem).toHaveAttribute('data-active', 'true');
    const kifuItem = screen.getByText('棋谱').closest('button');
    expect(kifuItem).toHaveAttribute('data-active', 'false');
  });

  it('navigates on item click', () => {
    renderWithProviders(<NavigationRail />);
    fireEvent.click(screen.getByText('死活'));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tsumego');
  });

  it('settings item is visually separated at the bottom', () => {
    renderWithProviders(<NavigationRail />);
    const settingsItem = screen.getByText('设置').closest('button');
    expect(settingsItem).toHaveAttribute('data-section', 'footer');
  });
});
