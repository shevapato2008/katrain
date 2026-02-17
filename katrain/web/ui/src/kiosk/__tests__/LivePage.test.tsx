import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import LivePage from '../pages/LivePage';

describe('LivePage', () => {
  it('renders without crashing and shows key elements', () => {
    render(
      <ThemeProvider theme={kioskTheme}>
        <MemoryRouter>
          <LivePage />
        </MemoryRouter>
      </ThemeProvider>
    );
    expect(screen.getByRole('heading', { name: /直播/i })).toBeInTheDocument();
    expect(screen.getByText(/柯洁/)).toBeInTheDocument();
    expect(screen.getByText(/春兰杯/)).toBeInTheDocument();
  });
});
