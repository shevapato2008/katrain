/**
 * useSound - Hook for playing sound effects
 *
 * Provides a simple API to play sounds with preloading for instant playback.
 * Sound effects are served from /assets/sounds/
 */

import { useCallback, useRef, useEffect } from 'react';

export type SoundName = 'stone' | 'capture' | 'correct' | 'incorrect' | 'solved';

const SOUND_FILES: Record<SoundName, string> = {
  stone: '/assets/sounds/stone1.wav',
  capture: '/assets/sounds/capturing.wav',
  correct: '/assets/sounds/stone2.wav',
  incorrect: '/assets/sounds/boing.wav',
  solved: '/assets/sounds/victory1.mp3',
};

// Preloaded audio cache (shared across hook instances)
const audioCache: Record<string, HTMLAudioElement> = {};
let preloaded = false;

function preloadSounds() {
  if (preloaded) return;
  preloaded = true;

  Object.entries(SOUND_FILES).forEach(([name, src]) => {
    const audio = new Audio(src);
    audio.preload = 'auto';
    audio.volume = 0.5;
    audioCache[name] = audio;
  });
}

export interface UseSoundReturn {
  play: (name: SoundName) => void;
  setEnabled: (enabled: boolean) => void;
  isEnabled: boolean;
}

export function useSound(): UseSoundReturn {
  const enabledRef = useRef(true);

  // Preload sounds on first hook mount
  useEffect(() => {
    preloadSounds();
  }, []);

  const play = useCallback((name: SoundName) => {
    if (!enabledRef.current) return;

    const audio = audioCache[name];
    if (audio) {
      // Clone to allow overlapping sounds
      const clone = audio.cloneNode() as HTMLAudioElement;
      clone.volume = 0.5;
      clone.play().catch(() => {
        // Ignore autoplay restrictions - user interaction will unlock audio
      });
    }
  }, []);

  const setEnabled = useCallback((enabled: boolean) => {
    enabledRef.current = enabled;
  }, []);

  return {
    play,
    setEnabled,
    isEnabled: enabledRef.current,
  };
}

export default useSound;
