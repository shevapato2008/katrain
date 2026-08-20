import { useCallback, useEffect, useRef, useState } from 'react';
import { AiLadderApiError, getAiLadderStatus } from './api';
import { AI_LADDER_COPY } from './copy';
import {
  isAiLadderReadyStatus,
  type AiLadderSettlementSync,
  type AiLadderStatus,
} from './types';

/**
 * The message the player sees. The server's `detail` is English operator text
 * ("Ranked AI ladder authority is unavailable on this node") and was being rendered
 * verbatim on a Chinese kiosk, so translate the cases we actually produce and fall back
 * to a generic line rather than leaking the raw body.
 */
export const aiLadderStatusErrorMessage = (error: unknown): string => {
  if (error instanceof AiLadderApiError) {
    if (error.status === 503) return AI_LADDER_COPY.loadErrorNotAuthoritative;
    if (error.status === 401 || error.status === 403) return AI_LADDER_COPY.loadErrorUnauthorized;
  }
  return AI_LADDER_COPY.loadError;
};

/**
 * 有一局挡着的时候,多久回头问一次。
 *
 * 走秒那一半不靠它 —— 「下一次重试还有多久」在本地数,到点自己改口。这条管的是
 * 时刻之外的变化(那一局在别处结束了、状态从「在下」变成「成绩未送达」、outbox
 * 自己在后台送成了),所以不必密。15 秒够快到用户察觉不出延迟,又不会让一台开着
 * 页面的一体机每秒去敲一次云端。
 */
export const AI_LADDER_BLOCKED_REFRESH_MS = 15_000;

export const useAiLadderStatus = (token?: string, enabled = true) => {
  const [status, setStatus] = useState<AiLadderStatus>({ view_state: 'loading' });
  const generation = useRef(0);
  const activeRequest = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    if (!enabled) return;
    const requestGeneration = ++generation.current;
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    setStatus({ view_state: 'loading' });
    try {
      const next = await getAiLadderStatus(token, controller.signal);
      if (controller.signal.aborted || generation.current !== requestGeneration) return;
      // A 200 is not a promise about the body's shape. Say "failed to load" rather than
      // handing a half-formed object to the card and taking the page down with it.
      setStatus(isAiLadderReadyStatus(next) ? next : { view_state: 'error', message: AI_LADDER_COPY.loadError });
    } catch (error) {
      if (controller.signal.aborted || generation.current !== requestGeneration) return;
      setStatus({ view_state: 'error', message: aiLadderStatusErrorMessage(error) });
    }
  }, [enabled, token]);

  /**
   * 后台复查:只在**答案会在用户不动的情况下改变**的那一屏上跑,而那一屏只有一个——
   * 有一局挡着新局的时候。
   *
   * 不加这条,「字段会随时间变」和「屏上会变」就成了两件事:载荷里
   * `can_force_resign` 每次现算,查载荷的时候完全正确,而这块屏从进入到离开
   * **只问过一次**。另一台设备下完了、那一局消失了,用户仍然停在「正在其他设备上进行」,
   * 除非他自己想起来去按刷新。(象棋在同一格上量出来的:假时钟走满十分钟,
   * 取数一共只发生了 1 次。)
   *
   * 到期时刻那一半不靠它——`useCountdown` 在本地走秒并到点自动启用按钮,
   * 所以门开的那一刻不依赖任何一次网络往返。这条复查管的是**时刻之外**的变化:
   * 局结束了、状态从「在下」变成「成绩未送达」、或者账号被别的设备解开了。
   *
   * 失败**不改相位**:一次网络抖动被渲染成「加载失败」,会把用户从一个正确的状态
   * 吓走,而这块屏是那两条出路唯一的入口。所以背景复查只在成功时替换状态。
   */
  const blocked = isAiLadderReadyStatus(status) && Boolean(status.blocking_game);
  const refresh = useCallback(async () => {
    if (!enabled) return;
    try {
      const next = await getAiLadderStatus(token);
      if (isAiLadderReadyStatus(next)) setStatus(next);
    } catch {
      // 见上:背景复查失败保持原样,不把用户赶出一个正确的屏。
    }
  }, [enabled, token]);

  useEffect(() => {
    if (!enabled || !blocked) return undefined;
    const timer = window.setInterval(() => void refresh(), AI_LADDER_BLOCKED_REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [enabled, blocked, refresh]);

  /**
   * 把 outbox 刚刚给出的同步状态就地贴上去,**不再向云端要一次**。
   *
   * 「立即重试」这个按钮存在的理由就是网络不好,而 `/status` 在盒子上是转发到云端的:
   * 失败即 503,`load()` 一 catch 就把整块面板换成「加载失败」。于是专为离线准备的
   * 那个按钮,恰恰在离线时会毁掉屏幕。
   *
   * 而重试那个请求打的是盒子自己(127.0.0.1),断网照样成功,它的响应里就带着这一次
   * 尝试之后的真实状态 —— 那是此刻手上**唯一确定收到过**的事实,所以用它。
   */
  const applyBlockingSync = useCallback((gameId: string, sync: AiLadderSettlementSync | null) => {
    setStatus((previous) => {
      if (!isAiLadderReadyStatus(previous)) return previous;
      const blocking = previous.blocking_game;
      if (!blocking || blocking.game_id !== gameId) return previous;
      const { sync: _dropped, ...rest } = blocking;
      return {
        ...previous,
        blocking_game: sync === null ? rest : { ...rest, sync },
      };
    });
  }, []);

  useEffect(() => {
    void load();
    return () => {
      generation.current += 1;
      activeRequest.current?.abort();
    };
  }, [load]);

  return { status, retry: load, applyBlockingSync };
};
