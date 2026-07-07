import { useState, useEffect, useCallback } from 'react';
import { Box, Typography, Grid, Card, CardActionArea, CircularProgress, Alert, Button, useTheme } from '@mui/material';
import { alpha } from '@mui/material/styles';
import { ArrowBack, GridView, Extension, AutoAwesome, TrackChanges, Assignment } from '@mui/icons-material';
import type { SvgIconComponent } from '@mui/icons-material';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from '../../hooks/useTranslation';
import { useTsumegoProgress } from '../../context/TsumegoProgressContext';
import ProgressDots from '../components/tsumego/ProgressDots';

interface CategoryInfo {
  category: string;
  name: string;
  count: number;
}

interface ProblemSummary {
  id: string;
}

const CATEGORY_ICONS: Record<string, SvgIconComponent> = {
  'life-death': Extension,
  tesuji: AutoAwesome,
  endgame: TrackChanges,
};

/**
 * Route: tsumego/:level — categories within a difficulty level.
 *
 * Category-level completed/total is BEST-EFFORT (R2): the total `count` is shown
 * immediately from the categories endpoint, then each category's full ID list is
 * fetched in parallel (?limit=1000, non-blocking) and the "completed" count is
 * filled in via categoryProgress() once it resolves. The single shared `progress`
 * map is the only progress source — no per-page GET /progress.
 */
const TsumegoCategoriesPage = () => {
  const { level } = useParams<{ level: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { categoryProgress } = useTsumegoProgress();
  const theme = useTheme();

  const [categories, setCategories] = useState<CategoryInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Best-effort per-category ID lists (key = category slug). Filled lazily/non-blocking.
  const [categoryIds, setCategoryIds] = useState<Record<string, string[]>>({});

  const loadCategories = useCallback((lvl: string, signal: AbortSignal) => {
    setLoading(true);
    setError(null);
    setCategoryIds({});

    fetch(`/api/v1/tsumego/levels/${lvl}/categories`, { signal })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: CategoryInfo[]) => {
        setCategories(data);
        setLoading(false);

        // Non-blocking: fetch each category's IDs in parallel for completed counts.
        data.forEach((cat) => {
          fetch(`/api/v1/tsumego/levels/${lvl}/categories/${cat.category}?limit=1000`, { signal })
            .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`HTTP ${res.status}`))))
            .then((problems: ProblemSummary[]) => {
              if (Array.isArray(problems)) {
                setCategoryIds((prev) => ({ ...prev, [cat.category]: problems.map((p) => p.id) }));
              }
            })
            .catch(() => {
              /* best-effort: leave completed count blank for this category */
            });
        });
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          setError(err.message);
          setLoading(false);
        }
      });
  }, []);

  useEffect(() => {
    if (!level) return;
    const controller = new AbortController();
    loadCategories(level, controller.signal);
    return () => controller.abort();
  }, [level, loadCategories]);

  const totalCount = categories.reduce((sum, c) => sum + c.count, 0);

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
        <Button variant="outlined" onClick={() => navigate('/kiosk/tsumego')} startIcon={<ArrowBack />}>
          {t('Back', '返回')}
        </Button>
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 2, pt: 2, pb: 1 }}>
        <Button onClick={() => navigate('/kiosk/tsumego')} startIcon={<ArrowBack />} sx={{ minWidth: 40, p: 0.5 }} />
        <Box>
          <Typography variant="h5">
            {level?.toUpperCase()} {t('tsumego:selectCategory', '选择分类')}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {totalCount} {t('tsumego:problems', '题')}
          </Typography>
        </Box>
      </Box>

      <Box sx={{ flex: 1, overflow: 'auto', p: 2, pt: 1 }}>
        <Grid container spacing={2}>
          {/* "全部题目" shortcut → flat list at tsumego/{level}/all */}
          <Grid size={{ xs: 6, sm: 4, md: 3 }}>
            <Card
              sx={{
                bgcolor: alpha(theme.palette.primary.main, 0.10),
                border: `2px solid ${alpha(theme.palette.primary.main, 0.35)}`,
                borderRadius: '12px',
                height: '100%',
                '&:hover': { bgcolor: alpha(theme.palette.primary.main, 0.16) },
                transition: 'background-color 0.15s ease',
              }}
            >
              <CardActionArea
                onClick={() => navigate(`/kiosk/tsumego/${level}/all`)}
                sx={{ p: 2, height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <GridView sx={{ color: 'primary.main' }} />
                  <Typography variant="h6" sx={{ fontWeight: 600 }}>
                    {t('tsumego:allProblems', '全部题目')}
                  </Typography>
                </Box>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                  {totalCount} {t('tsumego:problems', '题')}
                </Typography>
              </CardActionArea>
            </Card>
          </Grid>

          {categories.map((cat) => {
            const ids = categoryIds[cat.category];
            const summary = ids ? categoryProgress(ids) : null;
            const CatIcon = CATEGORY_ICONS[cat.category] ?? Assignment;
            return (
              <Grid key={cat.category} size={{ xs: 6, sm: 4, md: 3 }}>
                <Card
                  sx={{
                    bgcolor: 'rgba(255,255,255,0.05)',
                    borderRadius: '12px',
                    height: '100%',
                    '&:hover': { bgcolor: 'rgba(255,255,255,0.08)' },
                    transition: 'background-color 0.15s ease',
                  }}
                >
                  <CardActionArea
                    onClick={() => navigate(`/kiosk/tsumego/${level}/${cat.category}`)}
                    sx={{ p: 2, height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}
                  >
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <CatIcon sx={{ fontSize: 28, color: 'primary.main' }} />
                      <Typography variant="h6" sx={{ fontWeight: 600 }}>
                        {t(`tsumego:${cat.category}`, cat.name)}
                      </Typography>
                    </Box>
                    <Box
                      sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', mt: 1.5 }}
                    >
                      <Typography variant="body2" color="text.secondary">
                        {summary ? `${summary.completed}/${summary.total}` : `${cat.count}`}{' '}
                        {t('tsumego:problems', '题')}
                      </Typography>
                      {summary && <ProgressDots completed={summary.completed} total={summary.total} />}
                    </Box>
                  </CardActionArea>
                </Card>
              </Grid>
            );
          })}
        </Grid>
      </Box>
    </Box>
  );
};

export default TsumegoCategoriesPage;
