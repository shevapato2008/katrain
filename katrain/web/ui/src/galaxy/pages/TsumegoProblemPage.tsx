/**
 * TsumegoProblemPage - Main page for solving a tsumego problem
 *
 * Brings together the board, controls, and problem-solving logic.
 */

import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  CircularProgress,
  IconButton,
  Breadcrumbs,
  Link,
  Snackbar,
  Alert,
  useMediaQuery,
  useTheme
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { useSettings } from '../../context/SettingsContext';
import { useTranslation } from '../../hooks/useTranslation';
import { useSound } from '../../hooks/useSound';
import { useTsumegoProblem } from '../../hooks/useTsumegoProblem';
import type { MoveResult } from '../../hooks/useTsumegoProblem';
import TsumegoBoard from '../components/tsumego/TsumegoBoard';
import TsumegoProblemControls from '../components/tsumego/TsumegoProblemControls';
import SuccessOverlay from '../components/tsumego/SuccessOverlay';
import { MobileHeader, MobileToolbar } from '../components/tsumego/MobileControls';

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
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  // Problem list for navigation (loaded from localStorage or fetched)
  const [problemList, setProblemList] = useState<ProblemListItem[]>([]);
  const [currentIndex, setCurrentIndex] = useState(-1);

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

  const handleBack = () => {
    if (problem) {
      navigate(`/galaxy/tsumego/${problem.level}/${problem.category}`);
    } else {
      navigate('/galaxy/tsumego');
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

  // Shared board area with animations
  const boardArea = (
    <Box
      sx={{
        flexGrow: 1,
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        p: 0.5,
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
  );

  // Mobile layout: Header + Board + Toolbar
  if (isMobile) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden', bgcolor: '#0f0f0f' }}>
        {/* Mobile Header */}
        <MobileHeader
          level={problem.level}
          problemNumber={currentIndex + 1}
          totalProblems={problemList.length || 1}
          hint={problem.hint}
          nextPlayer={nextPlayer}
          isSolved={isSolved}
          isFailed={isFailed}
          isTryMode={isTryMode}
          onBack={handleBack}
        />

        {/* Board Area */}
        {boardArea}

        {/* Mobile Toolbar */}
        <MobileToolbar
          showHint={showHint}
          canUndo={moveHistory.length > 0 && !isSolved}
          hasPrevious={hasPrevious}
          hasNext={hasNext}
          isSolved={isSolved}
          isTryMode={isTryMode}
          onUndo={undo}
          onReset={reset}
          onToggleHint={toggleHint}
          onToggleTryMode={isTryMode ? exitTryMode : enterTryMode}
          onPrevious={handlePrevious}
          onNext={handleNext}
        />

        {/* Feedback Snackbar */}
        <Snackbar
          open={snackbar.open}
          autoHideDuration={3000}
          onClose={() => setSnackbar(prev => ({ ...prev, open: false }))}
          anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
        >
          <Alert
            severity={snackbar.severity}
            variant="filled"
            onClose={() => setSnackbar(prev => ({ ...prev, open: false }))}
          >
            {snackbar.message}
          </Alert>
        </Snackbar>
      </Box>
    );
  }

  // Desktop layout: Header + Board | Sidebar
  return (
    <Box sx={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* Main Area: Header + Board */}
      <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', bgcolor: '#0f0f0f' }}>
        {/* Header */}
        <Box sx={{ p: 1, bgcolor: 'rgba(0,0,0,0.3)', display: 'flex', alignItems: 'center', px: 2 }}>
          <IconButton onClick={handleBack} size="small" sx={{ mr: 1 }}>
            <ArrowBackIcon />
          </IconButton>
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
              {t(`tsumego:${problem.category}`)}
            </Link>
            <Typography variant="body2" color="text.primary">
              {t('tsumego:problem_n').replace('{n}', String(currentIndex + 1))}
            </Typography>
          </Breadcrumbs>
        </Box>

        {/* Board Area */}
        {boardArea}
      </Box>

      {/* Right Sidebar with Controls */}
      <Box
        sx={{
          width: 320,
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          bgcolor: 'background.paper',
          borderLeft: '1px solid rgba(255,255,255,0.05)'
        }}
      >
        <TsumegoProblemControls
          level={problem.level}
          category={problem.category}
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
          onPrevious={handlePrevious}
          onNext={handleNext}
          hasPrevious={hasPrevious}
          hasNext={hasNext}
        />
      </Box>

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
    </Box>
  );
};

export default TsumegoProblemPage;
