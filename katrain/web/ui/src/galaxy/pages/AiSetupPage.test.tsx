import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import AiSetupPage from './AiSetupPage';

// Task 11: 棋力阶梯 (strength ladder) 37-rung opponent selector on the galaxy AiSetupPage.
// Mirrors the Vitest/RTL pattern in kiosk/pages/PlatformEngineSetupPage.test.tsx: mock the
// API module (vi.hoisted so the mocked fns are reachable from assertions) and mock the
// auth/settings contexts (this page isn't wrapped in their Providers in isolation).
//
// This page's pre-existing Selects (Board Size / Ruleset / Your Color / AI Strategy) don't
// wire an MUI `labelId`, so `getByRole('combobox', { name })` can't resolve an accessible
// name for them (unlike kiosk/pages/AiSetupPage.tsx, which does). That's pre-existing,
// out-of-scope behavior — so tests locate a Select by its <label> text instead of relying
// on the accessible-name computation.

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const { mockAiConstants, mockRungsResponse, mockNewGame, mockUpdateConfig } = vi.hoisted(() => ({
  mockAiConstants: {
    strategies: ['ai:human', 'ai:ladder'],
    options: {},
    key_properties: [],
    default_strategy: 'ai:human',
    strategy_defaults: {
      'ai:human': { human_kyu_rank: 0 },
      'ai:ladder': {},
    },
  },
  mockRungsResponse: {
    rungs: [
      { rung: 18, rank_name: '3K' },
      { rung: 37, rank_name: 'KataGo中等' },
    ],
  },
  mockNewGame: vi.fn().mockResolvedValue({ session_id: 's1', state: {} }),
  mockUpdateConfig: vi.fn().mockResolvedValue({ session_id: 's1', state: {} }),
}));

vi.mock('../../api', () => ({
  API: {
    createSession: vi.fn().mockResolvedValue({ session_id: 's1', state: {} }),
    getAIConstants: vi.fn().mockResolvedValue(mockAiConstants),
    getLadderRungs: vi.fn().mockResolvedValue(mockRungsResponse),
    newGame: mockNewGame,
    updateConfigBulk: vi.fn().mockResolvedValue({ session_id: 's1', state: {} }),
    updatePlayer: vi.fn().mockResolvedValue({ session_id: 's1', state: {} }),
    updateConfig: mockUpdateConfig,
    estimateRank: vi.fn().mockResolvedValue({ rank: '5k' }),
  },
}));

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({ token: 'test-token', user: { id: 1, username: 'test' }, isAuthenticated: true }),
}));

vi.mock('../../context/SettingsContext', () => ({
  useSettings: () => ({ language: 'cn', setLanguage: vi.fn(), languages: [] }),
}));

const renderPage = (mode = 'free', demoState?: string) => {
  const params = new URLSearchParams({ mode });
  if (demoState) params.set('ai-ladder-demo', demoState);
  return render(
    <MemoryRouter initialEntries={[`/galaxy/play/ai/setup?${params.toString()}`]}>
      <Routes>
        <Route path="/galaxy/play/ai/setup" element={<AiSetupPage />} />
      </Routes>
    </MemoryRouter>
  );
};

// Locate a Select's combobox by its <label> text (no labelId wiring on this page's Selects,
// so getByRole('combobox', { name }) can't resolve; the label text also appears in the
// notched-outline <legend>, so filter to the actual <label> element).
const comboboxForLabel = (text: string): HTMLElement => {
  const label = screen.getAllByText(text).find((el) => el.tagName === 'LABEL');
  if (!label) throw new Error(`No <label> found with text "${text}"`);
  const formControl = label.closest('.MuiFormControl-root') as HTMLElement;
  return within(formControl).getByRole('combobox');
};

