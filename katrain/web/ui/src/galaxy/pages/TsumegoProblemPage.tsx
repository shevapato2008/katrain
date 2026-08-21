/**
 * TsumegoProblemPage - Main page for solving a tsumego problem
 *
 * Brings together the board, controls, and problem-solving logic.
 *
 * 版式：走统一的 `BoardPageShell` —— 棋盘是唯一连续伸缩区域，棋盘正上方不放任何东西，
 * 右栏三段（模块牌 / 可滚中段 / 动作区）。迁版式前这里是桌面和移动**两套 JSX**：
 * 桌面版把返回箭头和面包屑压在棋盘正上方，移动版另有一套 `MobileHeader`/`MobileToolbar`。
 * 现在合成一套，横竖屏的差别由 shell 自己按 900px 断点处理，两套能力一个不少：
 * 返回 → 模块牌，上一题/下一题 → 动作区，撤销/重置/提示/试下 → 中段的工具格。
 */

import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  CircularProgress,
  Breadcrumbs,
  Link,
  Snackbar,
  Alert
} from '@mui/material';
import { useSettings } from '../../context/SettingsContext';
import { useTranslation } from '../../hooks/useTranslation';
import { useSound } from '../../hooks/useSound';
import { useTsumegoProblem } from '../../hooks/useTsumegoProblem';
import type { MoveResult } from '../../hooks/useTsumegoProblem';
import TsumegoBoard from '../../components/tsumego/TsumegoBoard';
import BoardPageShell from '../components/board/BoardPageShell';
import ModulePlate from '../components/layout/ModulePlate';
import TsumegoProblemControls, {
  TsumegoDisplayControls,
  TsumegoProblemActions,
} from '../components/tsumego/TsumegoProblemControls';
import SuccessOverlay from '../components/tsumego/SuccessOverlay';

interface ProblemListItem {
  id: string;
  level: string;
  category: string;
}

