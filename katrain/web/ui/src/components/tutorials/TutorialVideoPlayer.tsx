import { useState, useEffect } from 'react';
import { Box, Typography } from '@mui/material';

interface Props {
  src: string;
  poster?: string;
  /** Fired once when the <video> element errors (e.g. media missing / 404). */
  onError?: () => void;
  /** When true, fill the parent box (height 100%, object-fit contain) instead of sizing by width. */
  fill?: boolean;
  maxHeight?: number | string;
}

/**
 * Shared HTML5 teaching-video player with graceful degradation. On a media
 * error it swaps to a "video unavailable" placeholder and notifies `onError`
 * so the host page can fall back.
 *
 * Kiosk note: media is served from a hotlink-protected gateway that 403s on a
 * non-origin `Referer`. The kiosk runs on the board origin (not the media
 * domain). `<video>`/`<audio>` do not honor a `referrerpolicy` attribute, so the
 * kiosk build strips the Referer document-wide via `<meta name="referrer"
 * content="no-referrer">` (injected in vite.config.ts) — the gateway's
 * "no Referer → allow" path then serves the bytes (and the poster).
 */
export default function TutorialVideoPlayer({ src, poster, onError, fill = false, maxHeight = '60vh' }: Props) {
  const [failed, setFailed] = useState(false);

  // Reset the failed state when the source changes (e.g. stepping to another figure),
  // so a previously-broken video doesn't keep the placeholder for a new, valid one.
  useEffect(() => {
    setFailed(false);
  }, [src]);

  if (failed) {
    return (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          p: 4,
          height: fill ? '100%' : 'auto',
          minHeight: 160,
          bgcolor: 'rgba(0,0,0,0.25)',
          borderRadius: 2,
        }}
      >
        <Typography color="text.secondary">视频加载失败</Typography>
      </Box>
    );
  }

  const fillStyle = { width: '100%', height: '100%', objectFit: 'contain' as const };
  const sizeStyle = { width: '100%', maxHeight };

  return (
    <video
      key={src}
      src={src}
      poster={poster}
      controls
      preload="none"
      onError={() => {
        setFailed(true);
        onError?.();
      }}
      style={{ ...(fill ? fillStyle : sizeStyle), background: '#000', borderRadius: 8, display: 'block' }}
    />
  );
}
