import React, { useEffect, useRef, useState } from 'react';
import Box from '@mui/material/Box';
import IconButton from '@mui/material/IconButton';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';

interface AudioPlayerProps {
  src: string | null;
  autoPlay?: boolean;
  onEnded?: () => void;
}

export default function AudioPlayer({ src, autoPlay = false, onEnded }: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.pause();
    audio.load();
    setPlaying(false);
    if (autoPlay && src) {
      audio.play().then(() => setPlaying(true)).catch(() => {});
    }
  }, [src, autoPlay]);

  const toggle = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (playing) {
      audio.pause();
      setPlaying(false);
    } else {
      audio.play().then(() => setPlaying(true)).catch(() => {});
    }
  };

  if (!src) return null;

  return (
    <Box display="flex" alignItems="center" gap={1}>
      <audio
        ref={audioRef}
        src={src}
        onEnded={() => { setPlaying(false); onEnded?.(); }}
        onPause={() => setPlaying(false)}
        onPlay={() => setPlaying(true)}
      />
      <IconButton onClick={toggle} size="small" color="primary" aria-label={playing ? 'Pause' : 'Play'}>
        {playing ? <PauseIcon /> : <PlayArrowIcon />}
      </IconButton>
    </Box>
  );
}
