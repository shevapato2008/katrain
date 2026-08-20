import { useEffect, useState } from 'react';
import { identityPresentation, type ShellIdentity } from './identityPresentation';

function clockText(date: Date): string {
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
}

/**
 * 先对齐到**下一个整分**,之后才每 60 秒一跳(五子棋 hooks/useClock.ts 的做法)。
 * 挂载即 `setInterval(60_000)` 会漂:最坏要等 59 秒才翻第一次,屏上的分钟数一直是慢的。
 * 国象那份 1 秒一跳也能对,但为同一个 HH:MM 多渲染 60 倍。
 */
function useMinuteClock(): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    let interval: number | undefined;
    const timeout = window.setTimeout(() => {
      setNow(new Date());
      interval = window.setInterval(() => setNow(new Date()), 60_000);
    }, 60_000 - (Date.now() % 60_000));
    return () => {
      window.clearTimeout(timeout);
      if (interval !== undefined) window.clearInterval(interval);
    };
  }, []);
  return now;
}

/**
 * §6 上边条。**任何层级、任何模块都不变高、不隐藏**(防跳铁律 1),
 * 右簇内容与位置在所有页面完全恒定(防跳铁律 2)。
 *
 * 「智星盒」三个字走**龙藏行楷**,只此一处(规范 §2/§9)。字族与 `font-synthesis:none`
 * 都由 `tokens.css` 的 `.kiosk-topbar__brand-zh` 给,这里**不要**再写 sx/style 覆盖 ——
 * 上一轮那个 bug 正是 React 侧把字族覆盖掉了。
 *
 * 返回、2D/3D、页面标题一律**不在这里**,下放到 §11 的页控条。
 *
 * ⚠️ 顶栏上**没有**引擎状态点、摄像头、标定、设置齿轮(D9)。象棋 / 国象 / 五子棋
 * 三家顶栏都是零指示器零齿轮;器件状态四家共同的位置是 L1 左栏 `.kiosk-console`
 * 底部那三格(围棋在 `SmartBoardConsole` 里已经有了),L3 走 `VisionSyncOverlay` +
 * `PhysicalPlayStatusChip`。设置的入口在 Dock 里,顶栏再放一个是两个入口。
 */
export function KioskTopbar({ identity, onHome, homeBusy = false }: {
  identity: ShellIdentity;
  onHome?: () => void;
  homeBusy?: boolean;
}) {
  const clock = clockText(useMinuteClock());
  const presented = identityPresentation(identity);

  return (
    <header className="kiosk-topbar">
      {/* 规范 §10 钉死的那一份 logo。围棋是青毡深底,不加象棋那条 invert 滤镜。
          alt="" 是有意的:紧挨着就是「智星盒 StellaBox」两个可读文本,
          读屏软件再念一遍图片说明就是复读。 */}
      <img className="kiosk-topbar__logo" src="/assets/img/logo-white.png" alt="" />
      <span className="kiosk-topbar__brand">
        <span className="kiosk-topbar__brand-zh" data-testid="kiosk-brand-zh">智星盒</span>
        <span className="kiosk-topbar__brand-en">StellaBox</span>
      </span>
      <span className="kiosk-topbar__rule" aria-hidden="true" />
      <span className="kiosk-topbar__game">围棋</span>
      <div className="kiosk-topbar__right">
        {onHome && (
          <button
            type="button"
            className="kiosk-topbar__home"
            aria-label="返回智星盒主页"
            data-testid="kiosk-home-action"
            disabled={homeBusy}
            onClick={onHome}
          >
            <span className="kiosk-topbar__home-icon" aria-hidden="true" />
            <span>主页</span>
          </button>
        )}
        <span className="kiosk-topbar__avatar" aria-hidden="true">{presented.avatar}</span>
        <span className="kiosk-topbar__user" data-testid="header-username">{presented.label}</span>
        {/* dateTime 和正文复用同一份格式化结果 —— 各写一套会独立漂移。 */}
        <time className="kiosk-topbar__clock" data-testid="clock" dateTime={clock}>{clock}</time>
      </div>
    </header>
  );
}

export default KioskTopbar;
