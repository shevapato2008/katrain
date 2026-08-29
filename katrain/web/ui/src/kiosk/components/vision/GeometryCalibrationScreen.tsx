import { useCallback, useEffect, useState } from 'react';
import type { ReactNode } from 'react';

import { KioskPagebar } from '../../shell/KioskPagebar';
import { KioskStatusCells, type StatusCell } from '../../shell/KioskStatusCells';
import { KioskScrollZone } from '../../shell/KioskScrollZone';
import GeometryVideoPanel from './GeometryVideoPanel';
import CameraGeometryOverlay from './CameraGeometryOverlay';
import { useGeometry } from '../../context/GeometryContext';
import { GeometryAPI, type GeometryLayout } from '../../../api/geometryApi';
import { useTranslation } from '../../../hooks/useTranslation';
import {
  buildAnchorGeometryModel, buildRawGeometryModel, buildWarpedGeometryModel,
  type OverlayViewport,
} from './geometryOverlay';

/**
 * 屏 26 棋盘标定(**布局 B**:无棋盘 ⇒ 页控条通栏 x16–1008,内容区 992×460)。
 *
 * ## 为什么是一个「屏」而不是一个「工作区」
 *
 * 上一版叫 `GeometryCalibrationWorkspace`,有一个 `mode: 'guard' | 'settings'` 的开关,
 * **只渲染中间那块**,外面的壳由两个调用方各自套。两个后果:
 *  · `PhysicalBoardGuard` 那一路**整屏没有任何返回** —— L2 无 Dock、顶栏恒品牌态,
 *    屏 14 做题和屏 17 摆谱遇到未标定时,用户**出不去**。这是 bug,不是美化。
 *  · 同一份「13 个锚点走到哪儿了」的状态,两个壳各画各的。
 *
 * 这一版把**壳也一起抽进来**:本组件自己拥有页控条和整个 body,只收四个字面量
 * (`backLabel/onBack/title/sub`)。`mode` 那个 prop 因此消失 —— 两条路走的是同一段代码,
 * 差的只是壳上那四个字。**不能让两条路共用同一句「← 设置」**:guard 是从做题/摆谱里被拦下的,
 * 写「设置」是对来路撒谎,按下去还会把人扔进设置页。
 *
 * ## 稿子在这一屏有一处硬不成立:第 2 步
 *
 * 稿子画五步,其中第 2 步「采集熄灯参考帧 / 先拍一张全灭的，作对照」对应 `dark_reference`,
 * 而**全仓没有任何地方写入这个 phase** —— 它只活在两处「哪些 phase 算进行中」的常量集合里
 * (`geometry_calibration_service.py:20`、`endpoints/geometry.py:27`)。
 *
 * 那件事确实在做,但**不是一个步**:`_locate_anchor`(`led_geometry_calibrator.py:221-255`)
 * 对**每一个**锚点都先 `led.clear()` 拍一张熄灯帧、再点亮拍一张,然后做差分 —— 13+ 次、
 * 与亮灯帧交替,没有独立的开始和结束。⇒ 画成一行,要么和第 3 步同一瞬间从「未开始」跳到
 * 「完成」、要么一直挂着「完成」,**两种都在对顺序撒谎**。删掉这一行,把机制写进
 * 「定位棋盘四角」的副行。省下的 60px(52 + 8)正好给失败时的诊断卡。
 *
 * 真正会被报出来的只有三个:`flashing_corners`(第 1–4 个锚点)、`verifying`(第 5–13 个)、
 * `building_baseline`。`waiting_empty` 只在服务启动线程那一瞬设一次,一个轮询周期内就被盖掉 ——
 * 它作为「按下之后的状态」不可见,作为「按下之前的指令」才是这一屏的全部内容。
 */

/** 四步。**不是五步** —— 见页头注。 */
const STEPS = [
  { key: 'empty', title: '准备空盘标定', hint: '确认盘上一颗子都没有' },
  { key: 'corners', title: '定位棋盘四角', hint: '四角的灯逐个点亮' },
  { key: 'stars', title: '定位九个星位', hint: '九个星位的灯逐个点亮' },
  { key: 'baseline', title: '生成空盘基线', hint: '之后识子都拿它作底' },
] as const;

const ACTIVE_PHASES = new Set(['waiting_empty', 'dark_reference', 'flashing_corners', 'verifying', 'building_baseline']);

const GTP_LETTERS = 'ABCDEFGHJKLMNOPQRSTUVWXYZ';
const gtpPoint = (row: number, col: number) => `${GTP_LETTERS[col] ?? '?'}${19 - row}`;

interface Diagnostic { title: string; body: string; action: string; detail?: string }

