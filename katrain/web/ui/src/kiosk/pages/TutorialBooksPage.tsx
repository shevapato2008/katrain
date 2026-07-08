import { useState, useEffect, useCallback } from 'react';
import { Box, Typography, Grid, Card, CardActionArea, CircularProgress, Alert, Button } from '@mui/material';
import { ArrowBack } from '@mui/icons-material';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from '../../hooks/useTranslation';
import { TutorialReadAPI } from '../../api/tutorialApi';
import type { TutorialBook } from '../../types/tutorial';

/**
 * Route: tutorial/:category — the book list within a single tutorial category.
 *
 * READ-ONLY kiosk mirror: consumes only TutorialReadAPI (no write methods).
 */
const TutorialBooksPage = () => {
  const { category } = useParams<{ category: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();

  const [books, setBooks] = useState<TutorialBook[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadBooks = useCallback((cat: string, isCancelled: () => boolean) => {
    setLoading(true);
    setError(null);

    TutorialReadAPI.getBooks(cat)
      .then((data) => {
        if (isCancelled()) return;
        setBooks(data);
        setLoading(false);
      })
      .catch((err) => {
        if (isCancelled()) return;
        setError(err instanceof Error ? err.message : String(err));
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    if (!category) return;
    let cancelled = false;
    loadBooks(category, () => cancelled);
    return () => {
      cancelled = true;
    };
  }, [category, loadBooks]);

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
        <Button
          variant="outlined"
          onClick={() => category && loadBooks(category, () => false)}
          startIcon={<ArrowBack />}
        >
          {t('Retry', '重试')}
        </Button>
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 2, pt: 2, pb: 1 }}>
        <Button onClick={() => navigate('/kiosk/tutorial')} startIcon={<ArrowBack />} sx={{ minWidth: 40, p: 0.5 }} />
        <Box>
          <Typography variant="h5">
            {t('tutorial:selectBook', '选择书籍')}
          </Typography>
          {category && (
            <Typography variant="body2" color="text.secondary">
              {category}
            </Typography>
          )}
        </Box>
      </Box>

      <Box sx={{ flex: 1, overflow: 'auto', p: 2, pt: 1 }}>
        {books.length === 0 ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', mt: 6 }}>
            <Typography variant="body1" color="text.secondary">
              {t('tutorial:noBooks', '该分类暂无书籍')}
            </Typography>
          </Box>
        ) : (
          <Grid container spacing={2}>
            {books.map((book) => (
              <Grid key={book.id} size={{ xs: 6, sm: 4, md: 3 }}>
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
                    onClick={() => navigate(`/kiosk/tutorial/book/${book.id}`)}
                    sx={{ p: 2, height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}
                  >
                    <Typography variant="h6" sx={{ fontWeight: 600 }}>
                      {book.title}
                    </Typography>
                    {/* Fixed-height region (NOT minHeight): author is optional. Reserving a
                        single line of height whether or not it's present keeps every card
                        identical across the whole grid, not just within a flex-wrap row
                        (height:100% on the Card only equalizes within a row). */}
                    <Box sx={{ mt: 0.5, width: '100%', height: 20, overflow: 'hidden' }}>
                      {book.author && (
                        <Typography
                          variant="body2"
                          color="text.secondary"
                          sx={{ whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}
                        >
                          {book.author}
                        </Typography>
                      )}
                    </Box>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 1, color: 'primary.main' }}>
                      {book.chapter_count} {t('tutorial:chapters', '章')}
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

export default TutorialBooksPage;
