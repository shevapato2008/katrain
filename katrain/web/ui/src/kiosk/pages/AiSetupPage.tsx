import { useCallback, useMemo, useState } from 'react';
import { Alert, Box, Button } from '@mui/material';
import { useParams, useNavigate } from 'react-router-dom';
import { useVision } from '../context/VisionContext';
import { KioskPagebar } from '../shell/KioskPagebar';
import { KioskScrollZone } from '../shell/KioskScrollZone';
import { KioskSecLabel } from '../shell/KioskSecLabel';
import { interpolate } from '../utils/interpolate';
import {
  FREE_KOMI_MAX, FREE_KOMI_VALUES, HANDICAP_LABEL, RULES, RULE_LABEL,
  TIME_PRESETS, TIME_TRACK_ORDER, handicapKeysFor, resolveGameTerms,
  type HandicapKey,
} from '../utils/setupOptions';
import { SetupPopoverHost } from '../components/setup/SetupPopoverHost';
import { SetupSelect } from '../components/setup/SetupSelect';
import { SetupDerived, SetupFixed } from '../components/setup/SetupDerived';
import { SetupStepper } from '../components/setup/SetupStepper';
import { komiReadout } from '../components/setup/komiReadout';
import { playInputState, writePlayOnBoard } from '../utils/playInput';
import { API } from '../../api';
import { internalToRank, sliderToInternal } from '../../utils/rankUtils';
import { useTranslation } from '../../hooks/useTranslation';
import { useAuth } from '../../context/AuthContext';
import { writeActiveSession } from '../utils/activeSession';
import KioskAiLadderOpponent from '../components/aiLadder/KioskAiLadderOpponent';
import {
  AiLadderApiError,
  endAiLadderGame,
  retryAiLadderSettlement,
  startAiLadderGame,
} from '../../features/aiLadder/api';
import { useAiLadderStatus } from '../../features/aiLadder/useAiLadderStatus';
import { aiLadderStartUnavailableMessage } from '../../features/aiLadder/startErrors';
import { aiLadderBlockingGame, canStartAiLadderGame } from '../../features/aiLadder/startGate';
import { saveAiLadderBefore } from '../../features/aiLadder/settlement';
import KioskAiLadderBlockingPanel from '../components/aiLadder/KioskAiLadderBlockingPanel';
import KioskSetupBoard from '../components/board/KioskSetupBoard';

/* **AI 策略那一组撤掉了(2026-09-21),对手钉死拟人。**

   不是为了省一行:改版前 `showRankSlider = !isRanked && aiStrategy === 'ai:human'` ——
   选了 KataGo / 实地 / 厚势 / 策略就**连棋力档都不给选**,而后端仍照写
   `ai/{strategy}/kyu_rank`(`server.py:1253`)。一根只对五分之一选项成立的档位轴,
   不该用一个平行的五选一去否定它。五条策略说明随之下屏。 */
const AI_STRATEGY = 'ai:human';

/** 我执三档。`guess`(猜先)在发出去之前解成 black/white —— 见 `drawSeat`。 */
type SetupColor = 'black' | 'white' | 'nigiri';

