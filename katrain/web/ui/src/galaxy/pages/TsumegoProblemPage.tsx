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
import { useSettings } from '../context/SettingsContext';
import { useTranslation } from '../../hooks/useTranslation';
import { useTsumegoProblem } from '../hooks/useTsumegoProblem';
import type { MoveResult } from '../hooks/useTsumegoProblem';
import TsumegoBoard from '../components/tsumego/TsumegoBoard';
import TsumegoProblemControls from '../components/tsumego/TsumegoProblemControls';

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
    elapsedTime,
    attempts,
    showHint,
    hintCoords,
    placeStone,
    undo,
    reset,
    toggleHint
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
      showFeedback(result);
    }
  };

  // Show feedback snackbar
  const showFeedback = (result: MoveResult) => {
    switch (result.type) {
      case 'solved':
        setSnackbar({
          open: true,
          message: result.message || t('tsumego:solved'),
          severity: 'success'
        });
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

  return (
    <Box sx={{ p: { xs: 2, md: 4 }, maxWidth: 1400, mx: 'auto', height: '100%' }}>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
        <IconButton onClick={handleBack} sx={{ mr: 1 }}>
          <ArrowBackIcon />
        </IconButton>
        <Breadcrumbs>
          <Link
            component="button"
            variant="body1"
            onClick={() => navigate('/galaxy/tsumego')}
            sx={{ cursor: 'pointer' }}
          >
            {t('Tsumego')}
          </Link>
          <Link
            component="button"
            variant="body1"
            onClick={() => navigate(`/galaxy/tsumego/${problem.level}`)}
            sx={{ cursor: 'pointer' }}
          >
            {problem.level.toUpperCase()}
          </Link>
          <Link
            component="button"
            variant="body1"
            onClick={() => navigate(`/galaxy/tsumego/${problem.level}/${problem.category}`)}
            sx={{ cursor: 'pointer' }}
          >
            {t(`tsumego:${problem.category}`)}
          </Link>
          <Typography color="text.primary">
            {t('tsumego:problem_n').replace('{n}', String(currentIndex + 1))}
          </Typography>
        </Breadcrumbs>
      </Box>

      {/* Main Content */}
      <Box
        sx={{
          display: 'flex',
          flexDirection: isMobile ? 'column' : 'row',
          gap: 3,
          height: isMobile ? 'auto' : 'calc(100vh - 180px)',
          minHeight: 500
        }}
      >
        {/* Board */}
        <Box
          sx={{
            flex: isMobile ? 'none' : 1,
            height: isMobile ? '60vw' : '100%',
            maxHeight: isMobile ? 500 : 'none',
            minHeight: 300
          }}
        >
          <TsumegoBoard
            boardSize={boardSize}
            stones={stones}
            lastMove={lastMove}
            hintCoords={hintCoords}
            showHint={showHint}
            disabled={isSolved}
            onPlaceStone={handlePlaceStone}
          />
        </Box>

        {/* Controls */}
        <Box
          sx={{
            width: isMobile ? '100%' : 280,
            flexShrink: 0,
            height: isMobile ? 'auto' : '100%'
          }}
        >
          <TsumegoProblemControls
            level={problem.level}
            category={problem.category}
            hint={problem.hint}
            showHint={showHint}
            isSolved={isSolved}
            isFailed={isFailed}
            elapsedTime={elapsedTime}
            attempts={attempts}
            nextPlayer={nextPlayer}
            canUndo={moveHistory.length > 0 && !isSolved}
            onUndo={undo}
            onReset={reset}
            onToggleHint={toggleHint}
            onPrevious={handlePrevious}
            onNext={handleNext}
            hasPrevious={currentIndex > 0}
            hasNext={currentIndex < problemList.length - 1}
          />
        </Box>
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
