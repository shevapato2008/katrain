import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import KifuPage from '../pages/KifuPage';

describe('KifuPage', () => {
  it('renders game list from mock data', () => {
    render(
      <ThemeProvider theme={kioskTheme}>
        <MemoryRouter>
          <KifuPage />
        </MemoryRouter>
      </ThemeProvider>
    );
    expect(screen.getByText(/柯洁/)).toBeInTheDocument();
    expect(screen.getByText(/LG杯/)).toBeInTheDocument();
    expect(screen.getByText(/张三/)).toBeInTheDocument();
  });
});
