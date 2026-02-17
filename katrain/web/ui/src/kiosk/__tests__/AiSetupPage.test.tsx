import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import AiSetupPage from '../pages/AiSetupPage';

const renderPage = (mode = 'free') =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[`/kiosk/play/ai/setup/${mode}`]}>
        <Routes>
          <Route path="/kiosk/play/ai/setup/:mode" element={<AiSetupPage />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );

describe('AiSetupPage', () => {
  it('renders board size options', () => {
    renderPage();
    expect(screen.getByText('棋盘')).toBeInTheDocument();
    expect(screen.getByText('9路')).toBeInTheDocument();
    expect(screen.getByText('19路')).toBeInTheDocument();
  });

  it('renders color selection', () => {
    renderPage();
    expect(screen.getByText(/黑/)).toBeInTheDocument();
    expect(screen.getByText(/白/)).toBeInTheDocument();
  });

  it('renders start button', () => {
    renderPage();
    expect(screen.getByRole('button', { name: /开始对弈/i })).toBeInTheDocument();
  });

  it('shows AI strength slider for free mode', () => {
    renderPage('free');
    expect(screen.getByText(/AI 强度/i)).toBeInTheDocument();
  });

  it('hides AI strength slider for ranked mode', () => {
    renderPage('ranked');
    expect(screen.queryByText(/AI 强度/i)).not.toBeInTheDocument();
  });
});
