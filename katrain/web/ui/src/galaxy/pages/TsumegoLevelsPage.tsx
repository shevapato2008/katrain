import { useState, useEffect } from 'react';
import { Box, Typography, Grid, Card, CardContent, CardActionArea, CircularProgress, Alert } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useSettings } from '../context/SettingsContext';
import { useTranslation } from '../../hooks/useTranslation';

interface LevelInfo {
  level: string;
  categories: Record<string, number>;
  total: number;
}

const TsumegoLevelsPage = () => {
  const navigate = useNavigate();
  useSettings(); // Subscribe to settings changes
  const { t } = useTranslation();
  const [levels, setLevels] = useState<LevelInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('/api/v1/tsumego/levels')
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(data => {
        setLevels(data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load levels:', err);
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 4, maxWidth: 1200, mx: 'auto' }}>
        <Alert severity="error">
          {t('tsumego:loadError', 'Failed to load tsumego data. Please run: python scripts/generate_tsumego_index.py')}
        </Alert>
      </Box>
    );
  }

  if (levels.length === 0) {
    return (
      <Box sx={{ p: 4, maxWidth: 1200, mx: 'auto' }}>
        <Typography variant="h4" sx={{ mb: 1, fontWeight: 'bold' }}>{t('Tsumego')}</Typography>
        <Alert severity="info">
          {t('tsumego:noData', 'No tsumego problems available.')}
        </Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 4, maxWidth: 1200, mx: 'auto' }}>
      <Typography variant="h4" sx={{ mb: 1, fontWeight: 'bold' }}>
        {t('Tsumego')}
      </Typography>
      <Typography variant="subtitle1" color="text.secondary" sx={{ mb: 4 }}>
        {t('tsumego:selectLevel')}
      </Typography>

      <Grid container spacing={3}>
        {levels.map((level) => (
          <Grid size={{ xs: 6, sm: 4, md: 3 }} key={level.level}>
            <Card
              sx={{
                borderRadius: 3,
                transition: 'transform 0.2s, box-shadow 0.2s',
                '&:hover': {
                  transform: 'translateY(-4px)',
                  boxShadow: 8
                }
              }}
            >
              <CardActionArea onClick={() => navigate(`/galaxy/tsumego/${level.level}`)}>
                <CardContent sx={{ textAlign: 'center', py: 4 }}>
                  <Typography variant="h3" sx={{ fontWeight: 'bold', color: 'primary.main', mb: 1 }}>
                    {level.level.toUpperCase()}
                  </Typography>
                  <Typography variant="h6" color="text.secondary">
                    {level.total} {t('tsumego:problems')}
                  </Typography>
                  <Box sx={{ mt: 2, display: 'flex', justifyContent: 'center', gap: 1, flexWrap: 'wrap' }}>
                    {Object.entries(level.categories).map(([cat, count]) => (
                      <Typography key={cat} variant="caption" sx={{
                        px: 1,
                        py: 0.5,
                        bgcolor: 'action.hover',
                        borderRadius: 1
                      }}>
                        {t(`tsumego:${cat}`)}: {count}
                      </Typography>
                    ))}
                  </Box>
                </CardContent>
              </CardActionArea>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
};

export default TsumegoLevelsPage;
