import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import ResearchPage from '../pages/ResearchPage';

const renderPage = () =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter>
        <ResearchPage />
      </MemoryRouter>
    </ThemeProvider>
  );

describe('ResearchPage', () => {
  it('renders the heading', () => {
    renderPage();
    expect(screen.getByRole('heading', { name: /研究/ })).toBeInTheDocument();
  });

  it('renders game info section with player placeholders', () => {
    renderPage();
    expect(screen.getByText('对局信息')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('黑方')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('白方')).toBeInTheDocument();
  });

  it('renders rules settings section', () => {
    renderPage();
    expect(screen.getByText('规则设置')).toBeInTheDocument();
    // MUI Select renders label text in both <label> and notchedOutline <span>
    expect(screen.getAllByText('棋盘大小').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('规则').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('贴目').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('让子').length).toBeGreaterThanOrEqual(1);
  });

  it('renders edit tools section', () => {
    renderPage();
    expect(screen.getByText('编辑工具')).toBeInTheDocument();
    expect(screen.getByText('手数')).toBeInTheDocument();
    expect(screen.getByText('停一手')).toBeInTheDocument();
    expect(screen.getByText('移动')).toBeInTheDocument();
    expect(screen.getByText('删除')).toBeInTheDocument();
    expect(screen.getByText('建议')).toBeInTheDocument();
    expect(screen.getByText('领地')).toBeInTheDocument();
    expect(screen.getByText('打开')).toBeInTheDocument();
    expect(screen.getByText('保存')).toBeInTheDocument();
  });

  it('renders bottom move navigation bar', () => {
    renderPage();
    const nav = screen.getByTestId('move-navigation');
    expect(nav).toBeInTheDocument();
    expect(screen.getByText('0 / 0 手')).toBeInTheDocument();
  });

  it('renders "开始研究" button', () => {
    renderPage();
    expect(screen.getByRole('button', { name: /开始研究/ })).toBeInTheDocument();
  });
});
