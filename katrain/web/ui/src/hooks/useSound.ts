/**
 * useSound - Hook for playing sound effects
 *
 * Provides a simple API to play sounds with preloading for instant playback.
 * Sound effects are served from /assets/sounds/
 */

import { useCallback, useEffect } from 'react';

import { readAudioPref } from '../utils/audioPrefs';

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
}

/**
 * ⚠️ 这里曾经有 `setEnabled` / `isEnabled`,它们**零个调用点**,而且关不掉声音:
 * `enabledRef` 是 `useRef`(每个 hook 实例各一份)而 `audioCache` 是模块级的 ——
 * A 组件静音,B 组件照响。开关搬到 `utils/audioPrefs`(模块级 + localStorage),
 * 用户出口是屏 27 设置的「声音」组。详见那个文件顶上的说明。
 */
export function useSound(): UseSoundReturn {
  // Preload sounds on first hook mount
  useEffect(() => {
    preloadSounds();
  }, []);

  const play = useCallback((name: SoundName) => {
    // **每次播放都现读**,不缓存进闭包:设置屏可以在任意一屏开着的时候被改。
    if (!readAudioPref('sfx')) return;

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

  return { play };
}

export default useSound;
