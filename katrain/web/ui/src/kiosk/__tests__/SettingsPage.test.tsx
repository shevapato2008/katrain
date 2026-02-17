import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import SettingsPage from '../pages/SettingsPage';

describe('SettingsPage', () => {
  it('renders without crashing and shows key elements', () => {
    render(
      <ThemeProvider theme={kioskTheme}>
        <MemoryRouter>
          <SettingsPage />
        </MemoryRouter>
      </ThemeProvider>
    );
    expect(screen.getByRole('heading', { name: /设置/i })).toBeInTheDocument();
    expect(screen.getByText(/语言/)).toBeInTheDocument();
    expect(screen.getByText(/外部平台/)).toBeInTheDocument();
    expect(screen.getByText(/野狐围棋/)).toBeInTheDocument();
  });
});
