import { useState, useEffect, useCallback } from 'react';
import { Box, Typography, Grid, CircularProgress, Alert, Button, Chip } from '@mui/material';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from '../../hooks/useTranslation';
import { useTsumegoProgress } from '../../context/TsumegoProgressContext';
import ProblemCard from '../components/tsumego/ProblemCard';
import { UNIT_SIZE, sequenceKey } from './tsumegoUnits';
import SubPageBar from '../components/layout/SubPageBar';

interface ProblemSummary {
  id: string;
  level: string;
  category: string;
  hint: string;
  initialBlack: string[];
  initialWhite: string[];
}

/**
 * Route: tsumego/:level/:category/:unit — problem cards for one 20-problem unit.
 *
 * Fetches the unit's slice (offset=(unit-1)*20, limit=20) with initialBlack/initialWhite for
 * MiniBoard thumbnails. Ensures sessionStorage['problems_{level}_{category}'] is populated
 * (fetches the full ?limit=1000 list if missing) so the problem page has the prev/next sequence.
 */
const TsumegoUnitListPage = () => {
  const { level, category, unit } = useParams<{ level: string; category: string; unit: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { unitProgress } = useTsumegoProgress();

  const [problems, setProblems] = useState<ProblemSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const unitNumber = parseInt(unit || '1', 10);
  const offset = (unitNumber - 1) * UNIT_SIZE;

  const loadUnit = useCallback((lvl: string, cat: string, off: number, signal: AbortSignal) => {
    setLoading(true);
    setError(null);
    fetch(`/api/v1/tsumego/levels/${lvl}/categories/${cat}?offset=${off}&limit=${UNIT_SIZE}`, { signal })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: ProblemSummary[]) => {
        setProblems(Array.isArray(data) ? data : []);
        setLoading(false);
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          setError(err.message);
          setLoading(false);
        }
      });

    // Ensure the full category sequence is cached for prev/next (Phase 4). If a user
    // deep-links here without passing through the units page, fetch the full list once.
    const key = sequenceKey(lvl, cat);
    if (!sessionStorage.getItem(key)) {
      fetch(`/api/v1/tsumego/levels/${lvl}/categories/${cat}?limit=1000`, { signal })
        .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`HTTP ${res.status}`))))
        .then((data: ProblemSummary[]) => {
          if (Array.isArray(data)) {
            try {
              sessionStorage.setItem(key, JSON.stringify(data.map((p) => p.id)));
            } catch {
              /* best-effort */
            }
          }
        })
        .catch(() => {
          /* best-effort; problem page falls back to its own fetch */
        });
    }
  }, []);

  useEffect(() => {
    if (!level || !category) return;
    const controller = new AbortController();
    loadUnit(level, category, offset, controller.signal);
    return () => controller.abort();
  }, [level, category, offset, loadUnit]);

  const { completed: completedCount } = unitProgress(problems.map((p) => p.id));
  const startProblem = offset + 1;
  const endProblem = offset + problems.length;

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2, mt: 4 }}>
        <Alert severity="error">{error}</Alert>
        <Button
          variant="outlined"
          onClick={() => navigate(`/kiosk/tsumego/${level}/${category}`)}
        >
          {t('Back', '返回')}
        </Button>
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <SubPageBar
        title={`${t('tsumego:unit', '单元')} ${unitNumber} · ${startProblem}–${endProblem}`}
        to={`/kiosk/tsumego/${level}/${category}`}
        right={
          <Chip
            label={`${completedCount}/${problems.length}`}
            color={completedCount === problems.length && problems.length > 0 ? 'success' : 'default'}
            sx={{ fontSize: '0.95rem', px: 1 }}
          />
        }
      />

      <Box sx={{ flex: 1, overflow: 'auto', p: 2, pt: 1 }}>
        <Grid container spacing={2}>
          {problems.map((problem, index) => (
            <Grid size={{ xs: 6, sm: 4, md: 3 }} key={problem.id}>
              <ProblemCard
                problemId={problem.id}
                index={offset + index}
                initialBlack={problem.initialBlack}
                initialWhite={problem.initialWhite}
                onClick={() => navigate(`/kiosk/tsumego/problem/${problem.id}`)}
              />
            </Grid>
          ))}
        </Grid>
      </Box>
    </Box>
  );
};

export default TsumegoUnitListPage;
