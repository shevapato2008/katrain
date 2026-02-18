import { useState, useEffect } from 'react';
import { Box, Typography, Grid, Card, CardActionArea, CircularProgress, Alert } from '@mui/material';
import { useNavigate } from 'react-router-dom';

interface LevelInfo {
  level: string;
  categories: Record<string, number>;
  total: number;
}

const TsumegoPage = () => {
  const navigate = useNavigate();
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
      <Box sx={{ p: 2 }}>
        <Alert severity="error">{error}</Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <Box sx={{ px: 2, pt: 2, pb: 1 }}>
        <Typography variant="h5">死活题</Typography>
        <Typography variant="body2" color="text.secondary">选择难度级别</Typography>
      </Box>
      <Box sx={{ flex: 1, overflow: 'auto', p: 2, pt: 1 }}>
        <Grid container spacing={2}>
          {levels.map((level) => (
            <Grid key={level.level} size={{ xs: 6, sm: 4, md: 3 }}>
              <Card
                sx={{
                  bgcolor: 'rgba(255,255,255,0.05)',
                  borderRadius: '12px',
                  '&:hover': { bgcolor: 'rgba(255,255,255,0.08)' },
                  transition: 'background-color 0.15s ease',
                }}
              >
                <CardActionArea
                  onClick={() => navigate(`/kiosk/tsumego/${level.level}`)}
                  sx={{ p: 2 }}
                >
                  <Typography variant="h4" sx={{ color: '#5cb57a', fontWeight: 600 }}>
                    {level.level.toUpperCase()}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                    {level.total} 题
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 1 }}>
                    {Object.entries(level.categories).map(([name, count]) => (
                      <Typography key={name} variant="caption" sx={{ color: 'text.secondary' }}>
                        {name}: {count}
                      </Typography>
                    ))}
                  </Box>
                </CardActionArea>
              </Card>
            </Grid>
          ))}
        </Grid>
      </Box>
    </Box>
  );
};

export default TsumegoPage;
