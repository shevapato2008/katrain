import { useEffect, useState } from 'react';
import { BaipuAPI } from '../../api/baipuApi';
import type { GeometryPhase } from '../../api/geometryApi';
import { useTranslation } from '../../hooks/useTranslation';
import GeometryCalibrationScreen from '../components/vision/GeometryCalibrationScreen';
import PhysicalBoardGuard from '../components/vision/PhysicalBoardGuard';
import { useGeometry } from '../context/GeometryContext';
import { useBackTo } from '../hooks/useBackTo';
import { KioskPagebar } from '../shell/KioskPagebar';
import BaipuSessionPage from './BaipuSessionPage';

/**
 * 标定线程还在跑的那五个 phase。与 `GeometryContext.tsx` 的 `ACTIVE`、服务端
 * `GeometryCalibrationService.ACTIVE_PHASES` 是同一份名单(那两处都没导出,这里不为它改别人的文件)。
 */
const CALIBRATION_RUNNING: readonly GeometryPhase[] = [
  'waiting_empty', 'dark_reference', 'flashing_corners', 'verifying', 'building_baseline',
];

/**
 * `/kiosk/baipu/session/:source` 的入口:先问这台机器摆谱拍不拍照,再决定要不要先标定。
 *
 * - **上线态(`collect=false`,盒子默认)**:不套 `PhysicalBoardGuard`。摆谱只用灯,灯的
 *   (行,列)→灯珠是公式 LUT,不需要摄像头。以前这条路由无条件套守卫 ⇒ 服务每次重启
 *   `session_calibrated=false`,不先标定摄像头就进不了摆谱,而上线版摆谱根本不用摄像头。
 *   **唯一的例外:标定线程正在跑。** 标定屏的返回键不取消标定(设置 → 开始标定 → 返回,服务端线程
 *   接着跑),而摆谱屏一挂就点灯;标定每个锚点都是 clear → 拍熄灯帧 → 点亮 → 拍亮灯帧,`/led/point`
 *   先 CLEAR 再点、没有忙检查 ⇒ 两边互相冲掉对方的灯。以前是守卫顺带挡住的,摘掉守卫要把这一条留下。
 *   这时给标定屏(进度 + 「取消标定」),跑完或取消后 phase 离开这五态,直接挂摆谱屏。
 *   **读到过**的 required / failed / cancelled / disabled / ready / degraded 一律直接放行。
 *   ⚠️ 「读到过」是判据的一半:`loaded=false` 时 `status.phase` 是 `GeometryProvider` 的**初值**
 *   `required`,不是结论。刷新直接进这条 URL 时 `/mode` 可能先回 —— 只看 phase 就会先挂页面点灯、
 *   等迟到的 `flashing_corners` 再把它卸掉(卸载还要清一次灯),照样冲掉标定。所以没读到之前只给
 *   「正在检查棋盘状态」+ 返回键;Provider 读不到时每秒自己重试,读到就往下走。
 * - **采集态(`collect=true`,`--baipu-collect` 起的采集机)**:照旧先过守卫 —— 拍照要几何锁
 *   (守卫在标定进行中本来就不放行,不用另管)。
 *
 * 守卫必须包在**页面外面**、不能挪进页面里:页面挂着时它的效应会点灯,而标定台也在点灯。
 * 还没问到时也给页控条:这一屏不许再是一块没有出口的屏(K1 修的就是这个)。
 * `collect` 只会从 null 变一次:`BaipuAPI.mode()` 恰好 settle 一次(超时即「不拍」,迟到的结果丢掉)。
 */
export default function BaipuSessionRoute() {
  const { t } = useTranslation();
  // 与摆谱屏同一个去处:打开它的那一页(棋谱屏 / 棋谱详情),没写明回棋谱屏。
  const back = useBackTo('/kiosk/kifu');
  const { status, loaded } = useGeometry();
  const [collect, setCollect] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    void BaipuAPI.mode().then((m) => { if (!cancelled) setCollect(m.collect); });
    return () => { cancelled = true; };
  }, []);

  // 上线态还要等棋盘状态**读到过**(见页头注「读到过」那段);采集态交给守卫。
  if (collect === null || (!collect && !loaded)) {
    return (
      <div className="kiosk-layout-b" data-testid="baipu-session-page">
        <KioskPagebar
          testId="baipu-pagebar"
          backLabel={t('baipu:back_kifu', '棋谱')}
          onBack={back}
          title={t('baipu:title', '摆谱')}
        />
        <div className="empty" data-testid="baipu-loading">
          <h4>{collect === null ? t('baipu:loading', '正在读这份谱') : t('baipu:checking_board', '正在检查棋盘状态')}</h4>
        </div>
      </div>
    );
  }
  if (collect) {
    return (
      <PhysicalBoardGuard sub={t('baipu:guard_sub_collect', '采集训练数据要先让摄像头看清盘面')} fallback="/kiosk/kifu">
        <BaipuSessionPage collect />
      </PhysicalBoardGuard>
    );
  }
  if (CALIBRATION_RUNNING.includes(status.phase)) {
    return (
      <GeometryCalibrationScreen
        backLabel={t('baipu:back_kifu', '棋谱')}
        onBack={back}
        title={t('baipu:calib_running_title', '棋盘标定还在进行')}
        sub={t('baipu:calib_running_sub', '标定也在用灯 · 跑完或取消后直接进摆谱')}
      />
    );
  }
  return <BaipuSessionPage collect={false} />;
}

// 已知不处理的一小段窗口:服务端先把 phase 写成终态、再在 finally 里 led.clear,轮询恰好卡在两者之间时
// 摆谱第一颗灯会被清掉一次,屏上「重新点灯」即可恢复;摆谱屏挂着时标定才开始只可能来自别的客户端,
// 盒上不会发生。都不为它加东西。
