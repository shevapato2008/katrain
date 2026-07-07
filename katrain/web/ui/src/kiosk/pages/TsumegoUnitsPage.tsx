import { useState, useEffect, useCallback } from 'react';
import { Box, Typography, Card, CardActionArea, CircularProgress, Alert, Button } from '@mui/material';
import { ArrowBack } from '@mui/icons-material';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from '../../hooks/useTranslation';
import { useTsumegoProgress } from '../../context/TsumegoProgressContext';
import ProgressDots from '../components/tsumego/ProgressDots';
import { UNIT_SIZE, sequenceKey } from './tsumegoUnits';

interface ProblemSummary {
  id: string;
}

/**
 * Route: tsumego/:level/:category — 20-problem units within a category.
 *
 * Fetches ALL problem IDs (?limit=1000), groups by UNIT_SIZE=20, renders unit cards with
 * ProgressDots + completed/total (computed locally via unitProgress — cheap, full accuracy).
 *
 * CRITICAL CONTRACT for Phase 4: writes the ordered full category ID list to
 * sessionStorage['problems_{level}_{category}'] as a JSON string[] (in order) so the
 * problem page can compute prev/next without re-fetching.
 */
const TsumegoUnitsPage = () => {
  const { level, category } = useParams<{ level: string; category: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { unitProgress } = useTsumegoProgress();

  const [problemIds, setProblemIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadUnits = useCallback((lvl: string, cat: string, signal: AbortSignal) => {
    setLoading(true);
    setError(null);
    fetch(`/api/v1/tsumego/levels/${lvl}/categories/${cat}?limit=1000`, { signal })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: ProblemSummary[]) => {
        const ids = Array.isArray(data) ? data.map((p) => p.id) : [];
        setProblemIds(ids);
        // Phase 4 contract: persist the ordered sequence for prev/next.
        try {
          sessionStorage.setItem(sequenceKey(lvl, cat), JSON.stringify(ids));
        } catch {
          /* best-effort */
        }
        setLoading(false);
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          setError(err.message);
          setLoading(false);
        }
      });
  }, []);

  useEffect(() => {
    if (!level || !category) return;
    const controller = new AbortController();
    loadUnits(level, category, controller.signal);
    return () => controller.abort();
  }, [level, category, loadUnits]);

  const totalProblems = problemIds.length;
  const totalUnits = Math.ceil(totalProblems / UNIT_SIZE);

  const units = Array.from({ length: totalUnits }, (_, i) => {
    const start = i * UNIT_SIZE;
    const end = Math.min(start + UNIT_SIZE, totalProblems);
    const unitIds = problemIds.slice(start, end);
    const { completed } = unitProgress(unitIds);
    return {
      unitNumber: i + 1,
      startProblem: start + 1,
      endProblem: end,
      total: end - start,
      completed,
    };
  });

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
          onClick={() => navigate(`/kiosk/tsumego/${level}`)}
          startIcon={<ArrowBack />}
        >
          {t('Back', '返回')}
        </Button>
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 2, pt: 2, pb: 1 }}>
        <Button
          onClick={() => navigate(`/kiosk/tsumego/${level}`)}
          startIcon={<ArrowBack />}
          sx={{ minWidth: 40, p: 0.5 }}
        />
        <Box>
          <Typography variant="h5">
            {level?.toUpperCase()} {t(`tsumego:${category}`, category)} · {t('tsumego:selectUnit', '选择单元')}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {totalProblems} {t('tsumego:problems', '题')} · {totalUnits} {t('tsumego:unit', '单元')}
          </Typography>
        </Box>
      </Box>

      <Box sx={{ flex: 1, overflow: 'auto', p: 2, pt: 1 }}>
        <Box
          sx={{
            display: 'grid',
            gap: 1.5,
            gridTemplateColumns: { xs: 'repeat(2, 1fr)', sm: 'repeat(3, 1fr)', md: 'repeat(4, 1fr)' },
          }}
        >
          {units.map((unit) => {
            const isComplete = unit.completed === unit.total && unit.total > 0;
            return (
              <Card
                key={unit.unitNumber}
                sx={{
                  borderRadius: 2.5,
                  bgcolor: 'background.paper',
                  border: '2px solid',
                  borderColor: isComplete ? 'primary.main' : 'transparent',
                  transition: 'transform 0.15s ease, box-shadow 0.15s ease',
                  '&:hover': { transform: 'translateY(-2px)', boxShadow: 4 },
                }}
              >
                <CardActionArea
                  onClick={() => navigate(`/kiosk/tsumego/${level}/${category}/${unit.unitNumber}`)}
                  sx={{ p: 2 }}
                >
                  <Typography variant="h6" sx={{ fontWeight: 600 }}>
                    {t('tsumego:unit', '单元')} {unit.unitNumber}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                    {unit.startProblem}–{unit.endProblem}
                  </Typography>
                  <Box
                    sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mt: 1.5 }}
                  >
                    <ProgressDots completed={unit.completed} total={unit.total} />
                    <Typography
                      variant="body2"
                      sx={{ color: isComplete ? 'primary.main' : 'text.secondary', fontWeight: 500 }}
                    >
                      {unit.completed}/{unit.total}
                    </Typography>
                  </Box>
                </CardActionArea>
              </Card>
            );
          })}
        </Box>
      </Box>
    </Box>
  );
};

export default TsumegoUnitsPage;