describe('AiSetupPage — 棋力阶梯 ladder opponent', () => {
  beforeEach(() => {
    mockNavigate.mockReset();
    mockNewGame.mockClear();
    mockUpdateConfig.mockClear();
  });

  it('lists 棋力阶梯 in the AI Strategy dropdown', async () => {
    renderPage();
    await waitFor(() => expect(comboboxForLabel('AI Strategy')).toBeInTheDocument());
    const user = userEvent.setup();
    await user.click(comboboxForLabel('AI Strategy'));
    expect(screen.getByRole('option', { name: '棋力阶梯' })).toBeInTheDocument();
  });

  it('shows a rung selector (not the human-rank slider) once 棋力阶梯 is chosen', async () => {
    renderPage();
    await waitFor(() => expect(comboboxForLabel('AI Strategy')).toBeInTheDocument());
    const user = userEvent.setup();

    await user.click(comboboxForLabel('AI Strategy'));
    await user.click(screen.getByRole('option', { name: '棋力阶梯' }));

    // Default rung 18 (native HumanSL 3K) is pre-selected; label is rank_name only, no elo.
    await waitFor(() => {
      expect(screen.getByText('3K')).toBeInTheDocument(); // rank_name only, no elo
    });
    // The generic human-rank slider (visible for ai:human) must not be showing.
    expect(screen.queryByText('20k')).not.toBeInTheDocument();
  });

  it('starts the game with ladder_rung and skips human_kyu_rank/strategySettings writes', async () => {
    renderPage();
    await waitFor(() => expect(comboboxForLabel('AI Strategy')).toBeInTheDocument());
    const user = userEvent.setup();

    await user.click(comboboxForLabel('AI Strategy'));
    await user.click(screen.getByRole('option', { name: '棋力阶梯' }));

    // Pick the strongest rung (37, KataGo中等) from the rung selector.
    await waitFor(() => expect(screen.getByText('3K')).toBeInTheDocument());
    await user.click(comboboxForLabel('棋力等级'));
    await user.click(screen.getByRole('option', { name: 'KataGo中等' }));

    await user.click(screen.getByRole('button', { name: /start game/i }));

    await waitFor(() => {
      expect(mockNewGame).toHaveBeenCalledWith(
        's1',
        expect.objectContaining({ ladder_rung: 37 }),
      );
    });

    // No ai:ladder config write (human_kyu_rank is only ever written for ai:human;
    // strategySettings for ai:ladder is always {} so updateConfig(`ai/ai:ladder`, ...)
    // must never fire).
    const ladderConfigCalls = mockUpdateConfig.mock.calls.filter(([, setting]) => setting === 'ai/ai:ladder');
    expect(ladderConfigCalls).toHaveLength(0);
  });
});

describe('AiSetupPage — rated AI ladder visual slice', () => {
  beforeEach(() => {
    mockNavigate.mockReset();
  });

  it('replaces the rated HumanSL controls with the server-decided placement opponent', async () => {
    renderPage('rated', 'placement');

    expect(await screen.findByRole('heading', { name: '41档升降级AI' })).toBeInTheDocument();
    expect(screen.getByText('定级进度 3/5')).toBeInTheDocument();
    expect(screen.getByText('定级对手：4级')).toBeInTheDocument();
    expect(screen.queryByText('20k')).not.toBeInTheDocument();
    expect(screen.queryByText('9d')).not.toBeInTheDocument();
    expect(screen.queryByText('Human-like')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Start Game' })).toBeDisabled();
    expect(screen.queryByText('累计净胜分：0')).not.toBeInTheDocument();
  });

  it('shows the current public 41-rung rank without an internal rung number', async () => {
    renderPage('rated', 'placed');

    expect(await screen.findByText('本局对手：5段')).toBeInTheDocument();
    expect(screen.queryByText('第30档')).not.toBeInTheDocument();
  });

  it('retries a failed ranked-status load inside the rated setup flow', async () => {
    const user = userEvent.setup();
    renderPage('rated', 'error');

    await user.click(await screen.findByRole('button', { name: '重试' }));

    expect(await screen.findByText('定级进度 3/5')).toBeInTheDocument();
  });

  it.each(['toString', 'constructor', 'unknown'])('ignores unsupported demo state %s', async (state) => {
    renderPage('rated', state);

    await waitFor(() => expect(comboboxForLabel('AI Strategy')).toBeInTheDocument());
    expect(screen.queryByRole('heading', { name: '41档升降级AI' })).not.toBeInTheDocument();
    expect(screen.getByText('20k')).toBeInTheDocument();
  });

  it('keeps rated setup unchanged when no explicit preview state is requested', async () => {
    renderPage('rated');

    await waitFor(() => expect(comboboxForLabel('AI Strategy')).toBeInTheDocument());
    expect(screen.getByText('20k')).toBeInTheDocument();
    expect(screen.getByText('9d')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: '41档升降级AI' })).not.toBeInTheDocument();
  });

  it('does not mount the ranked preview in free play', async () => {
    renderPage('free', 'placement');

    await waitFor(() => expect(comboboxForLabel('AI Strategy')).toBeInTheDocument());
    expect(screen.queryByRole('heading', { name: '41档升降级AI' })).not.toBeInTheDocument();
  });
});
