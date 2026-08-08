import { createElement, useEffect, useRef, useState } from 'react';
import { Alert, Button } from '@mui/material';
import { getAiLadderStatus } from './api';
import { AI_LADDER_COPY, settlementCopy } from './copy';
import { useTranslation } from '../../hooks/useTranslation';
import { isAiLadderReadyStatus, type AiLadderReadyStatus } from './types';

export type SettlementFeedbackKind = 'placement_progress' | 'placement_complete' | 'promotion' | 'demotion' | 'score_change' | 'no_change' | 'authoritative_complete' | 'pending' | 'error';
export interface SettlementFeedback { kind: SettlementFeedbackKind; message: string; status?: AiLadderReadyStatus; retry?: () => void }

const keyFor = (sessionId: string) => `ai-ladder-before:${sessionId}`;
// Same guard the status hook uses — it lives in types.ts now so both entry points agree
// on what "a usable ready status" means.
const isReadyStatus = isAiLadderReadyStatus;

export const saveAiLadderBefore = (sessionId: string, status: AiLadderReadyStatus, identity: string) => {
  if (!sessionId || !identity || !isReadyStatus(status)) return;
  try { sessionStorage.setItem(keyFor(sessionId), JSON.stringify({ identity, status })); } catch { /* storage unavailable */ }
};
const takeAiLadderBefore = (sessionId: string, identity: string): AiLadderReadyStatus | null => {
  try {
    const value = sessionStorage.getItem(keyFor(sessionId));
    sessionStorage.removeItem(keyFor(sessionId));
    if (!value) return null;
    const parsed = JSON.parse(value) as { identity?: unknown; status?: unknown };
    return parsed.identity === identity && isReadyStatus(parsed.status) ? parsed.status : null;
  } catch { return null; }
};
const clearAiLadderBefore = (sessionId: string) => { try { sessionStorage.removeItem(keyFor(sessionId)); } catch { /* noop */ } };

const score = (value: number) => value > 0 ? `+${value}` : String(value);
export const deriveSettlementFeedback = (before: AiLadderReadyStatus | null, after: AiLadderReadyStatus): SettlementFeedback => {
  if (!before) return { kind: 'authoritative_complete', message: settlementCopy.authoritativeComplete(), status: after };
  if (before.placement_state.phase === 'placement') {
    if (after.placement_state.phase === 'placed') return { kind: 'placement_complete', message: settlementCopy.placementComplete(after.placement_state.rung.rank_name), status: after };
    return { kind: 'placement_progress', message: settlementCopy.placementProgress(after.placement_state.completed_games, after.placement_state.total_games), status: after };
  }
  if (after.placement_state.phase === 'placed') {
    const delta = after.placement_state.rung.rung - before.placement_state.rung.rung;
    if (delta > 0) return { kind: 'promotion', message: settlementCopy.promotion(after.placement_state.rung.rank_name), status: after };
    if (delta < 0) return { kind: 'demotion', message: settlementCopy.demotion(after.placement_state.rung.rank_name), status: after };
  }
  if (after.net_score !== before.net_score) return { kind: 'score_change', message: settlementCopy.scoreChange(score(after.net_score)), status: after };
  return { kind: 'no_change', message: settlementCopy.noChange(score(after.net_score)), status: after };
};

type GetStatus = (token?: string, signal?: AbortSignal) => Promise<AiLadderReadyStatus>;
export const pollAiLadderSettlement = async (
  getStatus: GetStatus, token: string | undefined, signal: AbortSignal, attempts = 5,
  wait: () => Promise<void> = () => new Promise((resolve) => setTimeout(resolve, 750)),
) => {
  let status: AiLadderReadyStatus | null = null;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    status = await getStatus(token, signal);
    if (!status.pending_settlement || signal.aborted) return status;
    if (attempt < attempts - 1) await wait();
  }
  return status!;
};

export const useAiLadderSettlement = (
  sessionId: string | undefined, gameType: string | undefined, endResult: string | null | undefined,
  token?: string, identity = '', wait?: () => Promise<void>,
) => {
  const [feedback, setFeedback] = useState<SettlementFeedback | null>(null);
  const [retryGeneration, setRetryGeneration] = useState(0);
  const beforeRef = useRef<{ key: string; value: AiLadderReadyStatus | null } | null>(null);
  useEffect(() => {
    if (!sessionId || gameType !== 'ai_ladder_ranked' || !endResult) {
      setFeedback(null);
      beforeRef.current = null;
      return;
    }
    const controller = new AbortController();
    const snapshotKey = `${sessionId}:${identity}`;
    if (beforeRef.current?.key !== snapshotKey) beforeRef.current = { key: snapshotKey, value: takeAiLadderBefore(sessionId, identity) };
    const before = beforeRef.current.value;
    const retry = () => setRetryGeneration((value) => value + 1);
    void pollAiLadderSettlement(getAiLadderStatus, token, controller.signal, 5, wait).then((after) => {
      if (controller.signal.aborted) return;
      if (after.pending_settlement) {
        setFeedback({ kind: 'pending', message: settlementCopy.pending(), status: after, retry });
      } else {
        clearAiLadderBefore(sessionId);
        setFeedback(deriveSettlementFeedback(before, after));
      }
    }).catch((error) => {
      if (!controller.signal.aborted) setFeedback({ kind: 'error', message: error instanceof Error ? error.message : settlementCopy.unavailable(), status: before ?? undefined, retry });
    });
    return () => controller.abort();
  }, [endResult, gameType, identity, retryGeneration, sessionId, token, wait]);
  return feedback;
};

export const AiLadderSettlementAlert = ({ feedback }: { feedback: SettlementFeedback | null }) => {
  // The message itself was formatted when the game ended and is held in state, so a
  // language switch mid-alert does not rewrite it; the retry label re-renders with the hook.
  useTranslation();
  return feedback ? createElement(Alert, {
    severity: feedback.kind === 'error' ? 'error' : feedback.kind === 'pending' || feedback.kind === 'demotion' ? 'warning' : 'success',
    action: feedback.retry ? createElement(Button, { color: 'inherit', size: 'small', onClick: feedback.retry }, AI_LADDER_COPY.retry) : undefined,
  }, feedback.message) : null;
};
