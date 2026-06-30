import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Box,
  Typography,
  CircularProgress,
  Alert,
  Button,
  IconButton,
  Slider,
} from '@mui/material';
import { ArrowBack, NavigateBefore, NavigateNext } from '@mui/icons-material';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from '../../hooks/useTranslation';
import { TutorialReadAPI } from '../../api/tutorialApi';
import type { TutorialSectionDetail, TutorialFigure } from '../../types/tutorial';
import SGFBoard, { type SGFPayload } from '../../components/tutorials/SGFBoard';
import TutorialVideoPlayer from '../../components/tutorials/TutorialVideoPlayer';
import { useOrientation } from '../context/OrientationContext';
import type { SectionNavState } from '../types/tutorialNav';

/** Highest numeric move label on a figure's board (0 when there are none). */
function maxMoveOf(fig: TutorialFigure | null): number {
  return Math.max(
    0,
    ...Object.values(fig?.board_payload?.labels ?? {})
      .map(Number)
      .filter((n) => !Number.isNaN(n)),
  );
}

/**
 * Route: /kiosk/tutorial/section/:sectionId — the "study" page.
 *
 * Mirrors the galaxy figure view (read-only): step through the section's figures
 * (图 X / N), each showing its board with a 手数 replay slider plus that figure's
 * own video (figure.video_asset), narration and audio. We use the per-figure
 * `video_asset` field directly (no constructed section-level URL), and media is
 * loaded with `referrerPolicy="no-referrer"` so the hotlink-protected gateway
 * (which 403s a non-origin Referer) serves it to the board origin.
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
  const [index, setIndex] = useState(0);
  const [step, setStep] = useState<number | null>(null); // null → show all moves
  const [showFull, setShowFull] = useState(true); // default to the complete board (toggle to 局部 to zoom)

  const loadSection = useCallback((id: number, isCancelled: () => boolean) => {
    setLoading(true);
    setError(null);

    TutorialReadAPI.getSection(id)
      .then((data) => {
        if (isCancelled()) return;
        setSection(data);
        setIndex(0);
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

  // Figures that can be displayed (have a board). Stepping/nav is over these.
  const figures = useMemo(() => (section?.figures ?? []).filter((f) => f.board_payload), [section]);
  const current = figures[index] ?? null;
  const maxStep = useMemo(() => maxMoveOf(current), [current]);

  // Reset replay state whenever the active figure (or section) changes.
  useEffect(() => {
    setStep(null);
    setShowFull(true);
  }, [index, sectionId]);

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

  // Breadcrumb — never render `undefined`.
  const crumbParts = navState
    ? [navState.bookTitle, navState.chapterTitle, `${section.section_number}. ${section.title}`]
    : [t('tutorial:title', '教程'), `${section.section_number}. ${section.title}`];
  const breadcrumb = crumbParts.filter(Boolean).join(' ▸ ');

  const onBack = () =>
    navState?.bookId
      ? navigate('/kiosk/tutorial/book/' + navState.bookId)
      : navigate('/kiosk/tutorial');

  const goPrev = () => setIndex((i) => Math.max(0, i - 1));
  const goNext = () => setIndex((i) => Math.min(figures.length - 1, i + 1));
  const effStep = step ?? maxStep;

  if (figures.length === 0 || !current) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 2, pt: 2, pb: 1 }}>
          <Button onClick={onBack} startIcon={<ArrowBack />} sx={{ minWidth: 40, p: 0.5 }} />
          <Typography variant="subtitle1" sx={{ color: 'text.secondary' }} noWrap>
            {breadcrumb}
          </Typography>
        </Box>
        <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Typography color="text.secondary">{t('tutorial:noFigures', '本节暂无棋谱')}</Typography>
        </Box>
      </Box>
    );
  }

  // ── Board column: diagram + 手数 replay slider + 全盘/局部 toggle ──
  // The board fits its box by height (width auto, via CSS overriding SGFBoard's
  // width="100%"), so tall corner/side diagrams scale down instead of clipping.
  const boardArea = (
    <Box sx={{ flex: 1, minWidth: 0, minHeight: 0, display: 'flex', flexDirection: 'column', gap: 1 }}>
      <Box
        sx={{
          flex: 1,
          minHeight: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          overflow: 'hidden',
        }}
      >
        <SGFBoard
          payload={current.board_payload as SGFPayload}
          maxMoveStep={maxStep > 0 ? effStep : undefined}
          showFullBoard={showFull}
          style={{ height: '100%', width: 'auto', maxWidth: '100%' }}
        />
      </Box>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 2,
          width: '100%',
          maxWidth: 560,
          alignSelf: 'center',
          px: 1,
          flexShrink: 0,
        }}
      >
        <Button size="small" variant="outlined" onClick={() => setShowFull((v) => !v)} sx={{ flexShrink: 0 }}>
          {showFull ? t('tutorial:partial', '局部') : t('tutorial:fullBoard', '全盘')}
        </Button>
        {maxStep > 0 && (
          <>
            <Slider
              min={0}
              max={maxStep}
              value={effStep}
              onChange={(_, v) => setStep(v as number)}
              aria-label="move-step"
              sx={{ flex: 1 }}
            />
            <Typography variant="body2" sx={{ whiteSpace: 'nowrap', minWidth: 64, textAlign: 'right' }}>
              {t('tutorial:moves', '手数')} {effStep}/{maxStep}
            </Typography>
          </>
        )}
      </Box>
    </Box>
  );

  // ── Media column: this figure's video, filling its half. The teaching video
  // already carries the narration audio, so for video figures we give it all the
  // space; only figures WITHOUT a video fall back to the narration text + audio. ──
  const mediaArea = (
    <Box sx={{ flex: 1, minWidth: 0, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
      {current.video_asset ? (
        <TutorialVideoPlayer
          fill
          src={TutorialReadAPI.assetUrl(current.video_asset)}
          poster={TutorialReadAPI.assetUrl(current.video_asset.replace(/\.mp4$/, '.jpg'))}
        />
      ) : (
        <Box
          sx={{
            flex: 1,
            minHeight: 0,
            display: 'flex',
            flexDirection: 'column',
            gap: 1.5,
            overflow: 'auto',
            bgcolor: 'rgba(0,0,0,0.18)',
            borderRadius: 2,
            p: 2,
          }}
        >
          <Typography color="text.secondary">{t('tutorial:noVideo', '本图暂无视频')}</Typography>
          {current.narration && (
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.8, color: 'text.secondary' }}>
              {current.narration}
            </Typography>
          )}
          {current.audio_asset && (
            <audio
              key={current.audio_asset}
              src={TutorialReadAPI.assetUrl(current.audio_asset)}
              controls
              preload="none"
              style={{ width: '100%' }}
            />
          )}
        </Box>
      )}
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Header: back + breadcrumb */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 2, pt: 2, pb: 0.5 }}>
        <Button onClick={onBack} startIcon={<ArrowBack />} sx={{ minWidth: 40, p: 0.5 }} />
        <Typography variant="subtitle1" sx={{ color: 'text.secondary' }} noWrap>
          {breadcrumb}
        </Typography>
      </Box>

      {/* Figure navigation: ◀ 图X (i / N) ▶ */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1, py: 0.5 }}>
        <IconButton onClick={goPrev} disabled={index === 0} aria-label="上一图">
          <NavigateBefore />
        </IconButton>
        <Typography variant="subtitle1" sx={{ fontWeight: 600, minWidth: 140, textAlign: 'center' }}>
          {current.figure_label} ({index + 1} / {figures.length})
        </Typography>
        <IconButton onClick={goNext} disabled={index === figures.length - 1} aria-label="下一图">
          <NavigateNext />
        </IconButton>
      </Box>

      {/* Main: board | media */}
      <Box
        sx={{
          flex: 1,
          minHeight: 0,
          display: 'flex',
          flexDirection: isPortrait ? 'column' : 'row',
          gap: 2,
          px: 2,
          py: 1,
        }}
      >
        {boardArea}
        {mediaArea}
      </Box>
    </Box>
  );
};

export default TutorialSectionPage;
