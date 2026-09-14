import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
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
const { auth } = vi.hoisted(() => ({
  auth: { current: { token: 'tok' as string | null, isAuthenticated: true } },
}));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => auth.current }));
const { get } = vi.hoisted(() => ({
  get: vi.fn().mockResolvedValue({ id: 'g1', sgf_content: '(;GM[1]FF[4])' }),
}));
vi.mock('../../api/userGamesApi', () => ({ UserGamesAPI: { get, list: vi.fn() } }));

import ResearchPage from './ResearchPage';

beforeEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();
  auth.current = { token: 'tok', isAuthenticated: true };
});

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
   * S1 回归钉子(2026-09-14 调研):盒上严格 SSO 的 token 恒为 null,人是登录的
   * (凭据在 HttpOnly cookie 里)。闸判在 token 上时,屏 20「去研究」在盒上打开的是一块空盘。
   * 变异验证:把 ResearchPage 里的 `!isAuthenticated` 改回 `!token`,这条红。
   */
  it('token 为 null 而已登录(盒上):照样按 ?user_game_id 取谱', async () => {
    auth.current = { token: null, isAuthenticated: true };
    renderAt('/kiosk/research?user_game_id=g1&from=report');
    await waitFor(() => expect(get).toHaveBeenCalledWith(null, 'g1'));
    await waitFor(() => expect(loadFromSGF).toHaveBeenCalledWith('(;GM[1]FF[4])'));
  });

  it('没登录时不去取谱', async () => {
    auth.current = { token: null, isAuthenticated: false };
    renderAt('/kiosk/research?user_game_id=g1&from=report');
    await act(async () => { await Promise.resolve(); });
    expect(get).not.toHaveBeenCalled();
  });

  it('谱取不到时副标题说出来,不留一块没有解释的空盘', async () => {
    get.mockRejectedValueOnce(Object.assign(new Error('Request failed 503: {}'), { status: 503 }));
    renderAt('/kiosk/research?user_game_id=g1&from=report');
    expect(await screen.findByText('这一局读不到')).toBeInTheDocument();
  });

  /**
   * 盒上以前 provenance 永远是 null,返回键落在组件里算好的 `backPath`(带 `task` ⇒ 这一份报告)。
   * S1 修通之后 provenance 有了,它若还写 `BACK` 表里的 `backTo.path`(报告**列表**),
   * 盒上「去研究 → 返回」就从回到这份报告退成回到列表 —— 屏 20 的单测注释明写 `task` 是为了回到这一份。
   */
  it('从报告进来,返回键回的是这一份报告,不是报告列表', async () => {
    auth.current = { token: null, isAuthenticated: true };
    render(
      <ThemeProvider theme={kioskTheme}>
        <MemoryRouter initialEntries={['/kiosk/research?user_game_id=g1&from=report&task=42']}>
          <Routes>
            <Route path="/kiosk/research" element={<ResearchPage />} />
            <Route path="/kiosk/report" element={<div>复盘屏</div>} />
            <Route path="/kiosk/report/:taskId" element={<div>报告屏</div>} />
          </Routes>
        </MemoryRouter>
      </ThemeProvider>,
    );
    const bar = screen.getByTestId('research-pagebar');
    await waitFor(() => expect(bar.querySelector('.kiosk-pagebar__sub')).toHaveTextContent('我的对局'));
    fireEvent.click(within(bar).getByRole('button', { name: /复盘/ }));
    expect(await screen.findByText('报告屏')).toBeInTheDocument();
  });
});
