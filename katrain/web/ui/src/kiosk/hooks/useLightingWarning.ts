import { useCallback, useEffect, useRef, useState } from 'react';
import type { LightingReason } from '../../api/geometryApi';
import type { useVoice } from './useVoice';

/** A recognizing response can briefly omit the reason; it does not end the episode. */
export function useLightingWarning(reason: LightingReason | null, episodeKey: string, { speak, stop }: ReturnType<typeof useVoice>) {
  const lastEpisode = useRef<string | null>(null);
  const lastKey = useRef(episodeKey);
  const [visibleReason, setVisibleReason] = useState<LightingReason | null>(null);

  useEffect(() => {
    const keyChanged = lastKey.current !== episodeKey;
    lastKey.current = episodeKey;
    if (!reason) {
      if (keyChanged) {
        stop();
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setVisibleReason(null);
      }
      return;
    }
    const episode = `${episodeKey}:${reason}`;
    if (lastEpisode.current === episode) return;
    lastEpisode.current = episode;
    setVisibleReason(reason);
    speak(reason === 'frame_overexposed' ? 'lighting_overexposed' : 'lighting_underexposed');
  }, [episodeKey, reason, speak, stop]);

  const onClose = useCallback(() => { setVisibleReason(null); stop(); }, [stop]);
  return { reason: visibleReason, onClose };
}
