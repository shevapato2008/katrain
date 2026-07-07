import { useState, useEffect } from 'react';
import { Box, Typography, Grid, Card, CardActionArea, CircularProgress, Alert } from '@mui/material';
import { ArrowForward } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from '../../hooks/useTranslation';
import { readActiveSession } from '../utils/activeSession';
import { isDanLevel, readLastLevel } from './tsumegoUnits';

interface LevelInfo {
  level: string;
  categories: Record<string, number>;
  total: number;
}

/**
 * Route: tsumego — difficulty-level grid (entry point for the 5-level navigation).
 *
 * Navigates to /kiosk/tsumego/{level} (the categories page). Level-level "completed/total"
 * is intentionally NOT shown here: an accurate level completion count would require fetching
 * every problem ID for every level up-front, which is expensive on SBC terminals (R2 / §3.5).
 * We show only the total problem count + category breakdown (a weak summary, 弱汇总). Precise
 * per-category progress is computed one layer down (categories page) where the ID lists are
 * already needed for navigation.
 */
const TsumegoPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [levels, setLevels] = useState<LevelInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const resume = readActiveSession('practice');
  const lastLevel = readLastLevel();

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
      <Box sx={{ px: 2, pt: 2, pb: 1, display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 2 }}>
        <Box>
          <Typography variant="h5">{t('Tsumego', '死活题')}</Typography>
          <Typography variant="body2" color="text.secondary">
            {t('Select difficulty level', '选择难度级别')} · {t('Practice tsumego to improve your reading', '练习死活以提高计算力')}
          </Typography>
        </Box>
        {resume && (
          <Card
            data-testid="tsumego-resume-card"
            sx={{
              bgcolor: 'primary.dark',
              borderRadius: '12px',
              border: '1px solid',
              borderColor: 'primary.main',
              flexShrink: 0,
            }}
          >
            <CardActionArea
              onClick={() => navigate(resume.route)}
              sx={{ display: 'flex', alignItems: 'center', gap: 1.25, px: 1.75, py: 1 }}
            >
              <Box sx={{ width: 5, height: 24, borderRadius: '4px', bgcolor: 'primary.main', flexShrink: 0 }} />
              <Box>
                <Typography variant="subtitle2" sx={{ color: 'text.primary', fontWeight: 600 }}>
                  {t('Continue practicing', '继续练习')}
                </Typography>
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                  {resume.label}
                </Typography>
              </Box>
              <Box
                sx={{
                  width: 26,
                  height: 26,
                  borderRadius: '50%',
                  bgcolor: 'primary.main',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                <ArrowForward sx={{ fontSize: 16, color: 'background.default' }} />
              </Box>
            </CardActionArea>
          </Card>
        )}
      </Box>
      <Box sx={{ flex: 1, overflow: 'auto', p: 2, pt: 1 }}>
        <Grid container spacing={2}>
          {levels.map((level) => {
            const isLast = level.level === lastLevel;
            return (
              <Grid key={level.level} size={{ xs: 6, sm: 4, md: 3 }}>
                <Card
                  data-testid={`tsumego-level-card-${level.level}`}
                  sx={{
                    position: 'relative',
                    bgcolor: 'background.paper',
                    borderRadius: '12px',
                    '&:hover': { bgcolor: 'var(--raise2)' },
                    transition: 'background-color 0.15s ease',
                    ...(isLast ? { border: '2px solid', borderColor: 'primary.main' } : {}),
                  }}
                >
                  {isLast && (
                    <Box
                      sx={{
                        position: 'absolute',
                        top: 8,
                        right: 8,
                        zIndex: 1,
                        fontSize: '9.5px',
                        lineHeight: 1.6,
                        color: 'background.default',
                        bgcolor: 'primary.main',
                        borderRadius: '10px',
                        px: 0.9,
                      }}
                    >
                      {t('Last practiced', '上次')}
                    </Box>
                  )}
                  <CardActionArea
                    onClick={() => navigate(`/kiosk/tsumego/${level.level}`)}
                    sx={{ p: 2 }}
                  >
                    <Typography
                      variant="h4"
                      sx={{ color: isDanLevel(level.level) ? 'primary.main' : 'text.primary', fontWeight: 600 }}
                    >
                      {level.level.toUpperCase()}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                      {level.total} {t('problems', '题')}
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
            );
          })}
        </Grid>
      </Box>
    </Box>
  );
};

export default TsumegoPage;
