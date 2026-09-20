/**
 * useSound - Hook for playing sound effects
 *
 * Provides a simple API to play sounds with preloading for instant playback.
 * Sound effects are served from /assets/sounds/
 */

import { useCallback, useEffect } from 'react';

import { readAudioPref } from '../utils/audioPrefs';

export type SoundName = 'stone' | 'capture' | 'correct' | 'incorrect' | 'solved' | 'countdownbeep';

const SOUND_FILES: Record<SoundName, string> = {
  stone: '/assets/sounds/stone1.wav',
  capture: '/assets/sounds/capturing.wav',
  correct: '/assets/sounds/stone2.wav',
  incorrect: '/assets/sounds/boing.wav',
  solved: '/assets/sounds/victory1.mp3',
  countdownbeep: '/assets/sounds/countdownbeep.wav',
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

/**
 * `countdownbeep.wav` is not a beep — it is a **5.000-second track containing five
 * beeps at 0/1/2/3/4 s**, i.e. the whole "last five seconds" cue, meant to be started
 * once when the window opens and stopped if the player moves inside it (that is what
 * the desktop app does: `gui/controlspanel.py:83,242-247`). Cloning it per call would
 * make five overlapping copies impossible to stop, so it plays on the single cached
 * element and is stoppable. Overlap is still wanted for stone/capture.
 */
const SINGLETON_SOUNDS: ReadonlySet<SoundName> = new Set<SoundName>(['countdownbeep']);

export interface UseSoundReturn {
  play: (name: SoundName) => void;
  /** Stop a singleton sound and rewind it. No-op for overlapping (cloned) sounds. */
  stop: (name: SoundName) => void;
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
    if (!audio) return;
    if (SINGLETON_SOUNDS.has(name)) {
      // Reuse the cached element: a clone cannot be stopped, and cloneNode() re-parses
      // the src on every call (measured on RK3562: play() → 'playing' 140–1065 ms).
      audio.pause();
      audio.currentTime = 0;
      audio.volume = 0.5;
      audio.play().catch(() => {});
      return;
    }
    // Clone to allow overlapping sounds
    const clone = audio.cloneNode() as HTMLAudioElement;
    clone.volume = 0.5;
    clone.play().catch(() => {
      // Ignore autoplay restrictions - user interaction will unlock audio
    });
  }, []);

  const stop = useCallback((name: SoundName) => {
    const audio = audioCache[name];
    if (!audio || !SINGLETON_SOUNDS.has(name)) return;
    audio.pause();
    audio.currentTime = 0;
  }, []);

  return { play, stop };
}

export default useSound;
