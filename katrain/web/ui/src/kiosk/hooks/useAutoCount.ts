import { useCallback, useEffect, useRef, useState } from 'react';
import { API, type GameState } from '../../api';
import { useTranslation } from '../../hooks/useTranslation';
import { countErrorCode, countErrorMessage } from '../utils/countErrors';

export type AutoCountStatus = 'idle' | 'counting' | 'failed';

/** `analysis_pending` 的退避间隔(毫秒)。累计 15 秒(v2-design §3.4),共 6 次请求;第 6 次仍 pending 就停。 */
export const AUTO_COUNT_BACKOFF_MS: readonly number[] = [1000, 2000, 3000, 4000, 5000];

/**
 * 这一局该不该**自动**数子:只给「这台机器上两边自己下完的局」—— 本地对局、人机自由对弈。
 * 不能只看 `game_type === 'free'`:大厅局和星阵人机局后端**也是 `free`**,数子在那两种局里是另一条协议。
 * 分得开它们的是座位字面量:kiosk 人机局 AI 座位是 `player:ai`,大厅/星阵两边都是裸 `human`。
 */
export function autoCountEligible(gs: GameState | null | undefined, engineMode: boolean): boolean {
  if (!gs || engineMode) return false;
  if (gs.game_type === 'pvp_local') return true;
  if (gs.game_type === 'ai_ladder_ranked') return true;
  if ((gs.game_type ?? 'free') !== 'free') return false;
  return gs.players_info.B.player_type === 'player:ai' || gs.players_info.W.player_type === 'player:ai';
}

export interface UseAutoCountOptions {
  sessionId: string | null | undefined;
  /** 调用方算好的「现在就该数」:`state.awaiting_count` ∧ 没有结果 ∧ `autoCountEligible`。 */
  awaitingCount: boolean;
  /** 当前节点 id。**同一个节点只自动数一次** —— 分析结果回来会再推一次同节点的 state。 */
  nodeId: number | null | undefined;
  /** 数子成功后把终局 state 交回去(GamePage 传 `session.setGameState`)。 */
  onState: (state: GameState) => void;
}

export interface AutoCountView { status: AutoCountStatus; reason: string | null; retry: () => void }

/**
 * **状态是算出来的,不是 effect 里 set 的**:「该数且这一轮还没失败」就是 `counting`。
 * 失败结论带上它属于哪一轮(`key`);换节点 / 按重试 ⇒ `key` 变,旧结论自然作废。
 * 这样 effect 体里没有同步 setState(仓里 `react-hooks/set-state-in-effect` 开着)。
 */
export function useAutoCount({ sessionId, awaitingCount, nodeId, onState }: UseAutoCountOptions): AutoCountView {
  const { t } = useTranslation();
  const [epoch, setEpoch] = useState(0);
  const [failure, setFailure] = useState<{ key: string; error: unknown } | null>(null);
  const onStateRef = useRef(onState);
  useEffect(() => { onStateRef.current = onState; }, [onState]);

  const key = awaitingCount && sessionId ? `${sessionId}|${nodeId ?? ''}|${epoch}` : null;

  useEffect(() => {
    if (!key || !sessionId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const attempt = async (n: number) => {
      try {
        const res = await API.requestCount(sessionId);
        if (cancelled) return;
        if (res?.state) onStateRef.current(res.state as GameState);
      } catch (error) {
        if (cancelled) return;
        if (countErrorCode(error) === 'analysis_pending' && n < AUTO_COUNT_BACKOFF_MS.length) {
          timer = setTimeout(() => { void attempt(n + 1); }, AUTO_COUNT_BACKOFF_MS[n]);
          return;
        }
        setFailure({ key, error });
      }
    };
    void attempt(0);
    return () => { cancelled = true; if (timer !== undefined) clearTimeout(timer); };
  }, [key, sessionId]);

  const retry = useCallback(() => { setEpoch((e) => e + 1); }, []);

  if (!key) return { status: 'idle', reason: null, retry };
  if (failure?.key === key) return { status: 'failed', reason: countErrorMessage(failure.error, t), retry };
  return { status: 'counting', reason: null, retry };
}
