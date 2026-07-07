import { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  CircularProgress,
  Alert,
  Button,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
} from '@mui/material';
import { ArrowBack, ExpandMore, PlayCircleOutline } from '@mui/icons-material';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from '../../hooks/useTranslation';
import { TutorialReadAPI } from '../../api/tutorialApi';
import type { TutorialBookDetail, TutorialSection } from '../../types/tutorial';
import type { SectionNavState } from '../types/tutorialNav';

/**
 * Route: /kiosk/tutorial/book/:bookId — chapter/section tree for one book.
 *
 * READ-ONLY mirror: consumes only TutorialReadAPI (no write methods).
 *
 * On mount we load the book, then fetch ALL chapters' sections IN PARALLEL via
 * Promise.all (never serialized). A cancellation guard prevents a fast route
 * change from overwriting state with a stale response.
 */
const TutorialBookDetailPage = () => {
  const { bookId } = useParams<{ bookId: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();

  const [book, setBook] = useState<TutorialBookDetail | null>(null);
  // Sections keyed by chapter id.
  const [sectionsByChapter, setSectionsByChapter] = useState<Record<number, TutorialSection[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadBook = useCallback((id: number, isCancelled: () => boolean) => {
    setLoading(true);
    setError(null);
    setBook(null);
    setSectionsByChapter({});

    TutorialReadAPI.getBook(id)
      .then(async (detail) => {
        if (isCancelled()) return;
        // Fetch every chapter's sections in parallel — DO NOT serialize.
        const sectionLists = await Promise.all(
          detail.chapters.map((ch) => TutorialReadAPI.getSections(ch.id)),
        );
        if (isCancelled()) return;

        const byChapter: Record<number, TutorialSection[]> = {};
        detail.chapters.forEach((ch, i) => {
          byChapter[ch.id] = sectionLists[i];
        });

        setBook(detail);
        setSectionsByChapter(byChapter);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (isCancelled()) return;
        setError(err instanceof Error ? err.message : String(err));
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    if (!bookId) return;
    let cancelled = false;
    loadBook(Number(bookId), () => cancelled);
    return () => {
      cancelled = true;
    };
  }, [bookId, loadBook]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error || !book) {
    return (
      <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2, mt: 4 }}>
        <Alert severity="error">{error ?? t('tutorial:bookNotFound', '未找到该书籍')}</Alert>
        <Button
          variant="outlined"
          onClick={() => navigate(-1)}
          startIcon={<ArrowBack />}
        >
          {t('Back', '返回')}
        </Button>
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 2, pt: 2, pb: 1 }}>
        <Button
          onClick={() => navigate('/kiosk/tutorial/' + book.category)}
          startIcon={<ArrowBack />}
          sx={{ minWidth: 40, p: 0.5 }}
        />
        <Box>
          <Typography variant="h5">{book.title}</Typography>
          {book.author && (
            <Typography variant="body2" color="text.secondary">
              {book.author}
            </Typography>
          )}
        </Box>
      </Box>

      <Box sx={{ flex: 1, overflow: 'auto', p: 2, pt: 1 }}>
        {book.chapters.length === 0 ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', mt: 6 }}>
            <Typography variant="body1" color="text.secondary">
              {t('tutorial:noChapters', '本书暂无章节内容')}
            </Typography>
          </Box>
        ) : (
          book.chapters.map((ch) => {
            const sections = sectionsByChapter[ch.id] ?? [];
            return (
              <Accordion
                key={ch.id}
                defaultExpanded
                disableGutters
                sx={{
                  bgcolor: 'rgba(255,255,255,0.05)',
                  borderRadius: '12px',
                  mb: 1.5,
                  '&:before': { display: 'none' },
                }}
              >
                <AccordionSummary expandIcon={<ExpandMore />}>
                  <Typography variant="h6" sx={{ fontWeight: 600 }}>
                    {ch.chapter_number} {ch.title}
                  </Typography>
                </AccordionSummary>
                <AccordionDetails sx={{ pt: 0 }}>
                  {sections.length === 0 ? (
                    <Typography variant="body2" color="text.secondary" sx={{ px: 2, py: 1 }}>
                      {t('tutorial:noSections', '暂无')}
                    </Typography>
                  ) : (
                    <List disablePadding>
                      {sections.map((s) => {
                        const state: SectionNavState = {
                          bookId: book.id,
                          bookTitle: book.title,
                          bookSlug: book.slug,
                          chapterTitle: ch.title,
                          sectionTitle: s.title,
                          hasVideo: s.has_video,
                        };
                        return (
                          <ListItem key={s.id} disablePadding divider>
                            <ListItemButton
                              onClick={() => navigate('/kiosk/tutorial/section/' + s.id, { state })}
                              sx={{ minHeight: 48 }}
                            >
                              <ListItemText
                                primary={`${s.section_number}. ${s.title}`}
                                primaryTypographyProps={{ variant: 'body1' }}
                              />
                              <Box
                                sx={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: 1,
                                  ml: 2,
                                  flexShrink: 0,
                                }}
                              >
                                <Typography variant="body2" color="text.secondary">
                                  {s.figure_count} {t('tutorial:figures', '图')}
                                </Typography>
                                {s.has_video && <PlayCircleOutline sx={{ color: 'primary.main' }} />}
                              </Box>
                            </ListItemButton>
                          </ListItem>
                        );
                      })}
                    </List>
                  )}
                </AccordionDetails>
              </Accordion>
            );
          })
        )}
      </Box>
    </Box>
  );
};

export default TutorialBookDetailPage;
