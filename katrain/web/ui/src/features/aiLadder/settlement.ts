import { uiMessage, renderUiMessage, type UiMessage } from '../../kiosk/utils/uiMessage';
import { rankLabel } from '../../kiosk/utils/playerRank';
import { createElement, useEffect, useRef, useState } from 'react';
import { Alert, Button } from '@mui/material';
import { getAiLadderSettlementReceipt, getAiLadderStatus } from './api';
import { AI_LADDER_COPY, settlementCopy } from './copy';
import { useTranslation } from '../../hooks/useTranslation';
import {
  isAiLadderReadyStatus,
  type AiLadderCountingReason,
  type AiLadderReadyStatus,
  type AiLadderSettlementReceipt,
} from './types';

export type SettlementFeedbackKind = 'placement_progress' | 'placement_complete' | 'promotion' | 'demotion' | 'score_change' | 'no_change' | 'authoritative_complete' | 'not_counted' | 'pending' | 'error';
export interface SettlementFeedback { kind: SettlementFeedbackKind; message: string; display?: UiMessage; status?: AiLadderReadyStatus; retry?: () => void }
interface StoredSettlementStart { status: AiLadderReadyStatus; gameId?: string }

const keyFor = (sessionId: string) => `ai-ladder-before:${sessionId}`;
// Same guard the status hook uses — it lives in types.ts now so both entry points agree
// on what "a usable ready status" means.
const isReadyStatus = isAiLadderReadyStatus;

export const saveAiLadderBefore = (sessionId: string, status: AiLadderReadyStatus, identity: string, gameId?: string) => {
  if (!sessionId || !identity || !isReadyStatus(status)) return;
  try { sessionStorage.setItem(keyFor(sessionId), JSON.stringify({ identity, status, game_id: gameId })); } catch { /* storage unavailable */ }
};
export const peekAiLadderBefore = (sessionId: string, identity: string): StoredSettlementStart | null => {
  try {
    const value = sessionStorage.getItem(keyFor(sessionId));
    if (!value) return null;
    const parsed = JSON.parse(value) as { identity?: unknown; status?: unknown; game_id?: unknown };
    return parsed.identity === identity && isReadyStatus(parsed.status)
      ? { status: parsed.status, gameId: typeof parsed.game_id === 'string' ? parsed.game_id : undefined }
      : null;
  } catch { return null; }
};
const takeAiLadderBefore = (sessionId: string, identity: string): StoredSettlementStart | null => {
  try {
    const stored = peekAiLadderBefore(sessionId, identity);
    sessionStorage.removeItem(keyFor(sessionId));
    return stored;
  } catch { return null; }
};
const clearAiLadderBefore = (sessionId: string) => { try { sessionStorage.removeItem(keyFor(sessionId)); } catch { /* noop */ } };

const score = (value: number) => value > 0 ? `+${value}` : String(value);
export const deriveSettlementFeedback = (before: AiLadderReadyStatus | null, after: AiLadderReadyStatus): SettlementFeedback => {
  const feedback = (kind: SettlementFeedbackKind, message: string, key: string, fallback: string, values?: Record<string, string | number>): SettlementFeedback =>
    ({ kind, message, display: uiMessage(key, fallback, values), status: after });
  if (!before) return feedback('authoritative_complete', settlementCopy.authoritativeComplete(), 'ladder:settled_generic', '升降级结算已完成，当前状态已更新');
  if (before.placement_state.phase === 'placement') {
    if (after.placement_state.phase === 'placed') return feedback('placement_complete', settlementCopy.placementComplete(after.placement_state.rung.rank_name), 'ladder:settled_placement_done', '定级完成：{rank}', { rank: after.placement_state.rung.rank_name });
    return feedback('placement_progress', settlementCopy.placementProgress(after.placement_state.completed_games, after.placement_state.total_games), 'ladder:settled_placement_progress', '定级中 {n}/{total}', { n: after.placement_state.completed_games, total: after.placement_state.total_games });
  }
  if (after.placement_state.phase === 'placed') {
    const delta = after.placement_state.rung.rung - before.placement_state.rung.rung;
    if (delta > 0) return feedback('promotion', settlementCopy.promotion(after.placement_state.rung.rank_name), 'ladder:settled_promoted', '升级：{rank}', { rank: after.placement_state.rung.rank_name });
    if (delta < 0) return feedback('demotion', settlementCopy.demotion(after.placement_state.rung.rank_name), 'ladder:settled_demoted', '降级：{rank}', { rank: after.placement_state.rung.rank_name });
  }
  if (after.net_score !== before.net_score) return feedback('score_change', settlementCopy.scoreChange(score(after.net_score)), 'ladder:settled_score_change', '累计净胜分：{score}', { score: score(after.net_score) });
  return feedback('no_change', settlementCopy.noChange(score(after.net_score)), 'ladder:settled_no_change', '段位未变化，累计净胜分：{score}', { score: score(after.net_score) });
};

type GetStatus = (token?: string, signal?: AbortSignal) => Promise<AiLadderReadyStatus>;
type GetReceipt = (gameId: string, token?: string, signal?: AbortSignal) => Promise<AiLadderSettlementReceipt>;
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