/**
 * 「失败时给**诊断**不给『重试』」是稿子写在屏上的承诺。兑现它的方式是失败那一刻出现的是
 * 一张**点名具体原因**的卡,而不是一颗孤零零的重试键。这段逐字保留自上一版,一个分支没删。
 */
function buildDiagnostic(error?: string | null): Diagnostic {
  const raw = error ?? '';
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
      body: '前面 13 个点都找到了，卡在最后一步。多半是灯带或摄像头这一刻掉线了。',
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
}

export function GeometryCalibrationScreen({
  backLabel, onBack, title, sub, requireRecognition = false,
}: GeometryCalibrationScreenProps) {
  const { status, loaded, startCalibration, confirmExisting, cancelCalibration } = useGeometry();
  const { t } = useTranslation();

  const [layout, setLayout] = useState<GeometryLayout | null>(null);
  const [rawFrame, setRawFrame] = useState<{ width: number; height: number } | null>(null);
  const [starting, setStarting] = useState(false);
  const [confirmingManual, setConfirmingManual] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [layoutError, setLayoutError] = useState<string | null>(null);
  const [manualView, setManualView] = useState<'raw' | 'warped' | null>(null);

  const phase = status.phase;
  const active = ACTIVE_PHASES.has(phase);
  const cameraReady = status.capabilities.camera_ready;
  const ledReady = status.capabilities.led_ready;

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
    layout ? buildWarpedGeometryModel(layout.out_size, phase, viewport) : null
  ), [layout, phase]);

  // ── 视图切换 ───────────────────────────────────────────────────────────────
  //
  // **常驻两段,都能按。** 一度想过「没标定好就把俯视那段灰掉」,那是错的:
  // 俯视此刻**画不出来**(没有单应矩阵)不蕴含**必须禁用** —— `GeometryVideoPanel` 收了
  // `waitingText`,切过去它自己会说「完成 LED 标定后生成俯视画面」,既不是黑屏也不是假画面。
  // 位置恒定 > 少按一次空;而且顺序照稿子(原始在前)也是对的因果:俯视是从原始算出来的。
  const view: 'raw' | 'warped' = manualView ?? (layout && phase === 'ready' ? 'warped' : 'raw');

  // ── 动作 ───────────────────────────────────────────────────────────────────
  const start = async () => {
    setStarting(true);
    setActionError(null);
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
    try {
      await confirmExisting();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : '沿用上次标定失败');
    } finally {
      setStarting(false);
    }
  };

  // ── 四步的状态 ─────────────────────────────────────────────────────────────
  //
  // 相位 → 第几步(0 基)。`waiting_empty` 与所有非运行态一样落在第 1 步:
  // 清空棋盘这个动作**本来就是操作员在按下之前做的**。
  const runningStep = phase === 'flashing_corners' ? 1
    : phase === 'verifying' ? 2
      : phase === 'building_baseline' ? 3
        : 0;

  /**
   * 失败 / 取消断在哪一步:**由 `detected_anchors` 的长度判,不靠错误串**。
   * 「这次运行确实走到了那儿」是能从数据说出来的事实;而错误串只说明**最后一下**出了什么问题,
   * 它反推不出前面走了多远(一条否定的答复不携带原因)。
   */
  const brokenStep = anchorCount < 4 ? 1 : anchorCount < 13 ? 2 : 3;
  const failed = phase === 'failed';
  const cancelled = phase === 'cancelled';
  const stopped = failed || cancelled;

  /**
   * 「做完了」和「做得好不好」在**同一个控件上**分开表达:
   * 13/13 → 绿「完成」;不足 13 → 琥珀「完成 · n / 13」;拿不到这个数 → 中性「完成」
   * (**不敢标绿** —— 不知道不是满分)。稿子那个只有一种 tag 的「第 5 步 完成」说不出这层。
   */
  const qualityTone = (): 'done' | 'warn' | 'plain' => {
    if (typeof inliers !== 'number') return 'plain';
    return inliers >= 13 ? 'done' : 'warn';
  };

  const stepState = (i: number): 'done' | 'now' | 'bad' | 'warn' | 'todo' | 'plain' => {
    if (phase === 'ready') return i === 3 ? qualityTone() : 'done';
    if (stopped) {
      if (i < brokenStep) return 'done';
      if (i === brokenStep) return failed ? 'bad' : 'warn';
      return 'todo';
    }
    if (!active) return i === 0 ? 'now' : 'todo';
    if (i < runningStep) return 'done';
    if (i === runningStep) return 'now';
    return 'todo';
  };

  /**
   * 标定质量的三个数。**它天然属于「生成空盘基线」这一步** —— 那一步做完了,做得怎么样
   * 就写在它的副行里,零额外高度。
   *
   * 🔴 上一版是 `metrics.inlier_count ?? 13` / `rms_residual ?? 0` / `max_residual ?? 0`
   * —— **后端没给这个数的时候它编一个满分出来**(13/13、0.000 px 读起来就是「完美」)。
   * 规范 §14:值写「—」不写 0。缺失一律「—」,而且 tag 不敢标绿(见 `qualityTone`)。
   */
  const num = (v: unknown, digits = 3) => (typeof v === 'number' && Number.isFinite(v) ? v.toFixed(digits) : '—');
  const inliers = status.metrics?.inlier_count;
  const qualityLine = () => {
    const m = status.metrics;
    if (!m) return '标定完成，但没拿到这次的残差数据';
    return `${typeof inliers === 'number' ? `${inliers} / 13 点` : '— / 13 点'} · RMS ${num(m.rms_residual)} px · 最大残差 ${num(m.max_residual)} px`;
  };

  const stepHint = (i: number): string => {
    // 跑到第 3 步(星位)时说「正在点第 N 个」—— N 从权威计数来,不估。
    if (i === 2 && phase === 'verifying') return `正在点第 ${Math.min(anchorCount - 4 + 1, 9)} 个`;
    if (i === 1 && phase === 'flashing_corners') return `正在点第 ${Math.min(anchorCount + 1, 4)} 个角`;
    if (i === 3 && phase === 'ready') return qualityLine();
    return STEPS[i].hint;
  };

  const stepTag = (i: number, state: string): { text: string; cls: string } => {
    if (state === 'done') return { text: '完成', cls: 'kiosk-tag--good' };
    if (state === 'plain') return { text: '完成', cls: '' };
    if (state === 'now') return { text: '进行中', cls: '' };
    if (state === 'bad') return { text: '失败', cls: 'kiosk-tag--bad' };
    // 第 4 步的 warn 是「完成但点数不足」,别的步骤的 warn 是「已取消」—— 两回事,别共用一句。
    if (state === 'warn') {
      return i === 3 && phase === 'ready'
        ? { text: `完成 · ${inliers} / 13`, cls: 'kiosk-tag--warn' }
        : { text: '已取消', cls: 'kiosk-tag--warn' };
    }
    return { text: '未开始', cls: 'kiosk-tag--dim' };
  };

  // ── 摄像头画面底下那条 ─────────────────────────────────────────────────────
  const capLeft = (): string => {
    if (phase === 'ready' || anchorCount === 13) return '四角 + 九星 13 / 13 已定位';
    if (anchorCount === 0) return '共 13 个定位点 · 四角 + 九星';
    if (anchorCount < 4) return `四角 ${anchorCount} / 4`;
    return `四角已定位 · 九星 ${anchorCount - 4} / 9`;
  };
  const capRight = (): string => {
    if (phase === 'ready') return '已完成';
    if (stopped) return `停在第 ${brokenStep + 1} 步`;
    if (active) return `第 ${runningStep + 1} / 4 步`;
    return '第 1 / 4 步';
  };

  // ── 三格状态 ───────────────────────────────────────────────────────────────
  //
  // **没读到之前一律「—」且不给 tone** —— `DEFAULT_STATUS` 三个 capability 全是 false,
  // 直接画就会在还没问过的时候说「未连接」。「还没读到」≠「读到了没连上」(G8)。
  const calibValue = (): StatusCell => {
    if (phase === 'ready' && status.session_calibrated) return { label: '标定', value: '已标定', tone: 'good' };
    if (phase === 'degraded') return { label: '标定', value: '已失效', tone: 'bad' };
    if (active) return { label: '标定', value: '标定中', tone: 'warn' };
    if (failed) return { label: '标定', value: '失败', tone: 'bad' };
    if (cancelled) return { label: '标定', value: '已取消', tone: 'warn' };
    if (status.last_valid) return { label: '标定', value: '待确认', tone: 'warn' };
    return { label: '标定', value: '未标定' };
  };
  const cells: StatusCell[] = loaded ? [
    { label: '摄像头', value: cameraReady ? '已连接' : '未连接', tone: cameraReady ? 'good' : 'bad' },
    calibValue(),
    { label: 'LED', value: ledReady ? '就绪' : '未连接', tone: ledReady ? 'good' : 'bad' },
  ] : [
    { label: '摄像头', value: '—' }, { label: '标定', value: '—' }, { label: 'LED', value: '—' },
  ];

  // ── 两颗键 ─────────────────────────────────────────────────────────────────
  const canStart = cameraReady && ledReady && !starting && !active;
  const canReuse = (phase === 'required' || phase === 'failed') && status.last_valid && cameraReady && !starting && !active;
  const reuseBlockedWhy = active ? '标定进行中'
    : !cameraReady ? '摄像头未连接，无法核对网格'
      : phase === 'ready' ? '这一局已经在用这次标定'
        : null;

  const primaryLabel = phase === 'ready' && !confirmingManual ? '重新标定棋盘'
    : confirmingManual ? '已清空，确认重新标定'
      : '重新开始标定';

  const diagnostic: Diagnostic | null = failed ? buildDiagnostic(status.error)
    : phase === 'degraded' ? buildDiagnostic('board_moved')
      : actionError ? { title: '操作没有生效', body: actionError, action: '再试一次；一直不行就检查摄像头和灯带的接线。' }
        : null;

  const preview: ReactNode = view === 'raw' ? (
    <GeometryVideoPanel
      fill
      src="/api/v1/geometry/stream"
      alt="摄像头原始画面"
      onImageLoad={setRawFrame}
      overlay={<CameraGeometryOverlay modelForViewport={rawModelForViewport} label="原始画面棋盘几何叠加层" />}
    />
  ) : (
    <GeometryVideoPanel
      fill
      /* ⚠️ `&& !active` 不是多余的:运行中 `layout` 往往非空(上一次的锁还在磁盘上),
         照播就是在放**一份正在被这次运行作废的**几何 —— 常驻分段方案里唯一会骗人的那一格。 */
      src={layout && !active ? `/api/v1/geometry/warped-stream?revision=${layout.revision}` : undefined}
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
      segment={{
        value: view,
        options: [['raw', '原始画面'], ['warped', '俯视矫正']] as const,
        onChange: (next) => setManualView(next as 'raw' | 'warped'),
        ariaLabel: '画面',
      }}
    />
  );

  /**
   * 这台盒子压根没有摄像头(`/status` 404 ⇒ `disabled`)。
   * 那台机器上 `/geometry/stream` 会 404、`/calibrate` 会 404、四步一步都不会走 ——
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

  return (
    <div className="calib-screen" data-testid="calib-screen">
      {pagebar}
      <div className="calib-body">
        {/* **故意不叫 `.kiosk-board`**,两条理由:① 稿子说的 —— 闸的真像素抽查会按木色
            (亮度 120–185)去量 `.kiosk-board`,而这儿是摄像头画面;② `.kiosk-board` 本身是
            3×3 栅格 + 四条 28px 刻度带,把视频塞进去等于四边各内缩 28 给「没东西可标」的刻度让位。 */}
        <div className="camview" data-testid="calib-camview">
          {preview}
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
              <div className="empty calib-diag" data-testid="geometry-diagnostic-card">
                <h4>{diagnostic.title}</h4>
                <p>{diagnostic.body}</p>
                <p><b>{diagnostic.action}</b></p>
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
                      <em>{stepHint(i)}</em>
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
              ——自己闪灯会把人和摄像头一起搞糊涂。
              {/* 诊断真在场时,那句「失败时给诊断」的预告就成了自我指涉 ⇒ 只在没失败时说。 */}
              {!diagnostic && (
                <><br />失败时给<b>诊断</b>不给「重试」：多半是子压着星位、灯太暗，或摄像头挪过。</>
              )}
              {/* 稿子把「采集熄灯参考帧」画成独立一步,而它其实是**每个点各做一次**的动作。
                  删掉那一步不等于可以不说这件事 —— 挪到这儿,它解释的正是「为什么没有那一步」。 */}
              <br />每个定位点都<b>先熄灯拍一张、亮灯再拍一张</b>，两张相减才找得出灯在哪。
              {reuseBlockedWhy && status.last_valid && (
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
               * **一颗都不成立**:「沿用上次标定」要 `phase ∈ {required,failed}`(否则服务端
               * `ValueError`),「重新开始标定」会撞 `CalibrationBusy` → 409。照画就是两颗按不动的键。
               *
               * 不能丢:13 个锚点、每个都要 clear→拍→点亮→拍,是分钟级的。中途发现盘上还有子
               * 却退不出去,人只能干等它失败 —— **一个没有退出路径的分钟级流程,在 7 寸触摸屏上就是卡死。**
               *
               * 走危险色不走绿:绿色在这一屏的其它每个状态下都是「开始 / 重来」,同一个位置同一个
               * 颜色换成「取消」,条件反射按下去就毁掉一次运行。不配确认弹层 —— 取消是廉价且可逆的。
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
                {/* `last_valid` 为假 = **从来没成功标定过** ⇒ 这颗键不渲染,主行动满宽。
                    「没有上一次可沿用」屏上已经有三处在说(状态格「未标定」、四步全「未开始」、
                    主键满宽),再摆一颗永远按不亮、还要配一行解释的键是往加的方向走。 */}
                {status.last_valid && (
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
    </div>
  );
}

export default GeometryCalibrationScreen;
