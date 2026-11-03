import { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { BaipuHistoryAPI, BaipuHistoryError, type BaipuHistoryDetail } from '../../api/baipuHistoryApi';
import { cacheSgf, getCachedSgf, getProgress, saveProgress } from '../../api/baipuApi';
import { kioskActivityStorage } from '../storage/kioskActivityStorage';
interface Navigation { sgf?: string; name?: string; baipuIdentity?: string }
interface CursorMutation { k: number; expected_local_revision: number; mutation_id: string }
interface SessionContext {
  owner: string | null; source: string; token: string | null; historyId: string | null;
  controller: AbortController; sgf: string | null; name: string | null;
  record: BaipuHistoryDetail | null; total: number | null; opened: boolean; tail: Promise<void>;
  failedSave: CursorMutation | null;
  queued: { k: number; promise: Promise<void> } | null; pending: number; blocked: boolean; activity: number; opening: Promise<{ k: number; total: number } | null> | null;
}
interface State {
  context: SessionContext | null; sgf: string | null; name: string | null;
  loading: boolean; error: string | null; record: BaipuHistoryDetail | null;
  saving: boolean; saveError: string | null;
}
/** The physical interpreter calls open only after its authoritative load succeeds. */
export function useBaipuSessionHistory({ source, navigation }: { source: string; navigation: Navigation | null }) {
  const auth = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const owner = auth.isLoading ? null : auth.isGuest ? 'guest' : auth.identityKey;
  const historyId = new URLSearchParams(location.search).get('history');
  const context = useRef<SessionContext | null>(null);
  const route = useRef({ location, navigate });
  route.current = { location, navigate };
  const previous = context.current;
  if (!previous || previous.owner !== owner || previous.source !== source || previous.historyId !== historyId || previous.controller.signal.aborted) {
    previous?.controller.abort();
    context.current = { owner, source, token: auth.token, historyId, controller: new AbortController(), sgf: null, name: null, record: null, total: null, opened: false, tail: Promise.resolve(), failedSave: null, queued: null, pending: 0, blocked: false, activity: 0, opening: null };
  }
  const current = context.current!;
  // Credentials belong to this generation. A token refresh does not change ownership.
  current.token = auth.token;
  const [state, setState] = useState<State>({ context: null, sgf: null, name: null, loading: true, error: null, record: null, saving: false, saveError: null });
  const alive = useCallback((ctx: SessionContext) => context.current === ctx && !ctx.controller.signal.aborted, []);
  const patch = useCallback((ctx: SessionContext, values: Partial<State>) => {
    if (alive(ctx)) setState(old => ({ ...old, context: ctx, ...values }));
  }, [alive]);
  const credentials = (ctx: SessionContext) => ({ identityKey: ctx.owner!, token: ctx.token, signal: ctx.controller.signal });
  useEffect(() => {
    const ctx = current;
    if (!ctx.owner) return;
    if (ctx.record && ctx.record.id === historyId) return;
    setState({ context: ctx, sgf: null, name: null, record: null, loading: true, error: null, saving: false, saveError: null });
    if (historyId) {
      if (ctx.owner === 'guest' || !/^[a-f0-9]{64}$/.test(historyId)) {
        patch(ctx, { loading: false, error: 'Invalid account history' });
        return;
      }
      BaipuHistoryAPI.get(historyId, credentials(ctx)).then(record => {
        if (!alive(ctx)) return;
        ctx.record = record; ctx.sgf = record.sgf_content; ctx.name = record.name;
        patch(ctx, { record, sgf: ctx.sgf, name: ctx.name, loading: false });
      }).catch(error => patch(ctx, { loading: false, error: error instanceof Error ? error.message : 'History unavailable' }));
      return;
    }
    // A navigation payload is usable only by the identity that selected it.
    if (navigation?.sgf && navigation.baipuIdentity !== ctx.owner) {
      patch(ctx, { loading: false, error: 'The selected game belongs to another session' });
      return;
    }
    const cached = getCachedSgf(source, kioskActivityStorage(ctx.owner === 'guest' ? null : ctx.owner, ctx.owner === 'guest'));
    ctx.sgf = navigation?.sgf ?? cached?.sgf ?? null;
    ctx.name = navigation?.name ?? cached?.name ?? source;
    patch(ctx, { sgf: ctx.sgf, name: ctx.name, loading: false, error: ctx.sgf ? null : 'No game record is available' });
  }, [current, historyId, navigation?.sgf, navigation?.name, navigation?.baipuIdentity, source, alive, patch]);
  useEffect(() => () => { context.current?.controller.abort(); }, []);

  const open = useCallback((total: number): Promise<{ k: number; total: number } | null> => {
    const ctx = context.current!;
    if (!alive(ctx) || !ctx.owner || !ctx.sgf || !Number.isInteger(total) || total <= 0) return Promise.resolve(null);
    if (ctx.opening) return ctx.opening;
    const run = async () => {
      try {
        if (ctx.owner === 'guest') {
          const store = kioskActivityStorage(null, true);
          ctx.total = total;
          cacheSgf(ctx.source, ctx.name ?? ctx.source, ctx.sgf!, store);
          const progress = getProgress(ctx.source, store);
          return { k: Math.min(total, Math.max(0, progress?.k ?? 0)), total };
        }
        // Capture credentials before any await; a login cannot rebind this payload.
        const captured = credentials(ctx);
        const record = ctx.opened && ctx.record ? ctx.record : await BaipuHistoryAPI.open({
          sgf_content: ctx.sgf!, source_id: ctx.record?.source_id ?? ctx.source, name: ctx.name ?? ctx.source,
        }, captured);
        if (!alive(ctx)) return null;
        if (record.total !== total || record.replay_version !== 2) throw new Error('Saved replay does not match this game');
        ctx.total = total; ctx.opened = true; ctx.record = record; ctx.historyId = record.id;
        patch(ctx, { record, error: null });
        const { location: from, navigate: go } = route.current;
        const query = new URLSearchParams(from.search);
        if (query.get('history') !== record.id) {
          query.set('history', record.id);
          go({ pathname: from.pathname, search: `?${query}`, hash: from.hash }, { replace: true, state: from.state });
        }
        return { k: record.k, total: record.total };
      } catch (error) {
        patch(ctx, { error: error instanceof Error ? error.message : 'History unavailable' });
        return null;
      }
    };
    ctx.opening = run().finally(() => { ctx.opening = null; });
    return ctx.opening;
  }, [alive, patch]);

  const save = useCallback((k: number): Promise<void> => {
    const ctx = context.current!;
    if (!alive(ctx) || !ctx.owner || ctx.total == null || !Number.isInteger(k) || k < 0 || k > ctx.total) return Promise.resolve();
    ctx.activity += 1;
    if (ctx.owner === 'guest') {
      saveProgress(ctx.source, { k, total: ctx.total, frames: 0, updatedAt: Date.now() }, kioskActivityStorage(null, true));
      return Promise.resolve();
    }
    if (ctx.queued) {
      ctx.queued.k = k;
      return ctx.queued.promise;
    }
    if (ctx.pending === 0) ctx.blocked = false;
    ctx.pending += 1;
    // Once dispatched, a small keepalive PUT uses the API's own 10-second deadline.
    // Page cleanup still invalidates unsent work/results; it must not abort that write.
    const captured = { identityKey: ctx.owner!, token: ctx.token };
    const mutation_id = crypto.randomUUID();
    patch(ctx, { saving: true });
    const batch = { k, promise: Promise.resolve() };
    const work = ctx.tail.then(async () => {
      if (ctx.queued === batch) ctx.queued = null;
      if (!alive(ctx) || ctx.blocked || !ctx.record) return;
      const mutation = ctx.failedSave?.k === batch.k ? ctx.failedSave
        : { k: batch.k, expected_local_revision: ctx.record.local_revision, mutation_id };
      try {
        const record = await BaipuHistoryAPI.save(ctx.record.id, mutation, captured);
        if (!alive(ctx)) return;
        ctx.record = record;
        ctx.failedSave = null;
        patch(ctx, { record, saveError: null });
      } catch (error) {
        ctx.blocked = true;
        ctx.failedSave = error instanceof BaipuHistoryError && error.status < 500 ? null : mutation;
        if (error instanceof BaipuHistoryError && error.current && alive(ctx)) ctx.record = error.current;
        patch(ctx, { record: ctx.record, saveError: error instanceof Error ? error.message : 'Progress was not saved' });
      }
    });
    batch.promise = work;
    ctx.queued = batch;
    ctx.tail = work;
    void work.then(() => { ctx.pending -= 1; if (ctx.tail === work) patch(ctx, { saving: false }); });
    return work;
  }, [alive, patch]);

  const resolve = useCallback((strategy: 'use_cloud' | 'keep_local'): Promise<BaipuHistoryDetail | null> => {
    const ctx = context.current!;
    if (!alive(ctx) || !ctx.record || ctx.owner === 'guest') return Promise.resolve(null);
    // Resolution is an ordering boundary: later physical actions get their own slot.
    ctx.queued = null;
    const expected_local_revision = ctx.record.local_revision;
    const captured = credentials(ctx);
    const activity = ctx.activity;
    const id = ctx.record.id;
    patch(ctx, { saving: true });
    let result: BaipuHistoryDetail | null = null;
    const work = ctx.tail.then(async () => {
      if (!alive(ctx)) return;
      try {
        const record = await BaipuHistoryAPI.resolve(id, { strategy, expected_local_revision }, captured);
        if (!alive(ctx)) return;
        ctx.record = record;
        ctx.blocked = false;
        ctx.failedSave = null;
        patch(ctx, { record, saveError: null });
        // A later physical action supersedes this choice; callers must not move its cursor.
        if (ctx.activity === activity) result = record;
      } catch (error) {
        if (error instanceof BaipuHistoryError && error.current && alive(ctx)) ctx.record = error.current;
        patch(ctx, { record: ctx.record, saveError: error instanceof Error ? error.message : 'Resolution failed' });
      }
    });
    ctx.tail = work;
    return work.then(() => { if (ctx.tail === work) patch(ctx, { saving: false }); return result; });
  }, [alive, patch]);
  const visible = state.context === current;
  return {
    sgf: visible ? state.sgf : null, name: visible ? state.name : null,
    loading: auth.isLoading || (owner !== null && (!visible || state.loading)),
    error: !auth.isLoading && !owner ? 'Account identity unavailable' : visible ? state.error : null,
    historyId: visible ? state.record?.id ?? null : null, record: visible ? state.record : null,
    open, save, saving: visible && state.saving, saveError: visible ? state.saveError : null, resolve,
  };
}
