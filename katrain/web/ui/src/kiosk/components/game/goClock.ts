import { useEffect, useRef, useState } from 'react';
import type { GameState } from '../../../api';

/**
 * 对局屏玩家卡的时钟(A18)。
 *
 * 算法与服务端 `interface.py` `update_timer` 一致:主时间先扣;扣完之后,**这一手**里超出主时间的部分才进读秒,
 * 每满一次读秒长度记一次;次数用完即超时。服务端在 get_state、落子和导航时结算,两次推送之间按本地流逝时间外推
 * (galaxy `components/PlayerCard.tsx` 同一套 —— 那个文件是 galaxy 的 MUI 卡,kiosk 不引它,只对齐算法)。
 * 服务端快照携带主时间累计、已用读秒次数与本手已记读秒用时;新基准到达后,本地外推从零重新开始。
 */
export interface GoClockReading {
  /** 主时间还剩几秒;用完或没有主时间时为 0。 */
  mainLeft: number;
  /** 本次读秒还剩几秒;还在主时间里时为 null。 */
  byoLeft: number | null;
  /** 还剩几次读秒。 */
  periodsLeft: number;
  expired: boolean;
}

export interface GoClockInput {
  /** 主时间,**分钟**(与 `timer.settings.main_time`、开局设置 `TIME_PRESETS` 同单位)。 */
  mainTimeMin: number;
  byoLength: number;
  byoPeriods: number;
  mainUsed: number;
  periodsUsed: number;
  /** 当前这一手已记的秒数(`timer.current_node_time_used`);只对轮到的一方有意义。 */
  nodeTimeUsed: number;
  active: boolean;
  /** 上一次计时基准变化之后本地流逝的秒数。 */
  elapsed: number;
}

export function readGoClock(i: GoClockInput): GoClockReading {
  const extra = i.active ? i.elapsed : 0;
  const mainTotal = Math.max(0, i.mainTimeMin) * 60;
  const periodsTotal = Math.max(0, i.byoPeriods);
  const mainLeft = Math.max(0, mainTotal - (i.mainUsed + extra));
  if (mainLeft > 0) {
    return { mainLeft, byoLeft: null, periodsLeft: Math.max(0, periodsTotal - i.periodsUsed), expired: false };
  }
  const byoLen = Math.max(0, i.byoLength);
  const mainAvailableAtNodeStart = Math.max(0, mainTotal - i.mainUsed);
  let overflow = Math.max(0, (i.active ? i.nodeTimeUsed : 0) + extra - mainAvailableAtNodeStart);
  let periodsUsed = i.periodsUsed;
  while (byoLen > 0 && overflow > byoLen && periodsUsed < periodsTotal) {
    overflow -= byoLen;
    periodsUsed += 1;
  }
  const periodsLeft = Math.max(0, periodsTotal - periodsUsed);
  if (byoLen <= 0 || periodsLeft <= 0) return { mainLeft: 0, byoLeft: 0, periodsLeft: 0, expired: true };
  return { mainLeft: 0, byoLeft: Math.max(0, byoLen - overflow), periodsLeft, expired: false };
}

/**
 * 这一局计不计时。**两段都要**:服务端说时限是开局设置写的(`configured`),且主时间或读秒至少一样非零。
 * 只看 `settings` 会把星阵 / 大厅局继承的默认「20 分 + 30 秒×5」当成真时限。
 */
export function isTimedGame(timer: GameState['timer']): boolean {
  const s = timer?.settings;
  return timer?.configured === true && !!s && (s.main_time > 0 || s.byo_length > 0);
}

const TICK_MS = 250;

/**
 * 一方的时钟读数;不计时的局返回 null。轮到的一方耗尽时调一次 `onExpired`(由假变真那一刻),
 * 以及计时基准换了(换了一手、服务端结算过)之后仍耗尽时再调一次 —— 服务端判「轮次过期」后前端重同步到新的一手,要能再核。
 */
export function useGoClock(gameState: GameState, color: 'B' | 'W', onExpired?: () => void): GoClockReading | null {
  const timer = gameState.timer;
  const timed = isTimedGame(timer);
  // 只在叶子上、且这一局没有终局事实时走钟 —— 与服务端 `update_timer` 同口径(它在有子节点时不计时)。
  // 翻到前面看棋时还按本地流逝倒数,会在服务端根本不会判的地方显示「超时」并发请求(r1 S6)。
  const active = timed && timer?.paused === false && !gameState.end_result && !gameState.terminal_result
    && (gameState.children?.length ?? 0) === 0 && gameState.player_to_move === color;
  const info = gameState.players_info[color];
  // 计时基准:服务端最近一次给的量。任何一个变了(换手、结算),本地流逝就从 0 重新数。
  const baseKey = `${gameState.game_id}|${timer?.settings.main_time}|${timer?.settings.byo_length}|${timer?.settings.byo_periods}|${active}|${info.main_time_used}|${info.periods_used}|${timer?.current_node_time_used ?? 0}|${gameState.current_node_id}`;
  const [tick, setTick] = useState({ key: baseKey, elapsed: 0 });

  useEffect(() => {
    if (!active) return undefined;
    const startedAt = Date.now();
    const id = window.setInterval(() => setTick({ key: baseKey, elapsed: (Date.now() - startedAt) / 1000 }), TICK_MS);
    return () => window.clearInterval(id);
  }, [active, baseKey]);

  const elapsed = tick.key === baseKey ? tick.elapsed : 0;
  const reading = timed && timer
    ? readGoClock({
      mainTimeMin: timer.settings.main_time,
      byoLength: timer.settings.byo_length,
      byoPeriods: timer.settings.byo_periods,
      mainUsed: info.main_time_used,
      periodsUsed: info.periods_used,
      nodeTimeUsed: timer.current_node_time_used,
      active,
      elapsed,
    })
    : null;

  const expired = active && !!reading?.expired;
  const onExpiredRef = useRef(onExpired);
  useEffect(() => { onExpiredRef.current = onExpired; }, [onExpired]);
  useEffect(() => { if (expired) onExpiredRef.current?.(); }, [expired, baseKey]);
  return reading;
}
