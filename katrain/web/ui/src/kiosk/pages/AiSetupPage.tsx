import { useMemo, useState } from 'react';
import { Alert, Box, Button } from '@mui/material';
import { useParams, useNavigate } from 'react-router-dom';
import OptionChips from '../components/common/OptionChips';
import { useVision } from '../context/VisionContext';
import { KioskOptSeg } from '../shell/KioskOptSeg';
import { KioskPagebar } from '../shell/KioskPagebar';
import { KioskScrollZone } from '../shell/KioskScrollZone';
import { KioskSecLabel } from '../shell/KioskSecLabel';
import { KioskStepTrack } from '../shell/KioskStepTrack';
import { interpolate } from '../utils/interpolate';
import { RULES_HINT, TIME_PRESETS, TIME_TRACK_ORDER } from '../utils/setupOptions';
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
import { aiLadderBlockingGame, canStartAiLadderGame } from '../../features/aiLadder/startGate';
import { saveAiLadderBefore } from '../../features/aiLadder/settlement';
import KioskAiLadderBlockingPanel from '../components/aiLadder/KioskAiLadderBlockingPanel';
import KioskSetupBoard from '../components/board/KioskSetupBoard';

/**
 * `.kiosk-opthint` 写的是**当前选中项**的大白话(规范 §11 v1.21)。
 *
 * **策略那四条空着是有意的。** 稿子只给了「拟人」一条;另外四条说的是引擎干什么,
 * 那是**对产品行为的断言**,不是文案润色 —— 编一句「实地:偏好占地」听起来通顺,
 * 可仓里没有任何一处证明它就是 `ai:territory` 的行为。`.kiosk-opthint` 定高
 * (`--opthint-h`),留空不会让下面那些组跳,所以空着的代价只是少一句话。
 * 补齐要去核 `core/ai.py` 里那几个策略的实现,登记为下一轮。
 */
