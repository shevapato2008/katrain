/**
 * SuccessOverlay - Celebration overlay when a problem is solved
 *
 * Shows confetti animation and success message.
 */

import React, { useEffect, useState } from 'react';
import { Box, Typography } from '@mui/material';
import { keyframes } from '@mui/system';

interface SuccessOverlayProps {
  show: boolean;
  message?: string;
  onComplete?: () => void;
}

// Confetti falling animation
const confettiFall = keyframes`
  0% {
    transform: translateY(-10vh) rotate(0deg);
    opacity: 1;
  }
  100% {
    transform: translateY(100vh) rotate(720deg);
    opacity: 0;
  }
`;

// Text pulse animation
const textPulse = keyframes`
  0% {
    transform: scale(0.5);
    opacity: 0;
  }
  50% {
    transform: scale(1.1);
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
`;

// Fade in animation
const fadeIn = keyframes`
  0% {
    opacity: 0;
  }
  100% {
    opacity: 1;
  }
`;

const CONFETTI_COLORS = ['#e89639', '#4caf50', '#2196f3', '#f44336', '#9c27b0', '#ffeb3b'];

interface ConfettiParticle {
  id: number;
  left: number;
  delay: number;
  duration: number;
  color: string;
  size: number;
  shape: 'circle' | 'square';
}

const SuccessOverlay: React.FC<SuccessOverlayProps> = ({
  show,
  message = '恭喜答对！',
  onComplete
}) => {
  const [particles, setParticles] = useState<ConfettiParticle[]>([]);

  // Generate confetti particles when shown
  useEffect(() => {
    if (show) {
      const newParticles: ConfettiParticle[] = Array.from({ length: 30 }).map((_, i) => ({
        id: i,
        left: 5 + Math.random() * 90,
        delay: Math.random() * 0.5,
        duration: 1.5 + Math.random() * 1,
        color: CONFETTI_COLORS[Math.floor(Math.random() * CONFETTI_COLORS.length)],
        size: 8 + Math.random() * 8,
        shape: Math.random() > 0.5 ? 'circle' : 'square'
      }));
      setParticles(newParticles);

      // Call onComplete after animation
      if (onComplete) {
        const timer = setTimeout(onComplete, 2000);
        return () => clearTimeout(timer);
      }
    }
  }, [show, onComplete]);

  if (!show) return null;

  return (
    <Box
      sx={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        bgcolor: 'rgba(0, 0, 0, 0.6)',
        zIndex: 100,
        animation: `${fadeIn} 0.3s ease-out`,
        pointerEvents: 'none'
      }}
    >
      {/* Confetti particles */}
      {particles.map((particle) => (
        <Box
          key={particle.id}
          sx={{
            position: 'absolute',
            top: 0,
            left: `${particle.left}%`,
            width: particle.size,
            height: particle.size,
            bgcolor: particle.color,
            borderRadius: particle.shape === 'circle' ? '50%' : '2px',
            animation: `${confettiFall} ${particle.duration}s ease-out forwards`,
            animationDelay: `${particle.delay}s`,
            boxShadow: '0 2px 4px rgba(0,0,0,0.2)'
          }}
        />
      ))}

      {/* Success text */}
      <Box
        sx={{
          textAlign: 'center',
          animation: `${textPulse} 0.5s ease-out`,
        }}
      >
        <Typography
          variant="h3"
          sx={{
            color: '#4caf50',
            fontWeight: 'bold',
            textShadow: '0 4px 12px rgba(0, 0, 0, 0.5)',
            mb: 1
          }}
        >
          🎉
        </Typography>
        <Typography
          variant="h4"
          sx={{
            color: '#f5f3f0',
            fontWeight: 'bold',
            textShadow: '0 2px 8px rgba(0, 0, 0, 0.5)',
          }}
        >
          {message}
        </Typography>
      </Box>
    </Box>
  );
};

export default SuccessOverlay;