const pollAiLadderReceipt = async (
  getReceipt: GetReceipt, gameId: string, token: string | undefined, signal: AbortSignal, attempts = 5,
  wait: () => Promise<void> = () => new Promise((resolve) => setTimeout(resolve, 750)),
) => {
  let receipt: AiLadderSettlementReceipt = { state: 'pending' };
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    receipt = await getReceipt(gameId, token, signal);
    if (receipt.state === 'settled' || signal.aborted) return receipt;
    if (attempt < attempts - 1) await wait();
  }
  return receipt;
};

const notCountedMessages: Record<AiLadderCountingReason, string> = {
  engine_unavailable: '本局不计入升降级：棋力服务未能正常完成对局',
  inconclusive: '本局不计入升降级：对局没有形成有效胜负',
  opponent_not_eligible: '本局不计入升降级：本局对手尚未通过计分认证',
  opponent_rung_mismatch: '本局不计入升降级：对手档位与开局快照不一致',
  invalid_game_type: '本局不计入升降级：对局类型不符合升降级规则',
};
const notCountedMessage = (reason: AiLadderCountingReason | null) =>
  (reason && Object.prototype.hasOwnProperty.call(notCountedMessages, reason) ? notCountedMessages[reason] : null) ?? '本局不计入升降级：服务器判定本局不计入';

export const useAiLadderSettlement = (
  sessionId: string | undefined, gameType: string | undefined, endResult: string | null | undefined,
  token?: string, identity = '', wait?: () => Promise<void>,
) => {
  const [feedback, setFeedback] = useState<SettlementFeedback | null>(null);
  const [retryGeneration, setRetryGeneration] = useState(0);
  const beforeRef = useRef<{ key: string; value: StoredSettlementStart | null } | null>(null);
  useEffect(() => {
    if (!sessionId || gameType !== 'ai_ladder_ranked' || !endResult) {
      setFeedback(null);
      beforeRef.current = null;
      return;
    }
    const controller = new AbortController();
    const snapshotKey = `${sessionId}:${identity}`;
    if (beforeRef.current?.key !== snapshotKey) beforeRef.current = { key: snapshotKey, value: takeAiLadderBefore(sessionId, identity) };
    const stored = beforeRef.current.value;
    const before = stored?.status ?? null;
    const retry = () => setRetryGeneration((value) => value + 1);
    const settle = async () => {
      if (stored?.gameId) {
        const receipt = await pollAiLadderReceipt(
          getAiLadderSettlementReceipt, stored.gameId, token, controller.signal, 5, wait,
        );
        if (receipt.state === 'pending') {
          return { kind: 'pending', message: settlementCopy.pending(), display: uiMessage('ladder:settled_pending', '升降级结算仍在处理中'), status: before ?? undefined, retry } satisfies SettlementFeedback;
        }
        const after = await getAiLadderStatus(token, controller.signal);
        if (!receipt.counted) {
          clearAiLadderBefore(sessionId);
          return { kind: 'not_counted', message: notCountedMessage(receipt.reason), display: uiMessage(notCountedMessage(receipt.reason), notCountedMessage(receipt.reason)), status: after } satisfies SettlementFeedback;
        }
        clearAiLadderBefore(sessionId);
        return deriveSettlementFeedback(before, after);
      }
      const after = await pollAiLadderSettlement(getAiLadderStatus, token, controller.signal, 5, wait);
      if (after.pending_settlement) {
        return { kind: 'pending', message: settlementCopy.pending(), display: uiMessage('ladder:settled_pending', '升降级结算仍在处理中'), status: after, retry } satisfies SettlementFeedback;
      }
      clearAiLadderBefore(sessionId);
      return deriveSettlementFeedback(before, after);
    };
    void settle().then((result) => {
      if (controller.signal.aborted) return;
      setFeedback(result);
    }).catch((error) => {
      if (!controller.signal.aborted) setFeedback({ kind: 'error', message: error instanceof Error ? error.message : settlementCopy.unavailable(), display: error instanceof Error ? undefined : uiMessage('ladder:settled_unavailable', '结算状态暂不可用'), status: before ?? undefined, retry });
    });
    return () => controller.abort();
  }, [endResult, gameType, identity, retryGeneration, sessionId, token, wait]);
  return feedback;
};

export const AiLadderSettlementAlert = ({ feedback }: { feedback: SettlementFeedback | null }) => {
  const { t } = useTranslation();
  const display = feedback?.display;
  const message = display ? renderUiMessage({ ...display, values: { ...display.values,
    ...(typeof display.values?.rank === 'string' ? { rank: rankLabel(display.values.rank, t) } : {}),
  } }, t) : feedback?.message;
  return feedback ? createElement(Alert, {
    severity: feedback.kind === 'error' ? 'error' : feedback.kind === 'pending' || feedback.kind === 'demotion' || feedback.kind === 'not_counted' ? 'warning' : 'success',
    action: feedback.retry ? createElement(Button, { color: 'inherit', size: 'small', onClick: feedback.retry }, AI_LADDER_COPY.retry) : undefined,
  }, message) : null;
};
