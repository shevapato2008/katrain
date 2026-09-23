import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useParams, useLocation } from 'react-router-dom';

import { useTranslation } from '../../hooks/useTranslation';
import { type BaipuCaptureErrorReason,
  BaipuAPI, getCachedSgf, saveProgress, getProgress, clearProgress, forgetSgf,
  canonToGtp, type BaipuStep, type BaipuMeta, type BaipuGeometryCorrection,
} from '../../api/baipuApi';
import { LedAPI, type LedColor } from '../../api/ledApi';
import { LED_HEX } from '../constants/ledColors';
import { replayBaipuMatrix, replayBaipuSteps } from '../../utils/baipuReplay';
import { GoBoardSvg } from '../shell/GoBoardSvg';
import { colsFor, rowsFor } from '../shell/goBoard';
import { KioskActions, type KioskAction } from '../shell/KioskActions';
import { KioskFold } from '../shell/KioskFold';
import { KioskPagebar } from '../shell/KioskPagebar';
import { useBackTo } from '../hooks/useBackTo';
import { driftLine } from '../utils/baipuDrift';
import { playShutter } from '../utils/baipuShutter';
import { interpolate } from '../utils/interpolate';
import { useAuth } from '../../context/AuthContext';
import { kioskActivityStorage } from '../storage/kioskActivityStorage';
import { useOptionalVision } from '../context/VisionContext';
import { useOptionalGeometry } from '../context/GeometryContext';
import { useVisionSync } from '../hooks/useVisionSync';
import { usePhysicalBaipu, type NextStone } from '../hooks/usePhysicalBaipu';
import { useBaipuHint } from '../hooks/useBaipuHint';

const stoneToLedColor = (c: 'B' | 'W'): LedColor => (c === 'B' ? 'black' : 'white');
/** 目差带符号、一位小数;先舍入再判号,-0.04 不会印成「-0.0」。 */
const signed = (x: number) => { const v = Math.round(x * 10) / 10; return `${v > 0 ? '+' : ''}${v.toFixed(1)}`; };

const savedFilename = (path?: string): string | null => {
  if (!path) return null;
  return path.split(/[\\/]/).filter(Boolean).at(-1) ?? null;
};

type Phase = 'loading' | 'guiding' | 'await_removal' | 'done' | 'error';

/** 右栏此刻在说哪一件事。**互斥且有序** —— 见页面头注那张优先级表。 */
type Mood = 'guiding' | 'removal' | 'failed' | 'done' | 'setup' | 'trying' | 'hint';
/** pcard 的色:待摆 / 支招 = turn,该拿走 / 把盘面摆对 = removal(蓝,和蓝灯同色),试下 = 无色。 */
const PCARD_CLASS: Record<Mood, string> = {
  guiding: 'turn', hint: 'turn', removal: 'removal', setup: 'removal', failed: 'failed', done: 'done', trying: '',
};

/**
 * 屏 17 · 摆谱 · 进行中 `/kiosk/baipu/session/:source` —— L2 布局 A(左盘 516 + 16 + 右栏 460)。
 *
 * **这一屏的主角不在屏幕上,在实体盘上。** 灯点着下一手该落哪儿,人把子摆上去,摄像头认到就自动下一手。
 * 提子要人**自己**把死子拿下来。屏幕在这儿只是副驾 —— 所以右栏第一块不是棋谱也不是记账,
 * 是「**现在轮到你摆哪一颗**」。
 *
 * ## 三路:摄像头 / 手动兜底 / 采集机(2026-09-23,Fan:「不要每走一步都要按屏幕上的确认键……应该使用摄像头确认」)
 *
 *  · **摄像头**(`camera`,盒子常态):没有确认键。复用死活题那条**监视模式**(`usePhysicalBaipu`,
 *    识别层七条约束写在它和 `physicalBaipuMachine` 头注里)。整页两个识别态:**等下一手**(下一手的灯亮)、
 *    **把盘面摆对**(缺的红绿灯常亮、多的蓝灯闪 —— 放错 / 提子 / 撤回 / 试下结束 / 进场有残子都走这一条)。
 *    判据照抄屏 14 的物理盘开关:`visionStatus.enabled && recognitionReady && 几何本次开机确认过`。
 *  · **手动兜底**(`manual`):摄像头用不了时**临时**露出「确认落子」,pcard 写明为什么(稿 17d)。
 *    恢复后自动收起 —— 判据变真,这一路就不渲染了。
 *  · **采集机**(`collect`,`--baipu-collect` 起的):原样三格(确认 / 撤回 / 完成),每手拍一帧 ——
 *    「拍照」只为收集 YOLO 训练数据(2026-09-14,Fan 纠正),拍照那一刻手不能在盘上,所以确认键留着。
 *    `collect` 由 `BaipuSessionRoute` 问 `GET /api/v1/baipu/mode` 得来(问不到 = `false`)。
 * ⚠️ 判别位只有 `collect`。盒子为了几何标定总是带着 `--capture-camera` 起,
 *    「有采集服务」**不等于**「要拍照」。
 *
 * ## 试下 / AI 支招(非采集机)
 *
 * 试下是开关:按下后识别暂停、灯全灭,盘上随便摆;再按一次回到谱上,灯带你把盘面摆回去(稿 17b)。
 * AI 支招与对弈页同一颗键(`Hints`):分析**谱上**当前局面、候选点亮白灯,开着时识别暂停(稿 17c)。
 * 两者互斥:开试下先收起支招;试下中支招灰掉 —— 摄像头不看盘,AI 不知道盘上是什么局面。
 * 撤回在摄像头态**立刻**生效、不弹确认框:撤错了再摆回去就是,盘面对上了自动继续。
 * 摆完自动清进度(「完成」键删了 —— Fan:「没什么用」);回去走左上角返回。
 *
 * ## 稿子那一帧有两行是错的(2026-08-24 裁定,已回报稿子作者)
 *
 * 稿子摄像头块右列写着「绿灯 = 该放上 / 红灯 = 该拿走」。**反了,而且漏了一色**:
 * `constants/ledColors.ts` 定死 `black:#ff3b30(红)` / `white:#34c759(绿)` / `remove:#2f6fff(蓝)`,
 * 后端 `COLOR_RGB`、`ledColors.test.ts` 那条精确相等、物理对弈与死活两条 track 的 PRD 全都一致。
 * ⇒ 绿灯是**该放白子**,红灯是**该放黑子**,该拿走是**蓝灯**。
 * 照稿子写,一局 241 手里每颗黑棋都会让操作员去拿一颗刚该放下的子。
 * 这一屏的 track 自己早就写死了正确版本(`review-feedback-gstack.md` 建议 E,已采纳):
 * **屏上必须常驻一条图例,而且屏上高亮色必须和灯同色**。所以盘上那个候选圈也跟着分色
 * (`GoBoardSvg` 的 `ghostFor`)—— 稿子把黑棋 C7 的圈画成绿的,同一处错。
 *
 * ## 沉浸模式撤了
 *
 * 上一版 `setImmersive(true)` 把顶栏和 Dock 都藏了。`ReportDetailPage:52-58` 已为同一件事
 * 判过一次,判据是量出来的:`immersive` 在 `KioskLayout` 里只让**顶栏不渲染**,而
 * `.kiosk-content` 的 `top` 仍是 `var(--topbar-h)` ⇒ 屏顶留一条 56 高的空黑带。
 * (2026-08-26:最后一个现场屏 14 也还完,`ImmersiveContext` 已删,这条开关不复存在。)
 * 返回归页控条「← 棋谱」,**但二次确认留着** —— 它不是实现遗留,是这一屏已采纳的裁定
 * (Blocker #2:「确认落子」一局按约 250 次,退出按一次,两颗不能同排;解法是移到角上 + 确认)。
 *
 * ## 四条通栏横幅一条都不进右栏
 *
 * 右栏的账是死的:页控条 44 + pcard 60 + 两个折叠头 30×2 + 动作区 52 + 四条间隙 48 = 264,
 * **两个折叠块的 body 一共只剩 252**;ledger 约 89 ⇒ 着法那块 ~163 ≈ 6 行。
 * 再插一块就把着法压到 3 行以下,右栏得整栏滚,而整栏一滚
 * `.kiosk-rail .kiosk-actions{margin-top:auto}` 就保不住动作区贴底 ——
 * **全 27 屏里最不能让「确认落子」动的就是这一屏**。所以:
 *
 * | 原来的横幅 | 现在 |
 * |---|---|
 * | 正在拍照,请勿伸手 | `.cdlg` 盖住**整个布局根**(不只是盘)—— 第一职责是挡住第二次按键 |
 * | 请移除被提的子 | **pcard 换内容**(`.pcard.removal`,蓝,和 `LED_HEX.remove` 同色) |
 * | 几何漂移三态 | 摄像头 ledger 一行 + 折叠头右端的结论词(收起也看得见) |
 * | 采集失败 | **pcard 换内容**(`.pcard.failed`),`k` 不推进 ⇒ 重按「确认落子」就是重试 |
 *
 * 优先级写死:`拍照遮罩` > `采集失败` > `待移除` > `已完成` > `试下` > `支招` > `把盘面摆对` > `待摆`
 * (后四档只有非采集机有;「把盘面摆对」只有摄像头态有)。
 *
 * ## 没有「虚手」键
 *
 * 这一屏是在重放一份既有的 SGF,pass 是「无物理动作」(`sbc-baipu-led-guide/plan.md`),页面自己跳过。
 * 「虚手」这个词留在着法表里做**记谱**(屏 16 同款)—— 它是事实,不是动作。
 *
 * ## 盘不用 `LiveBoard`
 *
 * 两条:① 它的 `gridMargins` 写死 1.5 格而刻度带按 0.5 格算,字和线错开约一格
 * (`KioskSetupBoard` 头注那段推导);② 它在渲染路径里**自己算提子**,而 `baipuApi` 决策 ②
 * 定死「前端是 `steps[]` 的笨播放器,永远不自己重算提子」—— 用它就是屏上画前端算的提子、
 * 灯点后端算的提子,两套气规则同屏跑。盘面走共享的 `replayBaipuSteps`(屏 16 / 屏 19 同款)。
 */