const TsumegoProblemPage: React.FC = () => {
  const { problemId } = useParams<{ problemId: string }>();
  const navigate = useNavigate();
  useSettings();
  const { t } = useTranslation();
  const { play: playSound } = useSound();

  // Problem list for navigation (loaded from localStorage or fetched)
  const [problemList, setProblemList] = useState<ProblemListItem[]>([]);
  const [currentIndex, setCurrentIndex] = useState(-1);

  // 坐标开关。默认开 —— 迁版式前 TsumegoBoard 是无条件画坐标的，这里保持原样。
  const [showCoordinates, setShowCoordinates] = useState(true);

  // Snackbar for move feedback
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: 'success' | 'error' | 'info';
  }>({
    open: false,
    message: '',
    severity: 'info'
  });

  // Animation state for wrong move shake
  const [isShaking, setIsShaking] = useState(false);

  // Use the tsumego problem hook
  const {
    problem,
    loading,
    error,
    boardSize,
    stones,
    lastMove,
    nextPlayer,
    moveHistory,
    isSolved,
    isFailed,
    isTryMode,
    elapsedTime,
    attempts,
    showHint,
    hintCoords,
    placeStone,
    undo,
    reset,
    toggleHint,
    enterTryMode,
    exitTryMode
  } = useTsumegoProblem(problemId || '');

  // Load problem list for navigation
  useEffect(() => {
    if (!problem) return;

    // Try to get cached problem list from session storage
    const cacheKey = `problems_${problem.level}_${problem.category}`;
    const cached = sessionStorage.getItem(cacheKey);

    if (cached) {
      const list = JSON.parse(cached) as ProblemListItem[];
      setProblemList(list);
      const idx = list.findIndex(p => p.id === problemId);
      setCurrentIndex(idx);
    } else {
      // Fetch problem list
      fetch(`/api/v1/tsumego/levels/${problem.level}/categories/${problem.category}?limit=100`)
        .then(res => res.json())
        .then((data: ProblemListItem[]) => {
          setProblemList(data);
          sessionStorage.setItem(cacheKey, JSON.stringify(data));
          const idx = data.findIndex(p => p.id === problemId);
          setCurrentIndex(idx);
        })
        .catch(console.error);
    }
  }, [problem, problemId]);

  // Handle stone placement
  const handlePlaceStone = (x: number, y: number) => {
    const result = placeStone(x, y);
    if (result) {
      // Play sound effect (except 'solved' which is handled by the isSolved effect)
      if (result.sound && result.type !== 'solved') {
        playSound(result.sound);
      }
      // Trigger shake animation for wrong moves
      if (result.type === 'incorrect') {
        setIsShaking(true);
        setTimeout(() => setIsShaking(false), 300);
      }
      showFeedback(result);
    }
  };

  // Show feedback snackbar
  const showFeedback = (result: MoveResult) => {
    switch (result.type) {
      case 'solved':
        // Don't show snackbar - the center overlay is already visible
        break;
      case 'incorrect':
        setSnackbar({
          open: true,
          message: result.message || t('tsumego:incorrect'),
          severity: 'error'
        });
        break;
      case 'correct':
        // Don't show snackbar for intermediate correct moves
        break;
      default:
        break;
    }
  };

  // Navigation handlers
  const handlePrevious = () => {
    if (currentIndex > 0) {
      navigate(`/galaxy/tsumego/problem/${problemList[currentIndex - 1].id}`);
    }
  };

  const handleNext = () => {
    if (currentIndex < problemList.length - 1) {
      navigate(`/galaxy/tsumego/problem/${problemList[currentIndex + 1].id}`);
    }
  };

  // Play victory sound when problem is solved
  useEffect(() => {
    if (isSolved) {
      playSound('solved');
    }
  }, [isSolved, playSound]);

  // Keyboard shortcuts
  const hasPrevious = currentIndex > 0;
  const hasNext = currentIndex < problemList.length - 1;

  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if typing in an input field
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      ) {
        return;
      }

      const key = e.key.toLowerCase();

      switch (key) {
        case 'u':
          e.preventDefault();
          undo();
          break;
        case 'z':
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            undo();
          }
          break;
        case 'r':
          e.preventDefault();
          reset();
          break;
        case 'h':
          e.preventDefault();
          toggleHint();
          break;
        case 'arrowleft':
        case '[':
          e.preventDefault();
          if (hasPrevious) handlePrevious();
          break;
        case 'arrowright':
        case ']':
          e.preventDefault();
          if (hasNext) handleNext();
          break;
        case 'enter':
          if (isSolved && hasNext) {
            e.preventDefault();
            handleNext();
          }
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [undo, reset, toggleHint, hasPrevious, hasNext, handlePrevious, handleNext, isSolved]);

  // Loading state
  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  // Error state
  if (error) {
    return (
      <Box sx={{ p: 4, textAlign: 'center' }}>
        <Typography variant="h5" color="error" gutterBottom>
          {t('tsumego:errorLoading')}
        </Typography>
        <Typography color="text.secondary">{error}</Typography>
      </Box>
    );
  }

  if (!problem) {
    return null;
  }

  const problemNumber = currentIndex + 1;
  const totalProblems = problemList.length || 1;
  const categoryLabel = t(`tsumego:${problem.category}`);

  // 面包屑在页面这一侧渲染 —— 导航是页面的事。按 spec §2.4 它不进页头，
  // 而是落到右栏中段的第一段。
  const breadcrumb = (
    <Breadcrumbs sx={{ '& .MuiBreadcrumbs-separator': { mx: 0.5 } }}>
      <Link
        component="button"
        variant="body2"
        onClick={() => navigate('/galaxy/tsumego')}
        sx={{ cursor: 'pointer' }}
      >
        {t('Tsumego')}
      </Link>
      <Link
        component="button"
        variant="body2"
        onClick={() => navigate(`/galaxy/tsumego/${problem.level}`)}
        sx={{ cursor: 'pointer' }}
      >
        {problem.level.toUpperCase()}
      </Link>
      <Link
        component="button"
        variant="body2"
        onClick={() => navigate(`/galaxy/tsumego/${problem.level}/${problem.category}`)}
        sx={{ cursor: 'pointer' }}
      >
        {categoryLabel}
      </Link>
      <Typography variant="body2" color="text.primary">
        {t('tsumego:problem_n').replace('{n}', String(problemNumber))}
      </Typography>
    </Breadcrumbs>
  );

  return (
    <>
      <BoardPageShell
        board={(
          <Box
            sx={{
              width: '100%',
              height: '100%',
              minWidth: 0,
              minHeight: 0,
              position: 'relative',
              animation: isShaking ? 'shake 0.3s ease-in-out' : 'none',
              '@keyframes shake': {
                '0%, 100%': { transform: 'translateX(0)' },
                '20%': { transform: 'translateX(-8px)' },
                '40%': { transform: 'translateX(8px)' },
                '60%': { transform: 'translateX(-6px)' },
                '80%': { transform: 'translateX(6px)' },
              }
            }}
          >
            <TsumegoBoard
              boardSize={boardSize}
              stones={stones}
              lastMove={lastMove}
              hintCoords={hintCoords}
              showHint={showHint}
              showCoordinates={showCoordinates}
              disabled={isSolved}
              moveHistory={moveHistory}
              showMoveNumbers={isTryMode}
              onPlaceStone={handlePlaceStone}
            />
            <SuccessOverlay
              show={isSolved}
              message={t('tsumego:solved')}
            />
          </Box>
        )}
        modulePlate={(
          <ModulePlate
            title={t('tsumego:problem_n').replace('{n}', String(problemNumber))}
            subtitle={`${problem.level.toUpperCase()} · ${categoryLabel} · ${problemNumber} / ${totalProblems}`}
            backTo={`/galaxy/tsumego/${problem.level}/${problem.category}`}
            backLabel={categoryLabel}
          />
        )}
        railBody={(
          <TsumegoProblemControls
            breadcrumb={breadcrumb}
            hint={problem.hint}
            showHint={showHint}
            isSolved={isSolved}
            isFailed={isFailed}
            isTryMode={isTryMode}
            elapsedTime={elapsedTime}
            attempts={attempts}
            nextPlayer={nextPlayer}
            canUndo={moveHistory.length > 0 && !isSolved}
            onUndo={undo}
            onReset={reset}
            onToggleHint={toggleHint}
            onEnterTryMode={enterTryMode}
            onExitTryMode={exitTryMode}
          />
        )}
        displayControls={(
          <TsumegoDisplayControls
            showCoordinates={showCoordinates}
            onToggleCoordinates={() => setShowCoordinates(prev => !prev)}
          />
        )}
        actions={(
          <TsumegoProblemActions
            isSolved={isSolved}
            hasPrevious={hasPrevious}
            hasNext={hasNext}
            onPrevious={handlePrevious}
            onNext={handleNext}
          />
        )}
      />

      {/* Feedback Snackbar */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={3000}
        onClose={() => setSnackbar(prev => ({ ...prev, open: false }))}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          severity={snackbar.severity}
          variant="filled"
          onClose={() => setSnackbar(prev => ({ ...prev, open: false }))}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </>
  );
};

export default TsumegoProblemPage;
