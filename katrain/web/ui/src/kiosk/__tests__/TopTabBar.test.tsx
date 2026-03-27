import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import TopTabBar from '../components/layout/TopTabBar';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock('../context/OrientationContext', () => ({
  useOrientation: () => ({ rotation: 0, isPortrait: false, setRotation: vi.fn() }),
}));

const renderBar = (route = '/kiosk/play') =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[route]}><TopTabBar /></MemoryRouter>
    </ThemeProvider>
  );

describe('TopTabBar', () => {
  it('renders all 6 nav labels', () => {
    renderBar();
    ['对弈', '死活', '研究', '棋谱', '直播', '设置'].forEach((l) =>
      expect(screen.getByText(l)).toBeInTheDocument()
    );
  });

  it('highlights active route', () => {
    renderBar('/kiosk/tsumego/problem/123');
    expect(screen.getByText('死活').closest('button')).toHaveAttribute('data-active', 'true');
  });

  it('navigates on click', () => {
    renderBar();
    fireEvent.click(screen.getByText('棋谱'));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/kifu');
  });

  it('renders as horizontal nav element', () => {
    renderBar();
    expect(screen.getByRole('navigation')).toBeInTheDocument();
  });
});