const BaipuSessionPage = ({ collect }: { collect: boolean }) => {
  const { source = '' } = useParams();
  const location = useLocation();
  const { t } = useTranslation();
  // 返回 / 退出 / 完成都去**打开这一屏的那一页**(2026-09-22):棋谱屏导入、棋谱详情「摆这一局」
  // 进来回那一页。摆谱列表 `/kiosk/baipu` 已删(K1,只剩重定向),所以入口只剩棋谱这一族,
  // 键名一律「棋谱」;没写明来处(直接输 URL)回棋谱屏,不回那条重定向。
  const back = useBackTo('/kiosk/kifu');
  const backLabel = t('baipu:back_kifu', '棋谱');
  const { user, isGuest, isLoading } = useAuth();
  const identityKey = user?.uuid ?? null;
  const store = useMemo(
    () => kioskActivityStorage(isLoading || isGuest ? null : identityKey, isGuest),
    [isLoading, isGuest, identityKey],
  );

  const [phase, setPhase] = useState<Phase>('loading');
  // ⚠️ `null` = 没失败;`''` = 失败了但服务端没给话。**存的不是译文**(见 `driftLine` 那段)。
  const [loadError, setLoadError] = useState<string | null>(null);
  /** 读到的谱不是 19 路时记下它的路数。实体盘和灯阵只有 19 路。 */
  const [wrongSize, setWrongSize] = useState<number | null>(null);
  const [captureError, setCaptureError] = useState<string | null>(null);
  /** 几何失效那一种「再按一次」永远不会成 —— 屏上得说另一句话。见 `BaipuCaptureErrorReason`。 */
  const [captureReason, setCaptureReason] = useState<BaipuCaptureErrorReason>('other');
  const [drift, setDrift] = useState<BaipuGeometryCorrection | null>(null);
  const [steps, setSteps] = useState<BaipuStep[]>([]);
  const [boardSize, setBoardSize] = useState(19);
  const [meta, setMeta] = useState<BaipuMeta | null>(null);
  const [k, setK] = useState(0);                       // 已经摆到实体盘上的手数
  const [exitOpen, setExitOpen] = useState(false);
  const [undoOpen, setUndoOpen] = useState(false);
  const [resumePrompt, setResumePrompt] = useState<number | null>(null);
  const [ledOk, setLedOk] = useState<boolean | null>(null);
  const [capturePending, setCapturePending] = useState(false);
  const [captureDisabled, setCaptureDisabled] = useState(false);
  const [frameCount, setFrameCount] = useState(0);
  const [latestSavedFile, setLatestSavedFile] = useState<string | null>(null);
  const [overwriteExisting, setOverwriteExisting] = useState(false);
  const initialCapturedRef = useRef(false);
  const mountedRef = useRef(true);
  const nowRef = useRef<HTMLSpanElement | null>(null);

  // Resolve SGF: fresh navigation state first, then the offline cache (identity-scoped —
  // empty while isLoading/guest, so this can never surface a prior real user's cached SGF;
  // `store` in the deps re-runs this once identity resolves, since the useMemo above only
  // captures its FIRST value otherwise).
  const cached = useMemo(() => getCachedSgf(source, store), [source, store]);
  const sgf = useMemo(() => {
    const navSgf = (location.state as { sgf?: string } | null)?.sgf;
    if (navSgf) return navSgf;
    return cached?.sgf ?? null;
  }, [location.state, cached]);

  useEffect(() => {
    if (!sgf) return;
    let cancelled = false;
    BaipuAPI.load({ sgf })
      .then((resp) => {
        if (cancelled) return;
        // 实体盘和灯阵都是 19 路。别的路数的行列发给灯会亮在左上角那一块 —— 每一颗都错位。
        // **这里是所有入口(屏 16 / 导入 SGF / 接着摆)的唯一汇合点**,所以拦在这儿,不在入口各拦一遍。
        // 顺手把它从「最近摆过」里拿掉:留着的话棋谱屏会给一颗点了还是摆不了的「接着摆」。
        if (resp.board_size !== 19) {
          forgetSgf(source, store);
          setWrongSize(resp.board_size);
          setPhase('error');
          return;
        }
        setSteps(resp.steps);
        setBoardSize(resp.board_size);
        setMeta(resp.meta);
        const prog = getProgress(source, store);
        if (prog && prog.k > 0 && prog.k < resp.steps.length) {
          setResumePrompt(prog.k); // ask continue vs restart
        }
        setPhase('guiding');
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setLoadError(err.message);
        setPhase('error');
      });
    return () => { cancelled = true; };
  }, [sgf, source, store]);

  const currentStep: BaipuStep | undefined = steps[k];
  const isPlaceable = !!currentStep && currentStep.kind !== 'pass' && currentStep.kind !== 'clear';

  const advance = useCallback(() => {
    setK((prev) => {
      const next = prev + 1;
      saveProgress(source, { k: next, frames: 0, updatedAt: Date.now(), total: steps.length }, store);
      setPhase(next >= steps.length ? 'done' : 'guiding');
      return next;
    });
  }, [source, steps.length, store]);

  // ── 三路判据 ── 照抄屏 14 物理盘开关(`TsumegoProblemPage` 那段):识别就绪 **不含**「本次开机确认过几何」,
  // 盒子一重启它就是真而几何是 required ⇒ 几何要单独判。没有 Provider(单测)= 没有摄像头 = 手动兜底。
  const visionStatus = useOptionalVision()?.visionStatus;
  const geoStatus = useOptionalGeometry()?.status;
  const geometryConfirmed = !geoStatus || geoStatus.phase === 'disabled'
    || (geoStatus.phase === 'ready' && geoStatus.session_calibrated && geoStatus.capabilities.geometry_ready);
  const cameraReady = !!visionStatus?.enabled && visionStatus.recognitionReady && geometryConfirmed;
  const camera = !collect && cameraReady;
  const manual = !collect && !cameraReady;
  // 手动兜底那句「为什么没用摄像头」。几何两种要多说一句去哪儿修。
  const geoPhase = geoStatus?.phase;
  const camWhy: { text: string; calib: boolean } | null = !manual ? null
    : !visionStatus?.enabled ? { text: t('baipu:cam_none', '没接摄像头'), calib: false }
      : !geometryConfirmed
        ? geoPhase === 'degraded' || geoPhase === 'failed'
          ? { text: t('baipu:cam_geo_drift', '棋盘标定已失效'), calib: true }
          : { text: t('baipu:cam_geo_confirm', '棋盘还没标定'), calib: true }
        : { text: t('baipu:cam_connecting', '正在连接摄像头'), calib: false };

  const [tryingRaw, setTrying] = useState(false);
  // 试下只在摄像头态、没摆完时成立 —— 摄像头中途掉了,不留一个手动态里看不见也关不掉的「试下中」。
  const trying = tryingRaw && camera && phase !== 'done';
  const hint = useBaipuHint({ steps, k, boardSize, meta });

  const visionSync = useVisionSync(null);
  const nextStone: NextStone | null = useMemo(() => {
    if (!isPlaceable || !currentStep || currentStep.row == null || currentStep.col == null || !currentStep.color) return null;
    return { row: currentStep.row, col: currentStep.col, color: currentStep.color === 'B' ? 1 : 2 };
  }, [isPlaceable, currentStep]);
  const visionBoard = useMemo(() => replayBaipuMatrix(steps, k, boardSize), [steps, k, boardSize]);
  const physical = usePhysicalBaipu({
    enabled: camera && phase === 'guiding' && resumePrompt === null,
    visionConnected: visionSync.connected,
    syncEvents: visionSync.syncEvents,
    k,
    board: visionBoard,
    next: nextStone,
    paused: trying || hint.open,
    hintLeds: hint.leds,
    onMatched: advance,
  });

  // 摆完就清进度(「完成」键删了)。采集机不清 —— 它的「完成」键还在,由人按。
  useEffect(() => {
    if (phase === 'done' && !collect) clearProgress(source, store);
  }, [phase, collect, source, store]);

  const doCapture = useCallback(
    async (moveIndex: number) => {
      if (!sgf) return;
      setCapturePending(true);
      setCaptureError(null);
      const out = await BaipuAPI.capture({
        game_id: source, move_index: moveIndex, sgf,
        overwrite_existing: overwriteExisting || undefined,
      });
      if (!mountedRef.current) return;
      setCapturePending(false);
      if (out.kind === 'error') { setCaptureError(out.message); setCaptureReason(out.reason); return; }
      if (out.kind === 'disabled') setCaptureDisabled(true);
      if (out.kind === 'ok') {
        const filename = savedFilename(out.result.path);
        if (filename) setLatestSavedFile(filename);
        setDrift(out.result.geometry_correction ?? null);
        setFrameCount((c) => c + 1);
        playShutter();   // 拍完才响 —— 它是「可以摆下一颗了」的信号
      }
      advance();
    },
    [sgf, source, overwriteExisting, advance],
  );

  // 开局那一帧(空盘 + 全灯):尽力而为,失败不拦路。**只有采集态拍。**
  useEffect(() => {
    if (collect && phase === 'guiding' && k === 0 && resumePrompt === null && !initialCapturedRef.current && sgf && steps.length > 0) {
      initialCapturedRef.current = true;
      BaipuAPI.capture({ game_id: source, move_index: -1, sgf, overwrite_existing: overwriteExisting || undefined })
        .then((out) => {
          if (!mountedRef.current) return;
          if (out.kind === 'disabled') { setCaptureDisabled(true); return; }
          if (out.kind !== 'ok') return;
          const filename = savedFilename(out.result.path);
          if (filename) setLatestSavedFile(filename);
          setFrameCount((c) => c + 1);
        })
        .catch(() => undefined);
    }
  }, [collect, phase, k, resumePrompt, sgf, source, steps.length, overwriteExisting]);

  // 没有物理动作的步(pass / AE)自己往前走。
  useEffect(() => {
    if (phase === 'guiding' && currentStep && (currentStep.kind === 'pass' || currentStep.kind === 'clear')) {
      const timer = setTimeout(advance, 500);
      return () => clearTimeout(timer);
    }
  }, [phase, currentStep, advance]);

  // 灯跟着屏走(手动兜底 / 采集机;摄像头态的灯归 `usePhysicalBaipu`)。
  // **失败只让那颗键变红,永不拦住摆放** —— 没灯照坐标摆,一样产出可用的帧。
  useEffect(() => {
    if (camera) return;
    if (hint.open) {
      // 支招开着:只亮 AI 候选(白);收起后这个 effect 重跑,按原逻辑重点。
      (hint.leds.length ? LedAPI.points(hint.leds) : LedAPI.clear())
        .then((r) => setLedOk(r.connected)).catch(() => setLedOk(false));
    } else if (phase === 'guiding' && currentStep && currentStep.kind !== 'pass' && currentStep.row != null && currentStep.col != null && currentStep.color) {
      LedAPI.point({ row: currentStep.row, col: currentStep.col, color: stoneToLedColor(currentStep.color) })
        .then((r) => setLedOk(r.connected)).catch(() => setLedOk(false));
    } else if (phase === 'await_removal' && currentStep && currentStep.removed.length > 0) {
      LedAPI.points(currentStep.removed.map((p) => ({ row: p.row, col: p.col, color: 'remove' as LedColor })))
        .then((r) => setLedOk(r.connected)).catch(() => setLedOk(false));
    } else if (phase === 'done') {
      LedAPI.clear().then((r) => setLedOk(r.connected)).catch(() => setLedOk(false));
    }
  }, [camera, hint.open, hint.leds, phase, k, currentStep]);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; LedAPI.clear().catch(() => undefined); };
  }, []);

  // 着法表滚到当前那一手 —— 241 手的谱靠手指翻是翻不到第 200 手的。
  useEffect(() => { nowRef.current?.scrollIntoView({ block: 'nearest' }); }, [k]);

  const relight = () => {
    if (camera) { physical.relight(); return; }
    if (hint.open) {
      if (hint.leds.length) LedAPI.points(hint.leds).then((r) => setLedOk(r.connected)).catch(() => setLedOk(false));
      return;
    }
    if (currentStep && currentStep.kind !== 'pass' && currentStep.row != null && currentStep.col != null && currentStep.color) {
      LedAPI.point({ row: currentStep.row, col: currentStep.col, color: stoneToLedColor(currentStep.color) })
        .then((r) => setLedOk(r.connected)).catch(() => setLedOk(false));
    }
  };

  const handleConfirm = () => {
    if (!currentStep) return;
    // 提子要人先把死子拿下来,拿完才存帧 —— 否则那一帧上是一个不该存在的局面。
    if (currentStep.removed.length > 0 && phase === 'guiding') { setPhase('await_removal'); return; }
    if (collect) void doCapture(k); else advance();
  };

  const handleUndo = () => {
    setUndoOpen(false);
    setCaptureError(null);
    setK((prev) => {
      const next = Math.max(0, prev - 1);
      saveProgress(source, { k: next, frames: 0, updatedAt: Date.now(), total: steps.length }, store);
      return next;
    });
    setPhase('guiding');
  };

  // ── 盘面:笨播放器,一条气都不算 ──
  const board = useMemo(() => replayBaipuSteps(steps, k, boardSize), [steps, k, boardSize]);
  const ghost = useMemo(() => {
    // 试下 / 支招开着时不画:那时盘上的主角是人自己的推演 / AI 的候选,不是谱上的下一手。
    if (trying || hint.open) return [];
    if (!['guiding', 'await_removal'].includes(phase) || !currentStep) return [];
    if (currentStep.row == null || currentStep.col == null) return [];
    return [canonToGtp(currentStep.row, currentStep.col, boardSize)];
  }, [trying, hint.open, phase, currentStep, boardSize]);
  // 摄像头态「把盘面摆对」时多出来的子(蓝灯闪的那几颗)。恰好是下一手的那一颗是对的,不圈。
  const setupExtra = useMemo(() => {
    if (!camera || physical.phase !== 'setup') return [];
    return physical.extra.filter(([r, c, v]) => !(nextStone && nextStone.row === r && nextStone.col === c && nextStone.color === v));
  }, [camera, physical.phase, physical.extra, nextStone]);
  const removeMarks = useMemo(() => setupExtra.map(([r, c]) => canonToGtp(r, c, boardSize)), [setupExtra, boardSize]);
  const hintMarks = useMemo(
    () => (hint.open ? hint.rows.map((r) => r.move).filter((m) => m.toLowerCase() !== 'pass') : []),
    [hint.open, hint.rows],
  );
  const atari = useMemo(() => {
    if (phase !== 'await_removal' || !currentStep) return [];
    return currentStep.removed.map((p) => canonToGtp(p.row, p.col, boardSize));
  }, [phase, currentStep, boardSize]);

  const nextColor = currentStep?.color ?? null;
  const coord = currentStep?.row != null && currentStep.col != null
    ? canonToGtp(currentStep.row, currentStep.col, boardSize) : null;

  // 着法表:一行一个回合(黑 / 白)。
  const rows = useMemo(() => {
    const out: { n: number; b: string | null; w: string | null; bAt: number; wAt: number }[] = [];
    steps.forEach((s, i) => {
      if (s.kind === 'setup' || s.kind === 'clear') return;
      const label = s.row != null && s.col != null ? canonToGtp(s.row, s.col, boardSize) : null;
      const tail = out[out.length - 1];
      if (s.color === 'B' || !tail || tail.w !== null) out.push({ n: out.length + 1, b: null, w: null, bAt: -1, wAt: -1 });
      const cur = out[out.length - 1];
      if (s.color === 'W') { cur.w = label; cur.wAt = i; } else { cur.b = label; cur.bAt = i; }
    });
    return out;
  }, [steps, boardSize]);

  const drifted = driftLine(drift);
  const driftText = drifted && {
    corrected: t('baipu:drift_corrected', '棋盘动过，已自动校正'),
    stale: t('baipu:drift_stale', '这一帧没能重新校正，沿用了上次的几何'),
    frozen: t('baipu:drift_frozen', '几何没有校正过'),
  }[drifted.key];
  const driftWord = drifted && {
    corrected: t('baipu:drift_word_corrected', '已校正'),
    stale: t('baipu:drift_word_stale', '沿用上次'),
    frozen: t('baipu:drift_word_frozen', '未校正'),
  }[drifted.key];

  const title = (location.state as { name?: string } | null)?.name
    ?? cached?.name
    ?? (meta ? `${meta.player_black || t('baipu:black', '黑方')} vs ${meta.player_white || t('baipu:white', '白方')}` : t('baipu:title', '摆谱'));

  // ── 读不到 / 还在读 ──
  if (!sgf || phase === 'error') {
    return (
      <div className="kiosk-layout-b" data-testid="baipu-session-page">
        <KioskPagebar
          testId="baipu-pagebar"
          backLabel={backLabel}
          onBack={back}
          title={t('baipu:title', '摆谱')}
        />
        <div className="empty" data-testid="baipu-load-error">
          {wrongSize !== null ? (
            <>
              <h4>{interpolate(t('baipu:wrong_size', '这是 {n} 路的谱，摆不了'), { n: wrongSize })}</h4>
              <p>{t('baipu:wrong_size_hint', '实体盘和灯都是 19 路的 —— 别的路数摆上去每一颗都会错位。')}</p>
            </>
          ) : (
            <>
              <h4>{sgf ? t('baipu:load_failed', '没读出这份谱') : t('baipu:no_sgf', '这台盒子上没有这份谱')}</h4>
              {loadError && <p>{loadError}</p>}
            </>
          )}
        </div>
      </div>
    );
  }
  if (phase === 'loading') {
    return (
      <div className="kiosk-layout-b" data-testid="baipu-session-page">
        <KioskPagebar
          testId="baipu-pagebar"
          backLabel={backLabel}
          onBack={back}
          title={title}
        />
        <div className="empty" data-testid="baipu-loading"><h4>{t('baipu:loading', '正在读这份谱')}</h4></div>
      </div>
    );
  }

  // 优先级写死,互斥 —— 见页头那一行。(拍照遮罩盖在最上面,不属于这一档。)
  const mood: Mood = captureError !== null ? 'failed'
    : phase === 'await_removal' ? 'removal'
      : phase === 'done' ? 'done'
        : trying ? 'trying'
          : hint.open ? 'hint'
            : camera && physical.phase === 'setup' ? 'setup'
              : 'guiding';

  const moveNo = Math.min(k + (phase === 'done' ? 0 : 1), steps.length);
  const colorWord = nextColor === 'W' ? t('baipu:white_s', '白') : t('baipu:black_s', '黑');
  const ledBad = camera ? !physical.ledOk : ledOk === false;

  // 摄像头态「把盘面摆对」说哪句 —— 收敛规则都一样,只按「为什么到这儿」换话。
  const setupCard = (): { h: string; p: string } => {
    switch (physical.reason) {
      case 'capture':
        return {
          h: interpolate(t('baipu:removal_title', '请拿走被提的 {n} 子'), {
            n: setupExtra.length || (steps[k - 1]?.removed.length ?? 0),
          }),
          p: t('baipu:capture_hint_camera', '亮蓝灯的那几颗 —— 拿干净了自动下一手'),
        };
      case 'wrong':
        return {
          h: interpolate(t('baipu:wrong_title', '放错了 · 应该在 {c}'), { c: coord ?? '' }),
          p: interpolate(t('baipu:wrong_hint', '把蓝灯那颗({w})拿起来，放到 {c} —— 对上了自动继续'), {
            w: physical.wrong ? canonToGtp(physical.wrong[0], physical.wrong[1], boardSize) : '',
            c: coord ?? '',
          }),
        };
      case 'undo':
        return {
          h: interpolate(t('baipu:undo_title', '撤回到第 {n} 手'), { n: k }),
          p: t('baipu:undo_hint_camera', '蓝灯的子拿走，被提的子放回红绿灯处 —— 对上了自动继续'),
        };
      case 'restore':
        return {
          h: interpolate(t('baipu:restore_title', '把盘面摆回第 {n} 手'), { n: k }),
          p: t('baipu:restore_hint', '试下的子拿走、挪动的放回 —— 对上了自动接着摆'),
        };
      case 'adopt':
      case 'verify':
        return { h: t('baipu:verify_title', '正在对一下盘面'), p: t('baipu:verify_hint', '多出来的子亮蓝灯 —— 拿走就继续') };
      default: // entry:进场先把实体盘摆成屏上这一手
        return {
          h: k === 0
            ? t('baipu:setup_clear_title', '先把盘上的子都拿下来')
            : interpolate(t('baipu:setup_entry_title', '先把盘面摆成第 {n} 手'), { n: k }),
          p: t('baipu:setup_entry_hint', '蓝灯的子拿走、红绿灯处放上 —— 对上了自动开始'),
        };
    }
  };

  // 待摆那一句:支招中 > 灯坏了 > 摄像头在看 > 手动兜底(写明为什么)> 采集机。
  const guidingLine = mood === 'hint'
    ? camera
      ? t('baipu:hint_on_hint', 'AI 支招中，识别暂停 —— 白灯是 AI 的候选点，收起支招后接着摆')
      // 手动兜底本来就没在识别,「识别暂停」是一句假话。
      : t('baipu:hint_on_hint_manual', 'AI 支招中 —— 白灯是 AI 的候选点，收起支招后接着摆')
    : ledBad
      ? interpolate(t('baipu:led_down', '灯没亮 —— 按右上角重新点灯，或照坐标 {c} 自己找'), { c: coord ?? '' })
      : camera
        ? interpolate(t('baipu:led_on_camera', '灯已点亮 —— 把{color}子放在亮着的那个交叉点，摄像头认到就自动下一手'), { color: colorWord })
        : camWhy
          ? interpolate(t('baipu:manual_hint', '{why} —— 摆好后按「确认落子」'), { why: camWhy.text })
            + (camWhy.calib ? t('baipu:manual_hint_calib', '；标定在「设置」里') : '')
          : interpolate(t('baipu:led_on', '灯已点亮 —— 把{color}子放在亮着的那个交叉点'), { color: colorWord });

  // ── 动作区:三路各一组(页头「三路」那段)──
  const confirmAction: KioskAction = mood === 'removal'
    ? {
      key: 'removed',
      // 相机图标只在真拍照时出现 —— 上线态画个相机,等于屏上说「这一下要拍照」。
      icon: collect ? 'camera' : 'hand-pointing',
      label: interpolate(t('baipu:removed_done', '已移除 {n} 子'), { n: currentStep?.removed.length ?? 0 }),
      disabled: capturePending,
      onClick: () => { if (collect) void doCapture(k); else advance(); },
    }
    : {
      key: 'confirm',
      // 手动兜底用箭头:和「试下」的手不撞(稿 17d)。
      icon: collect ? 'camera' : 'arrow-right',
      label: t('baipu:confirm', '确认落子'),
      disabled: capturePending || phase === 'done' || !isPlaceable,
      reason: phase === 'done' ? t('baipu:confirm_done_reason', '这份谱已经摆完了') : undefined,
      onClick: handleConfirm,
    };
  const undoAction: KioskAction = camera
    ? {
      key: 'undo',
      icon: 'arrow-counter-clockwise',
      label: t('baipu:undo', '撤回上一手'),
      // 立刻撤、不弹框:撤完灯带着把盘面摆回去,对上了自动继续。
      disabled: k === 0 || trying,
      reason: trying ? t('baipu:undo_try_reason', '试下中不能撤回')
        : k === 0 ? t('baipu:undo_reason', '还没摆下第一颗') : undefined,
      onClick: handleUndo,
    }
    : {
      key: 'undo',
      icon: 'arrow-counter-clockwise',
      label: t('baipu:undo', '撤回上一手'),
      disabled: k === 0 || capturePending,
      reason: k === 0 ? t('baipu:undo_reason', '还没摆下第一颗') : undefined,
      onClick: () => setUndoOpen(true),
    };
  const tryAction: KioskAction = camera
    ? {
      key: 'try',
      icon: 'hand-pointing',
      label: t('Try', '试下'),
      pressed: trying,
      disabled: phase === 'done',
      reason: phase === 'done' ? t('baipu:confirm_done_reason', '这份谱已经摆完了') : undefined,
      onClick: () => { if (!trying) hint.close(); setTrying(!trying); },
    }
    // 手动兜底:摄像头本来就没在看,「暂停识别」无从谈起 —— 灰着、说原因(暂时不可用灰着,不撤)。
    : {
      key: 'try', icon: 'hand-pointing', label: t('Try', '试下'),
      disabled: true, reason: t('baipu:try_off_reason', '摄像头没在识别'), onClick: () => {},
    };
  const hintAction: KioskAction = {
    key: 'hint',
    icon: 'lightbulb',
    label: t('Hints', 'AI支招'),
    pressed: hint.open,
    disabled: isGuest || trying || phase === 'done',
    reason: isGuest ? t('play:analysis_requires_login', '登录后可用')
      : trying ? t('baipu:hint_try_reason', '试下中摄像头不看盘，AI 不知道盘上是什么局面')
        : phase === 'done' ? t('baipu:confirm_done_reason', '这份谱已经摆完了') : undefined,
    onClick: hint.toggle,
  };
  const actions: KioskAction[] = collect
    ? [
      confirmAction,
      undoAction,
      {
        key: 'finish',
        icon: 'flag',
        label: t('baipu:finish', '完成'),
        // 采集机才有:常驻是为了格子不重排(「确认落子」一局按约 250 次,位置是肌肉记忆);
        // 摆完之前一律灰 —— 提前收工是**返回**该做的事,不是它。
        disabled: phase !== 'done',
        reason: phase !== 'done'
          ? interpolate(t('baipu:finish_reason', '还剩 {n} 手没摆'), { n: steps.length - k })
          : undefined,
        onClick: () => { clearProgress(source, store); back(); },
      },
    ]
    : manual
      ? [confirmAction, undoAction, tryAction, hintAction]
      : [
        // setup 10 s 没对上(密盘上识别一帧里凑不齐整盘)⇒ 按摄像头现在看到的接着摆。
        ...(physical.phase === 'setup' && physical.stuck
          ? [{ key: 'adopt', icon: 'arrow-right', label: t('baipu:setup_continue', '摆好了，继续'), onClick: physical.adopt } as KioskAction]
          : []),
        undoAction,
        tryAction,
        hintAction,
      ];

  const cols = colsFor(boardSize);
  const boardRows = rowsFor(boardSize);

  return (
    <div className="kiosk-layout-a baipu-layout" data-testid="baipu-session-page" data-mood={mood}>
      <div className="kiosk-board" data-testid="baipu-board">
        <div className="kiosk-board__ruler kiosk-board__ruler--top">
          {cols.map((c) => <span key={`t${c}`}>{c}</span>)}
        </div>
        <div className="kiosk-board__ruler kiosk-board__ruler--left">
          {boardRows.map((r) => <span key={`l${r}`}>{r}</span>)}
        </div>
        <div className="kiosk-board__play">
          <GoBoardSvg
            size={boardSize}
            black={board.black}
            white={board.white}
            last={board.last}
            ghost={ghost}
            // 屏上那个圈必须和盘上那颗灯同色 —— 黑子红、白子绿。
            ghostFor={nextColor ?? undefined}
            atari={atari}
            remove={removeMarks}
            hint={hintMarks}
            label={t('baipu:board_label', '摆谱盘面：圈是下一手该落的点')}
          />
        </div>
        <div className="kiosk-board__ruler kiosk-board__ruler--right">
          {boardRows.map((r) => <span key={`r${r}`}>{r}</span>)}
        </div>
        <div className="kiosk-board__ruler kiosk-board__ruler--bottom">
          {cols.map((c) => <span key={`b${c}`}>{c}</span>)}
        </div>
      </div>

      <div className="kiosk-rail">
        <KioskPagebar
          testId="baipu-pagebar"
          backLabel={backLabel}
          onBack={() => setExitOpen(true)}
          title={title}
          sub={interpolate(
            collect
              ? t('baipu:pagebar_sub', '第 {i} / {n} 手 · 已采集 {f} 帧')
              : t('baipu:pagebar_sub_placed', '第 {i} / {n} 手'),
            { i: Math.min(k + (phase === 'done' ? 0 : 1), steps.length), n: steps.length, f: frameCount },
          )}
          action={{
            // 2026-09-23 灯泡换成循环箭头:灯泡在对弈页是「AI 支招」,同一个图标两个意思(Fan 问过「灯泡是做什么的」)。
            icon: 'arrows-clockwise',
            label: t('baipu:relight', '重新点灯'),
            onClick: relight,
            // 这颗键兼当 LED 的状态点 —— 它本来就是这个故障的补救动作。
            state: ledBad ? 'bad' : undefined,
          }}
        />

        {/* ── 此刻你该做什么 ── 互斥,同一块 pcard 换内容 */}
        <div className={`pcard ${PCARD_CLASS[mood]}`.trim()} data-testid="baipu-pcard" data-mood={mood}>
          {nextColor && (mood === 'guiding' || mood === 'hint' || mood === 'setup' || mood === 'trying')
            && <span className={nextColor === 'B' ? 'disc b' : 'disc w'} />}
          <div>
            {mood === 'failed' ? (
              <>
                <h4>{t('baipu:failed_title', '这一手没采上')}</h4>
                {/* 服务端原文塞 title,不上屏:`.pcard p` 是 11px 单行省略,印上去只会被截断,
                    而站在盘前的人也不 debug HTTP。
                    ⚠️ **几何那一种不能说「再按一次」** —— 它的 409 会一直是同一个,
                    人照着做只会一直按下去。那一种要说的是「去哪儿修」。 */}
                <p title={captureError || undefined}>
                  {captureReason === 'geometry'
                    ? t('baipu:failed_hint_geometry', '棋盘位置对不上了 —— 去设置里重新标定，再按一次没用')
                    : t('baipu:failed_hint', '子先别动 —— 再按一次「确认落子」')}
                </p>
              </>
            ) : mood === 'removal' ? (
              <>
                <h4>{interpolate(t('baipu:removal_title', '请拿走被提的 {n} 子'), { n: currentStep?.removed.length ?? 0 })}</h4>
                <p>{t('baipu:removal_hint', '亮蓝灯的那几颗 —— 提子要人自己拿，拿完再按「已移除」')}</p>
              </>
            ) : mood === 'done' ? (
              <>
                <h4>{t('baipu:done_title', '这份谱摆完了')}</h4>
                <p>{collect
                  ? interpolate(t('baipu:done_hint', '一共 {n} 手 · 采到 {f} 帧'), { n: steps.length, f: frameCount })
                  : interpolate(t('baipu:done_hint_auto', '一共 {n} 手 · 进度已清掉，按左上角返回'), { n: steps.length })}</p>
              </>
            ) : mood === 'trying' ? (
              <>
                <h4>{t('baipu:trying_title', '试下中 · 摄像头暂停识别')}</h4>
                <p>{t('baipu:trying_hint', '盘上随便摆、推演。再按「试下」回到谱上，灯会带你把盘面摆回去')}</p>
              </>
            ) : mood === 'setup' ? (
              <>
                <h4>{setupCard().h}</h4>
                <p>{setupCard().p}</p>
              </>
            ) : (
              <>
                <h4>{coord
                  ? interpolate(t('baipu:place_at', '当前待摆 · {c}'), { c: coord })
                  : t('baipu:place_none', '这一步不用摆子')}</h4>
                <p>{guidingLine}</p>
              </>
            )}
          </div>
          <div className="clock">
            <b>{mood === 'removal' ? (currentStep?.removed.length ?? 0) : moveNo}</b>
            <span>{mood === 'removal' ? t('baipu:stones_unit', '子') : t('baipu:which_move', '第几手')}</span>
          </div>
        </div>

        {/* ── AI 支招(开着时)/ 摄像头(采集机)/ 灯(其余)── 这本账也是那条 LED 图例的落点。
            支招的三行**借灯图例这一块的位置**:右栏的账是死的,多插一块就压着法表(页头那段)。 */}
        {hint.open ? (
          <KioskFold
            fold="hint"
            testId="baipu-hint-fold"
            title={t('baipu:hint_title', 'AI 支招 · 白灯闪烁处')}
            value={t('baipu:hint_value', '再按一次收起')}
            bodyClassName="ledger"
          >
            {hint.status === 'loading' ? (
              <div className="lrow"><b>{t('baipu:hint_loading', 'AI 正在算这一手…')}</b></div>
            ) : hint.status === 'error' || hint.rows.length === 0 ? (
              <div className="lrow"><b className="warn">{t('baipu:hint_failed', '没算出来 —— 收起后再按一次试试')}</b></div>
            ) : hint.rows.map((r, i) => (
              <div className="lrow" key={r.move}>
                <b>{`${i + 1} · ${r.move}`}</b>
                <i>{interpolate(t('baipu:hint_row', '胜率 {w}% · 目差 {s}'), { w: (r.winrate * 100).toFixed(1), s: signed(r.scoreLead) })}</i>
              </div>
            ))}
          </KioskFold>
        ) : collect ? (
          <KioskFold
            fold="cam"
            testId="baipu-cam-fold"
            title={t('baipu:cam_title', '摄像头 · 这一手要采一帧')}
            // 收起的是明细不是结论:没接采集 / 几何有话说,这两句收起来也得看得见。
            value={captureDisabled
              ? t('baipu:capture_off', '这台机器没接采集')
              : driftWord ?? t('baipu:hands_off', '手不要在盘上')}
            bodyClassName="ledger"
          >
            <div className="lrow">
              <b>{interpolate(t('baipu:frames_n', '已采集 {n} 帧'), { n: frameCount })}</b>
              <span className="led" style={{ background: LED_HEX.black }} aria-hidden="true" />
              <i>{t('baipu:legend_black', '红灯 = 放黑子')}</i>
            </div>
            <div className="lrow">
              <b>{latestSavedFile
                ? interpolate(t('baipu:latest_saved', '最近保存 {f}'), { f: latestSavedFile })
                : t('baipu:no_frame_yet', '还没存过帧')}</b>
              <span className="led" style={{ background: LED_HEX.white }} aria-hidden="true" />
              <i>{t('baipu:legend_white', '绿灯 = 放白子')}</i>
            </div>
            <div className="lrow">
              <b>{interpolate(
                t('baipu:removed_n', '本手提子 {n} 子'),
                { n: mood === 'removal' ? (currentStep?.removed.length ?? 0) : 0 },
              )}</b>
              <span className="led" style={{ background: LED_HEX.remove }} aria-hidden="true" />
              <i>{t('baipu:legend_remove', '蓝灯 = 该拿走')}</i>
            </div>
            {driftText && (
              <div className="lrow" data-testid="baipu-drift-row" data-drift-status={drifted?.key}>
                <b style={drifted?.bad ? { color: 'var(--warn)' } : undefined}>{driftText}</b>
              </div>
            )}
          </KioskFold>
        ) : (
          /* 上线态没有摄像头这回事。**行数和采集态一样是三行** —— 右栏的账是死的(页头「四条通栏横幅一条都不进右栏」那段),
             这一块一变高就压着法表。图例文案沿用那三句,色点仍是灯的真值。 */
          <KioskFold
            fold="led"
            testId="baipu-led-fold"
            title={t('baipu:led_title', '灯 · 颜色对照')}
            value={trying
              ? t('baipu:led_value_try', '试下中 · 暂停识别')
              : camera ? t('baipu:led_value_camera', '摄像头在看') : t('baipu:led_value_manual', '手动确认')}
            valueTone={manual ? 'warn' : undefined}
            bodyClassName="ledger"
          >
            <div className="lrow">
              <b>{t('baipu:legend_black', '红灯 = 放黑子')}</b>
              <span className="led" style={{ background: LED_HEX.black }} aria-hidden="true" />
            </div>
            <div className="lrow">
              <b>{t('baipu:legend_white', '绿灯 = 放白子')}</b>
              <span className="led" style={{ background: LED_HEX.white }} aria-hidden="true" />
            </div>
            <div className="lrow">
              <b>{t('baipu:legend_remove', '蓝灯 = 该拿走')}</b>
              <span className="led" style={{ background: LED_HEX.remove }} aria-hidden="true" />
            </div>
          </KioskFold>
        )}

        {/* ── 已经摆过的 ── */}
        <KioskFold
          fold="moves"
          grow
          testId="baipu-moves-fold"
          title={t('baipu:moves_title', '已经摆过的')}
          value={interpolate(t('baipu:moves_value', '{k} 手 / 共 {n}'), { k, n: steps.length })}
          bodyClassName="mvrows"
        >
          {rows.length === 0 ? (
            <span className="n">{t('baipu:no_moves', '这份谱里没有着法')}</span>
          ) : rows.map((r) => (
            <BaipuMoveRow key={r.n} row={r} k={k} nowRef={nowRef} passLabel={t('baipu:pass', '虚手')} />
          ))}
        </KioskFold>

        <KioskActions
          testId="baipu-actions"
          ariaLabel={t('baipu:actions', '摆谱操作')}
          actions={actions}
        />
      </div>

      {/* 拍照遮罩:盖住**整个布局根**。第一职责是挡住第二次按下「确认落子」——
          只盖盘的话右栏三颗键看着是活的、按下去没反应,那比一句偏了的提示更像假话。 */}
      {capturePending && (
        <div className="cdlg" data-testid="baipu-capture-pending">
          <div className="cdlg__box" role="alertdialog" aria-modal="true">
            <h3>{t('baipu:capturing', '正在拍照，请勿伸手')}</h3>
            <p>{t('baipu:capturing_hint', '手挡住了这一手就采不到，得重来。')}</p>
          </div>
        </div>
      )}

      {resumePrompt !== null && (
        <div className="cdlg" data-testid="baipu-resume">
          <div className="cdlg__box" role="dialog" aria-modal="true">
            <h3>{t('baipu:resume_ask', '接着上次摆？')}</h3>
            <p>{interpolate(
              collect
                ? t('baipu:resume_body', '上次摆到第 {n} 手。重新开始会覆盖已经采过的帧。')
                : t('baipu:resume_body_placed', '上次摆到第 {n} 手。从头摆要先把盘上的子都拿下来。'),
              { n: resumePrompt },
            )}</p>
            <div className="cdlg__acts">
              <button
                type="button" className="ghost" data-testid="baipu-resume-restart"
                onClick={() => {
                  clearProgress(source, store);
                  setOverwriteExisting(true);
                  setFrameCount(0); setLatestSavedFile(null); setCaptureError(null); setDrift(null);
                  initialCapturedRef.current = false;
                  setK(0); setResumePrompt(null);
                }}
              >{t('baipu:restart', '从头摆')}</button>
              <button
                type="button" className="main" data-testid="baipu-resume-continue"
                onClick={() => { setK(resumePrompt); setOverwriteExisting(false); setResumePrompt(null); }}
              >{t('baipu:resume', '接着摆')}</button>
            </div>
          </div>
        </div>
      )}

      {undoOpen && (
        <div className="cdlg" data-testid="baipu-undo-confirm">
          <div className="cdlg__box" role="dialog" aria-modal="true">
            <h3>{t('baipu:undo_ask', '撤回上一手？')}</h3>
            <p>{t('baipu:undo_body', '先把刚摆的那颗子从盘上拿下来（被提的子也放回去），再按「已撤回」。')}</p>
            <div className="cdlg__acts">
              <button type="button" className="ghost" onClick={() => setUndoOpen(false)}>{t('cancel', '取消')}</button>
              <button type="button" className="main" data-testid="baipu-undo-confirm-action" onClick={handleUndo}>
                {t('baipu:undo_done', '已撤回')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 退出确认。**不是实现遗留,是这一屏已采纳的裁定**:「确认落子」一局按约 250 次,
          退出按一次,两颗不能同排;解法是移到角上(页控条)+ 二次确认,两半配套。 */}
      {exitOpen && (
        <div className="cdlg" data-testid="baipu-exit-confirm">
          <div className="cdlg__box" role="dialog" aria-modal="true">
            <h3>{t('baipu:exit_ask', '退出摆谱？')}</h3>
            <p>{t('baipu:exit_body', '进度已经存下了，回来还能接着摆。')}</p>
            <div className="cdlg__acts">
              <button type="button" className="ghost" onClick={() => setExitOpen(false)}>{t('cancel', '取消')}</button>
              <button
                type="button" className="main" data-testid="baipu-exit-confirm-action"
                onClick={back}
              >{t('baipu:exit', '退出')}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

/** 着法表一行:回合号 + 黑 + 白。当前那一手高亮,并把 ref 交出去好滚到视野里。 */
function BaipuMoveRow({ row, k, nowRef, passLabel }: {
  row: { n: number; b: string | null; w: string | null; bAt: number; wAt: number };
  k: number;
  nowRef: React.MutableRefObject<HTMLSpanElement | null>;
  passLabel: string;
}) {
  const cell = (label: string | null, at: number) => {
    if (at < 0) return <span className="mv" />;
    // 「已经摆过的」= 下标 < k。当前那一手(下标 k)还没摆,不算。
    const done = at < k;
    const isNow = at === k - 1;
    return (
      <span ref={isNow ? nowRef : undefined} className={isNow ? 'mv now' : 'mv'} style={done ? undefined : { opacity: 0.35 }}>
        {label ?? passLabel}
      </span>
    );
  };
  return (
    <>
      <span className="n">{row.n}</span>
      {cell(row.b, row.bAt)}
      {cell(row.w, row.wAt)}
    </>
  );
}

export default BaipuSessionPage;
