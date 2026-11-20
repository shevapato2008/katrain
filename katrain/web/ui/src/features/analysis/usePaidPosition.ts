import { useCallback, useEffect, useRef, useState } from 'react';
import { membershipApi } from '../../api/membershipApi';
import { notifyMembershipChanged } from '../membership/useMembership';
import type { BillingQuote, BillingQuoteRequest, MembershipProfile, PositionAnalysis } from '../membership/types';
import { useMembershipI18n } from '../membership/useMembershipI18n';
import { membershipErrorCode, membershipErrorText, type MembershipErrorCode } from '../membership/presentation';

type View = 'hints' | 'ownership' | 'score';
type PositionInput = Pick<BillingQuoteRequest, 'sgf' | 'game_id' | 'session_id' | 'expected_position_key'>;
interface Options {
  identityKey: string | null | undefined;
  status: string;
  token?: string | null;
  snapshotKey: string;
  input: PositionInput;
  profile?: MembershipProfile;
  enabled?: boolean;
}
interface Snapshot {
  scope: string;
  result: PositionAnalysis['result'] | null;
  hints: boolean;
  ownership: boolean;
  score: boolean;
  pending: { quote: BillingQuote; key: string } | null;
  busy: boolean;
  error: MembershipErrorCode | null;
}
const hiddenViews = { hints: false, ownership: false, score: false };
const blank = (scope: string): Snapshot => ({ scope, result: null, ...hiddenViews, pending: null, busy: false, error: null });

