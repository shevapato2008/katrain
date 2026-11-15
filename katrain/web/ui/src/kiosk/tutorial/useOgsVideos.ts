import { useEffect, useState } from 'react';
import { TutorialReadAPI } from '../../api/tutorialApi';
import type { OgsVideoManifest } from '../../types/ogsVideo';

export function useOgsVideos() {
  const [manifest, setManifest] = useState<OgsVideoManifest | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => {
      controller.abort(); setManifest(null); setLoading(false); setError(true);
    }, 12000);
    TutorialReadAPI.getOgsVideoManifest(controller.signal).then(data => {
      window.clearTimeout(timeout);
      if (!controller.signal.aborted) { setManifest(data); setLoading(false); }
    }).catch(() => {
      window.clearTimeout(timeout);
      if (!controller.signal.aborted) { setManifest(null); setLoading(false); setError(true); }
    });
    return () => { window.clearTimeout(timeout); controller.abort(); };
  }, [revision]);
  return { manifest, error, loading, retry: () => {
    setLoading(true); setError(false); setRevision(n => n + 1);
  } };
}
