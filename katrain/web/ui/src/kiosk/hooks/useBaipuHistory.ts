import { useCallback, useEffect, useMemo, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { BaipuHistoryAPI, type BaipuHistorySummary, type HistoryAuthority } from '../../api/baipuHistoryApi';
import { getProgress, listRecent, type BaipuProgress } from '../../api/baipuApi';
import { kioskActivityStorage } from '../storage/kioskActivityStorage';
export interface BaipuRecentItem {
  id: string; name: string; savedAt: number; progress: BaipuProgress | null;
  record?: BaipuHistorySummary;
}
/** Fetch by resolved owner, and never render a preceding owner's list during a switch. */
export function useBaipuHistory(active = false) {
  const { identityKey, token, isGuest, isLoading, status } = useAuth();
  const owner = isLoading ? null : isGuest ? 'guest' : identityKey;
  const [refresh, setRefresh] = useState(0);
  const [state, setState] = useState<{ owner: string | null; items: BaipuRecentItem[]; authority: HistoryAuthority | null; loading: boolean; error: string | null }>({ owner: null, items: [], authority: null, loading: true, error: null });
  const store = useMemo(() => kioskActivityStorage(null, true), []);
  useEffect(() => {
    const controller = new AbortController();
    let current = true;
    if (!owner) return () => controller.abort();
    if (owner === 'guest') {
      setState({ owner, items: listRecent(store).map(entry => ({ ...entry, progress: getProgress(entry.id, store) })), authority: null, loading: false, error: null });
      return () => controller.abort();
    }
    setState({ owner, items: [], authority: null, loading: true, error: null });
    BaipuHistoryAPI.list({ identityKey: owner, token, signal: controller.signal }).then(result => {
      if (current) setState({ owner, items: result.items.map(record => ({ id: record.id, name: record.name, savedAt: Date.parse(record.updated_at), progress: { k: record.k, total: record.total, frames: 0, updatedAt: Date.parse(record.updated_at) }, record })), authority: result.authority, loading: false, error: null });
    }).catch(error => {
      if (current) setState({ owner, items: [], authority: null, loading: false, error: error instanceof Error ? error.message : 'History unavailable' });
    });
    return () => { current = false; controller.abort(); };
  }, [owner, token, refresh, active, store]);
  const matching = state.owner === owner && owner !== null;
  return {
    items: matching ? state.items : [], authority: matching ? state.authority : null,
    loading: isLoading || (owner !== null && (!matching || state.loading)),
    error: !isLoading && !owner ? status ?? 'unavailable' : matching ? state.error : null,
    isGuest, refresh: useCallback(() => setRefresh(value => value + 1), []),
  };
}
