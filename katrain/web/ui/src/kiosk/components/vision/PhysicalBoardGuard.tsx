import type { ReactNode } from 'react';
import { useGeometry } from '../../context/GeometryContext';
import { useSafeBack } from '../../hooks/useSafeBack';
import GeometryCalibrationScreen from './GeometryCalibrationScreen';

/**
 * 几何没就绪时,把整屏换成标定台。套在 `tsumego/problem/:id` 和 `baipu/session/:source` 外面。
 *
 * 🔴 **2026-08-24 补上返回键。** 上一版直接渲染裸的工作区 —— 而这两条都是 L2(无 Dock),
 * 顶栏又恒为品牌态、不带返回 ⇒ 用户从做题或摆谱走进来撞上「未标定」,**整屏一个出口都没有**,
 * 只能重启。回到拦下他的那条路由的来路,那是唯一正确的去向 —— 但走 `useSafeBack`,不走裸
 * `navigate(-1)`:2026-09-21 板上卡顿时排队的 3 下点击连退出了 katrain(见那个 hook 的注释)。
 *
 * 放行条件**一个字没动**(`disabled` 视为放行 —— 没摄像头的盒子不该被标定台挡住)。
 */
const PhysicalBoardGuard = ({
  children, requireRecognition = false, sub, fallback = '/kiosk/play',
}: {
  children: ReactNode;
  requireRecognition?: boolean;
  /** 为什么这一屏需要摄像头。**由调用点给** —— 做题和摆谱要说的不是同一句话。 */
  sub: string;
  /** 已在本 app 第一条历史上时,返回去哪儿(本模块首页)。 */
  fallback?: string;
}) => {
  const { status } = useGeometry();
  const back = useSafeBack(fallback);
  const ready = status.phase === 'disabled' || (
    status.phase === 'ready' && status.session_calibrated && status.capabilities.geometry_ready
    && (!requireRecognition || status.capabilities.recognition_ready)
  );

  if (ready) return <>{children}</>;

  return (
    <GeometryCalibrationScreen
      backLabel="返回"
      onBack={back}
      title="先标定棋盘"
      sub={sub}
      requireRecognition={requireRecognition}
    />
  );
};

export default PhysicalBoardGuard;