// Canonical kiosk setup skeleton: left preview console + right token-themed form. pvp/cross-platform setup pages restyle against this — tokens only, no flow change.
const AiSetupPage = () => {
  const { mode } = useParams<{ mode: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { token, user, isAuthenticated, isLoading: authLoading } = useAuth();
  // 「落子」那一格读的是它 —— 设备能力,不是设置项。
  const { isVisionEnabled } = useVision();
  const isRanked = mode === 'ranked';
  const {
    status: aiLadderStatus,
    retry: retryAiLadderStatus,
    applyBlockingSync,
  /* 第二个参数是「要不要拉」。游客拉这个必 401,而 `KioskAuthGuard` 2026-08-28 从这条
     路由上摘掉之后,游客**真的能走到这一屏**(`:mode` 也匹配 ranked)⇒ 不加这一条就是
     每次进屏一发注定失败的请求,外加一句「登录已失效」——对从没登录过的人那句是假的。 */
  } = useAiLadderStatus(token ?? undefined, isRanked && isAuthenticated);
  // 挡着新局的那一局。有它的时候整个右栏换成挡局面板 —— 底下那些设置一个都用不上,
  // 摆着只会让用户以为改一改就能开局。
  const blockingGame = isRanked ? aiLadderBlockingGame(aiLadderStatus) : null;

  /* 升降级的登录门**补在页面里,不在路由上** —— `play/ai/setup/:mode` 一条路由两种对弈,
     Fan 只让摘自由对弈那条。段位记在账号上,没有账号就无处可记 ⇒ 这一屏对游客不是
     「暂时不可用」而是**永远需要先有账号**,所以说的是原因不是故障。
     `authLoading` 必须等:`/me` 没回来之前 `isAuthenticated` 是 false,
     不等就会让已登录用户每次进来先闪一下「需要登录」。 */
  const rankedNeedsLogin = isRanked && !authLoading && !isAuthenticated;

  // Board & rules
  const [boardSize, setBoardSize] = useState(19);
  const [rules, setRules] = useState<string>('chinese');
  const [color, setColor] = useState<SetupColor>('black');

  const [rank, setRank] = useState(14); // 0=20k, 19=1d, 28=9d; default 14 = ~6k

  /* 让子与贴目是**一个**枚举,不是两条轨 —— 见 `utils/setupOptions.ts`。
     `freeKomi` 只在「自定贴目」那一档用得上。 */
  const [handicapKey, setHandicapKey] = useState<HandicapKey>('even');
  const [freeKomi, setFreeKomi] = useState(FREE_KOMI_MAX);

  // Time control
  const [timeEnabled, setTimeEnabled] = useState(isRanked);
  const [mainTime, setMainTime] = useState(0);
  const [byoyomiTime, setByoyomiTime] = useState(30);
  const [byoyomiPeriods, setByoyomiPeriods] = useState(3);

  /** 下拉弹层的宿主 —— 用 state 而不是 ref,因为挂上去那一刻要重渲染才轮得到弹层。 */
  const [railEl, setRailEl] = useState<HTMLDivElement | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  /* 未登录时该说的那句话。与 `error` 分开:它不是故障,而且**要给可按的东西**。 */
  const [authPrompt, setAuthPrompt] = useState('');
  const [lifecyclePending, setLifecyclePending] = useState(false);
  const [lifecycleError, setLifecycleError] = useState('');
  const [syncRetryPending, setSyncRetryPending] = useState(false);

  const timePresets = TIME_PRESETS(t);
  const currentTimeKey = !isRanked && !timeEnabled ? 'untimed' : mainTime === 0 ? 'byoOnly' : String(mainTime);
  const applyTimePreset = (key: string) => {
    const preset = timePresets.find((p) => p.key === key);
    if (!preset) return;
    if (!isRanked) setTimeEnabled(preset.enabled);
    setMainTime(preset.main);
    setByoyomiTime(preset.byo);
    setByoyomiPeriods(preset.periods);
  };

  const rankOptions = Array.from({ length: 29 }, (_, v) => ({ value: v, label: internalToRank(sliderToInternal(v)) }));

  const ruleLabels = RULE_LABEL(t);
  const handicapLabels = HANDICAP_LABEL(t);

  /* **送给后端的 `handicap` / `komi` 只从这里出。** 升降级那一路不走它 ——
     那一路的盘面条件由服务端写死,客户端发了会被 `extra="forbid"` 拒掉。 */
  const terms = resolveGameTerms(rules, handicapKey, freeKomi);
  const ruleDef = RULES.find((r) => r.key === rules) ?? RULES[0];
  const komiText = isRanked
    ? komiReadout(t, 'chinese', 'even', FREE_KOMI_MAX)
    : komiReadout(t, rules, handicapKey, freeKomi);
  const pickKomi = !isRanked && handicapKey === 'free';
  const freeKomiOptions = useMemo(
    () => FREE_KOMI_VALUES.map((v) => ({
      key: String(v),
      label: interpolate(t('setup:komi_points', '{n} 目'), { n: v }),
    })),
    [t],
  );



  /* 「猜先」怎么落到 black/white。**后端现在任何非 "black" 的值都落到白**
     (`server.py:1230` 的 `human_bw = "B" if color === "black" else "W"`),
     所以这一层必须在发出去之前把 `guess` 解掉,不能指望后端认得它。 */
  const drawSeat = useCallback(
    (): 'black' | 'white' => (Math.random() < 0.5 ? 'black' : 'white'),
    [],
  );

  const handleStart = async () => {
    setError('');
    setAuthPrompt('');
    setLoading(true);
    const seatColor = color === 'nigiri' ? drawSeat() : color;
    try {
      if (isRanked) {
        const { session_id, game_id, status } = await startAiLadderGame({
          color: seatColor,
          time_enabled: true,
          main_time: mainTime,
          byo_length: byoyomiTime,
          byo_periods: byoyomiPeriods,
        }, token ?? undefined);
        saveAiLadderBefore(session_id, status, String(user?.id ?? user?.username ?? 'anonymous'), game_id);
        writeActiveSession({
          kind: 'game', label: t('Ranked Game', '升降级对弈'),
          route: `/kiosk/play/ai/game/${session_id}`, ts: Date.now(),
        });
        navigate(`/kiosk/play/ai/game/${session_id}`);
        return;
      }
      const { session_id } = await API.createSession(token ?? undefined);
      await API.gameSetup(session_id, isRanked ? 'ranked' : 'free', {
        board_size: boardSize,
        rules: ruleDef.wire,
        color: seatColor,
        ai_strategy: AI_STRATEGY,
        rank,
        handicap: terms.handicap,
        komi: terms.komi,
        time_enabled: isRanked || timeEnabled,
        main_time: mainTime,
        byo_length: byoyomiTime,
        byo_periods: byoyomiPeriods,
      });
      writeActiveSession({
        kind: 'game',
        label: isRanked ? t('Ranked Game', '升降级对弈') : t('Free Game', '自由对弈'),
        route: `/kiosk/play/ai/game/${session_id}`,
        ts: Date.now(),
      });
      navigate(`/kiosk/play/ai/game/${session_id}`);
    } catch (e: any) {
      /* 把服务端那句英文原样贴上去(`Request failed 401: {"detail":"Not authenticated"}`)
         既没说是什么事,也没给可按的东西。但**只有 401 才是「去登录」**:
         403 在这条链上说的是「知道你是谁,可这件事现在不能做」—— 最常见的是
         `guard_user_has_no_pending_ranked_game` 的「你有一局升降级还没结算」。
         把它也翻成「需要登录」,就是对一个明明登录着的人说假话,而且他照着做也解决不了。
         **未登录时**的 403(`guard_session_reader` 的「不是这局的参与者」)仍归登录引导。 */
      /* 读 `.status` 而不是 `e instanceof ApiError`:**这是 catch 块,它自己不许再抛**。
         `instanceof` 依赖那个类在此刻真的是个构造函数 —— 模块被替换/摇树/mock 掉时它是
         `undefined`,`e instanceof undefined` 当场 TypeError,于是下面一行 `setError` 根本
         不会执行,用户点完开局屏上一个字都没有(实测:本文件的单测就是这么挂的)。
         `ApiError` 和 `AiLadderApiError` 都带数字 `status`,这里认那个形状就够。 */
      const status = typeof e?.status === 'number' ? e.status : null;
      if (status === 401 || (status === 403 && !isAuthenticated)) {
        setError('');
        setAuthPrompt(isRanked
          ? t('ladder:login_required', '升降级对弈会记录段位，需要登录后才能开始。')
          : t('play:login_required_free', '开始对局需要登录，请先登录后再试。'));
      } else if (status === 503 && isRanked) {
        setAuthPrompt('');
        setError(aiLadderStartUnavailableMessage(typeof e?.message === 'string' ? e.message : ''));
      } else {
        setAuthPrompt('');
        setError(e.message || t('Failed to create game', '创建对局失败'));
      }
    } finally {
      setLoading(false);
    }
  };

  const handleContinue = (sessionId: string) => {
    writeActiveSession({
      kind: 'game', label: t('Ranked Game', '升降级对弈'),
      route: `/kiosk/play/ai/game/${sessionId}`, ts: Date.now(),
    });
    navigate(`/kiosk/play/ai/game/${sessionId}`);
  };

  const handleEndGame = async (gameId: string) => {
    setLifecycleError('');
    setLifecyclePending(true);
    try {
      await endAiLadderGame(gameId, token ?? undefined);
      // `settled`(认输,记一负)/`released`(让掉,什么都不记)/`pending_settlement`
      // 三种成功形状在这块屏上是同一个后续:占位没了,回到开局卡。区别已经在按下之前
      // 由代价行和弹窗说清了,这里再复述一遍只会多一个会漂的副本。
      await retryAiLadderStatus();
    } catch (endError) {
      if (endError instanceof AiLadderApiError && endError.status === 404) {
        // 那一局已经不在了(多半是原盒子刚把结果送到,或者重复按了一次)。这是成功,
        // 不是失败 —— 说成失败会让用户在一个已经放开的账号上继续按。
        setLifecycleError('');
        await retryAiLadderStatus();
      } else if (endError instanceof AiLadderApiError && (endError.status === 401 || endError.status === 403)) {
        setLifecycleError(t('Session expired, please sign in again', '登录已失效，请重新登录后再试'));
      } else {
        setLifecycleError(t('Could not end that game, please retry', '结束对局失败，请重试'));
      }
    } finally {
      setLifecyclePending(false);
    }
  };

  /**
   * 「立即重试」按下去之后的每一条路。
   *
   * 关键是**不要为了刷新去打一次云端**:`/status` 在盒子上是转发到云端的,断网时 503,
   * 而 `retryAiLadderStatus` 一失败就把整块面板换成「加载失败」—— 那正是这个按钮存在的
   * 场景。重试请求本身打的是盒子自己(127.0.0.1),断网照样成功,响应里带着这一次尝试
   * 之后的真实状态,所以失败路径只就地贴这份状态,不碰云端。
   */
  const handleRetrySettlement = async (gameId: string) => {
    if (syncRetryPending) return;
    setLifecycleError('');
    setSyncRetryPending(true);
    try {
      const { sync } = await retryAiLadderSettlement(gameId, token ?? undefined);
      if (sync && sync.state !== 'synced') {
        applyBlockingSync(gameId, sync);
        return;
      }
      await retryAiLadderStatus();
    } catch (retryError) {
      if (retryError instanceof AiLadderApiError && (retryError.status === 401 || retryError.status === 403)) {
        setLifecycleError(t('Session expired, please sign in again', '登录已失效，请重新登录后再试'));
      } else if (retryError instanceof AiLadderApiError && retryError.status === 404) {
        // 队列里已经没有这一局了 —— 多半是后台那一轮刚把它送成。只有这一条 catch 该去
        // 复查:它意味着屏上这一格已经不成立了。
        await retryAiLadderStatus();
      } else {
        setLifecycleError(t('Retry failed, please try again later', '重试失败，请稍后再试'));
      }
    } finally {
      setSyncRetryPending(false);
    }
  };

  /* 用时那几档在下拉里的顺序由 `utils/setupOptions` 的 `TIME_TRACK_ORDER` 定(理由写在那儿)。
     计分局把「不限时」整档摘掉 —— **不是灰掉**:那一档在这一局里根本不存在。 */
  const timeTrack = [...TIME_TRACK_ORDER]
    .filter((key) => !isRanked || key !== 'untimed')
    .map((key) => timePresets.find((p) => p.key === key)!)
    .filter(Boolean);

  const rankName = (v: number) => internalToRank(sliderToInternal(v));

  // ── 升降级那两格「赌多少」 ──────────────────────────────────────
  // 稿子写的是「胜 · 升到 4 级」「负 · 退到 6 级」。**那是净胜分正好 ±2 时的特例。**
  // 真规则在 `core/ai_ladder_ranked.py:1503-1506`:每局 ±1,**到 ±3 才升降一档**,
  // 然后清零。所以只有 net_score === 2 时「这一局赢了就升」才是真的。
  //
  // 而且**升到「几级」这个名字这块屏拿不到** —— `AiLadderStatus` 只带当前档和对手档,
  // 不带整份阶梯目录,下一档叫什么得再要一次目录。所以到点那一格写「升一档」:
  // 少一个名字,但没有一个字是编的。
  const readyStatus = aiLadderStatus.view_state === 'ready' ? aiLadderStatus : null;
  const netScore = readyStatus?.net_score ?? 0;
  const PROMOTE_AT = 3;
  // 净胜分要带符号,而**负数自己就带着一个** —— 无脑前缀 `+` 会写出 `+-1`。
  // (2026-08-23 那条 `net_score = −2` 的闸当场逮到的就是这个。)
  const signed = (n: number) => (n > 0 ? `+${n}` : String(n));
  const stakeWin = netScore + 1 >= PROMOTE_AT
    ? t('ladder:stake_win_promote', '胜 · 升一档')
    : interpolate(t('ladder:stake_win_score', '胜 · 净胜分 {n}'), { n: signed(netScore + 1) });
  const stakeLoss = netScore - 1 <= -PROMOTE_AT
    ? t('ladder:stake_loss_demote', '负 · 退一档')
    : interpolate(t('ladder:stake_loss_score', '负 · 净胜分 {n}'), { n: signed(netScore - 1) });

  // ── 「落子」是**真开关**(2026-08-23 改回来的)────────────────────────
  // 第一版画成了一格读数,理由写的是「全仓没有任何地方能让用户切」——**那句话是错的**:
  // 做题屏(`TsumegoProblemPage`)早就有这颗开关。设备能不能(`isVisionEnabled`,后端给)
  // 和这一局想不想是**两段**,第一版把后一段抹掉了。偏好存在 `utils/playInput.ts`,
  // `KioskApp` 的 `PlayInputGuard` 和 `GamePage` 都认它。
  //
  // 选中的是**这一局实际会落在哪**(`onBoard`),不是偏好本身:左边那块盘画的是
  // 「按下按钮后真会出现的局面」,同一屏上的控件不能说另一件事。
  const [inputTick, setInputTick] = useState(0);
  const playInput = useMemo(
    () => playInputState(isVisionEnabled, isRanked ? 19 : boardSize),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- inputTick 就是「偏好刚被改过」这个信号
    [isVisionEnabled, isRanked, boardSize, inputTick],
  );
  /* 「这局棋」那一组底下那行:只在**有约束正在生效**时才出现,没有就整行不画
     (`.su-hint:empty{display:none}`)。 */
  const gameHint = playInput.reason === 'notNineteen' && playInput.wanted
    ? t('setup:size_not19_hint', '盘上那块是 19 路 —— 这一局只能下在屏幕上,调回 19 路就还用实体盘')
    : '';

  /* 「怎么坐」那一组底下那行:说的是**这台机器现在的状态**,不是通用说明。 */
  const seatHint = playInput.available
    ? t('setup:seat_hint_ready', '实体盘和屏幕随时可切,开局后就定了')
    : playInput.reason === 'notNineteen'
      ? t('setup:seat_hint_not19', '这一局不是 19 路,只能下在屏幕上')
      : t('setup:seat_hint_uncalibrated', '这台机器没标定过摄像头,只能下在屏幕上');

  const setPlayOnBoard = (next: boolean) => {
    writePlayOnBoard(next);
    setInputTick((n) => n + 1);
  };

  return (
    // 规范 §11 **布局 A**(`kiosk-shell-spec.md:510-512`):「开局设置是对局的前一步,所以它走
    // 布局 A,和对局屏同一个骨架 —— 左盘 516 + 16 + 右栏 460」。
    //
    // 外框:`:399` L2/L3 可用高度 600 − 56(顶栏)− 28(上下各 14 内边距)= **516**,
    // 左右各 16(`:64` `--content-x`)⇒ 内容 992,减去盘 516 与栏距 16,右栏正好 460。
    // 这三个数一个都不在这里写死 —— `.kiosk-layout-a` / `.kiosk-board` 用的是
    // `tokens.css` 的 `--board-size` / `--content-x`,改规范时不用回来改这里。
    <div className="kiosk-layout-a" data-testid="ai-setup-page">
      {/* 左栏 = 按下「开始对局」后真会出现的那个局面(`:512`),不是摄像头镜像 ——
          镜像栏是 L1 的东西(`SmartBoardConsole`,296 宽),它留在 `/kiosk/play`。 */}
      {/* 左盘是右栏的读数:路数换它就换格子,让子换它就换星位上的子。
          「猜先」这一态盘上先按执黑画 —— 真正落座要到按下开始那一刻。 */}
      <KioskSetupBoard
        color={color === 'white' ? 'white' : 'black'}
        size={isRanked ? 19 : boardSize}
        handicap={isRanked ? 0 : terms.handicap}
      />

      {/* `data-su` 打开这三屏的紧排,并给下拉弹层当定位原点(`.kiosk-rail[data-su]{position:relative}`)。
          弹层挂在这一层而不是里面那个滚动盒:滚动盒 `overflow-y:auto` 会把它裁掉,
          而挂在这儿顺带保证它盖不到左边那块盘。 */}
      <div className="kiosk-rail" data-su={isRanked ? 'ranked' : 'free'} ref={setRailEl}>
        <SetupPopoverHost.Provider value={railEl}>
        <KioskPagebar
          testId="kiosk-setup-pagebar"
          backLabel={t('Back to play', '返回对弈')}
          onBack={() => navigate('/kiosk/play')}
          title={isRanked ? t('Ranked Game', '升降级对弈') : t('Free Game', '自由对弈')}
          sub={isRanked
            ? t('ladder:setup_sub', '开局设置 · 计入段位 · 全程封分析')
            : t('play:free_setup_sub', '开局设置 · 人机 · 不计入段位')}
        />

        {rankedNeedsLogin ? (
          <Box data-testid="ranked-login-required" sx={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', gap: 1.5, justifyContent: 'center' }}>
            <Alert severity="info">
              {t('ladder:login_required', '升降级对弈会记录段位，需要登录后才能开始。')}
            </Alert>
            <button type="button" className="kiosk-primary-action" onClick={() => navigate('/kiosk/login')}>
              {t('auth:go_login', '去登录')}
            </button>
            {/* 给第二条出路:他现在就能下的那一种。只说「去登录」等于把人堵在这儿。 */}
            <Button size="small" color="inherit" onClick={() => navigate('/kiosk/play/ai/setup/free')}>
              {t('play:go_free_play', '先去自由对弈')}
            </Button>
          </Box>
        ) : blockingGame ? (
          // 有一局挡着的时候,整个右栏换成挡局面板:执子、用时、开始按钮此刻一个都用不上,
          // 摆着只会让用户以为改一改就能开局,而真正能推进事情的两三个按钮反倒被挤到看不见。
          // `:512`「按下按钮时骨架不动,只有右栏换内容」—— 这是同一个位置的两种内容。
          <Box data-testid="ranked-settings-panel" sx={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
            <KioskAiLadderBlockingPanel
              game={blockingGame}
              pending={lifecyclePending}
              error={lifecycleError}
              syncRetryPending={syncRetryPending}
              onContinue={handleContinue}
              onEndGame={handleEndGame}
              onRetrySettlement={handleRetrySettlement}
            />
          </Box>
        ) : (
          <>
            <KioskScrollZone className="setgrp-scroll" resetKey={isRanked ? 'ranked' : 'free'}>
              {/* ── 这局棋 ────────────────────────────────────────────────────
                  **三个输入 + 一条推导。** 贴目不在这三格里,因为它不是输入 ——
                  它是 (规则 × 让子) 的结果,算在 `utils/setupOptions.ts` 的
                  `resolveGameTerms()`,那是整条链上唯一算它的地方。

                  升降级这三格是**读数不是控件**:盘面条件在服务端写死,而且客户端连发
                  都不许发(`api/v1/endpoints/ai_ladder.py:105-108` 的 `LADDER_*`
                  + `AiLadderStartRequest` 的 `extra="forbid"`)。虚线 + 无 chevron
                  说的是「这条路本来就没得选」,和灰掉(「你现在不能改」)不是一回事。 */}
              <section className="setgrp" data-testid="setup-game-group">
                <KioskSecLabel
                  zh={isRanked ? t('ladder:fixed_by_box', '盒子定好的') : t('setup:game_terms', '这局棋')}
                  en={isRanked ? 'Fixed' : 'Game'}
                  value={isRanked
                    ? t('ladder:terms_fixed', '都不可改')
                    : t('setup:locked_after_start', '开局后不可改')}
                />
                <div className="su-row">
                  {isRanked ? (
                    <>
                      <SetupFixed label={t('setup:size', '路数')} value={t('setup:size_19', '19 路')} testId="setup-size" />
                      <SetupFixed label={t('Rules', '规则')} value={ruleLabels.chinese} testId="setup-rules" />
                      <SetupFixed label={t('Handicap', '让子')} value={handicapLabels.even} testId="setup-handicap" />
                    </>
                  ) : (
                    <>
                      <SetupSelect
                        testId="setup-size"
                        label={t('setup:size', '路数')}
                        value={String(boardSize)}
                        /* 三档**一律可选**。路数和落子的耦合走另一个方向:
                           选了 9/13 路,「实体盘」自己塌掉(`playInputState` 的 `notNineteen`),
                           偏好不动、调回 19 路它自己回来。反过来拿实体盘锁死路数的话,
                           用户会**点不到 9 路** —— 那是把一条路堵死,不是表达约束。 */
                        options={[19, 13, 9].map((n) => ({
                          key: String(n),
                          label: interpolate(t('setup:size_n', '{n} 路'), { n }),
                        }))}
                        onChange={(k) => setBoardSize(Number(k))}
                      />
                      <SetupSelect
                        testId="setup-rules"
                        label={t('Rules', '规则')}
                        value={rules}
                        options={RULES.map((r) => ({ key: r.key, label: ruleLabels[r.key] }))}
                        onChange={(k) => setRules(k)}
                      />
                      <SetupSelect
                        testId="setup-handicap"
                        label={t('Handicap', '让子')}
                        value={handicapKey}
                        columns={2}
                        options={handicapKeysFor(boardSize).map((k) => ({ key: k, label: handicapLabels[k] }))}
                        onChange={(k) => setHandicapKey(k as HandicapKey)}
                      />
                    </>
                  )}
                </div>

                {/* 贴目条。**平时它不是控件** —— 无 chevron、点不动:它是上面三格的结果。
                    唯一的例外是「自定贴目」那一档,那时贴目真的是个可选项,
                    条子才长出边框和 chevron 变回控件。 */}
                <SetupDerived
                  testId="setup-komi"
                  label={t('Komi', '贴目')}
                  note={isRanked
                    ? t('ladder:komi_note', '档位按这个盘量的')
                    : handicapKey === 'free'
                      ? t('setup:komi_pick', '点此改贴目')
                      : t('setup:komi_derived', '随规则和让子定')}
                  options={pickKomi ? freeKomiOptions : undefined}
                  value={String(freeKomi)}
                  onChange={pickKomi ? (k) => setFreeKomi(Number(k)) : undefined}
                >
                  {komiText}
                </SetupDerived>

                {/* 升降级的「对手」并在这一段里,不另起一段:**盘面和对手是同一件事的两半** ——
                    都是盒子定的,而且档位的强度就是按上面那个盘量出来的。
                    (拆成两段会让右栏溢出 41px,真浏览器几何闸量到的。) */}
                {/* 这里**不再重复「全程封分析」**:页控条副标已经写着
                    「开局设置 · 计入段位 · 全程封分析」,同一件事说两遍。
                    撤掉它是为了给右栏留余量 —— 留之前实测只剩 2.2px,
                    一条文案换行就破(真浏览器量的)。撤掉后 24.5px。 */}
                {isRanked && (
                  <KioskAiLadderOpponent status={aiLadderStatus} onRetry={retryAiLadderStatus} />
                )}
                {!isRanked && <p className="su-hint">{gameHint}</p>}
              </section>

              {/* ── 对手 ──────────────────────────────────────────────────────
                  **AI 策略那一组撤掉了,钉死拟人。** 不是为了省一行:
                  改版前 `showRankSlider = aiStrategy === 'ai:human'` —— 选了
                  KataGo/实地/厚势/策略就**连棋力档都不给选**,而后端还照写
                  `ai/{strategy}/kyu_rank`(`server.py:1253`)。一根只对五分之一选项
                  成立的档位轴,不该用一个平行的五选一去否定它。 */}
              {isRanked ? (
                  <section className="setgrp" data-testid="setup-stake-group">
                    <KioskSecLabel
                      zh={t('ladder:stake', '这一局赌多少')}
                      en="Stake"
                      value={t('ladder:frozen_at_start', '开局那一刻冻结')}
                    />
                    <div className="su-stake" data-testid="setup-stakes">
                      <span>{stakeWin}</span>
                      <span>{stakeLoss}</span>
                    </div>
                    <p className="su-hint">
                      {interpolate(
                        t('ladder:stake_rule', '净胜分到 +3 升一档、到 −3 退一档 · 当前 {n}'),
                        { n: signed(netScore) },
                      )}
                    </p>
                  </section>
              ) : (
                <section className="setgrp" data-testid="setup-strength-group">
                  <KioskSecLabel
                    zh={t('AI Strength', '棋力')}
                    en="Strength"
                    value={t('setup:strength_humanlike', '拟人 · 开局后不可改')}
                  />
                  <SetupStepper
                    testId="setup-strength"
                    count={rankOptions.length}
                    index={rank}
                    onChange={setRank}
                    decLabel={t('setup:strength_down', '降低一档')}
                    incLabel={t('setup:strength_up', '提高一档')}
                    /* 「第 N 档 · X 级」—— 等级那半截改版前**从来没接上过**:
                       那句 msgid 的缺省值结尾就是「第 {n} 档 · 」,屏上是个吊着的点号。 */
                    value={(
                      <>
                        {interpolate(t('setup:strength_rung', '第 {n} 档'), { n: rank + 1 })}
                        {' · '}
                        <i>{rankName(rank)}</i>
                      </>
                    )}
                    meta={interpolate(t('setup:strength_meta', '共 {n} 档 · {lo} – {hi}'), {
                      n: rankOptions.length, lo: rankName(0), hi: rankName(rankOptions.length - 1),
                    })}
                  />
                  {/* 一行。右栏余量只有 5.5px(内容 364.5 / 可视 370,真浏览器量的),
                      这句要是折成两行就溢出 —— 改文案时请连着
                      `tests/kiosk-setup-r2-geometry.spec.ts` 一起看。 */}
                  <p className="su-hint">
                    {t('setup:strength_hint2', '拟人会犯这一档该犯的错;档位说的是对手,不是你的段位')}
                  </p>
                </section>
              )}

              {/* ── 怎么坐 ──────────────────────────────────────────────────── */}
              <section className="setgrp" data-testid="setup-seat-group">
                <KioskSecLabel zh={t('setup:seat', '怎么坐')} en="Seat" />
                <div className="su-row">
                  <SetupSelect
                    testId="setup-input"
                    label={t('setup:input_where', '落子')}
                    value={playInput.onBoard ? 'board' : 'screen'}
                    options={[
                      // 「屏幕」**永远选得了** —— 条件掉了不能把人锁在一块用不了的盘上。
                      { key: 'screen', label: t('setup:on_screen', '屏幕') },
                      {
                        key: 'board',
                        label: t('setup:on_board', '实体盘'),
                        disabled: !playInput.available,
                        /* 两种灰因要分开说:没标定 vs 这一局不是 19 路。
                           合成一句「用不了」,用户不知道该去标定还是该换路数。 */
                        reason: playInput.reason === 'notNineteen'
                          ? t('setup:board_only_19', '盘上那块是 19 路')
                          : t('setup:board_not_ready', '没标定过摄像头'),
                      },
                    ]}
                    onChange={(k) => setPlayOnBoard(k === 'board')}
                  />
                  <SetupSelect
                    testId="setup-color"
                    label={t('My Color', '我执')}
                    value={color}
                    options={[
                      { key: 'black', label: <><span className="disc b" />{t('setup:side_black', '执黑')}</> },
                      { key: 'white', label: <><span className="disc w" />{t('setup:side_white', '执白')}</> },
                      {
                        key: 'nigiri',
                        label: <><span className="disc rnd" />{t('setup:side_nigiri', '猜先')}</>,
                        // 让子局黑方先摆子 —— 让哪一方是这一局的前提,不能再抽签。
                        disabled: terms.handicap > 0,
                        reason: t('setup:nigiri_blocked', '让子局黑方先摆子'),
                      },
                    ]}
                    onChange={(k) => setColor(k as SetupColor)}
                  />
                  <SetupSelect
                    testId="setup-clock"
                    label={t('Time Control', '用时')}
                    value={currentTimeKey}
                    columns={2}
                    options={timeTrack.map((p) => ({ key: p.key, label: p.label }))}
                    onChange={applyTimePreset}
                  />
                </div>
                <p className="su-hint" data-testid="setup-seat-hint">{seatHint}</p>
              </section>
            </KioskScrollZone>

            {/* 出错时那条横幅在**滚动区外面** —— 它说的是「刚才那次开局失败了」,
                跟着设置一起滚走就等于没说。 */}
            {error && <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert>}

            {/* 需要登录那一条。**与错误横幅互斥**(两个 setter 各自清掉对方),所以这一格
                任何时刻最多只有一条横幅 —— 版式高度的上限没有变。
                它不是故障,所以不用红;而且**要给可按的东西** —— 一句「需要登录」旁边
                没有入口,跟没说一样。 */}
            {authPrompt && (
              <Alert
                severity="warning"
                sx={{ mb: 1 }}
                data-testid="setup-auth-prompt"
                action={
                  /* 用 MUI 而不是新起一个 `.kiosk-*` 类:`src/kiosk-shell/` 带
                     `MANIFEST.sha256`,是跨 track 校验过的共享资产,往里加类会动到校验。 */
                  <Button size="small" color="inherit" onClick={() => navigate('/kiosk/login')}>
                    {t('auth:go_login', '去登录')}
                  </Button>
                }
              >
                {authPrompt}
              </Alert>
            )}

            {/* 🔴 **今天这一条在 kiosk 上走不到。** `KioskApp.tsx:81` 用 `KioskAuthGuard`
                把除登录页外的**每一条** kiosk 路由都包住了,未登录会 `<Navigate to="/kiosk/login">`
                ⇒ 游客根本到不了这一屏。**kiosk 没有游客模式,这是设计,不是漏做** ——
                galaxy 允许不登录随便逛,kiosk 不允许。
                留着这一条是因为它是**对的**:服务端(develop 的 guest-free-play)已经放行无主会话,
                哪天产品决定盒上也开游客对弈(那是动鉴权边界,要 Fan 拍),这一条当天就生效,
                不用再想一遍。**它不假装自己现在有用。**

                下面那个判据本身:**是 `isAuthenticated` 不是 `!token`** —— strict box kiosk 上
                鉴权走 HttpOnly 的 `sb_go_token` cookie,`token` 恒为 null,拿它判游客
                会对盒上**每一个已登录用户**都说「你正在以游客身份对弈」。
                `authLoading` 必须等:挂载时那次 `/me` 探针没回来之前 `isAuthenticated` 是
                false,不等就会让已登录用户每次进这一屏都先闪一下这句话。
                升降级那一屏不说 —— 它对游客根本开不了局,该说的是「需要登录」不是「你是游客」。 */}
            {!isRanked && !authLoading && !isAuthenticated && !error && !authPrompt && (
              <Alert severity="info" sx={{ mb: 1 }} data-testid="setup-guest-notice">
                {t('play:guest_free_notice',
                   '你正在以游客身份对弈：本局不会保存到棋谱库，也不计入段位。登录后可保存对局。')}
              </Alert>
            )}

            {/* **升降级那一屏没有这一段。** 稿子 03 屏从滚动区直接接主行动键 ——
                该说的话已经在页控条副标(「计入段位 · 全程封分析」)和「对手」那组的提示行里
                说过了,再摆一段就是同一句话说两遍。第一版给它编了一段,四图一比才看出来:
                **稿子上没有的东西,写出来通顺也还是编的。** */}
            {/* 一行,不是两行。「开局后不可改」已经写在「这局棋」那一组的组标右端了,
                原来第一行是把同一句话再说一遍 —— 而右栏一行 ≈ 19px,这一屏正卡在那上头。 */}
            {!isRanked && (
              <p className="setnote" data-testid="setup-note">
                {t('setup:note_r2_a', '这几项')}
                <b>{t('setup:note_r2_b', '开局后都不能改')}</b>
                {t('setup:note_r2_c', ',中途换等于换了一局棋;自由对弈')}
                <b>{t('setup:note_r2_d', '不计入段位')}</b>
                {t('setup:note_h', '。')}
              </p>
            )}

            <button
              type="button"
              className="kiosk-primary-action"
              data-testid={isRanked ? 'ranked-start-action' : 'free-start-action'}
              disabled={loading || (isRanked && !canStartAiLadderGame(aiLadderStatus))}
              onClick={handleStart}
            >
              {loading
                ? t('Creating...', '创建中...')
                : isRanked ? t('ladder:start', '开始计分局') : t('setup:start', '开始对局')}
            </button>
          </>
        )}
        </SetupPopoverHost.Provider>
      </div>
    </div>
  );
};

export default AiSetupPage;
