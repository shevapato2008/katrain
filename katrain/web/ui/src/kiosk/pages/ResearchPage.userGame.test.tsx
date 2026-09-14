import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';

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
// 可以逐条改 token:盒上(严格盒端 SSO)token 恒为 null 而人是登录的。
const { auth } = vi.hoisted(() => ({ auth: { token: 'tok' as string | null } }));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => auth }));
const { get } = vi.hoisted(() => ({
  get: vi.fn().mockResolvedValue({ id: 'g1', sgf_content: '(;GM[1]FF[4])' }),
}));
vi.mock('../../api/userGamesApi', () => ({ UserGamesAPI: { get, list: vi.fn() } }));

import ResearchPage from './ResearchPage';

beforeEach(() => { vi.clearAllMocks(); sessionStorage.clear(); auth.token = 'tok'; });

const renderAt = (path: string) =>
  render(<ThemeProvider theme={kioskTheme}><MemoryRouter initialEntries={[path]}><ResearchPage /></MemoryRouter></ThemeProvider>);

describe('ResearchPage local-play review entry', () => {
  it('loads SGF handed off via sessionStorage (复盘本局)', async () => {
    sessionStorage.setItem('kioskReviewSgf', '(;GM[1]FF[4])');
    renderAt('/kiosk/research');
    await waitFor(() => expect(loadFromSGF).toHaveBeenCalledWith('(;GM[1]FF[4])'));
    expect(sessionStorage.getItem('kioskReviewSgf')).toBeNull();
  });

  it('loads a recorded game by ?user_game_id', async () => {
    renderAt('/kiosk/research?user_game_id=g1');
    await waitFor(() => expect(get).toHaveBeenCalledWith('tok', 'g1'));
    await waitFor(() => expect(loadFromSGF).toHaveBeenCalledWith('(;GM[1]FF[4])'));
  });

  /**
   * 回归钉子(P13):上一条把 token mock 成 'tok',**正好避开了盒子上那条路**。
   * 严格盒端 SSO 里 token 恒为 null;原来的 `!token` 早退让盒上从报告点「去研究」落到空棋盘,
   * 而 `GET /api/v1/user-games/{id}` 本来就认 cookie。
   */
  it('盒上 token 恒为 null 时照样按 ?user_game_id 读谱', async () => {
    auth.token = null;
    renderAt('/kiosk/research?user_game_id=g1');
    await waitFor(() => expect(get).toHaveBeenCalledWith(null, 'g1'));
    await waitFor(() => expect(loadFromSGF).toHaveBeenCalledWith('(;GM[1]FF[4])'));
  });
});
