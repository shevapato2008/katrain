import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';

vi.mock('../context/ImmersiveContext', () => ({
  useImmersive: () => ({ immersive: false, setImmersive: vi.fn() }),
}));

vi.mock('../../api', () => ({
  API: {
    quickAnalyze: vi.fn().mockResolvedValue({ turnInfos: [{ moveInfos: [], ownership: null }] }),
    analysisScan: vi.fn().mockResolvedValue({}),
    analysisProgress: vi.fn(),
  },
}));

vi.mock('../../api/kifuApi', () => ({
  KifuAPI: {
    getAlbum: vi.fn(),
    getAlbums: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 15 }),
  },
}));

const { loadFromSGF } = vi.hoisted(() => ({ loadFromSGF: vi.fn() }));
vi.mock('../hooks/useResearchBoard', () => ({
  useResearchBoard: () => ({
    loadFromSGF,
    moves: [],
    stoneColors: [],
    currentMove: 0,
    boardSize: 19,
    handicapCount: 0,
    rules: 'japanese',
    komi: 6.5,
    handicap: 0,
    playerBlack: '',
    playerWhite: '',
    showMoveNumbers: false,
    placeMode: 'alternate',
    editMode: null,
    lastLoadClamped: false,
    lastLoadedSize: null,
    serializeToSGF: () => ({ sgf: '' }),
    getSnapshot: () => ({}),
    restoreSnapshot: vi.fn(),
    handleIntersectionClick: vi.fn(),
    handlePass: vi.fn(),
    handleClear: vi.fn(),
    handleMoveChange: vi.fn(),
    setPlaceMode: vi.fn(),
    setEditMode: vi.fn(),
    setShowMoveNumbers: vi.fn(),
    setRules: vi.fn(),
    setKomi: vi.fn(),
    setHandicap: vi.fn(),
    setPlayerBlack: vi.fn(),
    setPlayerWhite: vi.fn(),
    openLocalSGF: vi.fn(),
    saveLocalSGF: vi.fn(),
    copyToClipboard: vi.fn(),
  }),
}));
vi.mock('../../hooks/useResearchSession', () => ({
  useResearchSession: () => ({
    createSession: vi.fn().mockResolvedValue('s2'),
    gameState: null,
    sessionId: null,
    onNavigate: vi.fn(),
    onMove: vi.fn(),
    onPass: vi.fn(),
    destroySession: vi.fn(),
    toggleHints: vi.fn(),
    toggleOwnership: vi.fn(),
  }),
}));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => ({ token: 'tok' }) }));
const { get } = vi.hoisted(() => ({
  get: vi.fn().mockResolvedValue({ id: 'g1', sgf_content: '(;GM[1]FF[4])' }),
}));
vi.mock('../../api/userGamesApi', () => ({ UserGamesAPI: { get, list: vi.fn() } }));

import ResearchPage from './ResearchPage';
import { getCurrentKioskActivityStorage, __resetKioskActivityStorageForTests } from '../storage/kioskActivityStorage';

beforeEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();
  localStorage.clear();
  __resetKioskActivityStorageForTests();
});

const renderAt = (path: string) =>
  render(<ThemeProvider theme={kioskTheme}><MemoryRouter initialEntries={[path]}><ResearchPage /></MemoryRouter></ThemeProvider>);

describe('ResearchPage local-play review entry', () => {
  it('loads SGF handed off via the identity-scoped storage (复盘本局)', async () => {
    // Box-SSO guest mode (client-side zero-persistence, 4th layer): the handoff is routed
    // through the identity-scoped singleton, not raw sessionStorage directly.
    getCurrentKioskActivityStorage().setItem('kioskReviewSgf', '(;GM[1]FF[4])');
    renderAt('/kiosk/research');
    await waitFor(() => expect(loadFromSGF).toHaveBeenCalledWith('(;GM[1]FF[4])'));
    expect(getCurrentKioskActivityStorage().getItem('kioskReviewSgf')).toBeNull();
  });

  it('loads a recorded game by ?user_game_id', async () => {
    renderAt('/kiosk/research?user_game_id=g1');
    await waitFor(() => expect(get).toHaveBeenCalledWith('tok', 'g1'));
    await waitFor(() => expect(loadFromSGF).toHaveBeenCalledWith('(;GM[1]FF[4])'));
  });
});
