/**
 * SuccessOverlay — kiosk version (self-contained; does NOT import galaxy's overlay).
 *
 * Shows a celebratory overlay when a tsumego problem is solved. If `onComplete` is
 * provided, it fires after `delayMs` (default 1500ms) — Phase 4 uses this for the
 * "auto-advance to next problem" behaviour. The timer is cleaned up on unmount / when
 * `show` flips back to false, so it cannot leak or mis-fire (R5).
 */

import { useEffect, useState } from 'react';
import { Box, Typography } from '@mui/material';
import { keyframes } from '@mui/system';

interface SuccessOverlayProps {
  show: boolean;
  message?: string;
  /** Fired once after `delayMs` while shown — Phase 4 auto-advance hook. */
  onComplete?: () => void;
  /** Delay before onComplete fires (default 1500ms per D4). */
  delayMs?: number;
}

const fadeIn = keyframes`
  0% { opacity: 0; }
  100% { opacity: 1; }
`;

const pop = keyframes`
  0% { transform: scale(0.5); opacity: 0; }
  60% { transform: scale(1.12); opacity: 1; }
  100% { transform: scale(1); opacity: 1; }
`;

const confettiFall = keyframes`
  0% { transform: translateY(-12vh) rotate(0deg); opacity: 1; }
  100% { transform: translateY(100vh) rotate(540deg); opacity: 0; }
`;

const CONFETTI_COLORS = ['#58b57a', '#e0a24a', '#5b9bd5', '#e2685c', '#7ec994'];

interface ConfettiParticle {
  id: number;
  left: number;
  delay: number;
  duration: number;
  color: string;
  size: number;
  circle: boolean;
}

const SuccessOverlay = ({
  show,
  message = '恭喜答对！',
  onComplete,
  delayMs = 1500,
}: SuccessOverlayProps) => {
  // Confetti is randomized, so it can't be computed during render (must stay pure). Generate
  // a fresh batch in an effect each time the overlay becomes visible.
  const [particles, setParticles] = useState<ConfettiParticle[]>([]);

  useEffect(() => {
    if (!show) return;
    setParticles(
      Array.from({ length: 28 }).map((_, i) => ({
        id: i,
        left: 4 + Math.random() * 92,
        delay: Math.random() * 0.4,
        duration: 1.4 + Math.random() * 1,
        color: CONFETTI_COLORS[Math.floor(Math.random() * CONFETTI_COLORS.length)],
        size: 8 + Math.random() * 8,
        circle: Math.random() > 0.5,
      })),
    );
  }, [show]);

  // Auto-advance hook (R5): fire onComplete after delayMs while shown; clean up on hide/unmount.
  useEffect(() => {
    if (!show || !onComplete) return;
    const timer = setTimeout(onComplete, delayMs);
    return () => clearTimeout(timer);
  }, [show, onComplete, delayMs]);

  if (!show) return null;

  return (
    <Box
      sx={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        bgcolor: 'rgba(0,0,0,0.62)',
        zIndex: 100,
        animation: `${fadeIn} 0.25s ease-out`,
        pointerEvents: 'none',
      }}
    >
      {particles.map((p) => (
        <Box
          key={p.id}
          sx={{
            position: 'absolute',
            top: 0,
            left: `${p.left}%`,
            width: p.size,
            height: p.size,
            bgcolor: p.color,
            borderRadius: p.circle ? '50%' : '2px',
            animation: `${confettiFall} ${p.duration}s ease-out forwards`,
            animationDelay: `${p.delay}s`,
            boxShadow: '0 2px 4px rgba(0,0,0,0.25)',
          }}
        />
      ))}

      <Box sx={{ textAlign: 'center', animation: `${pop} 0.5s ease-out` }}>
        <Typography variant="h2" sx={{ mb: 1 }}>
          🎉
        </Typography>
        <Typography
          variant="h4"
          sx={{
            color: '#e8e4dc',
            fontWeight: 700,
            textShadow: '0 2px 8px rgba(0,0,0,0.5)',
          }}
        >
          {message}
        </Typography>
      </Box>
    </Box>
  );
};

export default SuccessOverlay;
