import { useCallback, useEffect, useRef, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { membershipApi } from '../../api/membershipApi';
import { createServerClock, remainingSeconds, type ServerClock } from './presentation';
import type { MembershipCatalog, MembershipUsage } from './types';

export const MEMBERSHIP_REFRESH_MS = 15_000;
const CHANGED_EVENT = 'membership:changed';
/** Call after a settled consumption or server-confirmed payment, never to grant local credit. */
export const notifyMembershipChanged = () => window.dispatchEvent(new Event(CHANGED_EVENT));

export type MembershipStatus = 'loading' | 'ready' | 'error' | 'unavailable' | 'unauthenticated';
interface Snapshot {
  scope: string;
  catalog: MembershipCatalog | null;
  usage: MembershipUsage | null;
  status: MembershipStatus;
  error: unknown;
  clock: ServerClock | null;
}
export interface UseMembershipOptions { environment?: string; enabled?: boolean; visible?: boolean }

export function useMembership({ environment, enabled = true, visible = true }: UseMembershipOptions = {}) {
  const { identityKey, status: authStatus, token } = useAuth();
  const authenticated = authStatus === 'authenticated' && identityKey !== null;
  const scope = JSON.stringify([identityKey, authStatus, environment ?? 'server']);
  const scopeRef = useRef(scope);
  scopeRef.current = scope;
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const snapshotRef = useRef<Snapshot | null>(null);
  const requestSequence = useRef(0);
  const activeRequest = useRef<AbortController | null>(null);
  const crossedBoundaries = useRef(new Set<string>());
  const [monotonicNow, setMonotonicNow] = useState(() => performance.now());

  const refresh = useCallback(async () => {
    if (!enabled || !authenticated || scopeRef.current !== scope) return;
    const sequence = ++requestSequence.current;
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    const current = () => scopeRef.current === scope && requestSequence.current === sequence && !controller.signal.aborted;
    try {
      const [catalog, usage] = await Promise.all([
        membershipApi.getCatalog(token, controller.signal),
        membershipApi.getUsage(token, controller.signal),
      ]);
      if (!current()) return;
      if (catalog.environment !== usage.environment || (environment !== undefined && usage.environment !== environment)
        || !['test', 'production', 'development'].includes(usage.environment?.toLowerCase())
        || catalog.catalog_version !== usage.catalog_version || !Number.isSafeInteger(usage.revision)
        || !Number.isFinite(Date.parse(usage.server_now)) || typeof usage.capabilities?.usage !== 'boolean') {
        throw new Error('Membership snapshot could not be verified');
      }
      const previous = snapshotRef.current?.scope === scope ? snapshotRef.current : null;
      if (previous?.usage && previous.usage.environment !== usage.environment) {
        snapshotRef.current = null;
        throw new Error('Membership environment changed; reload this account');
      }
      if (previous?.usage && usage.revision < previous.usage.revision) return;
      const now = performance.now();
      const clock = createServerClock(usage.server_now, now);
      // A retry returning the same snapshot must not wind an already running countdown back.
      if (previous?.clock) clock.epochMs = Math.max(clock.epochMs, previous.clock.epochMs + Math.max(0, now - previous.clock.monotonicMs));
      const next: Snapshot = { scope, catalog, usage, clock, status: usage.capabilities.usage ? 'ready' : 'unavailable', error: null };
      snapshotRef.current = next;
      setSnapshot(next);
      setMonotonicNow(now);
    } catch (error) {
      if (!current()) return;
      const previous = snapshotRef.current?.scope === scope ? snapshotRef.current : null;
      const next: Snapshot = { scope, catalog: previous?.catalog ?? null, usage: previous?.usage ?? null,
        clock: previous?.clock ?? null, status: 'error', error };
      snapshotRef.current = next;
      setSnapshot(next);
    } finally {
      if (activeRequest.current === controller) activeRequest.current = null;
    }
  }, [authenticated, enabled, environment, scope, token]);

  useEffect(() => {
    snapshotRef.current = null;
    setSnapshot(null);
    crossedBoundaries.current.clear();
    void refresh();
    return () => {
      requestSequence.current += 1;
      activeRequest.current?.abort();
      activeRequest.current = null;
    };
  }, [refresh]);

  useEffect(() => {
    if (!enabled || !authenticated) return;
    const isVisible = () => visible && document.visibilityState === 'visible';
    const poll = window.setInterval(() => { if (isVisible()) void refresh(); }, MEMBERSHIP_REFRESH_MS);
    const tick = window.setInterval(() => { if (isVisible()) setMonotonicNow(performance.now()); }, 1000);
    const foreground = () => { if (isVisible()) { setMonotonicNow(performance.now()); void refresh(); } };
    const changed = () => { if (isVisible()) void refresh(); };
    document.addEventListener('visibilitychange', foreground);
    window.addEventListener('focus', foreground);
    window.addEventListener(CHANGED_EVENT, changed);
    return () => {
      window.clearInterval(poll);
      window.clearInterval(tick);
      document.removeEventListener('visibilitychange', foreground);
      window.removeEventListener('focus', foreground);
      window.removeEventListener(CHANGED_EVENT, changed);
    };
  }, [authenticated, enabled, refresh, visible]);

  // Scope-check during render, so no render after a switch can expose the previous identity.
  const current = enabled && authenticated && snapshot?.scope === scope ? snapshot : null;
  const usage = current?.usage ?? null;
  const seconds = (at?: string | null) => current?.clock ? remainingSeconds(at, current.clock, monotonicNow) : null;
  const countdowns = { term: seconds(usage?.term?.reset_at), week: seconds(usage?.week?.reset_at), free: seconds(usage?.free?.reset_at) };

  useEffect(() => {
    if (!visible || document.visibilityState !== 'visible' || !usage || current?.status !== 'ready') return;
    for (const [name, at] of [['term', usage.term?.reset_at], ['week', usage.week?.reset_at], ['free', usage.free?.reset_at]] as const) {
      if (!at || countdowns[name] !== 0) continue;
      const key = `${name}:${at}`;
      if (crossedBoundaries.current.has(key)) continue;
      crossedBoundaries.current.add(key);
      void refresh();
    }
  }, [countdowns.term, countdowns.week, countdowns.free, current?.status, refresh, usage, visible]);

  return { catalog: current?.catalog ?? null, usage, status: !enabled || !authenticated ? 'unauthenticated' as const : current?.status ?? 'loading' as const,
    error: current?.error ?? null, countdowns, refresh };
}
