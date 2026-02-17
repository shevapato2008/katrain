import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
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

  it('renders win rate', () => {
    renderPage();
    expect(screen.getByText(/56.3%/)).toBeInTheDocument();
  });

  it('renders control buttons', () => {
    renderPage();
    expect(screen.getByText('悔棋')).toBeInTheDocument();
    expect(screen.getByText('认输')).toBeInTheDocument();
  });

  it('does NOT render navigation rail (fullscreen)', () => {
    renderPage();
    // NavigationRail-only labels (not in GameControlPanel)
    expect(screen.queryByText('对弈')).not.toBeInTheDocument();
    expect(screen.queryByText('死活')).not.toBeInTheDocument();
    expect(screen.queryByText('棋谱')).not.toBeInTheDocument();
  });
});
