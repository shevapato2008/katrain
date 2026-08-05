import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import ResearchPage from './ResearchPage';
import { useAuth } from '../../context/AuthContext';
import { vi, describe, it, expect, Mock } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { API } from '../../api';

vi.mock('../../api', () => ({ API: { quickAnalyze: vi.fn().mockResolvedValue({ turnInfos: [{ moveInfos: [] }] }) } }));

// Mock useAuth so authentication state can be toggled per test.
// NOTE: ResearchPage only reads `token` from useAuth (for cloud-save); it does NOT
// gate rendering on auth — the board is available logged-out by design.
vi.mock('../../context/AuthContext', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    useAuth: vi.fn(),
  };
});

// ResearchPage calls useGameNavigation() and reads registerActiveGame/unregisterActiveGame.
// Without a provider the hook throws, so stub it (matches the file's vi.mock style).
vi.mock('../context/GameNavigationContext', () => ({
  useGameNavigation: () => ({
    registerActiveGame: vi.fn(),
    unregisterActiveGame: vi.fn(),
  }),
}));

// LiveBoard paints to a <canvas>, which jsdom cannot render — stub it to a testid div.
// This is the board shown on the default (edit) path, regardless of auth.
vi.mock('../../components/live/LiveBoard', () => ({
  default: () => <div data-testid="mock-live-board">Live Board</div>,
}));

// ResearchSetupPanel is the right-hand setup sidebar on the default (edit) path — stub it.
vi.mock('../components/research/ResearchSetupPanel', () => ({
  default: ({ onToggleHints }: { onToggleHints: () => void }) => <div data-testid="mock-setup-panel"><button onClick={onToggleHints}>建议</button></div>,
}));

// Legacy Board (canvas) is only used in the L2 analysis-complete branch, not the default
// path exercised here. Stub it as harmless insurance so it never tries to paint a canvas.
vi.mock('../../components/Board', () => ({
  default: () => <div data-testid="mock-board">Board Component</div>,
}));

const renderPage = () =>
  render(
    <MemoryRouter>
      <ResearchPage />
    </MemoryRouter>
  );

describe('ResearchPage', () => {
  // Test A — research is intentionally available without login (no auth gate).
  it('renders the board and setup panel without requiring login', () => {
    (useAuth as Mock).mockReturnValue({ isAuthenticated: false, token: null });

    renderPage();

    // The default edit-mode path renders the board + setup panel for everyone.
    expect(screen.getByTestId('mock-live-board')).toBeInTheDocument();
    expect(screen.getByTestId('mock-setup-panel')).toBeInTheDocument();
    // There is no login gate — proves research is un-gated by design.
    expect(screen.queryByText(/Login Required/i)).not.toBeInTheDocument();
  });

  // Test B — authenticated render still shows the same edit-mode board + setup panel.
  it('renders the board and setup panel when authenticated', () => {
    (useAuth as Mock).mockReturnValue({ isAuthenticated: true, token: 'test-token' });

    renderPage();

    expect(screen.getByTestId('mock-live-board')).toBeInTheDocument();
    expect(screen.getByTestId('mock-setup-panel')).toBeInTheDocument();
  });

  it('passes the Galaxy access token to quick analysis', async () => {
    (useAuth as Mock).mockReturnValue({ isAuthenticated: true, token: 'test-token' });
    renderPage();
    fireEvent.click(screen.getByRole('button', { name: '建议' }));
    await waitFor(() => expect(API.quickAnalyze).toHaveBeenCalledWith(expect.any(Object), 'test-token'));
  });
});
