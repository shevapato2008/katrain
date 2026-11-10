/**
 * useSound - Hook for playing sound effects
 *
 * Provides a simple API to play sounds with preloading for instant playback.
 * Sound effects are served from /assets/sounds/
 */

import { useCallback, useEffect, useRef } from 'react';

import {
  STONE_SOUND_TONE_KEY,
  readAudioPref,
  readStoneSoundPref,
  resolveStoneSoundUrl,
} from '../utils/audioPrefs';

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
  /** True only after the browser confirms playback. Existing fire-and-forget callers still work. */
  play: (name: SoundName, options?: { offsetSeconds?: number }) => Promise<boolean>;
  /** Only stops a singleton owned by this hook instance. */
  stop: (name: SoundName) => void;
  /** Call synchronously from a user gesture; never blocks starting a game. */
  unlock: () => Promise<boolean>;
}

type Attempt = { owner: symbol };
const attempts = new Map<SoundName, Attempt>();

export function useSound(): UseSoundReturn {
  const owner = useRef(Symbol('sound-owner')).current;

  const stop = useCallback((name: SoundName) => {
    if (attempts.get(name)?.owner !== owner) return;
    attempts.delete(name);
    const audio = audioCache[name];
    audio.pause();
    audio.currentTime = 0;
    audio.volume = 0.5;
  }, [owner]);

  useEffect(() => {
    preloadSounds();
    return () => { SINGLETON_SOUNDS.forEach(stop); };
  }, [stop]);

  const play = useCallback(async (name: SoundName, options?: { offsetSeconds?: number }): Promise<boolean> => {
    if (!readAudioPref('sfx')) return false;
    preloadSounds();
    const cached = audioCache[name];
    const singleton = SINGLETON_SOUNDS.has(name);
    let audio: HTMLAudioElement;
    if (name === 'stone') {
      let hasConfiguredTone = false;
      try {
        hasConfiguredTone = localStorage.getItem(STONE_SOUND_TONE_KEY) !== null;
      } catch {
        hasConfiguredTone = false;
      }
      const targetUrl = hasConfiguredTone
        ? resolveStoneSoundUrl(readStoneSoundPref())
        : resolveStoneSoundUrl('stone1');
      if (!targetUrl) return false;
      audio = targetUrl === SOUND_FILES.stone
        ? (cached.cloneNode() as HTMLAudioElement)
        : new Audio(targetUrl);
    } else {
      audio = singleton ? cached : (cached.cloneNode() as HTMLAudioElement);
    }
    const attempt: Attempt = { owner };
    if (singleton) {
      attempts.set(name, attempt);
      audio.pause();
      audio.currentTime = Math.max(0, options?.offsetSeconds ?? 0);
    }
    audio.volume = 0.5;
    try {
      await audio.play();
      if (singleton && attempts.get(name) !== attempt) return false;
      if (!readAudioPref('sfx')) {
        if (singleton) stop(name);
        else audio.pause();
        return false;
      }
      return true;
    } catch {
      if (singleton && attempts.get(name) === attempt) stop(name);
      return false;
    }
  }, [owner, stop]);

  const unlock = useCallback(async (): Promise<boolean> => {
    if (!readAudioPref('sfx')) return false;
    preloadSounds();
    const name = 'countdownbeep';
    // A gesture during real playback must not interrupt it (including another seat).
    if (attempts.has(name)) return false;
    const audio = audioCache[name];
    const attempt: Attempt = { owner };
    attempts.set(name, attempt);
    audio.volume = 0;
    try {
      await audio.play();
      if (attempts.get(name) !== attempt) return false;
      stop(name);
      return true;
    } catch {
      if (attempts.get(name) === attempt) stop(name);
      return false;
    }
  }, [owner, stop]);

  return { play, stop, unlock };
}

export default useSound;
