import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import TsumegoPage from '../pages/TsumegoPage';

const renderPage = () =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter>
        <TsumegoPage />
      </MemoryRouter>
    </ThemeProvider>
  );

describe('TsumegoPage', () => {
  it('renders level filter chips', () => {
    renderPage();
    ['全部', '入门', '初级', '中级', '高级'].forEach((level) => {
      expect(screen.getByText(level)).toBeInTheDocument();
    });
  });

  it('renders problem buttons from fixed mock data', () => {
    renderPage();
    expect(screen.getByText('入门 1')).toBeInTheDocument();
    expect(screen.getByText('高级 2')).toBeInTheDocument();
  });

  it('filters problems when clicking a level chip', () => {
    renderPage();
    fireEvent.click(screen.getByText('入门'));
    expect(screen.getByText('入门 1')).toBeInTheDocument();
    expect(screen.queryByText('高级 1')).not.toBeInTheDocument();
  });
});
