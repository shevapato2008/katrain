import { useState } from 'react';
import { Box, Typography } from '@mui/material';

interface Props {
  src: string;
  poster?: string;
  /** Fired once when the <video> element errors (e.g. media missing / 404). */
  onError?: () => void;
  maxHeight?: number | string;
}

/**
 * Shared HTML5 teaching-video player with graceful degradation. On a media
 * error it swaps to a "video unavailable" placeholder and notifies `onError`
 * so the host page can fall back (e.g. show only the board diagrams).
 *
 * Note: kiosk intentionally does NOT gate playback on the section-detail
 * `has_video` flag (that endpoint does not compute it). Callers try to play
 * whenever a slug is known and rely on `onError` to degrade.
 */
export default function TutorialVideoPlayer({ src, poster, onError, maxHeight = '60vh' }: Props) {
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          p: 4,
          minHeight: 160,
          bgcolor: 'rgba(0,0,0,0.25)',
          borderRadius: 2,
        }}
      >
        <Typography color="text.secondary">视频加载失败</Typography>
      </Box>
    );
  }

  return (
    <video
      src={src}
      poster={poster}
      controls
      preload="none"
      onError={() => {
        setFailed(true);
        onError?.();
      }}
      style={{ width: '100%', maxHeight, background: '#000', borderRadius: 8, display: 'block' }}
    />
  );
}
