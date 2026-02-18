import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import ResearchPage from '../pages/ResearchPage';

vi.mock('../../hooks/useResearchSession', () => ({
  useResearchSession: () => ({
    createSession: vi.fn().mockResolvedValue('session-123'),
    destroySession: vi.fn(),
    sessionId: null,
    gameState: null,
    error: null,
    isConnected: false,
    onMove: vi.fn(),
    onPass: vi.fn(),
    onNavigate: vi.fn(),
    handleNavAction: vi.fn(),
    toggleHints: vi.fn(),
    toggleOwnership: vi.fn(),
    toggleMoveNumbers: vi.fn(),
    toggleCoordinates: vi.fn(),
    analyzeGame: vi.fn(),
    analysisScan: vi.fn(),
  }),
}));

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

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

  it('navigates on "开始研究" button click', async () => {
    renderPage();
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /开始研究/ }));
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/kiosk/research/session/session-123');
    });
  });
});
