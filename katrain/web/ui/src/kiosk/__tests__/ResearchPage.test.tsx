import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import ResearchPage from '../pages/ResearchPage';

describe('ResearchPage', () => {
  it('renders without crashing and shows key elements', () => {
    render(
      <ThemeProvider theme={kioskTheme}>
        <MemoryRouter>
          <ResearchPage />
        </MemoryRouter>
      </ThemeProvider>
    );
    expect(screen.getByRole('heading', { name: /研究/i })).toBeInTheDocument();
    expect(screen.getByText(/AI 推荐/)).toBeInTheDocument();
  });
});
