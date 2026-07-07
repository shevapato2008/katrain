import { useState, useEffect, useCallback } from 'react';
import { Box, Typography, Grid, Card, CardActionArea, CircularProgress, Alert, Button } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from '../../hooks/useTranslation';
import { TutorialReadAPI } from '../../api/tutorialApi';
import type { TutorialCategory } from '../../types/tutorial';

/**
 * Route: /kiosk/tutorial — top-level tutorial landing page.
 *
 * READ-ONLY kiosk mirror of the galaxy tutorial module. Lists the tutorial
 * categories (e.g. 入门 / 定式 / 布局) sorted by `order`; tapping a card drills
 * into /kiosk/tutorial/:slug. This is a top-level nav page, so there is no back
 * button. Consumes only TutorialReadAPI — never the galaxy-admin write methods.
 */
const TutorialCategoriesPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();

  const [categories, setCategories] = useState<TutorialCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadCategories = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    TutorialReadAPI.getCategories()
      .then((data) => {
        if (cancelled) return;
        setCategories(data);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => loadCategories(), [loadCategories]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <CircularProgress sx={{ color: 'primary.main' }} />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2, mt: 4 }}>
        <Alert severity="error">{error}</Alert>
        <Button variant="outlined" onClick={() => loadCategories()}>
          {t('Retry', '重试')}
        </Button>
      </Box>
    );
  }

  const sorted = [...categories].sort((a, b) => a.order - b.order);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <Box sx={{ px: 2, pt: 2, pb: 1 }}>
        <Typography variant="h5">{t('tutorial:title', '教程')}</Typography>
        <Typography variant="body2" color="text.secondary">
          {t('tutorial:subtitle', '系统学习围棋')}
        </Typography>
      </Box>

      <Box sx={{ flex: 1, overflow: 'auto', p: 2, pt: 1 }}>
        {sorted.length === 0 ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', mt: 6 }}>
            <Typography variant="body1" color="text.secondary">
              {t('tutorial:empty', '暂无教程')}
            </Typography>
          </Box>
        ) : (
          <Grid container spacing={2}>
            {sorted.map((cat) => (
              <Grid key={cat.slug} size={{ xs: 6, sm: 4, md: 3 }}>
                <Card
                  sx={{
                    bgcolor: 'background.paper',
                    borderRadius: '12px',
                    height: '100%',
                    border: '1px solid',
                    borderColor: 'divider',
                    '&:hover': { bgcolor: 'var(--raise2)' },
                    transition: 'background-color 0.15s ease',
                  }}
                >
                  <CardActionArea
                    onClick={() => navigate(`/kiosk/tutorial/${cat.slug}`)}
                    sx={{ p: 2, height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}
                  >
                    <Typography variant="h6" sx={{ fontWeight: 600, color: 'primary.main' }}>
                      {cat.title}
                    </Typography>
                    {cat.summary && (
                      <Typography
                        variant="body2"
                        color="text.secondary"
                        sx={{
                          mt: 0.5,
                          display: '-webkit-box',
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: 'vertical',
                          overflow: 'hidden',
                        }}
                      >
                        {cat.summary}
                      </Typography>
                    )}
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>
                      {cat.book_count} {t('tutorial:booksUnit', '本')}
                    </Typography>
                  </CardActionArea>
                </Card>
              </Grid>
            ))}
          </Grid>
        )}
      </Box>
    </Box>
  );
};

export default TutorialCategoriesPage;
