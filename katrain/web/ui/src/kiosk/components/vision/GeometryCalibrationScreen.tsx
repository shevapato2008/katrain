import { useCallback, useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';

import { KioskPagebar } from '../../shell/KioskPagebar';
import { KioskStatusCells, type StatusCell } from '../../shell/KioskStatusCells';
import { KioskScrollZone } from '../../shell/KioskScrollZone';
import GeometryVideoPanel from './GeometryVideoPanel';
import CameraGeometryOverlay from './CameraGeometryOverlay';
import { useGeometry } from '../../context/GeometryContext';
import { GeometryAPI, type GeometryLayout, type GeometryPhase, type GeometryStatus, type LightingReason } from '../../../api/geometryApi';
import LightingWarningDialog from './LightingWarningDialog';
import { useLightingWarning } from '../../hooks/useLightingWarning';
import { useTranslation } from '../../../hooks/useTranslation';
import { useVoice, type VoiceName } from '../../hooks/useVoice';
import {
  buildAnchorGeometryModel, buildRawGeometryModel, buildWarpedGeometryModel,
  type OverlayViewport,
} from './geometryOverlay';

/**
 * 设置入口与实体盘守卫共用这一整屏。页控条的返回文案由入口提供。
 * 每个 LED 定位点内部各自拍摄熄灯帧与亮灯帧；用户只看五点总进度。
 */

/** 用户可见的四步；四角和天元合为一次五点定位。 */
const STEPS = [
  { key: 'empty', title: '等待棋盘稳定' },
  { key: 'exposure', title: '确认并锁定曝光' },
  { key: 'points', title: '定位棋盘' },
  { key: 'baseline', title: '生成空盘基线' },
] as const;

/**
 * 实时画面按屏上尺寸推(后端 `?scale=`)。画面区只有 ~514 px 宽:原样推 1920x1080 / 1056x1056 时,
 * RK3562 上标定收尾那 19 s 里页面主线程 6.8 s 花在解码/绘制这些大图上(JS 合计 <2%),点击排队。
 * 缩完仍不小于显示尺寸:原始 1920/3 = 640,俯视 1056/2 = 528。
 */
const RAW_STREAM_SCALE = 3;
const WARPED_STREAM_SCALE = 2;
const ACTIVE_PHASES = new Set([
  'waiting_empty', 'waiting_stable', 'converging_exposure', 'dark_reference', 'flashing_corners', 'verifying',
  'building_baseline', 'obstructed', 'lighting_paused', 'lighting_rechecking',
]);

const isExposureError = (error?: string | null) =>
  Boolean(error && (/exposure/i.test(error) || error === 'frame_overexposed' || error === 'frame_underexposed'));

function lightingReason(status: GeometryStatus): LightingReason | null {
  const exposure = status.metrics?.exposure;
  if (status.phase !== 'failed' || !exposure
    || !Number.isFinite(exposure.median) || exposure.median < 0 || exposure.median > 255
    || !Number.isFinite(exposure.clip_frac) || exposure.clip_frac < 0 || exposure.clip_frac > 1
    || !Number.isFinite(exposure.shadow_frac) || exposure.shadow_frac < 0 || exposure.shadow_frac > 1) return null;
  if (exposure.confirmed === true
    && (exposure.reason === 'frame_overexposed' || exposure.reason === 'frame_underexposed')) return exposure.reason;
  return status.error === 'frame_overexposed' || status.error === 'frame_underexposed' ? status.error : null;
}

const GTP_LETTERS = 'ABCDEFGHJKLMNOPQRSTUVWXYZ';
const gtpPoint = (row: number, col: number) => `${GTP_LETTERS[col] ?? '?'}${19 - row}`;

interface Diagnostic { title: string; body: string; action: string; detail?: string; kind?: 'relocate' }

/**
 * 「失败时给**诊断**不给『重试』」是稿子写在屏上的承诺。兑现它的方式是失败那一刻出现的是
 * 一张**点名具体原因**的卡,而不是一颗孤零零的重试键。这段逐字保留自上一版,一个分支没删。
 */
function buildDiagnostic(error?: string | null, stoppedPhase?: GeometryPhase | null): Diagnostic {
  const raw = error ?? '';
  if (/manual exposure lock|verified manual exposure/.test(raw)) {
    return {
      title: '摄像头曝光没有锁定',
      body: '没能确认固定曝光状态，这次标定已停止。',
      action: '检查摄像头连接，再重新开始标定。',
      detail: raw,
    };
  }
  if (raw === 'frame_overexposed' || raw === 'frame_underexposed') {
    return {
      title: raw === 'frame_overexposed' ? '摄像头画面过亮' : '摄像头画面过暗',
      body: '盘面细节看不清，这次标定无法继续。',
      action: '换到光线合适的位置，再重新开始标定。',
      detail: raw,
    };
  }
  if (stoppedPhase === 'converging_exposure' || isExposureError(raw)) {
    return {
      title: '曝光收敛没有完成',
      body: '摄像头未能完成曝光调整和锁定。',
      action: '检查摄像头连接，再重新开始标定。',
      detail: raw || undefined,
    };
  }
  const anchor = raw.match(/^anchor_not_found:(\d+),(\d+)$/);
  if (anchor) {
    const row = Number(anchor[1]);
    const col = Number(anchor[2]);
    return {
      title: `没找到 ${gtpPoint(row, col)} 这个点的灯`,
      body: '多半是这三种:那个点上压着一颗子、这一带的灯太暗、或者摄像头被挪过。',
      action: `把 ${gtpPoint(row, col)} 附近清空，再看一眼摄像头有没有动过。`,
      detail: raw,
    };
  }
  if (raw === 'board_moved' || raw === 'displaced') {
    return {
      title: '棋盘和上次标定的位置对不上了',
      body: '摄像头或棋盘被挪动过，之前那份几何已经不能用了。',
      action: '把棋盘摆回原位；摆不回去就重新标定一次。',
    };
  }
  if (raw === 'non_empty_baseline') {
    return {
      title: '生成基线时盘上还有子',
      body: '空盘基线是之后识子的底片，底片上有子，之后每一手都会认错。',
      action: '把盘清空，再重新开始标定。',
      detail: raw,
    };
  }
  if (raw === 'led_clear_failed' || raw === 'baseline_frames_missing') {
    return {
      title: raw === 'led_clear_failed' ? '灯没能全部熄灭' : '基线照片没拍够',
      body: '前面五个点都找到了，卡在最后一步。多半是灯带或摄像头这一刻掉线了。',
      action: '检查灯带和摄像头的接线，再重新开始标定。',
      detail: raw,
    };
  }
  return {
    title: '这次标定没有完成',
    body: '没有拿到能用的棋盘几何。',
    action: '先确认盘是空的、摄像头没被挪过，再重新开始标定。',
    detail: raw || undefined,
  };
}

export interface GeometryCalibrationScreenProps {
  /** 页控条返回键上的字。**guard 和设置两条路不一样** —— 见页头注。 */
  backLabel: string;
  onBack: () => void;
  title: string;
  sub: string;
  /** guard 那一路:除了几何,还要求识别模型就绪。 */
  requireRecognition?: boolean;
  allowExistingReuse?: boolean;
}

export function GeometryCalibrationScreen({
  backLabel, onBack, title, sub, requireRecognition = false, allowExistingReuse = true,
}: GeometryCalibrationScreenProps) {
  const { status, loaded, startCalibration, confirmExisting, cancelCalibration, recheckLighting, relocate } = useGeometry();
  const { t } = useTranslation();
  const voice = useVoice();
  const { speak, stop } = voice;
  const lightingWarning = useLightingWarning(lightingReason(status), String(status.geometry_revision ?? 'unknown'), voice);
  const spokenRef = useRef(new Set<VoiceName>());
  const sawRunningRef = useRef(false);

  const [layout, setLayout] = useState<GeometryLayout | null>(null);
  const [rawFrame, setRawFrame] = useState<{ width: number; height: number } | null>(null);
  const [starting, setStarting] = useState(false);
  const [confirmingManual, setConfirmingManual] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [layoutError, setLayoutError] = useState<string | null>(null);
  const [manualView, setManualView] = useState<'raw' | 'warped' | null>(null);
  const [relocating, setRelocating] = useState(false);
  const [relocateError, setRelocateError] = useState<string | null>(null);
  const [lightError, setLightError] = useState<string | null>(null);
  const [rechecking, setRechecking] = useState(false);

  const phase = status.phase;
  const active = ACTIVE_PHASES.has(phase);
  const waitingForBoard = phase === 'waiting_empty' || phase === 'waiting_stable';
  const cameraReady = status.capabilities.camera_ready;
  const ledReady = status.capabilities.led_ready;

  useEffect(() => {
    if (active) sawRunningRef.current = true;
    let name: VoiceName | null = null;
    if (waitingForBoard && !spokenRef.current.has('calibration_move_hand')) name = 'calibration_move_hand';
    else if (phase === 'obstructed') name = 'calibration_obstructed';
    else if (phase === 'lighting_paused' && status.pause_reason === 'frame_overexposed') name = 'calibration_too_bright';
    else if (phase === 'lighting_paused' && status.pause_reason === 'frame_underexposed') name = 'calibration_too_dark';
    else if ((phase === 'flashing_corners' || phase === 'verifying') && !spokenRef.current.has('calibration_running')) name = 'calibration_running';
    else if (phase === 'ready' && sawRunningRef.current) name = 'calibration_done';
    if (name && !spokenRef.current.has(name)) {
      spokenRef.current.add(name);
      speak(name);
    }
    if (phase === 'cancelled' || phase === 'failed') stop();
  }, [active, waitingForBoard, phase, status.pause_reason, speak, stop]);

  /**
   * 已经定位到的锚点数。**用服务端那个数组,不用 `progress.current`** ——
   * 前者是标定器每定位成功一个就 append 一次的权威记录(start 时清空),
   * 后者是「正在试第几个」(`index - 1`),两者在失败那一刻差一个。
   */
  const anchorCount = status.detected_anchors?.length ?? 0;

  useEffect(() => {
    let cancelled = false;
    if (!(status.last_valid || phase === 'ready' || phase === 'degraded')) { setLayout(null); return; }
    GeometryAPI.layout()
      .then((next) => { if (!cancelled) { setLayout(next as GeometryLayout); setLayoutError(null); } })
      .catch((error: unknown) => {
        if (cancelled) return;
        setLayoutError(error instanceof Error ? error.message : '无法读取棋盘几何');
      });
    return () => { cancelled = true; };
  }, [status.last_valid, phase, status.geometry_revision]);

  const rawModelForViewport = useCallback((viewport: OverlayViewport) => {
    if (active) {
      const frame = rawFrame ?? layout?.frame;
      return frame ? buildAnchorGeometryModel(status.detected_anchors ?? [], frame, viewport) : null;
    }
    return layout ? buildRawGeometryModel(layout, phase, viewport) : null;
  }, [active, rawFrame, layout, phase, status.detected_anchors]);

  const warpedModelForViewport = useCallback((viewport: OverlayViewport) => (
    layout ? buildWarpedGeometryModel(
      layout.out_size, layout.stale ? 'degraded' : phase, viewport, layout.warped_margin_cells ?? 0,
    ) : null
  ), [layout, phase]);

  // ── 视图切换 ───────────────────────────────────────────────────────────────
  //
  // While calibrating, the previous geometry is invalid and warped video is
  // unavailable. Keep the raw live preview visible regardless of the last choice.
  const view: 'raw' | 'warped' = active ? 'raw' : manualView ?? (layout && phase === 'ready' ? 'warped' : 'raw');

  // ── 动作 ───────────────────────────────────────────────────────────────────
  const start = async () => {
    spokenRef.current.clear();
    sawRunningRef.current = false;
    spokenRef.current.add('calibration_move_hand');
    speak('calibration_move_hand');
    setStarting(true);
    setActionError(null);
    // 上一次「对齐外框」的失败卡排在诊断链最前:不清掉,这一次按键若失败(phase 不变),新错误会被旧卡盖住。
    setRelocateError(null);
    try {
      // `trigger` 区分「第一次自动标定」和「操作员按下重来」。两者走的是**同一条** LED 流程
      // (后端 `service.start` → `LedGeometryCalibrator.calibrate`),差别只在这条记录上 ——
      // 但那是既有行为,重画不该顺手改掉它。
      await startCalibration(phase === 'required' ? 'auto' : 'manual');
      setConfirmingManual(false);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : '启动标定失败');
    } finally {
      setStarting(false);
    }
  };

  /** 标定好了还要再按一次:那是在确认「我真的要作废现在这份、重来」。 */
  const handleStart = () => {
    if (phase === 'ready' && !confirmingManual) { setConfirmingManual(true); return; }
    void start();
  };

  const reuseExisting = async () => {
    setStarting(true);
    setActionError(null);
    setRelocateError(null);
    try {
      await confirmExisting();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : '沿用上次标定失败');
    } finally {
      setStarting(false);
    }
  };

  const handleRelocate = async () => {
    setRelocating(true);
    setRelocateError(null);
    setActionError(null);
    try {
      await relocate();
    } catch (err) {
      // 失败要说话。最常见的一种是外框被人挡住 / 画面太暗,说得出来用户才知道怎么办。
      setRelocateError(
        err instanceof Error && /no_board_detected/.test(err.message)
          ? t('vision:relocate_no_board', '画面里找不到棋盘外框，挪开挡住边框的东西再试一次。')
          : t('vision:relocate_failed', '再试一次；一直不行就清空棋盘重新标定。'),
      );
    } finally {
      setRelocating(false);
    }
  };

  const handleRecheckLighting = async () => {
    if (rechecking || phase !== 'lighting_paused') return;
    setRechecking(true);
    setLightError(null);
    try {
      await recheckLighting();
    } catch (error) {
      setLightError(error instanceof Error ? error.message : '光线重检没有启动，请再试一次。');
    } finally {
      setRechecking(false);
    }
  };

  useEffect(() => { setRelocateError(null); }, [phase]);

  // ── 五步的状态 ─────────────────────────────────────────────────────────────
  //
  const paused = phase === 'obstructed' || phase === 'lighting_paused' || phase === 'lighting_rechecking';
  const runningStep = phase === 'building_baseline' || (paused && anchorCount === 5) ? 3
    : phase === 'flashing_corners' || phase === 'verifying' || (paused && anchorCount > 0) ? 2
    : phase === 'converging_exposure' || phase === 'dark_reference' || phase === 'lighting_paused' || phase === 'lighting_rechecking' ? 1
        : 0;

  /**
   * 优先使用服务端保存的失败 / 取消前阶段。旧响应才通过曝光错误或锚点计数回落。
   */
  const brokenStep = status.stopped_phase === 'building_baseline' || anchorCount === 5 ? 3
    : status.stopped_phase === 'flashing_corners' || status.stopped_phase === 'verifying' || anchorCount > 0 ? 2
      : status.stopped_phase === 'converging_exposure' || status.stopped_phase === 'dark_reference'
        || isExposureError(status.error) ? 1 : 0;
  const failed = phase === 'failed';
  const cancelled = phase === 'cancelled';
  const stopped = failed || cancelled;

  /** 没拿到质量指标时不用绿色暗示五点全部通过。 */
  const qualityTone = (): 'done' | 'warn' | 'plain' => {
    if (typeof inliers !== 'number') return 'plain';
    return inliers >= 5 ? 'done' : 'warn';
  };

  const stepState = (i: number): 'done' | 'now' | 'bad' | 'warn' | 'paused' | 'todo' | 'plain' => {
    if (phase === 'ready') return i === 3 ? qualityTone() : 'done';
    if (stopped) {
      if (i < brokenStep) return 'done';
      if (i === brokenStep) return failed ? 'bad' : 'warn';
      return 'todo';
    }
    if (!active) return i === 0 ? 'now' : 'todo';
    if (i < runningStep) return 'done';
    if (i === runningStep) return paused ? 'paused' : 'now';
    return 'todo';
  };

  const inliers = status.metrics?.inlier_count;

  const stepTag = (i: number, state: string): { text: string; cls: string } => {
    if (state === 'done') return { text: '完成', cls: 'kiosk-tag--win' };
    if (state === 'plain') return { text: '完成', cls: '' };
    if (state === 'now') return { text: waitingForBoard && i === 0 ? '等待中' : '进行中', cls: '' };
    if (state === 'paused') return { text: '已暂停', cls: 'kiosk-tag--warn' };
    if (state === 'bad') return { text: '失败', cls: 'kiosk-tag--bad' };
    // 第 5 步的 warn 是「完成但点数不足」,别的步骤的 warn 是「已取消」。
    if (state === 'warn') {
      return i === 3 && phase === 'ready'
        ? { text: `完成 · ${inliers} / 5`, cls: 'kiosk-tag--warn' }
        : { text: '已取消', cls: 'kiosk-tag--warn' };
    }
    return { text: '未开始', cls: 'kiosk-tag--dim' };
  };

  // ── 摄像头画面底下那条 ─────────────────────────────────────────────────────
  const capLeft = (): string => {
    if (phase === 'ready' || anchorCount === 5) return '5 / 5 已定位';
    if (anchorCount > 0) return `已完成 ${anchorCount} 个点 · ${paused ? '灯已熄灭' : '继续标定'}`;
    return active ? '双手离开后自动点灯' : '共 5 个定位点 · 四角和天元';
  };
  const capRight = (): string => {
    if (phase === 'ready') return '已完成';
    if (stopped) return `停在第 ${brokenStep + 1} 步`;
    if (active) return `${anchorCount} / 5`;
    return '第 1 / 4 步';
  };

  // ── 三格状态 ───────────────────────────────────────────────────────────────
  //
  // 没读到时不给 tone；LED 未确认不能当成未连接。
  const calibValue = (): StatusCell => {
    if (phase === 'ready' && status.session_calibrated) return { label: '标定', value: '已标定', tone: 'good' };
    if (phase === 'degraded') return { label: '标定', value: '已失效', tone: 'bad' };
    if (phase === 'obstructed') return { label: '标定', value: '等待移手', tone: 'warn' };
    if (phase === 'lighting_paused') return { label: '标定', value: '等待调光', tone: 'warn' };
    if (phase === 'waiting_empty' || phase === 'waiting_stable') return { label: '标定', value: '等待稳定', tone: 'warn' };
    if (active) return { label: '标定', value: '标定中', tone: 'warn' };
    if (failed) return { label: '标定', value: '失败', tone: 'bad' };
    if (cancelled) return { label: '标定', value: '已取消', tone: 'warn' };
    if (allowExistingReuse && status.last_valid) return { label: '标定', value: '待确认', tone: 'warn' };
    return { label: '标定', value: '未标定' };
  };
  const cells: StatusCell[] = loaded ? [
    { label: '摄像头', value: cameraReady ? '已连接' : '未连接', tone: cameraReady ? 'good' : 'bad' },
    calibValue(),
    { label: 'LED', value: ledReady == null ? '未确认' : ledReady ? t('settings:camera_connected', '已连接') : '未连接',
      tone: ledReady == null ? undefined : ledReady ? 'good' : 'warn' },
  ] : [
    { label: '摄像头', value: '—' }, { label: '标定', value: '—' }, { label: 'LED', value: '未确认' },
  ];

  // ── 两颗键 ─────────────────────────────────────────────────────────────────
  const canStart = cameraReady && ledReady && !starting && !relocating && !active;
  // `lock_moved`:degraded 之后重新标定又取消/失败,phase 会落回可沿用的三态,但锁还是挪动前那把。
  const canReuse = (phase === 'required' || phase === 'failed' || phase === 'cancelled')
    && status.last_valid && !status.lock_moved && cameraReady && !starting && !relocating && !active;
  const reuseBlockedWhy = active ? '标定进行中'
    : !cameraReady ? '摄像头未连接，无法核对网格'
      : phase === 'ready' ? '这一局已经在用这次标定'
        // 「按不了」永远要有话说:degraded 是唯一剩下的按不了的情形。新文案走 t(),译文在 Task 7b 收口。
        : phase === 'degraded' || status.lock_moved ? t('vision:reuse_blocked_moved', '棋盘挪动过，上次的标定对不上了 —— 用「对齐外框」（不亮灯，盘上有子也能对）或重新标定')
          : null;

  const primaryLabel = phase === 'ready' && !confirmingManual ? '重新标定棋盘'
    : confirmingManual ? '已清空，确认重新标定'
      : '重新开始标定';

  // 刚按的「对齐外框」没成,排在最前;原来那条链接在它后面,一字不改。
  const diagnostic: Diagnostic | null = relocateError
    ? { kind: 'relocate', title: t('vision:relocate_failed_title', '没对上'), body: relocateError, action: '' }
    : failed ? buildDiagnostic(status.error, status.stopped_phase)
      : phase === 'degraded' ? buildDiagnostic('board_moved')
        : actionError ? { title: '操作没有生效', body: actionError, action: '再试一次；一直不行就检查摄像头和灯带的接线。' }
          : null;

  const lightingIssue = phase === 'lighting_paused' || phase === 'lighting_rechecking';
  const tooBright = status.pause_reason === 'frame_overexposed';
  const tooDark = status.pause_reason === 'frame_underexposed';
  const lightTitle = tooBright ? '画面过亮，棋盘细节可能看不清'
    : tooDark ? '画面过暗，棋盘细节可能看不清' : '当前光线可能影响棋盘识别';
  const lightGuidance = tooBright
    ? '请拉上窗帘，避开阳光直射棋盘。'
    : tooDark ? '请打开室内灯，或换到光线均匀的位置。' : '请调整为均匀、柔和的光线。';
  const lightVoiceText = tooBright ? '光线太亮，请拉上窗帘，避开直射光。'
    : tooDark ? '光线太暗，请打开室内灯。' : '请调整棋盘周围的光线。';
  const previewLabel = waitingForBoard ? '等待棋盘稳定'
    : phase === 'obstructed' ? '已暂停'
      : lightingIssue ? (phase === 'lighting_rechecking' ? '正在检测光线' : tooBright ? '光线过亮' : tooDark ? '光线过暗' : '光线待调整')
        : phase === 'ready' ? '标定完成' : '正在标定';
  const previewBanner = waitingForBoard
    ? (phase === 'waiting_empty' ? '请把手移开棋盘上方' : '画面不稳定，请保持棋盘上方无遮挡')
    : phase === 'obstructed' ? '检测到遮挡，标定已暂停'
      : lightingIssue ? (phase === 'lighting_rechecking' ? '正在重新检测光线' : `${tooBright ? '光线过亮' : tooDark ? '光线过暗' : '光线需要调整'}，标定已暂停`)
        : '正在标定';
  const previewDetail = waitingForBoard ? '稳定后自动开始'
    : paused ? `${anchorCount} 点已保留`
      : `已完成 ${anchorCount} / 5`;

  const preview: ReactNode = view === 'raw' ? (
    <GeometryVideoPanel
      fill
      snapshot
      src={`/api/v1/geometry/snapshot?view=raw&scale=${RAW_STREAM_SCALE}`}
      alt="摄像头原始画面"
      // 锚点坐标是相机原始像素 ⇒ 缩过的图要乘回去,覆盖层才对得上。
      onImageLoad={(s) => setRawFrame({ width: s.width * RAW_STREAM_SCALE, height: s.height * RAW_STREAM_SCALE })}
      overlay={<CameraGeometryOverlay modelForViewport={rawModelForViewport} label="原始画面棋盘几何叠加层" />}
    />
  ) : (
    <GeometryVideoPanel
      fill
      snapshot
      /* ⚠️ `&& !active` 不是多余的:运行中 `layout` 往往非空(上一次的锁还在磁盘上),
         照播就是在放**一份正在被这次运行作废的**几何 —— 常驻分段方案里唯一会骗人的那一格。 */
      src={layout && !active ? `/api/v1/geometry/snapshot?view=warped&revision=${layout.revision}&scale=${WARPED_STREAM_SCALE}` : undefined}
      alt="俯视矫正画面"
      waitingText={active ? '标定进行中，俯视画面在完成后重新生成' : '完成 LED 标定后生成俯视画面'}
      overlay={<CameraGeometryOverlay modelForViewport={warpedModelForViewport} label="俯视画面棋盘几何叠加层" />}
    />
  );

  const pagebar = (
    <KioskPagebar
      testId="calib-pagebar"
      backLabel={backLabel}
      onBack={onBack}
      title={title}
      sub={sub}
      segment={active ? undefined : {
        value: view,
        options: [['raw', '原始画面'], ['warped', '俯视矫正']] as const,
        onChange: (next) => setManualView(next as 'raw' | 'warped'),
        ariaLabel: '画面',
      }}
    />
  );

  /**
   * 这台盒子压根没有摄像头(`/status` 404 ⇒ `disabled`)。
   * 那台机器上 `/geometry/stream` 会 404、`/calibrate` 会 404、五步一步都不会走 ——
   * **把这些控件摆出来全是假的。** 页控条照旧(返回必须在)。
   */
  if (phase === 'disabled') {
    return (
      <div className="calib-screen" data-testid="calib-screen">
        {pagebar}
        <div className="empty" data-testid="calib-disabled">
          <h4>这台盒子没有配摄像头</h4>
          <p>实体棋盘识别、摆谱、实体做题都用不了；<b>屏幕上的功能不受影响</b>。</p>
        </div>
      </div>
    );
  }

  return (<>
    <LightingWarningDialog {...lightingWarning} />
    <div className="calib-screen" data-testid="calib-screen">
      {pagebar}
      <div className="calib-body">
        {/* **故意不叫 `.kiosk-board`**,两条理由:① 稿子说的 —— 闸的真像素抽查会按木色
            (亮度 120–185)去量 `.kiosk-board`,而这儿是摄像头画面;② `.kiosk-board` 本身是
            3×3 栅格 + 四条 28px 刻度带,把视频塞进去等于四边各内缩 28 给「没东西可标」的刻度让位。 */}
        <div className="camview" data-testid="calib-camview">
          {preview}
          {active && view === 'raw' && (
            <>
              <span className="calib-preview-label" data-testid="calib-preview-state">
                <span className="calib-preview-dot" />{previewLabel}
              </span>
              <div className={`calib-preview-banner${paused ? ' is-paused' : ''}`} data-testid="calib-preview-banner">
                <b>{previewBanner}</b><small>{previewDetail}</small>
              </div>
            </>
          )}
          <div className="cap" data-testid="calib-cap">
            <span>
              {capLeft()}
              {layoutError && <b> · 几何叠加读取失败</b>}
            </span>
            <i>{capRight()}</i>
          </div>
        </div>

        <div className="calib-rail">
          <KioskStatusCells cells={cells} />

          <KioskScrollZone grow className="calib-scroll">
            {diagnostic && (
              <div className="empty calib-diag" data-testid="geometry-diagnostic-card" data-kind={diagnostic.kind ?? 'status'}>
                <h4>{diagnostic.title}</h4>
                <p>{diagnostic.body}</p>
                {diagnostic.action && <p><b>{diagnostic.action}</b></p>}
                {diagnostic.detail && <p className="calib-diag__raw">{diagnostic.detail}</p>}
              </div>
            )}

            <div className="kiosk-rows" data-testid="calib-steps">
              {STEPS.map((step, i) => {
                const state = stepState(i);
                const tag = stepTag(i, state);
                return (
                  <div
                    className={`kiosk-row kiosk-row--step is-${state}`}
                    key={step.key}
                    data-state={state}
                    data-testid="calib-step"
                  >
                    <span className="kiosk-row__lead">{i + 1}</span>
                    <span className="kiosk-row__t">
                      <b>{step.title}</b>
                    </span>
                    <span className="kiosk-row__end">
                      <span className={`kiosk-tag ${tag.cls}`}>{tag.text}</span>
                    </span>
                  </div>
                );
              })}
            </div>

            <p className="setnote calib-note">
              {/* 第一行**永远在**:这是 Fan 定的硬规矩,不因为屏上正在发生什么而消失。 */}
              <b data-testid="geometry-led-advisory">LED 只在你按下之后才亮，不会自动点亮 LED</b>
              。棋盘稳定后才开始；遮挡时灯熄灭，移手后从未完成的点继续。
              {/* 诊断真在场时,那句「失败时给诊断」的预告就成了自我指涉 ⇒ 只在没失败时说。 */}
              {!diagnostic && (
                <><br />失败时给<b>诊断</b>不给「重试」：多半是子压着星位、灯太暗，或摄像头挪过。</>
              )}
              {/* 旁注最多两行(稿子 §5)。原先还有「每个定位点先熄灯再亮灯各拍一张」和「LED 那格只说串口通了」两句,
                  Fan 2026-09-27 裁定删掉,别再加回来。 */}
              {allowExistingReuse && reuseBlockedWhy && status.last_valid && (
                <><br />「沿用上次标定」此刻按不了：{reuseBlockedWhy}。</>
              )}
              {requireRecognition && phase === 'ready' && !status.capabilities.recognition_ready && (
                <><br />棋盘已标定，但识别模型还没就绪。</>
              )}
            </p>
          </KioskScrollZone>

          <div className="calib-acts" data-testid="calib-actions">
            {active ? (
              /**
               * 运行中**整行只有一颗**「取消标定」。
               *
               * 稿子这里做不到 —— 它只画了一个静止帧,在任何状态下都是那两颗键,而运行中那两颗
               * **一颗都不成立**:「沿用上次标定」要 `phase ∈ {required,failed,cancelled}`(否则服务端
               * `ValueError`),「重新开始标定」会撞 `CalibrationBusy` → 409。照画就是两颗按不动的键。
               *
               * 不能丢:五个锚点逐个拍亮灭帧，还会等待移手或调光；用户需要随时退出。
               *
               * 走危险色不走绿:绿色在这一屏的其它每个状态下都是「开始 / 重来」,同一个位置同一个
               * 颜色换成「取消」,条件反射按下去就毁掉一次运行。
               * 不配确认弹层 —— 取消是廉价且可逆的:取消之后「沿用上次标定」仍然可以按
               * (2026-09-20 起,`_REUSABLE_PHASES` 含 cancelled)。**这句话在那之前是不成立的**,
               * 当时取消会让本次开机的标定一起作废;登记不做确认层的那条裁定,依据的正是这个前提。
               */
              <button
                type="button"
                className="kiosk-btn kiosk-btn--secondary is-danger"
                onClick={() => void cancelCalibration()}
              >
                {t('vision:cancel_calibration', '取消标定')}
              </button>
            ) : (
              <>
                {/* 盘被碰动之后的出口。**不亮灯、不要求空盘** —— 五点流程要清盘,
                    而这颗键存在的理由正是盘上有子(对局进行到一半)。
                    只在真的需要时出现:ready 态不给「修」的键。 */}
                {(phase === 'degraded' || phase === 'cancelled' || failed)
                  && status.last_valid && (allowExistingReuse || status.session_calibrated) && (
                  <button
                    type="button"
                    className="kiosk-btn kiosk-btn--secondary"
                    data-testid="calib-relocate"
                    disabled={!cameraReady || relocating || starting}
                    onClick={() => void handleRelocate()}
                  >
                    {relocating
                      ? t('vision:relocating', '正在对齐…')
                      : t('vision:relocate', '对齐外框')}
                  </button>
                )}
                {/* `last_valid` 为假 = **从来没成功标定过** ⇒ 这颗键不渲染,主行动满宽。
                    「没有上一次可沿用」屏上已经有三处在说(状态格「未标定」、步骤未开始、
                    主键满宽),再摆一颗永远按不亮、还要配一行解释的键是往加的方向走。 */}
                {allowExistingReuse && status.last_valid && (
                  <button
                    type="button"
                    className="kiosk-btn kiosk-btn--secondary"
                    disabled={!canReuse}
                    onClick={() => void reuseExisting()}
                  >
                    {t('vision:reuse_calibration', '沿用上次标定')}
                  </button>
                )}
                <button
                  type="button"
                  className="kiosk-btn kiosk-btn--primary"
                  disabled={!canStart}
                  onClick={handleStart}
                >
                  {primaryLabel}
                </button>
              </>
            )}
          </div>
        </div>
      </div>
      {lightingIssue && (
        <div className="calib-light-scrim">
          <section className="calib-light-dialog" role="dialog" aria-modal="true" aria-labelledby="calib-light-title">
            <span className="calib-light-eyebrow">光线提醒 · 标定已暂停</span>
            <h2 id="calib-light-title">{phase === 'lighting_rechecking' ? '正在重新检测光线' : lightTitle}</h2>
            <p>{lightGuidance}调整后重新检测光线，已完成的 {anchorCount} 个点会保留。</p>
            <div className="calib-light-voice"><b>语音提示</b>　{lightVoiceText}</div>
            {lightError && <p className="calib-light-error" role="alert">{lightError}</p>}
            <div className="calib-light-actions">
              <button type="button" className="kiosk-btn kiosk-btn--secondary is-danger" onClick={() => void cancelCalibration()}>
                取消标定
              </button>
              <button type="button" className="kiosk-btn kiosk-btn--primary"
                disabled={rechecking || phase === 'lighting_rechecking'} onClick={() => void handleRecheckLighting()}>
                {phase === 'lighting_rechecking' || rechecking ? '正在检测…' : '调整后重新检测'}
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  </>);
}

export default GeometryCalibrationScreen;
