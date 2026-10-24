import { useId } from 'react';

/** The rounded diagonal seam shared by Kiosk player pairs. */
export function PlayerCardSurface({ left }: { left: boolean }) {
  const id = useId();
  return <svg className="ai-player-card__surface" viewBox="0 0 234 126" preserveAspectRatio="none" aria-hidden="true">
    <defs><linearGradient id={id} x2="0.8" y2="1">
      <stop className="ai-player-card__gradient-start" />
      <stop className="ai-player-card__gradient-end" offset="1" />
    </linearGradient></defs>
    <path d={left
      ? 'M14 1 H218 Q233 1 230 15 L214 111 Q211 125 197 125 H14 Q1 125 1 112 V14 Q1 1 14 1 Z'
      : 'M36 1 H220 Q233 1 233 14 V112 Q233 125 220 125 H17 Q1 125 4 111 L20 15 Q22 1 36 1 Z'}
      fill={`url(#${id})`} strokeWidth="1.5" />
  </svg>;
}
