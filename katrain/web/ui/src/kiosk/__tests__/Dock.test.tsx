import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import Dock from '../components/layout/Dock';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const renderWithProviders = (ui: React.ReactElement, route = '/kiosk/play') =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </ThemeProvider>
  );

describe('Dock', () => {
  it('renders all 8 nav labels', () => {
    renderWithProviders(<Dock />);
    ['对弈', '死活', '研究', '棋谱', '摆谱', '直播', '教程', '设置'].forEach((label) => {
      expect(screen.getByText(label)).toBeInTheDocument();
    });
  });

  it('marks 对弈 active and 死活 inactive on /kiosk/play', () => {
    renderWithProviders(<Dock />, '/kiosk/play');
    expect(screen.getByText('对弈').closest('button')).toHaveAttribute('data-active', 'true');
    expect(screen.getByText('死活').closest('button')).toHaveAttribute('data-active', 'false');
  });

  it('navigates to /kiosk/tsumego on 死活 click', () => {
    renderWithProviders(<Dock />);
    fireEvent.click(screen.getByText('死活'));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tsumego');
  });
});
