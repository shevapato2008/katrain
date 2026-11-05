import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react';
import { readAudioPref, subscribeAudioPref } from '../utils/audioPrefs';
import { useSound } from './useSound';

const readSfx = () => readAudioPref('sfx');

/** Receives the existing clock reading; owns only the current five-second audio window. */
export function useByoyomiCountdownSound(secondsLeft: number | null, eligible: boolean, identity: string) {
  const { play, stop, unlock } = useSound();
  const sfx = useSyncExternalStore(subscribeAudioPref, readSfx);
  const [visible, setVisible] = useState(() => document.visibilityState !== 'hidden');
  const inWindow = eligible && secondsLeft !== null && secondsLeft > 0 && secondsLeft <= 5;
  const latest = useRef({ secondsLeft, inWindow, identity });
  latest.current = { secondsLeft, inWindow, identity };
  const attempt = useRef({ generation: 0, pending: false, started: false });

  const cancel = useCallback(() => {
    attempt.current = { generation: attempt.current.generation + 1, pending: false, started: false };
    stop('countdownbeep');
  }, [stop]);

  const start = useCallback(() => {
    const current = latest.current;
    if (!current.inWindow || !readSfx() || document.visibilityState === 'hidden'
      || attempt.current.pending || attempt.current.started) return;
    const generation = attempt.current.generation;
    const windowId = current.identity;
    attempt.current.pending = true;
    const offsetSeconds = Math.max(0, Math.min(5, 5 - current.secondsLeft!));
    void play('countdownbeep', { offsetSeconds }).then((played) => {
      if (attempt.current.generation !== generation || latest.current.identity !== windowId) return;
      attempt.current.pending = false;
      if (!latest.current.inWindow || !readSfx() || document.visibilityState === 'hidden') {
        cancel();
        return;
      }
      attempt.current.started = played;
    }).catch(() => {
      // A rejected attempt remains retryable in this window on the next real gesture.
      if (attempt.current.generation === generation) attempt.current.pending = false;
    });
  }, [play, cancel]);

  useEffect(() => {
    if (inWindow && sfx && visible) start();
    return cancel;
  }, [identity, inWindow, sfx, visible, start, cancel]);

  useEffect(() => {
    const onVisibility = () => {
      const shown = document.visibilityState !== 'hidden';
      if (!shown) cancel();
      setVisible(shown);
    };
    const onGesture = (event: Event) => {
      if (!event.isTrusted || !readSfx() || document.visibilityState === 'hidden') return;
      if (latest.current.inWindow) start();
      else void unlock();
    };
    document.addEventListener('visibilitychange', onVisibility);
    document.addEventListener('pointerdown', onGesture);
    document.addEventListener('keydown', onGesture);
    return () => {
      document.removeEventListener('visibilitychange', onVisibility);
      document.removeEventListener('pointerdown', onGesture);
      document.removeEventListener('keydown', onGesture);
    };
  }, [cancel, start, unlock]);
}
