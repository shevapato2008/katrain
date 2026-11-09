import { useTranslation } from '../../../hooks/useTranslation';
import { useState, type ReactNode } from 'react';
import { useLocation } from 'react-router-dom';
import { useGeometry } from '../../context/GeometryContext';
import { useBackTo } from '../../hooks/useBackTo';
import GeometryCalibrationScreen from './GeometryCalibrationScreen';

/**
 * 几何没就绪时,把整屏换成标定台。套在 `tsumego/problem/:id` 和 `baipu/session/:source` 外面。
 *
 * 🔴 **2026-08-24 补上返回键。** 上一版直接渲染裸的工作区 —— 而这两条都是 L2(无 Dock),
 * 顶栏又恒为品牌态、不带返回 ⇒ 用户从做题或摆谱走进来撞上「未标定」,**整屏一个出口都没有**,
 * 只能重启。返回去**打开被拦那一屏的那一页**(开局设置 / 单元列表 …,由那一页写进导航 state),
 * 不按浏览器历史后退:2026-09-21 板上卡顿时排队的 3 下点击连退出了 katrain(见 `useBackTo`)。
 *
 * 首次放行仍检查全部就绪条件；同一路由已进入后，设备瞬断不卸载页面。
 * `disabled` 视为放行 —— 没摄像头的盒子不该被标定台挡住。
 */
const PhysicalBoardGuard = ({
  children, requireRecognition = false, sub, fallback = '/kiosk/play',
}: {
  children: ReactNode;
  requireRecognition?: boolean;
  /** 为什么这一屏需要摄像头。**由调用点给** —— 做题和摆谱要说的不是同一句话。 */
  sub: string;
  /** 打开这一屏的那一页没写明返回去哪儿(继续上一局进来的)时,去这里(本模块首页)。 */
  fallback?: string;
}) => {
  const { t } = useTranslation();
  const { status } = useGeometry();
  const location = useLocation();
  const scope = `${location.key}|${location.pathname}`;
  const back = useBackTo(fallback);
  const geometryValid = status.phase === 'ready' && status.session_calibrated && status.capabilities.geometry_ready;
  const ready = status.phase === 'disabled' || (
    geometryValid
    && (!requireRecognition || status.capabilities.recognition_ready)
  );
  const [admission, setAdmission] = useState({ scope, admitted: !!ready });
  const admitted = admission.scope === scope && admission.admitted;
  const keepPage = !!ready || (admitted && geometryValid);
  if (admission.scope !== scope || admission.admitted !== keepPage) {
    setAdmission({ scope, admitted: keepPage });
  }

  if (keepPage) return <>{children}</>;

  return (
    <GeometryCalibrationScreen
      t={t}
      backLabel={t('Back', '返回')}
      onBack={back}
      title={t('vision:guard_title', '先标定棋盘')}
      sub={sub}
      requireRecognition={requireRecognition}
    />
  );
};

export default PhysicalBoardGuard;
