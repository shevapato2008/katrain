import { useState, useEffect, useCallback } from 'react';
import { Box, Typography, Grid, Card, CardActionArea, CircularProgress, Alert, Button, Chip } from '@mui/material';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowBack } from '@mui/icons-material';
import { useTranslation } from '../../hooks/useTranslation';

interface ProblemItem {
  id: string;
  category: string;
  hint: string;
}

const PAGE_SIZE = 50;

const TsumegoLevelPage = () => {
  const { levelId } = useParams<{ levelId: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [problems, setProblems] = useState<ProblemItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchPage = useCallback((pageNum: number, signal?: AbortSignal) => {
    const isFirst = pageNum === 1;
    if (isFirst) setLoading(true); else setLoadingMore(true);

    fetch(`/api/v1/tsumego/levels/${levelId}/problems?page=${pageNum}&page_size=${PAGE_SIZE}`, { signal })
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(data => {
        const items: ProblemItem[] = data.items ?? [];
        setProblems(prev => isFirst ? items : [...prev, ...items]);
        setTotal(data.total ?? 0);
        setPage(pageNum);
      })
      .catch(err => {
        if (err.name !== 'AbortError') {
          setError(err.message);
        }
      })
      .finally(() => {
        if (isFirst) setLoading(false); else setLoadingMore(false);
      });
  }, [levelId]);

  useEffect(() => {
    const controller = new AbortController();
    setProblems([]);
    setPage(1);
    setError(null);
    fetchPage(1, controller.signal);
    return () => controller.abort();
  }, [levelId, fetchPage]);

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
        <Button variant="outlined" onClick={() => { setError(null); fetchPage(1); }}>
          {t('Retry', '重试')}
        </Button>
      </Box>
    );
  }

  if (!loading && !error && problems.length === 0) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2, mt: 8 }}>
        <Typography variant="h6" color="text.secondary">{t('No problems for this level', '该难度暂无题目')}</Typography>
        <Button variant="outlined" onClick={() => navigate('/kiosk/tsumego')} startIcon={<ArrowBack />}>
          {t('Back', '返回')}
        </Button>
      </Box>
    );
  }

  const hasMore = problems.length < total;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 2, pt: 2, pb: 1 }}>
        <Button onClick={() => navigate('/kiosk/tsumego')} startIcon={<ArrowBack />} sx={{ minWidth: 40, p: 0.5 }} />
        <Box>
          <Typography variant="h5">{levelId?.toUpperCase()} {t('Level Problems', '级题目')}</Typography>
          <Typography variant="body2" color="text.secondary">
            {problems.length} / {total} {t('problems count', '道题目')}
          </Typography>
        </Box>
      </Box>
      <Box sx={{ flex: 1, overflow: 'auto', p: 2, pt: 1 }}>
        <Grid container spacing={2}>
          {problems.map((problem, idx) => (
            <Grid key={problem.id} size={{ xs: 6, sm: 4, md: 3 }}>
              <Card sx={{ bgcolor: 'rgba(255,255,255,0.05)', borderRadius: '12px', '&:hover': { bgcolor: 'rgba(255,255,255,0.08)' } }}>
                <CardActionArea onClick={() => navigate(`/kiosk/tsumego/problem/${problem.id}`)} sx={{ p: 2 }}>
                  <Typography variant="h6" sx={{ fontWeight: 600 }}>#{idx + 1}</Typography>
                  <Chip label={problem.category} size="small" sx={{ mt: 0.5 }} />
                  {problem.hint && (
                    <Typography variant="caption" sx={{ display: 'block', mt: 0.5, color: 'text.secondary' }}>{problem.hint}</Typography>
                  )}
                </CardActionArea>
              </Card>
            </Grid>
          ))}
        </Grid>
        {hasMore && (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
            <Button
              variant="outlined"
              onClick={() => fetchPage(page + 1)}
              disabled={loadingMore}
              startIcon={loadingMore ? <CircularProgress size={16} /> : undefined}
            >
              {loadingMore ? t('Loading', '加载中...') : t('Load more', '加载更多')}
            </Button>
          </Box>
        )}
      </Box>
    </Box>
  );
};

export default TsumegoLevelPage;
