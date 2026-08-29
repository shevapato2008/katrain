import type { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGeometry } from '../../context/GeometryContext';
import GeometryCalibrationScreen from './GeometryCalibrationScreen';

/**
 * 几何没就绪时,把整屏换成标定台。套在 `tsumego/problem/:id` 和 `baipu/session/:source` 外面。
 *
 * 🔴 **2026-08-24 补上返回键。** 上一版直接渲染裸的工作区 —— 而这两条都是 L2(无 Dock),
 * 顶栏又恒为品牌态、不带返回 ⇒ 用户从做题或摆谱走进来撞上「未标定」,**整屏一个出口都没有**,
 * 只能重启。`navigate(-1)` 回到拦下他的那条路由的来路,那是唯一正确的去向。
 *
 * 放行条件**一个字没动**(`disabled` 视为放行 —— 没摄像头的盒子不该被标定台挡住)。
 */
const PhysicalBoardGuard = ({
  children, requireRecognition = false, sub,
}: {
  children: ReactNode;
  requireRecognition?: boolean;
  /** 为什么这一屏需要摄像头。**由调用点给** —— 做题和摆谱要说的不是同一句话。 */
  sub: string;
}) => {
  const { status } = useGeometry();
  const navigate = useNavigate();
  const ready = status.phase === 'disabled' || (
    status.phase === 'ready' && status.session_calibrated && status.capabilities.geometry_ready
    && (!requireRecognition || status.capabilities.recognition_ready)
  );

  if (ready) return <>{children}</>;

  return (
    <GeometryCalibrationScreen
      backLabel="返回"
      onBack={() => navigate(-1)}
      title="先标定棋盘"
      sub={sub}
      requireRecognition={requireRecognition}
    />
  );
};

export default PhysicalBoardGuard;