/** A result belongs to one authenticated full position, never to the shared WS state. */
export function usePaidPosition({ identityKey, status, token, snapshotKey, input, profile = 'normal', enabled = true }: Options) {
  const { t } = useMembershipI18n();
  const authenticated = enabled && status === 'authenticated' && identityKey != null;
  const inputKey = JSON.stringify(input);
  const scope = JSON.stringify([identityKey, status, snapshotKey, profile, inputKey, enabled]);
  const scopeRef = useRef(scope);
  scopeRef.current = scope;
  const [snapshot, setSnapshot] = useState<Snapshot>(() => blank(scope));
  const snapshotRef = useRef(snapshot);
  const generationRef = useRef(0);
  const quoteRequest = useRef<Promise<void> | null>(null);
  const execution = useRef<Promise<void> | null>(null);
  const update = useCallback((changes: Partial<Snapshot>) => {
    if (scopeRef.current !== scope) return;
    const current = snapshotRef.current.scope === scope ? snapshotRef.current : blank(scope);
    const next = { ...current, ...changes };
    snapshotRef.current = next;
    setSnapshot(next);
  }, [scope]);

  useEffect(() => {
    ++generationRef.current;
    const next = blank(scope);
    snapshotRef.current = next;
    setSnapshot(next);
    quoteRequest.current = null;
    execution.current = null;
    return () => { ++generationRef.current; };
  }, [scope]);

  const quote = useCallback(async () => {
    const generation = generationRef.current;
    const current = () => scopeRef.current === scope && generationRef.current === generation;
    const catalog = await membershipApi.getCatalog(token);
    if (!current()) return;
    if (catalog.membership_mode !== 'enabled' || !catalog.capabilities.quotes || !catalog.capabilities.positions) {
      update({ ...hiddenViews, error: catalog.membership_mode === 'paused' ? 'service_paused' : 'position_unavailable' });
      return;
    }
    const response = await membershipApi.createQuote({ ...JSON.parse(inputKey) as PositionInput, kind: 'position', profile }, token);
    const expected = (JSON.parse(inputKey) as PositionInput).expected_position_key;
    if (expected && response.fingerprint !== expected) {
      if (current()) update({ ...hiddenViews, pending: null, error: 'position_changed' });
      return;
    }
    if (current()) update({ pending: { quote: response, key: crypto.randomUUID() }, error: null });
  }, [inputKey, profile, scope, token, update]);

  const toggle = useCallback(async (view: View) => {
    if (scopeRef.current !== scope) return;
    if (!authenticated) { update({ error: 'analysis_login_required' }); return; }
    const current = snapshotRef.current.scope === scope ? snapshotRef.current : blank(scope);
    update({ [view]: !current[view], error: null });
    if (current.result || current.pending || execution.current) return;
    if (quoteRequest.current) return quoteRequest.current;
    update({ busy: true });
    const generation = generationRef.current;
    const request = quote().catch((error: unknown) => {
      if (generationRef.current === generation) update({ ...hiddenViews, pending: null, error: membershipErrorCode(error, 'quote_failed') });
    }).finally(() => {
      if (generationRef.current === generation) { update({ busy: false }); quoteRequest.current = null; }
    });
    quoteRequest.current = request;
    return request;
  }, [authenticated, quote, scope, update]);

  const confirm = useCallback(async () => {
    if (scopeRef.current !== scope || !authenticated) return;
    if (execution.current) return execution.current;
    const pending = snapshotRef.current.scope === scope ? snapshotRef.current.pending : null;
    if (!pending) return;
    const generation = generationRef.current;
    const current = () => scopeRef.current === scope && generationRef.current === generation;
    const payload = { ...JSON.parse(inputKey) as PositionInput, profile, quote_token: pending.quote.token, idempotency_key: pending.key };
    update({ busy: true, error: null });
    const request = (async () => {
      try {
        let receipt: PositionAnalysis;
        try { receipt = await membershipApi.createPosition(payload, token); }
        catch (error) {
          if (error instanceof TypeError && current()) receipt = await membershipApi.createPosition(payload, token);
          else throw error;
        }
        // The POST normally returns a terminal receipt. Replays can observe work in progress.
        for (let attempt = 0; current() && (receipt.state === 'reserved' || receipt.state === 'running') && attempt < 40; attempt++) {
          await new Promise((resolve) => window.setTimeout(resolve, 2000));
          if (!current()) return;
          receipt = await membershipApi.getPosition(String(receipt.operation_id), token);
        }
        if (!current()) return;
        if (receipt.state === 'succeeded' && receipt.result) update({ result: receipt.result, pending: null });
        else if (receipt.state === 'reserved' || receipt.state === 'running') update({ error: 'operation_running' });
        else update({ result: null, pending: null, ...hiddenViews, error: receipt.state === 'result_expired'
          ? 'result_expired' : receipt.state === 'refunded' ? 'position_refunded' : 'position_failed' });
        notifyMembershipChanged();
      } catch (error) {
        if (!current()) return;
        const carrier = error as { detail?: { code?: string }; body?: string; status?: number };
        const errorCode = membershipErrorCode(error, 'position_failed');
        if (errorCode === 'position_changed') {
          update({ result: null, pending: null, ...hiddenViews, error: errorCode });
          return;
        }
        if (/quote/.test(carrier.detail?.code ?? carrier.body ?? String(error)) || carrier.status === 409) {
          update({ pending: null });
          await quote().catch(() => {});
        }
        update({ result: null, error: errorCode });
      } finally {
        if (current()) { execution.current = null; update({ busy: false }); }
      }
    })();
    execution.current = request;
    return request;
  }, [authenticated, inputKey, profile, quote, scope, token, update]);
  const cancel = useCallback(() => { if (!execution.current) update({ pending: null, ...hiddenViews }); }, [update]);
  const hideHints = useCallback(() => update({ hints: false }), [update]);
  const current = authenticated && snapshot.scope === scope ? snapshot : blank(scope);
  return { result: current.result, pendingQuote: current.pending?.quote ?? null, busy: current.busy, error: current.error ? membershipErrorText(current.error, t) : null,
    showHints: current.hints, showOwnership: current.ownership, showScore: current.score, toggle, confirm, cancel, hideHints };
}
