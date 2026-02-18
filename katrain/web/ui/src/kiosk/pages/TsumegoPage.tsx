import { Box, Typography, Grid, Card, CardActionArea } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { mockTsumegoLevels } from '../data/mocks';

const TsumegoPage = () => {
  const navigate = useNavigate();

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Title */}
      <Box sx={{ px: 2, pt: 2, pb: 1 }}>
        <Typography variant="h5">死活题</Typography>
        <Typography variant="body2" color="text.secondary">选择难度级别</Typography>
      </Box>

      {/* Level grid */}
      <Box sx={{ flex: 1, overflow: 'auto', p: 2, pt: 1 }}>
        <Grid container spacing={2}>
          {mockTsumegoLevels.map((level) => (
            <Grid key={level.id} size={{ xs: 6, sm: 4, md: 3 }}>
              <Card
                sx={{
                  bgcolor: 'rgba(255,255,255,0.05)',
                  borderRadius: '12px',
                  '&:hover': { bgcolor: 'rgba(255,255,255,0.08)' },
                  transition: 'background-color 0.15s ease',
                }}
              >
                <CardActionArea
                  onClick={() => navigate(`/kiosk/tsumego/${level.id}`)}
                  sx={{ p: 2 }}
                >
                  <Typography variant="h4" sx={{ color: '#5cb57a', fontWeight: 600 }}>
                    {level.rank}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                    {level.totalProblems} 题
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 1 }}>
                    {level.categories.map((cat) => (
                      <Typography key={cat.name} variant="caption" sx={{ color: 'text.secondary' }}>
                        {cat.name}: {cat.count}
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
