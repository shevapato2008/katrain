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
  it('renders title and subtitle', () => {
    renderPage();
    expect(screen.getByText('死活题')).toBeInTheDocument();
    expect(screen.getByText('选择难度级别')).toBeInTheDocument();
  });

  it('renders all level cards from 15K to 4K', () => {
    renderPage();
    const ranks = ['15K', '14K', '13K', '12K', '11K', '10K', '9K', '8K', '7K', '6K', '5K', '4K'];
    ranks.forEach((rank) => {
      expect(screen.getByText(rank)).toBeInTheDocument();
    });
  });

  it('shows problem count for each level', () => {
    renderPage();
    // 15K and 13K both have 1000 problems
    expect(screen.getAllByText('1000 题')).toHaveLength(2);
    expect(screen.getByText('988 题')).toBeInTheDocument();
    expect(screen.getByText('993 题')).toBeInTheDocument();
  });

  it('shows category labels on level cards', () => {
    renderPage();
    // 15K card categories
    expect(screen.getByText('手筋: 139')).toBeInTheDocument();
    expect(screen.getByText('吃子: 630')).toBeInTheDocument();
    expect(screen.getByText('死活: 167')).toBeInTheDocument();
  });

  it('level cards are clickable without errors', () => {
    renderPage();
    expect(() => {
      fireEvent.click(screen.getByText('15K'));
    }).not.toThrow();
  });
});
