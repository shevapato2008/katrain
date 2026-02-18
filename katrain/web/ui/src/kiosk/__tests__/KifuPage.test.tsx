import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import KifuPage from '../pages/KifuPage';

const renderPage = () =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter>
        <KifuPage />
      </MemoryRouter>
    </ThemeProvider>
  );

describe('KifuPage', () => {
  it('renders the title "棋谱库"', () => {
    renderPage();
    expect(screen.getByText('棋谱库')).toBeInTheDocument();
  });

  it('renders the search box', () => {
    renderPage();
    expect(screen.getByPlaceholderText('搜索棋手、赛事...')).toBeInTheDocument();
  });

  it('renders all mock kifu cards with player names and events', () => {
    renderPage();
    expect(screen.getByText('柯洁')).toBeInTheDocument();
    // 申真谞 appears in 2 kifu entries (kifu-1 and kifu-5)
    expect(screen.getAllByText('申真谞').length).toBe(2);
    expect(screen.getByText(/LG杯/)).toBeInTheDocument();
    expect(screen.getByText('张三')).toBeInTheDocument();
    expect(screen.getByText('朴廷桓')).toBeInTheDocument();
  });

  it('renders ResultBadge for each kifu', () => {
    renderPage();
    const badges = screen.getAllByTestId('result-badge');
    expect(badges.length).toBe(5); // 5 mock kifu entries
  });

  it('shows preview area with navigation when a card is selected', () => {
    renderPage();
    // Initially shows placeholder
    expect(screen.getByText('选择一局棋谱预览')).toBeInTheDocument();

    // Click first card
    fireEvent.click(screen.getByText('柯洁'));
    // Placeholder gone
    expect(screen.queryByText('选择一局棋谱预览')).not.toBeInTheDocument();
    // Navigation controls and "在研究中打开" button appear
    expect(screen.getByTestId('kifu-preview-nav')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /在研究中打开/ })).toBeInTheDocument();
  });
});
