import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import { AUTO_ADVANCE_KEY, sequenceKey } from '../pages/tsumegoUnits';

// ---- Hoisted spies referenced by the mock factories below ----
const { mockNavigate, mockFlush, mockReadPhysicalMode } = vi.hoisted(() => ({
  mockNavigate: vi.fn(),
  mockFlush: vi.fn(),
  mockReadPhysicalMode: vi.fn(() => false),
}));

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => mockNavigate };
});

// Only `readPhysicalMode` is mocked (D1.3) — every other export (sequenceKey,
// AUTO_ADVANCE_KEY, PHYSICAL_MODE_KEY, readAutoAdvance, levelChinese, ...) passes through
// unmocked so the rest of the test file's existing behavior is unaffected.
vi.mock('../pages/tsumegoUnits', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../pages/tsumegoUnits')>();
  return { ...actual, readPhysicalMode: () => mockReadPhysicalMode() };
});

vi.mock('../context/OrientationContext', () => ({
  useOrientation: () => ({ rotation: 0, setRotation: vi.fn() }),
}));

// Vision disabled — keeps the vision-setup branch (BoardSetupGuide / API.visionSetupMode) inert.
vi.mock('../context/VisionContext', () => ({
  useVision: () => ({
    visionStatus: { enabled: false, cameraConnected: false, poseLocked: false, syncState: 'idle', boundSessionId: null },
    isVisionEnabled: false,
    refreshStatus: vi.fn(),
  }),
}));

vi.mock('../context/ImmersiveContext', () => ({
  useImmersive: () => ({ immersive: false, setImmersive: vi.fn() }),
}));

vi.mock('../hooks/useVisionSync', () => ({
  useVisionSync: () => ({
    syncEvents: [],
    latestEvent: null,
    setupProgress: null,
    isSetupComplete: false,
  }),
}));

vi.mock('../../hooks/useSound', () => ({
  useSound: () => ({ play: vi.fn() }),
}));

// Progress source — `progress` map drives the "上次用时" (last-time) display.
const { mockProgress } = vi.hoisted(() => ({ mockProgress: {} as Record<string, any> }));
vi.mock('../../context/TsumegoProgressContext', () => ({
  useTsumegoProgress: () => ({
    progress: mockProgress,
    markProgress: vi.fn(),
    isCompleted: () => false,
    unitProgress: () => ({ completed: 0, total: 0 }),
    categoryProgress: () => ({ completed: 0, total: 0 }),
    refresh: vi.fn(),
  }),
}));

const mockUndo = vi.fn();
const mockReset = vi.fn();
const mockToggleHint = vi.fn();
const mockEnterTryMode = vi.fn();
const mockExitTryMode = vi.fn();
const mockPlaceStone = vi.fn();
const mockSaveProgress = vi.fn();

const defaultHookReturn = {
  problem: { id: 'p1', level: '15k', category: '手筋', hint: '找到要点', boardSize: 9, initialBlack: [], initialWhite: [], sgfContent: '' },
  loading: false,
  error: null,
  boardSize: 9,
  stones: [{ player: 'B' as const, coords: [2, 3] as [number, number] }],
  lastMove: [2, 3] as [number, number],
  currentNode: null,
  nextPlayer: 'W' as const,
  moveHistory: [],
  isSolved: false,
  isFailed: false,
  isTryMode: false,
  startTime: Date.now(),
  elapsedTime: 42,
  attempts: 1,
  showHint: false,
  hintCoords: [4, 4] as [number, number],
  placeStone: mockPlaceStone,
  undo: mockUndo,
  reset: mockReset,
  toggleHint: mockToggleHint,
  enterTryMode: mockEnterTryMode,
  exitTryMode: mockExitTryMode,
  saveProgress: mockSaveProgress,
  // Phase 4: the page calls flushProgress before every navigation away from a problem.
  flushProgress: mockFlush,
};

let hookReturn = { ...defaultHookReturn };

vi.mock('../../hooks/useTsumegoProblem', () => ({
  useTsumegoProblem: () => hookReturn,
}));

import TsumegoProblemPage from '../pages/TsumegoProblemPage';

// The category sequence used for prev/next. The mocked problem id is 'p1'.
const SEQUENCE = ['p0', 'p1', 'p2'];

const renderPage = (problemId = 'p1') =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={[`/kiosk/tsumego/problem/${problemId}`]}>
        <Routes>
          <Route path="/kiosk/tsumego/problem/:problemId" element={<TsumegoProblemPage />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );

beforeEach(() => {
  vi.clearAllMocks();
  hookReturn = { ...defaultHookReturn };
  for (const k of Object.keys(mockProgress)) delete mockProgress[k];
  sessionStorage.clear();
  localStorage.clear();
  // vi.clearAllMocks() clears call history but not a prior mockReturnValue override —
  // reset explicitly so physical mode defaults OFF for every test unless a case opts in.
  mockReadPhysicalMode.mockReturnValue(false);
  // Seed the prev/next sequence the units page would have written.
  sessionStorage.setItem(sequenceKey('15k', '手筋'), JSON.stringify(SEQUENCE));
});

