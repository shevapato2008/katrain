import { useTranslation } from '../../../hooks/useTranslation';
import { KioskConsoleRail } from '../../shell/KioskConsoleRail';
import { GoBoardSvg } from '../../shell/GoBoardSvg';
import type { StatusCell } from '../../shell/KioskStatusCells';
import { useOptionalVision } from '../../context/VisionContext';
import { useOptionalGeometry } from '../../context/GeometryContext';

/**
 * 把 `VisionContext` / `GeometryContext` 接到共享外壳的左栏上 —— 替掉
 * `SmartBoardConsole.tsx`(它自己造了一套 322 + 2×20 外边距 = 362 的几何,
 * 右边只剩 662;规范要的是 296 + 16 + 680)。
 *
 * **壳是共享的,接线是围棋自己的**,所以拆成两个文件:`shell/KioskConsoleRail` 只认
 * props,四棋类同一份;本文件知道围棋盘上有摄像头、有标定、有 LED。
 *
 * ⚠️ 镜像框里画的是**一块压暗的空盘**,一颗子都没有 —— 识别出的盘面还没有喂到这儿来。
 * 三件事要分开:
 *   · **不画盘**(上一版)= 画面上少一块东西,和稿子对不上,也没说清楚为什么;
 *   · **画一盘子** = 拿假数据充门面,不许;
 *   · **画空盘 + 压暗 + 同步行写「识别的盘面还没接进来」** = 盘在、但我看不到它。这一条才对。
 * `.gob.is-muted` 就是「看不到盘」和「盘上没子」的区分,别把它当成一个装饰。
 */
/**
 * 规范 §5:课程屏的左栏和对弈屏**逐像素相同**,差别只在同步行那句话
 * (对弈:「识别的盘面还没接进来」;课程:「课上的图会摆到盘上 / 等选课」)。
 * 所以开的口子只有这一处 —— 标题、盘、三格状态一律不给改。
 */
export function GoConsoleRail({ syncLeft, syncRight, help = false }: {
  syncLeft?: string;
  syncRight?: string;
  help?: boolean;
} = {}) {
  const { t } = useTranslation();
  const vision = useOptionalVision();
  const geometry = useOptionalGeometry();
  const cameraCell = (connected?: boolean | null): StatusCell => connected == null
    ? { label: t('Camera', '摄像头'), value: '—' }
    : { label: t('Camera', '摄像头'), value: connected ? t('Connected', '已连接') : t('Disconnected', '未连接'), tone: connected ? 'good' : 'bad' };
  const ledCell = (connected?: boolean | null): StatusCell => connected == null
    ? { label: 'LED', value: t('未确认', '未确认') }
    : { label: 'LED', value: connected ? t('Connected', '已连接') : t('Disconnected', '未连接'), tone: connected ? 'good' : 'warn' };
  const geometryCell = (phase?: string): StatusCell => {
    const label = t('Calibration', '标定');
    if (phase === undefined) return { label, value: '—' };
    if (phase === 'ready') return { label, value: t('已标定', '已标定'), tone: 'good' };
    if (phase === 'degraded' || phase === 'failed') return { label, value: t('异常', '异常'), tone: 'bad' };
    return { label, value: t('需校准', '需校准'), tone: 'warn' };
  };

  const statuses: readonly StatusCell[] = [
    cameraCell(vision?.visionStatus.cameraConnected),
    geometryCell(geometry?.status.phase),
    ledCell(vision?.visionStatus.ledConnected),
  ];

  return (
    <KioskConsoleRail
      helpLabel={t('实体棋盘说明', '实体棋盘说明')}
      closeLabel={t('Got it', '知道了')}
      title={t("实体棋盘", "实体棋盘")}
      sub="Camera board"
      board={<GoBoardSvg muted label={t("实体棋盘镜像:识别的盘面还没接进来", "实体棋盘镜像:识别的盘面还没接进来")} />}
      syncLeft={syncLeft ?? t("识别的盘面还没接进来", "识别的盘面还没接进来")}
      syncRight={syncRight ?? t("暂不可用", "暂不可用")}
      statuses={statuses}
      help={help ? t("这里展示实体棋盘与设备状态。识别盘面尚未接入时，预览显示空盘；摄像头、标定和 LED 的状态来自设备。", "这里展示实体棋盘与设备状态。识别盘面尚未接入时，预览显示空盘；摄像头、标定和 LED 的状态来自设备。") : undefined}
    />
  );
}
