import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';

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
};

let hookReturn = { ...defaultHookReturn };

vi.mock('../../hooks/useTsumegoProblem', () => ({
  useTsumegoProblem: () => hookReturn,
}));

import TsumegoProblemPage from '../pages/TsumegoProblemPage';

const renderPage = () =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter initialEntries={['/kiosk/tsumego/problem/p1']}>
        <Routes>
          <Route path="/kiosk/tsumego/problem/:problemId" element={<TsumegoProblemPage />} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>
  );

beforeEach(() => {
  vi.clearAllMocks();
  hookReturn = { ...defaultHookReturn };
});

describe('TsumegoProblemPage', () => {
  it('renders category and level', () => {
    renderPage();
    expect(screen.getByText('手筋')).toBeInTheDocument();
    expect(screen.getByText('15K')).toBeInTheDocument();
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

  it('passes hint state to board when showHint is true', () => {
    hookReturn = { ...defaultHookReturn, showHint: true, hintCoords: [4, 4] as [number, number] };
    renderPage();
    // Hint is rendered on canvas, so we verify the hint button toggles to "hide" text
    expect(screen.getByText('隐藏提示')).toBeInTheDocument();
  });

  it('changes hint button text when hint is shown', () => {
    hookReturn = { ...defaultHookReturn, showHint: true };
    renderPage();
    expect(screen.getByText('隐藏提示')).toBeInTheDocument();
  });
});
