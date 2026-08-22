import { KioskConsoleRail } from '../../shell/KioskConsoleRail';
import { GoBoardSvg } from '../../shell/GoBoardSvg';
import type { StatusCell } from '../../shell/KioskStatusCells';
import { GO_HARDWARE_CELLS } from '../../shell/goHardware';
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
export function GoConsoleRail() {
  const vision = useOptionalVision();
  const geometry = useOptionalGeometry();

  // ⚠️ Context 缺席(`useOptional*` 返回 null)和「读到了、结果是没连上」是**两回事**。
  // 前者保持 GO_HARDWARE_CELLS 的「—」不点灯,后者才给红灯 ——
  // 「否定的答复不携带原因」:一条消息的缺席不能当成判别位。
  const statuses: readonly StatusCell[] = vision || geometry
    ? [
        cameraCell(vision?.visionStatus.cameraConnected),
        geometryCell(geometry?.status.phase),
        ledCell(vision?.visionStatus.ledConnected),
      ]
    : GO_HARDWARE_CELLS;

  return (
    <KioskConsoleRail
      title="实体棋盘"
      sub="Camera board"
      board={<GoBoardSvg muted label="实体棋盘镜像:识别的盘面还没接进来" />}
      syncLeft="识别的盘面还没接进来"
      syncRight="暂不可用"
      statuses={statuses}
    />
  );
}

const cameraCell = (connected?: boolean | null): StatusCell =>
  connected == null
    ? { label: '摄像头', value: '—' }
    : { label: '摄像头', value: connected ? '已连接' : '未连接', tone: connected ? 'good' : 'bad' };

// ⚠️ `ledConnected` 的类型是 `boolean | null` —— **null 是「后端没说」,不是「没连上」**
// (`VisionContext.tsx:41` 的 `r.led_connected ?? null`)。旧 `SmartBoardConsole.tsx:83` 写的是
// `?? false`,于是「没说」被画成一颗琥珀灯的「未连接」。一条消息的缺席不是判别位。
const ledCell = (connected?: boolean | null): StatusCell =>
  connected == null
    ? { label: 'LED', value: '—' }
    // 没连上是**琥珀不是红**:没有它照样能下棋,只是没有提示灯。摄像头没连上才是故障。
    : { label: 'LED', value: connected ? '就绪' : '未连接', tone: connected ? 'good' : 'warn' };

const geometryCell = (phase?: string): StatusCell => {
  if (phase === undefined) return { label: '标定', value: '—' };
  if (phase === 'ready') return { label: '标定', value: '已标定', tone: 'good' };
  if (phase === 'degraded' || phase === 'failed') return { label: '标定', value: '异常', tone: 'bad' };
  return { label: '标定', value: '需校准', tone: 'warn' };
};
