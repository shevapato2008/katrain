import { useEffect, useState } from 'react';

/**
 * 屏上那条走秒 —— 现在只服务一件事:**距离下一次自动重试还有多久。**
 *
 * 这里曾经还有一个 `aiLadderExits()`,算的是「这扇门什么时候打开」(接管窗口、放弃窗口)。
 * 那两扇门连同它们的门槛一起删掉了:它们回答的是「另一台设备是不是真的死了」,而那个
 * 问题不需要回答 —— 站在两台机器之间的是同一个人,他就在屏幕前。剩下的这条倒计时不是
 * 同一类东西,它数的不是权限,是 outbox 下一次真的会发请求的时刻,所以它留下来了。
 */

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
 * 每秒走一格,到点自己归零 —— 不等下一次状态刷新。
 *
 * 走完了不代表下一次重试**已经**发生:后台复查隔十几秒才回来一次。所以调用方在 0:00
 * 之后该说「正在重试」,不该继续显示一个停在 0:00 的倒计时 —— 那是屏上唯一会被当成
 * 卡死的画面。
 *
 * 到点之后停表(总时长走完就不再起 interval),免得一个开着的页面永远每秒重渲染。
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
