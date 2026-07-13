import { useState, type ReactNode, type SyntheticEvent } from 'react';
import { Box, Button, Paper, Typography } from '@mui/material';
import { Refresh, VideocamOff } from '@mui/icons-material';

interface GeometryVideoPanelProps {
  title?: string;
  src?: string;
  alt: string;
  /** Fixed aspect ratio (e.g. "16 / 9"). Ignored when `fill` is set. */
  aspectRatio?: string;
  /** Fill the parent's height (single large preview) instead of using a fixed aspect ratio. */
  fill?: boolean;
  waitingText?: string;
  overlay?: ReactNode;
  onImageLoad?: (size: { width: number; height: number }) => void;
}

const GeometryVideoPanel = ({
  title,
  src,
  alt,
  aspectRatio,
  fill = false,
  waitingText,
  overlay,
  onImageLoad,
}: GeometryVideoPanelProps) => {
  const [streamError, setStreamError] = useState(false);
  const [streamKey, setStreamKey] = useState(0);

  const handleLoad = (event: SyntheticEvent<HTMLImageElement>) => {
    setStreamError(false);
    const image = event.currentTarget;
    if (image.naturalWidth && image.naturalHeight) {
      onImageLoad?.({ width: image.naturalWidth, height: image.naturalHeight });
    }
  };

  return (
    <Box sx={{ flex: 1, minWidth: 0, minHeight: 0, display: 'flex', flexDirection: 'column', gap: 1 }}>
      {title && <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>{title}</Typography>}
      <Paper
        elevation={2}
        sx={{
          width: '100%',
          ...(fill ? { flex: 1, minHeight: 0 } : { aspectRatio }),
          overflow: 'hidden',
          borderRadius: 2,
          bgcolor: 'grey.950',
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {!src ? (
          <Typography color="text.secondary" sx={{ px: 2, textAlign: 'center' }}>{waitingText}</Typography>
        ) : streamError ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1.5 }}>
            <VideocamOff color="error" sx={{ fontSize: 44 }} />
            <Typography color="error.light">视频流连接中断</Typography>
            <Button
              variant="outlined"
              color="error"
              startIcon={<Refresh />}
              onClick={() => { setStreamError(false); setStreamKey((value) => value + 1); }}
            >
              重试
            </Button>
          </Box>
        ) : (
          <img
            key={streamKey}
            src={src}
            alt={alt}
            onLoad={handleLoad}
            onError={() => setStreamError(true)}
            style={{ width: '100%', height: '100%', display: 'block', objectFit: 'contain' }}
          />
        )}
        {src && !streamError && overlay}
      </Paper>
    </Box>
  );
};

export default GeometryVideoPanel;
