import { useState, type ReactNode } from 'react';
import PhysicalBoardGuard from './PhysicalBoardGuard';
import { readPhysicalMode } from '../../pages/tsumegoUnits';

/**
 * 做题路由外面那一层(T9)。形状照 `PlayInputGuard`(对弈,2026-08-23)。
 *
 * `PhysicalBoardGuard` 守的是「要用实体盘就得先标定」,它本身没错;错在它被**无条件**
 * 套在做题上 —— 做题的实体开关默认是**关**的(`tsumegoUnits.ts` 的 `readPhysicalMode`),
 * 只想在屏幕上做题的人,盒子一重启(几何恒为 required)就被整屏换成标定台,
 * 做题屏里专为这种情况写的「物理棋盘需先确认棋盘标定 / 去标定」也永远渲染不到。
 *
 * ⇒ 开关开着才走那道守卫。不要求识别就绪,和改之前一样。**不改 `PhysicalBoardGuard` 自己**:
 * 摆谱也用它,对弈那边包的是另一把偏好键。
 *
 * ⚠️ 偏好只在挂载时读一次(`useState` 的惰性初始化),不在每次渲染时读:
 * 渲染时读的话,人在做题屏里一拨开关、下一次上层重渲染时这里的子树就从「守卫包着」变成
 * 「直接渲染」,做题屏会被整个卸载重挂,这一题的计时和落子全没了。
 * 读一次够用:做题屏里要**打开**实体开关,要求识别就绪**且几何本次开机确认过**
 * (`TsumegoProblemPage` 的 `physicalAvailable`,放行条件照抄 `PhysicalBoardGuard`);
 * 页内打开之后几何又失效,这里不接管 —— 做题屏开关旁说原因并挂「去标定」(`physicalHint`)。
 * 已知边角:同一次进入里先关掉开关、之后几何又失效,这一次仍会被标定台拦下 —— 按返回再进就好。
 */
const TsumegoInputGuard = ({ children }: { children: ReactNode }) => {
  const [onBoard] = useState(readPhysicalMode);
  return onBoard
    ? <PhysicalBoardGuard sub="实体做题要先让摄像头看清盘面" fallback="/kiosk/tsumego">{children}</PhysicalBoardGuard>
    : <>{children}</>;
};

export default TsumegoInputGuard;
