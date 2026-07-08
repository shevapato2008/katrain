import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import SmartBoardConsole from '../components/layout/SmartBoardConsole';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const renderWithProviders = (ui: React.ReactElement) =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={['/kiosk/play']}>{ui}</MemoryRouter>
    </ThemeProvider>
  );

describe('SmartBoardConsole', () => {
  it('renders standalone without VisionProvider/GeometryProvider ancestors', () => {
    expect(() => renderWithProviders(<SmartBoardConsole />)).not.toThrow();
  });

  it('renders the 智能棋盘 title', () => {
    renderWithProviders(<SmartBoardConsole />);
    expect(screen.getByText('智能棋盘')).toBeInTheDocument();
  });

  it('renders all three status cell labels', () => {
    renderWithProviders(<SmartBoardConsole />);
    expect(screen.getByText('摄像头')).toBeInTheDocument();
    expect(screen.getByText('标定')).toBeInTheDocument();
    expect(screen.getByText('LED')).toBeInTheDocument();
  });

  it('renders a visible no-live-feed label over the static board', () => {
    renderWithProviders(<SmartBoardConsole />);
    expect(screen.getByText('实时预览暂不可用 · no live feed')).toBeInTheDocument();
  });

  it('navigates to /kiosk/vision/setup when the 摄像头 cell is clicked', () => {
    renderWithProviders(<SmartBoardConsole />);
    fireEvent.click(screen.getByText('摄像头'));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/vision/setup');
  });

  it('navigates to /kiosk/vision/setup when the 标定 cell is clicked', () => {
    renderWithProviders(<SmartBoardConsole />);
    fireEvent.click(screen.getByText('标定'));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/vision/setup');
  });

  it('navigates to /kiosk/vision/setup when the LED cell is clicked', () => {
    renderWithProviders(<SmartBoardConsole />);
    fireEvent.click(screen.getByText('LED'));
    expect(mockNavigate).toHaveBeenCalledWith('/kiosk/vision/setup');
  });
});
