import { useState, useEffect } from 'react';
import { Box, Typography, Grid, Card, CardContent, CardActionArea, CircularProgress } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useSettings } from '../context/SettingsContext';
import { i18n } from '../../i18n';

interface LevelInfo {
  level: string;
  categories: Record<string, number>;
  total: number;
}

const TsumegoLevelsPage = () => {
  const navigate = useNavigate();
  useSettings(); // Subscribe to translation changes
  const [levels, setLevels] = useState<LevelInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/v1/tsumego/levels')
      .then(res => res.json())
      .then(data => {
        setLevels(data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to load levels:', err);
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

  return (
    <Box sx={{ p: 4, maxWidth: 1200, mx: 'auto' }}>
      <Typography variant="h4" sx={{ mb: 1, fontWeight: 'bold' }}>
        {i18n.t('Tsumego', '死活题')}
      </Typography>
      <Typography variant="subtitle1" color="text.secondary" sx={{ mb: 4 }}>
        {i18n.t('tsumego:selectLevel', '选择难度级别')}
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
                    {level.total} {i18n.t('tsumego:problems', '题')}
                  </Typography>
                  <Box sx={{ mt: 2, display: 'flex', justifyContent: 'center', gap: 1, flexWrap: 'wrap' }}>
                    {Object.entries(level.categories).map(([cat, count]) => (
                      <Typography key={cat} variant="caption" sx={{
                        px: 1,
                        py: 0.5,
                        bgcolor: 'action.hover',
                        borderRadius: 1
                      }}>
                        {cat === 'life-death' ? '死活' : cat === 'tesuji' ? '手筋' : '官子'}: {count}
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