describe('TsumegoProblemPage', () => {
  // ---- Existing behavior (still covered) ----
  it('renders category and level', () => {
    renderPage();
    expect(screen.getByText('手筋')).toBeInTheDocument();
    expect(screen.getByText('15 级')).toBeInTheDocument();
  });

  it('renders the physical-mode toggle', () => {
    renderPage();
    expect(screen.getByTestId('physical-mode-toggle')).toBeInTheDocument();
  });

  it('renders hint text', () => {
    renderPage();
    expect(screen.getByText('找到要点')).toBeInTheDocument();
  });

  it('renders board area', () => {
    renderPage();
    expect(screen.getByTestId('tsumego-board')).toBeInTheDocument();
  });

  it('renders timer and attempts', () => {
    renderPage();
    expect(screen.getByTestId('timer')).toHaveTextContent('0:42');
    expect(screen.getByTestId('attempts')).toHaveTextContent('1');
  });

  it('renders action buttons', () => {
    renderPage();
    expect(screen.getByText('悔棋')).toBeInTheDocument();
    expect(screen.getByText('重置')).toBeInTheDocument();
    expect(screen.getByText('提示')).toBeInTheDocument();
    expect(screen.getByText('试下')).toBeInTheDocument();
  });

  it('calls undo when button clicked', () => {
    renderPage();
    fireEvent.click(screen.getByText('悔棋'));
    expect(mockUndo).toHaveBeenCalled();
  });

  it('calls reset when button clicked', () => {
    renderPage();
    fireEvent.click(screen.getByText('重置'));
    expect(mockReset).toHaveBeenCalled();
  });

  it('calls toggleHint when button clicked', () => {
    renderPage();
    fireEvent.click(screen.getByText('提示'));
    expect(mockToggleHint).toHaveBeenCalled();
  });

  it('calls enterTryMode when try button clicked', () => {
    renderPage();
    fireEvent.click(screen.getByText('试下'));
    expect(mockEnterTryMode).toHaveBeenCalled();
  });

  it('shows success alert when solved', () => {
    hookReturn = { ...defaultHookReturn, isSolved: true };
    renderPage();
    expect(screen.getByText('正确!')).toBeInTheDocument();
  });

  it('shows error alert when failed', () => {
    hookReturn = { ...defaultHookReturn, isFailed: true };
    renderPage();
    expect(screen.getByText('不正确，请重试')).toBeInTheDocument();
  });

  it('shows try mode info alert', () => {
    hookReturn = { ...defaultHookReturn, isTryMode: true };
    renderPage();
    expect(screen.getByText('试下模式 - 自由探索')).toBeInTheDocument();
  });

  it('shows exit try mode button when in try mode', () => {
    hookReturn = { ...defaultHookReturn, isTryMode: true };
    renderPage();
    expect(screen.getByText('退出试下')).toBeInTheDocument();
  });

  it('calls exitTryMode when exit button clicked', () => {
    hookReturn = { ...defaultHookReturn, isTryMode: true };
    renderPage();
    fireEvent.click(screen.getByText('退出试下'));
    expect(mockExitTryMode).toHaveBeenCalled();
  });

  it('shows loading spinner when loading', () => {
    hookReturn = { ...defaultHookReturn, loading: true };
    renderPage();
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('shows error with back button on error', () => {
    hookReturn = { ...defaultHookReturn, error: 'Problem not found' };
    renderPage();
    expect(screen.getByText('Problem not found')).toBeInTheDocument();
    expect(screen.getByText('返回')).toBeInTheDocument();
  });

  it('changes hint button text when hint is shown', () => {
    hookReturn = { ...defaultHookReturn, showHint: true };
    renderPage();
    expect(screen.getByText('隐藏提示')).toBeInTheDocument();
  });

  // ---- Phase 4: prev/next navigation ----
  describe('prev/next navigation', () => {
    it('renders prev and next buttons', () => {
      renderPage();
      expect(screen.getByTestId('prev-problem')).toBeInTheDocument();
      expect(screen.getByTestId('next-problem')).toBeInTheDocument();
    });

    it('disables prev on the first problem in the sequence', () => {
      renderPage('p0');
      expect(screen.getByTestId('prev-problem')).toBeDisabled();
    });

    it('enables prev when not first', () => {
      renderPage('p1');
      expect(screen.getByTestId('prev-problem')).not.toBeDisabled();
    });

    it('navigates to the previous problem and flushes progress first', () => {
      renderPage('p1');
      fireEvent.click(screen.getByTestId('prev-problem'));
      expect(mockFlush).toHaveBeenCalled();
      expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tsumego/problem/p0');
      // flush must run BEFORE navigate.
      expect(mockFlush.mock.invocationCallOrder[0]).toBeLessThan(
        mockNavigate.mock.invocationCallOrder[0]
      );
    });

    it('navigates to the next problem and flushes progress first', () => {
      renderPage('p1');
      fireEvent.click(screen.getByTestId('next-problem'));
      expect(mockFlush).toHaveBeenCalled();
      expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tsumego/problem/p2');
      expect(mockFlush.mock.invocationCallOrder[0]).toBeLessThan(
        mockNavigate.mock.invocationCallOrder[0]
      );
    });

    it('on the last problem the next button becomes "返回单元" and navigates to the units page', () => {
      renderPage('p2');
      const nextBtn = screen.getByTestId('next-problem');
      expect(nextBtn).toHaveTextContent('返回单元');
      fireEvent.click(nextBtn);
      expect(mockFlush).toHaveBeenCalled();
      expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tsumego/15k/手筋');
    });

    it('back arrow flushes progress and returns to the units page', () => {
      renderPage('p1');
      // The header back-arrow button (icon-only) is the first button rendered.
      const backArrow = screen.getAllByRole('button')[0];
      fireEvent.click(backArrow);
      expect(mockFlush).toHaveBeenCalled();
      expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tsumego/15k/手筋');
    });
  });

  // ---- Phase 4: last-time display ----
  describe('last-time display', () => {
    it('does not show last-time when there is no prior record', () => {
      renderPage('p1');
      expect(screen.queryByTestId('last-time')).not.toBeInTheDocument();
    });

    it('shows last-time from progress[problemId].lastDuration', () => {
      mockProgress['p1'] = { completed: true, attempts: 2, lastDuration: 65 };
      renderPage('p1');
      const lastTime = screen.getByTestId('last-time');
      expect(lastTime).toBeInTheDocument();
      expect(lastTime).toHaveTextContent('1:05');
    });
  });

  // ---- Phase 4: SuccessOverlay + auto-advance ----
  describe('success overlay & auto-advance', () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });
    afterEach(() => {
      vi.runOnlyPendingTimers();
      vi.useRealTimers();
    });

    it('shows the success overlay message when solved', () => {
      hookReturn = { ...defaultHookReturn, isSolved: true };
      renderPage('p1');
      expect(screen.getByText('恭喜答对！')).toBeInTheDocument();
    });

    it('auto-advances to the next problem ~1.5s after solving (default ON)', () => {
      // auto-advance default is ON when the key is unset.
      hookReturn = { ...defaultHookReturn, isSolved: true };
      renderPage('p1'); // p1 has a next (p2)

      expect(mockNavigate).not.toHaveBeenCalled();
      act(() => {
        vi.advanceTimersByTime(1500);
      });
      expect(mockFlush).toHaveBeenCalled();
      expect(mockNavigate).toHaveBeenCalledWith('/kiosk/tsumego/problem/p2');
    });

    it('does NOT auto-advance when the preference is disabled', () => {
      localStorage.setItem(AUTO_ADVANCE_KEY, 'false');
      hookReturn = { ...defaultHookReturn, isSolved: true };
      renderPage('p1');

      act(() => {
        vi.advanceTimersByTime(3000);
      });
      expect(mockNavigate).not.toHaveBeenCalled();
    });

    it('does NOT auto-advance on the last problem (no next)', () => {
      localStorage.setItem(AUTO_ADVANCE_KEY, 'true');
      hookReturn = { ...defaultHookReturn, isSolved: true };
      renderPage('p2'); // p2 is the last → no next

      act(() => {
        vi.advanceTimersByTime(3000);
      });
      expect(mockNavigate).not.toHaveBeenCalled();
    });

    it('does NOT auto-advance while unsolved', () => {
      localStorage.setItem(AUTO_ADVANCE_KEY, 'true');
      hookReturn = { ...defaultHookReturn, isSolved: false };
      renderPage('p1');

      act(() => {
        vi.advanceTimersByTime(3000);
      });
      expect(mockNavigate).not.toHaveBeenCalled();
    });
  });

  // ---- Phase D: PhysicalStatePanel wiring behind readPhysicalMode (D1.3) ----
  describe('physical-state panel (D1.3)', () => {
    it('mounts PhysicalStatePanel starting at phase "setup" when physical mode is on', () => {
      mockReadPhysicalMode.mockReturnValue(true);
      renderPage('p1');
      const panel = screen.getByTestId('physical-state-panel');
      expect(panel).toBeInTheDocument();
      expect(panel).toHaveAttribute('data-phase', 'setup');
    });

    it('renders no PhysicalStatePanel when physical mode is off (default) and preserves existing testids', () => {
      renderPage('p1');
      expect(screen.queryByTestId('physical-state-panel')).not.toBeInTheDocument();
      // Existing surfaces must be unaffected by the D1.3 wiring.
      expect(screen.getByTestId('tsumego-board')).toBeInTheDocument();
      expect(screen.getByTestId('timer')).toBeInTheDocument();
      expect(screen.getByTestId('attempts')).toBeInTheDocument();
      expect(screen.getByTestId('prev-problem')).toBeInTheDocument();
      expect(screen.getByTestId('next-problem')).toBeInTheDocument();
    });
  });
});
