import { useState, useEffect } from 'react';
import { Box, Typography, Grid, Card, CardActionArea, CircularProgress, Alert, Button, Chip } from '@mui/material';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowBack } from '@mui/icons-material';
import { useTranslation } from '../../hooks/useTranslation';

interface Problem {
  id: string;
  level: string;
  category: string;
  hint: string;
  initialBlack: string[];
  initialWhite: string[];
}

const TsumegoLevelPage = () => {
  const { levelId } = useParams<{ levelId: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [problems, setProblems] = useState<Problem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    fetch(`/api/v1/tsumego/levels/${levelId}/problems?limit=1000`, { signal: controller.signal })
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(data => {
        setProblems(Array.isArray(data) ? data : []);
      })
      .catch(err => {
        if (err.name !== 'AbortError') {
          setError(err.message);
        }
      })
      .finally(() => setLoading(false));

    return () => controller.abort();
  }, [levelId]);

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
        <Button variant="outlined" onClick={() => { setError(null); setLoading(true); }}>
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

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 2, pt: 2, pb: 1 }}>
        <Button onClick={() => navigate('/kiosk/tsumego')} startIcon={<ArrowBack />} sx={{ minWidth: 40, p: 0.5 }} />
        <Box>
          <Typography variant="h5">{levelId?.toUpperCase()} {t('Level Problems', '级题目')}</Typography>
          <Typography variant="body2" color="text.secondary">{problems.length} {t('problems count', '道题目')}</Typography>
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
      </Box>
    </Box>
  );
};

export default TsumegoLevelPage;
