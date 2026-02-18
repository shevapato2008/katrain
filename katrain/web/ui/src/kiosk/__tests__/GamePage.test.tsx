import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import GamePage from '../pages/GamePage';

const renderPage = () =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={['/kiosk/play/ai/game/mock-session']}>
        <Routes>
          <Route path="/kiosk/play/ai/game/:sessionId" element={<GamePage />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );

describe('GamePage', () => {
  it('renders mock board with move number', () => {
    renderPage();
    expect(screen.getByText(/第42手/)).toBeInTheDocument();
  });

  it('renders player names', () => {
    renderPage();
    expect(screen.getByText(/张三/)).toBeInTheDocument();
    expect(screen.getByText(/KataGo/)).toBeInTheDocument();
  });

  it('renders player ranks', () => {
    renderPage();
    expect(screen.getByText('2D')).toBeInTheDocument();
    expect(screen.getByText('5D')).toBeInTheDocument();
  });

  it('renders game info bar with ruleset and komi', () => {
    renderPage();
    expect(screen.getByText(/日本 规则/)).toBeInTheDocument();
    expect(screen.getByText(/贴目: 6.5/)).toBeInTheDocument();
  });

  it('renders all 7 ItemToggles', () => {
    renderPage();
    expect(screen.getByText('领地')).toBeInTheDocument();
    expect(screen.getByText('建议')).toBeInTheDocument();
    expect(screen.getByText('图表')).toBeInTheDocument();
    expect(screen.getByText('悔棋')).toBeInTheDocument();
    expect(screen.getByText('停一手')).toBeInTheDocument();
    expect(screen.getByText('认输')).toBeInTheDocument();
    expect(screen.getByText('数子')).toBeInTheDocument();
  });

  it('toggles ScoreGraph visibility via chart toggle', () => {
    renderPage();
    // Score toggle is on by default — graph visible
    expect(screen.getByTestId('score-graph')).toBeInTheDocument();

    // Click "图表" toggle to hide
    fireEvent.click(screen.getByText('图表'));
    expect(screen.queryByTestId('score-graph')).not.toBeInTheDocument();

    // Click again to show
    fireEvent.click(screen.getByText('图表'));
    expect(screen.getByTestId('score-graph')).toBeInTheDocument();
  });

  it('renders navigation controls', () => {
    renderPage();
    expect(screen.getByTestId('nav-controls')).toBeInTheDocument();
  });

  it('renders timer values', () => {
    renderPage();
    // Black timer: 342s = 5:42
    expect(screen.getByText('5:42')).toBeInTheDocument();
    // White timer: 289s = 4:49
    expect(screen.getByText('4:49')).toBeInTheDocument();
  });

  it('renders header with game title and exit button', () => {
    renderPage();
    expect(screen.getByText('AI对弈 (自由)')).toBeInTheDocument();
    expect(screen.getByText('退出')).toBeInTheDocument();
  });

  it('renders winrate in score graph labels', () => {
    renderPage();
    expect(screen.getByText(/46.6%/)).toBeInTheDocument();
  });

  it('does NOT render navigation rail (fullscreen)', () => {
    renderPage();
    expect(screen.queryByText('对弈')).not.toBeInTheDocument();
    expect(screen.queryByText('死活')).not.toBeInTheDocument();
    expect(screen.queryByText('棋谱')).not.toBeInTheDocument();
  });
});