const AI_STRATEGY_HINT = (t: (en: string, zh: string) => string): Record<string, string> => ({
  'ai:human': t(
    'Human-like: plays at the chosen strength, mistakes of that level included',
    '拟人:按所选棋力下出该水平的棋,包括那个水平会犯的错',
  ),
});

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
  const [rules, setRules] = useState<'chinese' | 'japanese' | 'korean' | 'aga'>('chinese');
  const [color, setColor] = useState<'black' | 'white'>('black');

  // AI strategy & rank
  const [aiStrategy, setAiStrategy] = useState('ai:human');
  const [rank, setRank] = useState(14); // 0=20k, 19=1d, 28=9d; default 14 = ~6k

  // Handicap & komi
  const [handicap, setHandicap] = useState(0);
  const [komi, setKomi] = useState(6.5);

  // Time control
  const [timeEnabled, setTimeEnabled] = useState(isRanked);
  const [mainTime, setMainTime] = useState(0);
  const [byoyomiTime, setByoyomiTime] = useState(30);
  const [byoyomiPeriods, setByoyomiPeriods] = useState(3);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  /* 未登录时该说的那句话。与 `error` 分开:它不是故障,而且**要给可按的东西**。 */
  const [authPrompt, setAuthPrompt] = useState('');
  const [lifecyclePending, setLifecyclePending] = useState(false);
  const [lifecycleError, setLifecycleError] = useState('');
  const [syncRetryPending, setSyncRetryPending] = useState(false);

  const showRankSlider = !isRanked && aiStrategy === 'ai:human';

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

  const handleStart = async () => {
    setError('');
    setAuthPrompt('');
    setLoading(true);
    try {
      if (isRanked) {
        const { session_id, game_id, status } = await startAiLadderGame({
          color,
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
        rules,
        color,
        ai_strategy: aiStrategy,
        rank,
        handicap,
        komi,
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

  // ── 档位轨那四组 ────────────────────────────────────────────────
  // 规范 §11(v1.21)给 `.kiosk-optseg` 定的项数上限是 6,「超过就换下拉或滑条」。
  // 棋力 29 / 贴目 15 / 让子 10 / 用时 7 都超了,所以这四组走 `KioskStepTrack`。
  //
  // 用时那几档在轨上的顺序由 `utils/setupOptions` 的 `TIME_TRACK_ORDER` 定(理由写在那儿)。
  // 计分局把「不限时」整档摘掉 —— **不是灰掉**:那一档在这一局里根本不存在。
  const timeTrack = [...TIME_TRACK_ORDER]
    .filter((key) => !isRanked || key !== 'untimed')
    .map((key) => timePresets.find((p) => p.key === key)!)
    .filter(Boolean);
  const timeIndex = Math.max(0, timeTrack.findIndex((p) => p.key === currentTimeKey));

  // 贴目档就是原来那个下拉的 15 个值(0.5 – 7.5,半目一档)。**不收成稿子那句话里的三档** ——
  // 稿子 02 屏的「(6.5 / 7.5 / 0)」写在一段说明里,不是控件规格;把 15 档收成 3 档
  // 是删功能不是重画。屏 04 的贴目稿子画的正是一条档位轨,两屏因此同一种控件。
  const KOMI_STEP = 0.5;
  const KOMI_MIN = 0.5;
  const komiCount = 15;
  const komiIndex = Math.round((komi - KOMI_MIN) / KOMI_STEP);

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
      <KioskSetupBoard color={color} size={boardSize} handicap={isRanked ? 0 : handicap} />

      <div className="kiosk-rail">
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
              {/* ── 怎么落子 ── 三屏里唯一自带强调框的一组:它是**开局后不可改**的那一组 */}
              <section className="setgrp inputgrp" data-testid="setup-input-group">
                <KioskSecLabel
                  zh={t('setup:input', '怎么落子')}
                  en="Input"
                  value={t('setup:locked_after_start', '开局后不可改')}
                />
                <div className="igrow">
                  <span className="iglab">{t('setup:input_where', '落子')}</span>
                  <KioskOptSeg
                    ariaLabel={t('setup:input_where', '落子')}
                    testId="setup-input"
                    value={playInput.onBoard ? 'board' : 'screen'}
                    onChange={(v) => setPlayOnBoard(v === 'board')}
                    options={[
                      // 「屏幕」**永远选得了** —— 条件掉了不能把人锁在一块用不了的盘上。
                      { value: 'screen', label: t('setup:on_screen', '屏幕') },
                      { value: 'board', label: t('setup:on_board', '实体盘'), disabled: !playInput.available },
                    ]}
                  />
                </div>
                <div className="igrow">
                  <span className="iglab">{t('setup:size', '路数')}</span>
                  {isRanked ? (
                    // 升降级那一档的条件是**服务端定的**,前端给个下拉只会是个改不动的旋钮。
                    <span className="igfix" data-testid="setup-ranked-fixed">
                      <b>{t('ladder:fixed_size', '19 路')}</b>
                      {t('ladder:fixed_rest', '中国规则 · 贴 7.5 目 · 不让子')}
                    </span>
                  ) : (
                    <KioskOptSeg
                      ariaLabel={t('setup:size', '路数')}
                      testId="setup-size"
                      value={boardSize}
                      onChange={setBoardSize}
                      options={[
                        { value: 19, label: t('19x19', '19 路') },
                        { value: 13, label: t('13x13', '13 路') },
                        { value: 9, label: t('9x9', '9 路') },
                      ]}
                    />
                  )}
                </div>
                {/* 这一行有两个身份,**计分局只认后一个**:
                    · 自由对弈:稿子 02 屏本来就画了一行说明 ⇒ 常驻。
                    · 计分局:稿子 03 屏这一组**到路数那行就结束了**,没有说明行。
                      常驻会把它下面的每一组都往下推一行 —— 那就是上一轮「给升降级编了一段
                      `.setnote`」的同一个错(四图 refOnly 当场涨了 1900)。
                    ⇒ 计分局只在**实体盘那段灰掉时**说话:灰而不说原因是另一条更硬的规矩,
                      而稿子从没画过那一态。 */}
                {(!isRanked || playInput.reason !== null) && (
                  <p className="kiosk-opthint">
                    {playInput.reason === 'noCamera'
                      ? t('setup:board_no_camera', '这台机器没有标定过摄像头,只能下在屏幕上')
                      : playInput.reason === 'notNineteen'
                        ? t('setup:board_needs_19', '盘上那块是 19 路 —— 9 路和 13 路只有屏幕上有')
                        : playInput.onBoard
                          ? t('setup:input_hint_board', '这一局下在盘上,屏幕负责记谱、读秒和显示分析')
                          : t('setup:input_hint_screen', '这一局点屏幕落子 —— 盘就在旁边,也可以切回实体盘')}
                  </p>
                )}
              </section>

              {isRanked ? (
                <>
                  {/* 对手。2026-08-26 换成外壳写法:六种状态(加载 / 出错重试 / 定级进度 /
                      未认证档 / 不可挑战 / 待结算)全部搬过来了,词和判别位都还取自
                      `features/aiLadder` 那一份(`copy.ts` / `startGate.ts`),
                      两个视图说的是同一套话 —— `KioskAiLadderOpponent.parity.test.tsx` 逐状态钉住。
                      **没有在共享件上原地改样式**:它同时是 galaxy 那屏的消费者。 */}
                  <section className="setgrp" data-testid="setup-opponent-group">
                    <KioskSecLabel
                      zh={t('ladder:opponent', '对手')}
                      en="Opponent"
                      value={t('ladder:box_picks', '盒子配档,不可选')}
                    />
                    <KioskAiLadderOpponent status={aiLadderStatus} onRetry={retryAiLadderStatus} />
                    <p className="kiosk-opthint">
                      {t('ladder:sealed_hint', '提示、形势判断、变化图一律封掉 —— 硬规则,不是设置项')}
                    </p>
                  </section>

                  <section className="setgrp" data-testid="setup-stake-group">
                    <KioskSecLabel
                      zh={t('ladder:stake', '这一局赌多少')}
                      en="Stake"
                      value={t('ladder:frozen_at_start', '开局那一刻冻结')}
                    />
                    <div className="ranked-state__stakes" data-testid="setup-stakes">
                      <span>{stakeWin}</span>
                      <span>{stakeLoss}</span>
                    </div>
                    <p className="kiosk-opthint">
                      {interpolate(
                        t('ladder:stake_rule', '净胜分到 +3 升一档、到 −3 退一档 · 当前 {n}'),
                        { n: signed(netScore) },
                      )}
                    </p>
                  </section>
                </>
              ) : (
                <>
                  {showRankSlider && (
                    <section className="setgrp" data-testid="setup-strength-group">
                      <KioskStepTrack
                        label={t('AI Strength', '棋力')}
                        en="Strength"
                        secval={t('setup:locked_after_start', '开局后不可改')}
                        testId="setup-strength"
                        count={rankOptions.length}
                        index={rank}
                        onChange={setRank}
                        decLabel={t('setup:strength_down', '降低一档')}
                        incLabel={t('setup:strength_up', '提高一档')}
                        value={interpolate(t('setup:strength_value', '第 {n} 档 · '), { n: rank + 1 })}
                        meta={interpolate(t('setup:strength_meta', '共 {n} 档 · {lo} – {hi}'), {
                          n: rankOptions.length, lo: rankName(0), hi: rankName(rankOptions.length - 1),
                        })}
                        hint={t('setup:strength_hint', '档位说的是对手的水平,不是你的段位 —— 自由对弈不涨段')}
                      />
                    </section>
                  )}

                  <section className="setgrp">
                    <OptionChips
                      label={t('AI Strategy', 'AI 策略')}
                      en="Style"
                      testId="setup-strategy"
                      value={aiStrategy}
                      onChange={setAiStrategy}
                      options={[
                        { value: 'ai:human', label: t('Human-like', '拟人') },
                        { value: 'ai:default', label: 'KataGo' },
                        { value: 'ai:territory', label: t('setup:style_territory', '实地') },
                        { value: 'ai:influence', label: t('Influence', '厚势') },
                        { value: 'ai:policy', label: t('Policy', '策略') },
                      ]}
                      hint={AI_STRATEGY_HINT(t)[aiStrategy] ?? ''}
                    />
                  </section>
                </>
              )}

              {/* 我执。**两项,不是稿子上那三项。** 稿子第三项「随机」是搬象棋骨架带来的:
                  象棋 ranked 写死开局随机执棋,而围棋这边 kiosk(这一屏)和 galaxy
                  (`components/aiLadder/AiLadderRatedSetup.tsx`)**两处都只给黑白两项**。
                  在四家里只有围棋多一条路,不是对齐是分叉。 */}
              <section className="setgrp">
                <OptionChips
                  label={t('My Color', '我执')}
                  en="Side"
                  testId="setup-color"
                  value={color}
                  onChange={setColor}
                  options={[
                    // 铸的是新键,**不是套 `Black Stone`** —— PO 里那条是「● 黑」,
                    // 那个圆点是接外壳之前拿字符当棋子用的;现在子由 `.disc.b` 画,
                    // 再借那条 msgid,屏上会出现「● 执黑」两颗子。
                    { value: 'black' as const, label: <><span className="disc b" />{t('setup:side_black', '执黑')}</> },
                    { value: 'white' as const, label: <><span className="disc w" />{t('setup:side_white', '执白')}</> },
                  ]}
                  hint={isRanked
                    ? t('ladder:side_hint', '贴目按所选规则自动定,让子在计分局里一律为 0')
                    : t('setup:side_hint', '让子局里黑棋先摆子,所以执黑就是被让的那一方')}
                />
              </section>

              {!isRanked && (
                <>
                  <section className="setgrp" data-testid="setup-handicap-group">
                    <KioskStepTrack
                      label={t('Handicap', '让子')}
                      en="Handicap"
                      testId="setup-handicap"
                      count={10}
                      index={handicap}
                      onChange={setHandicap}
                      decLabel={t('setup:handicap_down', '少让一子')}
                      incLabel={t('setup:handicap_up', '多让一子')}
                      value={handicap === 0
                        ? t('setup:no_handicap', '不让子')
                        : interpolate(t('setup:handicap_value', '让 {n} 子'), { n: handicap })}
                      meta={t('setup:handicap_meta', '0 – 9 子 · 星位固定')}
                    />
                  </section>

                  <section className="setgrp" data-testid="setup-komi-group">
                    <KioskSecLabel
                      zh={t('Komi', '贴目')}
                      en="Komi"
                      value={handicap > 0 ? t('setup:not_applicable', '本局不适用') : undefined}
                    />
                    {handicap > 0 ? (
                      // **不是把控件灰掉。** 灰掉说的是「你现在不能改」,这里要说的是
                      // 「这一局没有贴目这回事」—— 让子和贴目补的都是先行那一方的便宜。
                      <p className="setexplain" data-testid="setup-komi-explain">
                        {interpolate(
                          t('setup:komi_explain', '已经让了 {n} 子,这一局不贴目。让子和贴目是同一件事的两种做法——补的都是先行那一方的便宜,两样一起用会补两遍。'),
                          { n: handicap },
                        )}
                        <br />
                        {t('setup:komi_explain_back', '把让子调回 0,这一组会变回可选的贴目档。')}
                      </p>
                    ) : (
                      <KioskStepTrack
                        testId="setup-komi"
                        count={komiCount}
                        index={komiIndex}
                        onChange={(i) => setKomi(KOMI_MIN + i * KOMI_STEP)}
                        decLabel={t('setup:komi_down', '减少贴目')}
                        incLabel={t('setup:komi_up', '增加贴目')}
                        value={interpolate(t('setup:komi_value', '贴 {n} 目'), { n: komi })}
                        meta={t('setup:komi_meta', '0.5 – 7.5 · 中国规则常用 7.5')}
                      />
                    )}
                  </section>

                  <section className="setgrp">
                    <OptionChips
                      label={t('Rules', '规则')}
                      en="Rules"
                      testId="setup-rules"
                      value={rules}
                      onChange={setRules}
                      options={[
                        { value: 'chinese' as const, label: t('Chinese', '中国') },
                        { value: 'japanese' as const, label: t('Japanese', '日本') },
                        { value: 'korean' as const, label: t('Korean', '韩国') },
                        { value: 'aga' as const, label: 'AGA' },
                      ]}
                      hint={RULES_HINT(t)[rules] ?? ''}
                    />
                  </section>
                </>
              )}

              <section className="setgrp" data-testid="setup-clock-group">
                <KioskStepTrack
                  label={t('Time Control', '用时')}
                  en="Clock"
                  testId="setup-clock"
                  count={timeTrack.length}
                  index={timeIndex}
                  onChange={(i) => applyTimePreset(timeTrack[i].key)}
                  decLabel={t('setup:clock_down', '减少用时')}
                  incLabel={t('setup:clock_up', '增加用时')}
                  value={timeTrack[timeIndex]?.label ?? '—'}
                  meta={interpolate(t('setup:clock_meta', '{n} 档 · {lo} → {hi}'), {
                    n: timeTrack.length,
                    lo: timeTrack[0]?.label ?? '—',
                    hi: timeTrack[timeTrack.length - 1]?.label ?? '—',
                  })}
                />
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
            {!isRanked && (
              <p className="setnote" data-testid="setup-note">
                {t('setup:note_a', '棋力、让子和执棋方')}
                <b>{t('setup:note_b', '开局后不能改')}</b>
                {t('setup:note_c', ',中途换等于换了一局棋。')}
                <br />
                {t('setup:note_d', '规则和用时')}
                <b>{t('setup:note_e', '写进这一局的棋谱')}</b>
                {t('setup:note_f', ';自由对弈')}
                <b>{t('setup:note_g', '不计入段位')}</b>
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
      </div>
    </div>
  );
};

export default AiSetupPage;
