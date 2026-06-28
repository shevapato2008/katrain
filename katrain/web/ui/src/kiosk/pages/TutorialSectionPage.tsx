import { useState, useEffect, useCallback } from 'react';
import { Box, Typography, CircularProgress, Alert, Button, Grid } from '@mui/material';
import { ArrowBack } from '@mui/icons-material';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from '../../hooks/useTranslation';
import { TutorialReadAPI } from '../../api/tutorialApi';
import type { TutorialSectionDetail, TutorialFigure } from '../../types/tutorial';
import { bookSlugFromFigures, sectionVideoUrl, sectionPosterUrl } from '../../utils/tutorialAssets';
import TutorialVideoPlayer from '../../components/tutorials/TutorialVideoPlayer';
import FigureThumb from '../components/tutorial/FigureThumb';
import FigureDialog from '../components/tutorial/FigureDialog';
import { useOrientation } from '../context/OrientationContext';
import type { SectionNavState } from '../types/tutorialNav';

/**
 * Route: /kiosk/tutorial/section/:sectionId — the core "study" page (Option B).
 *
 * Video-first + board-diagram panel. KEY (P0-1): we do NOT gate the video on the
 * section-detail `has_video` flag (that endpoint never computes it — it is always
 * false). Instead, if a book slug can be resolved (from router state on the normal
 * click path, or parsed from a figure asset path on deep-link/refresh), we TRY to
 * play the section video and degrade to "no video" only on a media error.
 *
 * READ-ONLY: consumes only TutorialReadAPI; no editing/admin UI.
 */
const TutorialSectionPage = () => {
  const { sectionId } = useParams<{ sectionId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  const { isPortrait } = useOrientation();

  const navState = (location.state ?? null) as SectionNavState | null;

  const [section, setSection] = useState<TutorialSectionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [videoFailed, setVideoFailed] = useState(false);
  const [openFigure, setOpenFigure] = useState<TutorialFigure | null>(null);

  const loadSection = useCallback((id: number, isCancelled: () => boolean) => {
    setLoading(true);
    setError(null);
    setVideoFailed(false);

    TutorialReadAPI.getSection(id)
      .then((data) => {
        if (isCancelled()) return;
        setSection(data);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (isCancelled()) return;
        setError(err instanceof Error ? err.message : String(err));
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    if (!sectionId) return;
    let cancelled = false;
    loadSection(Number(sectionId), () => cancelled);
    return () => {
      cancelled = true;
    };
  }, [sectionId, loadSection]);

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error || !section) {
    return (
      <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2, mt: 4 }}>
        <Alert severity="error">{error ?? t('tutorial:sectionNotFound', '未找到该小节')}</Alert>
        <Button variant="outlined" onClick={() => navigate('/kiosk/tutorial')} startIcon={<ArrowBack />}>
          {t('Back', '返回')}
        </Button>
      </Box>
    );
  }

  // Resolve book slug: prefer router state (normal click path), fall back to
  // parsing it from a figure asset path (deep-link / refresh).
  const slug = navState?.bookSlug ?? bookSlugFromFigures(section.figures);
  const numericId = Number(sectionId);
  const tryVideo = Boolean(slug) && !videoFailed; // NOT section.has_video

  // Breadcrumb — never render `undefined`. Use full crumb when state is present,
  // otherwise a short crumb rooted at "教程".
  const crumbParts = navState
    ? [navState.bookTitle, navState.chapterTitle, `${section.section_number}. ${section.title}`]
    : [t('tutorial:title', '教程'), `${section.section_number}. ${section.title}`];
  const breadcrumb = crumbParts.filter(Boolean).join(' ▸ ');

  const renderableFigures = section.figures.filter((f) => f.board_payload);

  const onBack = () =>
    navState?.bookId
      ? navigate('/kiosk/tutorial/book/' + navState.bookId)
      : navigate('/kiosk/tutorial');

  const videoArea = (
    <Box sx={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
      {tryVideo && slug ? (
        <TutorialVideoPlayer
          src={sectionVideoUrl(slug, numericId)}
          poster={sectionPosterUrl(slug, numericId)}
          onError={() => setVideoFailed(true)}
        />
      ) : (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: 160,
            bgcolor: 'rgba(0,0,0,0.25)',
            borderRadius: 2,
          }}
        >
          <Typography color="text.secondary">{t('tutorial:noVideo', '本节暂无视频')}</Typography>
        </Box>
      )}
    </Box>
  );

  const figuresArea = (
    <Box sx={{ flex: 1, minWidth: 0, overflow: 'auto' }}>
      <Typography variant="subtitle1" sx={{ mb: 1, fontWeight: 600 }}>
        {t('tutorial:figures', '本节棋谱')}
      </Typography>
      {renderableFigures.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          {t('tutorial:noFigures', '本节暂无棋谱')}
        </Typography>
      ) : (
        <Grid container spacing={1}>
          {renderableFigures.map((fig) => (
            <Grid key={fig.id} size={{ xs: 6, sm: 4, md: 3 }}>
              <FigureThumb figure={fig} onClick={() => setOpenFigure(fig)} />
            </Grid>
          ))}
        </Grid>
      )}
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 2, pt: 2, pb: 1 }}>
        <Button onClick={onBack} startIcon={<ArrowBack />} sx={{ minWidth: 40, p: 0.5 }} />
        <Typography variant="subtitle1" sx={{ color: 'text.secondary' }} noWrap>
          {breadcrumb}
        </Typography>
      </Box>

      <Box
        sx={{
          flex: 1,
          minHeight: 0,
          display: 'flex',
          flexDirection: isPortrait ? 'column' : 'row',
          gap: 2,
          p: 2,
          pt: 1,
        }}
      >
        {videoArea}
        {figuresArea}
      </Box>

      <FigureDialog figure={openFigure} open={!!openFigure} onClose={() => setOpenFigure(null)} />
    </Box>
  );
};

export default TutorialSectionPage;
