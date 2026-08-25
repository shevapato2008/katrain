import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useParams, useLocation, useNavigate } from 'react-router-dom';

import { useTranslation } from '../../hooks/useTranslation';
import { type BaipuCaptureErrorReason,
  BaipuAPI, getCachedSgf, saveProgress, getProgress, clearProgress,
  canonToGtp, type BaipuStep, type BaipuMeta, type BaipuGeometryCorrection,
} from '../../api/baipuApi';
import { LedAPI, type LedColor } from '../../api/ledApi';
import { LED_HEX } from '../constants/ledColors';
import { replayBaipuSteps } from '../../utils/baipuReplay';
import { GoBoardSvg } from '../shell/GoBoardSvg';
import { colsFor, rowsFor } from '../shell/goBoard';
import { KioskActions } from '../shell/KioskActions';
import { KioskFold } from '../shell/KioskFold';
import { KioskPagebar } from '../shell/KioskPagebar';
import { driftLine } from '../utils/baipuDrift';
import { interpolate } from '../utils/interpolate';

const stoneToLedColor = (c: 'B' | 'W'): LedColor => (c === 'B' ? 'black' : 'white');

const savedFilename = (path?: string): string | null => {
  if (!path) return null;
  return path.split(/[\\/]/).filter(Boolean).at(-1) ?? null;
};

// Short shutter "click" via WebAudio (no asset). Plays AFTER the frame is written
// (the "you may place the next stone" go-signal). Best-effort; ignored if blocked.
function playShutter() {
  try {
    const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const ctx = new Ctx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.frequency.value = 880;
    gain.gain.setValueAtTime(0.0001, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.2, ctx.currentTime + 0.005);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.09);
    osc.connect(gain).connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.1);
    osc.onended = () => ctx.close();
  } catch {
    // no audio available — silent
  }
}

type Phase = 'loading' | 'guiding' | 'await_removal' | 'done' | 'error';

/** 右栏此刻在说哪一件事。**互斥且有序** —— 见页面头注那张优先级表。 */
type Mood = 'guiding' | 'removal' | 'failed' | 'done';

/**
 * 屏 17 · 摆谱 · 进行中 `/kiosk/baipu/session/:source` —— L2 布局 A(左盘 516 + 16 + 右栏 460)。
 *
 * **这一屏的主角不在屏幕上,在实体盘上。** 灯点着下一手该落哪儿,人把子摆上去,摄像头采一帧
 * (那些帧是 YOLO 的训练数据)。提子要人**自己**把死子拿下来;拍照那一刻手不能在盘上。
 * 屏幕在这儿只是副驾 —— 所以右栏第一块不是棋谱也不是记账,是「**现在轮到你摆哪一颗**」。
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
 * 优先级写死:`拍照遮罩` > `采集失败` > `待移除` > `待摆` > `已完成`。
 *
 * ## 动作区三格,不是稿子那四格
 *
 * 稿子多画了一颗「虚手」。**不做**:这一屏是在重放一份既有的 SGF,而这条 track 的数据契约
 * 把 pass 定义成「无物理动作」(`sbc-baipu-led-guide/plan.md`:pass 不产帧、
 * `frames.length = 1 + 非 pass 落子数`、`next_guided_move_index` 跳过 pass)。
 * 一颗人能按的「虚手」要么产帧、破坏那条等式,要么什么都不干。
 * 「虚手」这个词留在着法表里做**记谱**(屏 16 同款)—— 它是事实,不是动作。
 *
 * 「完成」按稿子**常驻第三格**,但摆完之前一律灰 + 写明还差多少:常驻是为了格子不重排
 * (那颗「确认落子」一局按 250 次,位置是肌肉记忆);常亮则会变成一颗写着「完成」
 * 却在第 13 手把你送走的键 —— 提前收工是**返回**该做的事,不是它。
 *
 * ## 盘不用 `LiveBoard`
 *
 * 两条:① 它的 `gridMargins` 写死 1.5 格而刻度带按 0.5 格算,字和线错开约一格
 * (`KioskSetupBoard` 头注那段推导);② 它在渲染路径里**自己算提子**,而 `baipuApi` 决策 ②
 * 定死「前端是 `steps[]` 的笨播放器,永远不自己重算提子」—— 用它就是屏上画前端算的提子、
 * 灯点后端算的提子,两套气规则同屏跑。盘面走共享的 `replayBaipuSteps`(屏 16 / 屏 19 同款)。
 */
