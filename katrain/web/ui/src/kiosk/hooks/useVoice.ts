// Voice prompts for physical-board tsumego (kiosk only). Pre-generated mp3 assets
// under /assets/sounds/voice/ (see scripts/generate_tsumego_voice.py).
// Non-blocking: playback failures are swallowed (audio is advisory).

import { useCallback, useRef } from 'react';

export type VoiceName =
  | 'clear_board'
  | 'place_black'
  | 'place_white'
  | 'setup_done'
  | 'correct'
  | 'wrong_remove'
  | 'capture_remove';

export function useVoice() {
  // Only one voice line at a time — new line interrupts the previous.
  const currentRef = useRef<HTMLAudioElement | null>(null);

  const speak = useCallback((name: VoiceName) => {
    if (currentRef.current) {
      currentRef.current.pause();
    }
    const audio = new Audio(`/assets/sounds/voice/${name}.mp3`);
    currentRef.current = audio;
    // HTMLMediaElement.play() returns a Promise in modern browsers, but the spec allows
    // undefined (older engines, jsdom) — guard before .catch so a missing Promise can't throw.
    const played = audio.play();
    if (played && typeof played.catch === 'function') {
      played.catch(() => {
        /* advisory only */
      });
    }
  }, []);

  return { speak };
}
