import { useEffect, useState } from 'react';
import type { AiLadderBlockingGame } from './types';

/**
 * 挡住新局的那一局,用户能对它做什么 —— 以及**什么时候**能做。
 *
 * 抽出来单独一份,是因为同一个判断此前在服务端算过两次、错过两次:业务层问「这台设备
 * 能不能结束这局」,投影层却拿「别处那台能不能接管」去答,于是屏上说「不行,而且等也没用」
 * 而接口当场 200(见 `ai_ladder_ranked.remote_resign_barrier` 的说明)。这里是同一个判断
 * 在前端的落点,所以它也只能有一份 —— 组件读结论,不自己再推一遍。
 */

export type AiLadderExitKind = 'resign' | 'release';

export interface AiLadderExit {
  kind: AiLadderExitKind;
  /** 现在就能按 */
  ready: boolean;
  /**
   * 还要等多少秒。`null` = 等不来(此时若 ready 为假,这扇门就不该出现)。
   *
   * **是时长,不是时刻。** 拿服务端给的时刻去减本机的钟,差多少钟倒计时就错多少,
   * 而常年离线、没有可靠 NTP 的一体机正是钟偏最大的那一台;后果恰好是这块屏要避免的
   * 那种假话:按钮其实能按了,屏上还在数「还需 2 分钟」。时长是差值,对钟偏免疫。
   */
  readyInSeconds: number | null;
}

const parseSeconds = (value: number | null | undefined): number | null =>
  typeof value === 'number' && Number.isFinite(value) ? Math.max(0, value) : null;

/**
 * 服务端只在**这扇门能承载一个答案**的时候才发那组字段,所以键不在 = 这一格没有这扇门。
 * 判断一律看值,不看键在不在 —— 否则一个旧服务端和一扇关着的门在前端长得一模一样。
 */
export const aiLadderExits = (game: AiLadderBlockingGame): AiLadderExit[] => {
  const exits: AiLadderExit[] = [];
  if (game.can_force_resign !== undefined) {
    const readyInSeconds = parseSeconds(game.takeover_eligible_in_seconds);
    // `can_force_resign=false` 且没有剩余时长 ⇒ 等也不会变成真,这扇门对这一格不适用,
    // 摆一个永远按不动、也没有倒计时的按钮只会让人一直戳它。
    if (game.can_force_resign || readyInSeconds !== null) {
      exits.push({ kind: 'resign', ready: Boolean(game.can_force_resign), readyInSeconds });
    }
  }
  if (game.can_release_abandoned_settlement !== undefined) {
    const readyInSeconds = parseSeconds(game.abandoned_settlement_eligible_in_seconds);
    if (game.can_release_abandoned_settlement || readyInSeconds !== null) {
      exits.push({ kind: 'release', ready: Boolean(game.can_release_abandoned_settlement), readyInSeconds });
    }
  }
  return exits;
};

/** `4:12` / `1:03:20`。分秒补零,小时只在需要时出现。 */
export const formatCountdown = (msRemaining: number): string => {
  const total = Math.max(0, Math.ceil(msRemaining / 1000));
  const seconds = total % 60;
  const minutes = Math.floor(total / 60) % 60;
  const hours = Math.floor(total / 3600);
  const mmss = `${minutes}:${String(seconds).padStart(2, '0')}`;
  return hours > 0 ? `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}` : mmss;
};

/**
 * 每秒走一格,到点自己变成可用 —— 不等下一次状态刷新。
 *
 * 服务端的到期时刻和它自己那道闸吃的是同一个常量(两侧边界各有一条测试钉着),所以屏上
 * 走完的那一刻,接口就是通的。倒计时走完按钮还 409 比没有倒计时更坏:用户是被**明确告知**
 * 去信那个时刻的。
 *
 * 到点之后停表(`deadline` 过去就不再起 interval),免得一个开着的页面永远每秒重渲染。
 */
export const useCountdown = (seconds: number | null): number | null => {
  const [remaining, setRemaining] = useState<number | null>(seconds === null ? null : seconds * 1000);

  useEffect(() => {
    if (seconds === null) {
      setRemaining(null);
      return undefined;
    }
    // 起点是**这份数据到手的那一刻**,量的是本机自己走了多久 —— 全程不需要和服务端
    // 对表。`performance.now()` 不受用户改系统时间或 NTP 跳变影响。
    const startedAt = performance.now();
    const total = seconds * 1000;
    const tick = () => setRemaining(Math.max(0, total - (performance.now() - startedAt)));
    tick();
    if (total <= 0) return undefined;
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
  }, [seconds]);

  return remaining;
};