const BaipuSessionPage = () => {
  const { source = '' } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { t } = useTranslation();

  const [phase, setPhase] = useState<Phase>('loading');
  // ⚠️ `null` = 没失败;`''` = 失败了但服务端没给话。**存的不是译文**(见 `driftLine` 那段)。
  const [loadError, setLoadError] = useState<string | null>(null);
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

  const cached = useMemo(() => getCachedSgf(source), [source]);
  const sgf = useMemo(() => {
    const navSgf = (location.state as { sgf?: string } | null)?.sgf;
    return navSgf ?? cached?.sgf ?? null;
  }, [location.state, cached]);

  useEffect(() => {
    if (!sgf) return;
    let cancelled = false;
    BaipuAPI.load({ sgf })
      .then((resp) => {
        if (cancelled) return;
        setSteps(resp.steps);
        setBoardSize(resp.board_size);
        setMeta(resp.meta);
        const prog = getProgress(source);
        if (prog && prog.k > 0 && prog.k < resp.steps.length) setResumePrompt(prog.k);
        setPhase('guiding');
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setLoadError(err.message);
        setPhase('error');
      });
    return () => { cancelled = true; };
  }, [sgf, source]);

  const currentStep: BaipuStep | undefined = steps[k];
  const isPlaceable = !!currentStep && currentStep.kind !== 'pass' && currentStep.kind !== 'clear';

  const advance = useCallback(() => {
    setK((prev) => {
      const next = prev + 1;
      saveProgress(source, { k: next, frames: 0, updatedAt: Date.now(), total: steps.length });
      setPhase(next >= steps.length ? 'done' : 'guiding');
      return next;
    });
  }, [source, steps.length]);

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

  // 开局那一帧(空盘 + 全灯):尽力而为,失败不拦路。
  useEffect(() => {
    if (phase === 'guiding' && k === 0 && resumePrompt === null && !initialCapturedRef.current && sgf && steps.length > 0) {
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
  }, [phase, k, resumePrompt, sgf, source, steps.length, overwriteExisting]);

  // 没有物理动作的步(pass / AE)自己往前走。
  useEffect(() => {
    if (phase === 'guiding' && currentStep && (currentStep.kind === 'pass' || currentStep.kind === 'clear')) {
      const timer = setTimeout(advance, 500);
      return () => clearTimeout(timer);
    }
  }, [phase, currentStep, advance]);

  // 灯跟着屏走。**失败只让那颗键变红,永不拦住摆放** —— 没灯照坐标摆,一样产出可用的帧。
  useEffect(() => {
    if (phase === 'guiding' && currentStep && currentStep.kind !== 'pass' && currentStep.row != null && currentStep.col != null && currentStep.color) {
      LedAPI.point({ row: currentStep.row, col: currentStep.col, color: stoneToLedColor(currentStep.color) })
        .then((r) => setLedOk(r.connected)).catch(() => setLedOk(false));
    } else if (phase === 'await_removal' && currentStep && currentStep.removed.length > 0) {
      LedAPI.points(currentStep.removed.map((p) => ({ row: p.row, col: p.col, color: 'remove' as LedColor })))
        .then((r) => setLedOk(r.connected)).catch(() => setLedOk(false));
    } else if (phase === 'done') {
      LedAPI.clear().then((r) => setLedOk(r.connected)).catch(() => setLedOk(false));
    }
  }, [phase, k, currentStep]);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; LedAPI.clear().catch(() => undefined); };
  }, []);

  // 着法表滚到当前那一手 —— 241 手的谱靠手指翻是翻不到第 200 手的。
  useEffect(() => { nowRef.current?.scrollIntoView({ block: 'nearest' }); }, [k]);

  const relight = () => {
    if (currentStep && currentStep.kind !== 'pass' && currentStep.row != null && currentStep.col != null && currentStep.color) {
      LedAPI.point({ row: currentStep.row, col: currentStep.col, color: stoneToLedColor(currentStep.color) })
        .then((r) => setLedOk(r.connected)).catch(() => setLedOk(false));
    }
  };

  const handleConfirm = () => {
    if (!currentStep) return;
    // 提子要人先把死子拿下来,拿完才存帧 —— 否则那一帧上是一个不该存在的局面。
    if (currentStep.removed.length > 0 && phase === 'guiding') { setPhase('await_removal'); return; }
    void doCapture(k);
  };

  const handleUndo = () => {
    setUndoOpen(false);
    setCaptureError(null);
    setK((prev) => {
      const next = Math.max(0, prev - 1);
      saveProgress(source, { k: next, frames: 0, updatedAt: Date.now(), total: steps.length });
      return next;
    });
    setPhase('guiding');
  };

  // ── 盘面:笨播放器,一条气都不算 ──
  const board = useMemo(() => replayBaipuSteps(steps, k, boardSize), [steps, k, boardSize]);
  const ghost = useMemo(() => {
    if (!['guiding', 'await_removal'].includes(phase) || !currentStep) return [];
    if (currentStep.row == null || currentStep.col == null) return [];
    return [canonToGtp(currentStep.row, currentStep.col, boardSize)];
  }, [phase, currentStep, boardSize]);
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
          backLabel={t('baipu:back_kifu', '棋谱')}
          onBack={() => navigate('/kiosk/baipu')}
          title={t('baipu:title', '摆谱')}
        />
        <div className="empty" data-testid="baipu-load-error">
          <h4>{sgf ? t('baipu:load_failed', '没读出这份谱') : t('baipu:no_sgf', '这台盒子上没有这份谱')}</h4>
          {loadError && <p>{loadError}</p>}
        </div>
      </div>
    );
  }
  if (phase === 'loading') {
    return (
      <div className="kiosk-layout-b" data-testid="baipu-session-page">
        <KioskPagebar
          testId="baipu-pagebar"
          backLabel={t('baipu:back_kifu', '棋谱')}
          onBack={() => navigate('/kiosk/baipu')}
          title={title}
        />
        <div className="empty" data-testid="baipu-loading"><h4>{t('baipu:loading', '正在读这份谱')}</h4></div>
      </div>
    );
  }

  // 优先级写死,互斥:采集失败 > 待移除 > 待摆 > 已完成。(拍照遮罩盖在最上面,不属于这一档。)
  const mood: Mood = captureError !== null ? 'failed'
    : phase === 'await_removal' ? 'removal'
      : phase === 'done' ? 'done' : 'guiding';

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
          backLabel={t('baipu:back_kifu', '棋谱')}
          onBack={() => setExitOpen(true)}
          title={title}
          sub={interpolate(
            t('baipu:pagebar_sub', '第 {i} / {n} 手 · 已采集 {f} 帧'),
            { i: Math.min(k + (phase === 'done' ? 0 : 1), steps.length), n: steps.length, f: frameCount },
          )}
          action={{
            icon: 'lightbulb',
            label: t('baipu:relight', '重新点灯'),
            onClick: relight,
            // 这颗键兼当 LED 的状态点 —— 它本来就是这个故障的补救动作。
            state: ledOk === false ? 'bad' : undefined,
          }}
        />

        {/* ── 此刻你该做什么 ── 四态互斥,同一块 pcard 换内容 */}
        <div className={`pcard ${mood === 'guiding' ? 'turn' : mood}`} data-testid="baipu-pcard" data-mood={mood}>
          {mood === 'guiding' && nextColor && <span className={nextColor === 'B' ? 'disc b' : 'disc w'} />}
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
                <p>{interpolate(t('baipu:done_hint', '一共 {n} 手 · 采到 {f} 帧'), { n: steps.length, f: frameCount })}</p>
              </>
            ) : (
              <>
                <h4>{coord
                  ? interpolate(t('baipu:place_at', '当前待摆 · {c}'), { c: coord })
                  : t('baipu:place_none', '这一步不用摆子')}</h4>
                <p>{ledOk === false
                  ? interpolate(t('baipu:led_down', '灯没亮 —— 按右上角重新点灯，或照坐标 {c} 自己找'), { c: coord ?? '' })
                  : interpolate(
                    t('baipu:led_on', '灯已点亮 —— 把{color}子放在亮着的那个交叉点'),
                    { color: nextColor === 'W' ? t('baipu:white_s', '白') : t('baipu:black_s', '黑') },
                  )}</p>
              </>
            )}
          </div>
          <div className="clock">
            <b>{mood === 'removal' ? (currentStep?.removed.length ?? 0) : Math.min(k + (phase === 'done' ? 0 : 1), steps.length)}</b>
            <span>{mood === 'removal' ? t('baipu:stones_unit', '子') : t('baipu:which_move', '第几手')}</span>
          </div>
        </div>

        {/* ── 摄像头 ── 这本账既是采集记录,也是那条 LED 图例的落点 */}
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
          actions={[
            mood === 'removal'
              ? {
                key: 'removed',
                icon: 'camera',
                label: interpolate(t('baipu:removed_done', '已移除 {n} 子'), { n: currentStep?.removed.length ?? 0 }),
                disabled: capturePending,
                onClick: () => { void doCapture(k); },
              }
              : {
                key: 'confirm',
                icon: 'camera',
                label: t('baipu:confirm', '确认落子'),
                disabled: capturePending || phase === 'done' || !isPlaceable,
                reason: phase === 'done' ? t('baipu:confirm_done_reason', '这份谱已经摆完了') : undefined,
                onClick: handleConfirm,
              },
            {
              key: 'undo',
              icon: 'arrow-counter-clockwise',
              label: t('baipu:undo', '撤回上一手'),
              disabled: k === 0 || capturePending,
              reason: k === 0 ? t('baipu:undo_reason', '还没摆下第一颗') : undefined,
              onClick: () => setUndoOpen(true),
            },
            {
              key: 'finish',
              icon: 'flag',
              label: t('baipu:finish', '完成'),
              // 常驻是为了格子不重排(「确认落子」一局按约 250 次,位置是肌肉记忆);
              // 摆完之前一律灰 —— 提前收工是**返回**该做的事,不是它。
              disabled: phase !== 'done',
              reason: phase !== 'done'
                ? interpolate(t('baipu:finish_reason', '还剩 {n} 手没摆'), { n: steps.length - k })
                : undefined,
              onClick: () => { clearProgress(source); navigate('/kiosk/baipu'); },
            },
          ]}
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
            <p>{interpolate(t('baipu:resume_body', '上次摆到第 {n} 手。重新开始会覆盖已经采过的帧。'), { n: resumePrompt })}</p>
            <div className="cdlg__acts">
              <button
                type="button" className="ghost" data-testid="baipu-resume-restart"
                onClick={() => {
                  clearProgress(source);
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
                onClick={() => navigate('/kiosk/baipu')}
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
