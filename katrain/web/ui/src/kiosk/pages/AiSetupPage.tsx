import { useState } from 'react';
import { Box, Typography, Button, Alert, FormControl, InputLabel, Select, MenuItem } from '@mui/material';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowBack, PlayArrow } from '@mui/icons-material';
import OptionChips from '../components/common/OptionChips';
import { API } from '../../api';
import { internalToRank, sliderToInternal } from '../../utils/rankUtils';
import { useTranslation } from '../../hooks/useTranslation';
import { useAuth } from '../../context/AuthContext';
import { writeActiveSession } from '../utils/activeSession';
import AiLadderSetupOpponent from '../../features/aiLadder/AiLadderSetupOpponent';
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

// Time-control presets — each maps onto the existing timeEnabled/mainTime/byoyomiTime/
// byoyomiPeriods state so the submitted payload values are unchanged from the slider UI.
const TIME_PRESETS = (t: (en: string, zh: string) => string) => [
  { key: 'untimed', label: t('Untimed', '不限时'), enabled: false, main: 0, byo: 30, periods: 3 },
  { key: 'byoOnly', label: t('Byoyomi only 30s x3', '仅读秒 30秒×3'), enabled: true, main: 0, byo: 30, periods: 3 },
  { key: '5', label: t('5 min + 3x30s', '5分+3×30秒'), enabled: true, main: 5, byo: 30, periods: 3 },
  { key: '10', label: t('10 min + 3x30s', '10分+3×30秒'), enabled: true, main: 10, byo: 30, periods: 3 },
  { key: '20', label: t('20 min + 3x30s', '20分+3×30秒'), enabled: true, main: 20, byo: 30, periods: 3 },
  { key: '30', label: t('30 min + 3x30s', '30分+3×30秒'), enabled: true, main: 30, byo: 30, periods: 3 },
  { key: '60', label: t('60 min + 3x30s', '60分+3×30秒'), enabled: true, main: 60, byo: 30, periods: 3 },
];

// Canonical kiosk setup skeleton: left preview console + right token-themed form. pvp/cross-platform setup pages restyle against this — tokens only, no flow change.
const AiSetupPage = () => {
  const { mode } = useParams<{ mode: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { token, user } = useAuth();
  const isRanked = mode === 'ranked';
  const {
    status: aiLadderStatus,
    retry: retryAiLadderStatus,
    applyBlockingSync,
  } = useAiLadderStatus(token ?? undefined, isRanked);
  // 挡着新局的那一局。有它的时候整个右栏换成挡局面板 —— 底下那些设置一个都用不上,
  // 摆着只会让用户以为改一改就能开局。
  const blockingGame = isRanked ? aiLadderBlockingGame(aiLadderStatus) : null;

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
      setError(e.message || t('Failed to create game', '创建对局失败'));
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

  return (
    // 规范 §11 **布局 A**(`kiosk-shell-spec.md:510-512`):「开局设置是对局的前一步,所以它走
    // 布局 A,和对局屏同一个骨架 —— 左盘 516 + 16 + 右栏 460」。
    // 上一版是**通栏返回条 + 296 镜像栏**,那是把 §5 的 L1 构件(`:139`)搭在了一屏 L2 上,
    // 也是布局 B 的做法用在了有棋盘的屏上(`:742-743` 那张表的两行搞反了)。
    //
    // 外框:`:399` L2/L3 可用高度 600 − 56(顶栏)− 28(上下各 14 内边距)= **516**,
    // 左右各 16(`:64` `--content-x`)⇒ 内容 992,减去盘 516 与栏距 16,右栏正好 460。
    // 这三个数一个都不在这里写死 —— `.kiosk-layout-a` / `.kiosk-board` 用的是
    // `tokens.css` 的 `--board-size` / `--content-x`,改规范时不用回来改这里。
    // `px`/`py` 和 `.kiosk` 一起去掉(Task 1):`.kiosk-content` 现在自己就给
    // `left/right: var(--content-x)` 和 `padding: var(--content-pad-y) 0`。
    // 这一处曾经是对的(那时还没有 `.kiosk-content`),留着就是**两层内边距叠加** ——
    // 中间区从 992 缩成 960、纵向各多 14,不报错,只是尺寸悄悄小一圈。
    <Box sx={{ height: '100%', boxSizing: 'border-box' }}>
      <div className="kiosk-layout-a">
        {/* 左栏 = 按下「开始对弈」后真会出现的那个局面(`:512`),不是摄像头镜像 ——
            镜像栏是 L1 的东西(`SmartBoardConsole`,296 宽),它留在 `/kiosk/play`。 */}
        <KioskSetupBoard color={color} size={boardSize} />

        <div className="kiosk-rail">
          {/* 页控条:`:736` 顶栏在所有层级恒为品牌态,返回与标题一律下放到这里;
              `:742` 有棋盘 ⇒ 它在**右栏顶部**,不是通栏。内部尺寸见 `:750-759`,
              全部由 `.kiosk-pagebar*`(tokens.css:619-662)给。 */}
          <div className="kiosk-pagebar" data-testid="kiosk-setup-pagebar">
            <button type="button" className="kiosk-pagebar__back" onClick={() => navigate('/kiosk/play')}>
              <ArrowBack />
              {t('Back', '返回')}
            </button>
            <span className="kiosk-pagebar__title">
              {isRanked ? t('Ranked Game', '升降级对弈') : t('Free Game', '自由对弈')}
            </span>
            {/* 英文副标不是新文案:它就是上面那个 key 的英文侧,和标题同一句话的两种语言。 */}
            <span className="kiosk-pagebar__sub">{isRanked ? 'Ranked Game' : 'Free Game'}</span>
          </div>

          {/* 右栏内容:`:512`「按下按钮时骨架不动,只有右栏换内容」—— 挡局面板和设置表单
              是同一个位置的两种内容,不是两种布局。 */}
          <Box data-testid={isRanked ? 'ranked-settings-panel' : undefined} sx={{ flex: 1, minHeight: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          {blockingGame ? (
            // 有一局挡着的时候,整个右栏换成挡局面板:执子、用时、开始按钮此刻一个都用不上,
            // 摆着只会让用户以为改一改就能开局,而真正能推进事情的两三个按钮反倒被挤到看不见。
            <KioskAiLadderBlockingPanel
              game={blockingGame}
              pending={lifecyclePending}
              error={lifecycleError}
              syncRetryPending={syncRetryPending}
              onContinue={handleContinue}
              onEndGame={handleEndGame}
              onRetrySettlement={handleRetrySettlement}
            />
          ) : (
          <>
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: isRanked ? 1.25 : 2, alignContent: 'start' }}>
            {/* Board size — segmented, spans both columns */}
            {!isRanked && <Box sx={{ gridColumn: '1 / -1' }}>
              <OptionChips
                label={t('Board', '棋盘')}
                options={[{ value: 9, label: t('9x9', '9路') }, { value: 13, label: t('13x13', '13路') }, { value: 19, label: t('19x19', '19路') }]}
                value={boardSize}
                onChange={setBoardSize}
              />
            </Box>}

            {/* My color — segmented, spans both columns */}
            <Box sx={{ gridColumn: '1 / -1' }}>
              <OptionChips
                label={t('My Color', '我执')}
                options={[{ value: 'black' as const, label: t('Black Stone', '● 黑') }, { value: 'white' as const, label: t('White Stone', '○ 白') }]}
                value={color}
                onChange={setColor}
              />
            </Box>

            {isRanked && (
              <Box sx={{ gridColumn: '1 / -1' }}>
                <AiLadderSetupOpponent status={aiLadderStatus} onRetry={retryAiLadderStatus} compact />
              </Box>
            )}

            {/* The conditions every rung was calibrated under. Server-owned, so this is
                a read-out, not a control — a ruleset dropdown that the server overrides
                would be a knob that does nothing. */}
            {isRanked && (
              <Box sx={{ gridColumn: '1 / -1' }}>
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                  {t('ladder:fixed_setup', '19 路 · 中国规则 · 贴 7.5 目 · 不让子')}
                </Typography>
              </Box>
            )}

            {/* Ruleset — dropdown, free mode only */}
            {!isRanked && <FormControl size="small" fullWidth>
              <InputLabel id="ai-setup-rules-label">{t('Rules', '规则')}</InputLabel>
              <Select
                labelId="ai-setup-rules-label"
                label={t('Rules', '规则')}
                value={rules}
                onChange={(e) => setRules(e.target.value as typeof rules)}
              >
                <MenuItem value="chinese">{t('Chinese', '中国')}</MenuItem>
                <MenuItem value="japanese">{t('Japanese', '日本')}</MenuItem>
                <MenuItem value="korean">{t('Korean', '韩国')}</MenuItem>
                <MenuItem value="aga">AGA</MenuItem>
              </Select>
            </FormControl>}

            {/* AI strategy — dropdown, free mode only */}
            {!isRanked && (
              <FormControl size="small" fullWidth>
                <InputLabel id="ai-setup-strategy-label">{t('AI Strategy', 'AI 策略')}</InputLabel>
                <Select
                  labelId="ai-setup-strategy-label"
                  label={t('AI Strategy', 'AI 策略')}
                  value={aiStrategy}
                  onChange={(e) => setAiStrategy(e.target.value)}
                >
                  <MenuItem value="ai:human">{t('Human-like', '拟人')}</MenuItem>
                  <MenuItem value="ai:default">KataGo</MenuItem>
                  <MenuItem value="ai:territory">{t('Territory', '实地')}</MenuItem>
                  <MenuItem value="ai:influence">{t('Influence', '厚势')}</MenuItem>
                  <MenuItem value="ai:policy">{t('Policy', '策略')}</MenuItem>
                </Select>
              </FormControl>
            )}

            {/* AI strength — dropdown, shown for free+human or ranked */}
            {showRankSlider && (
              <FormControl size="small" fullWidth>
                <InputLabel id="ai-setup-rank-label">{t('AI Strength', 'AI 棋力')}</InputLabel>
                <Select
                  labelId="ai-setup-rank-label"
                  label={t('AI Strength', 'AI 棋力')}
                  value={rank}
                  onChange={(e) => setRank(e.target.value as number)}
                >
                  {rankOptions.map((opt) => (
                    <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            )}

            {/* Handicap — dropdown, free mode only (ranked is always an even game) */}
            {!isRanked && <FormControl size="small" fullWidth>
              <InputLabel id="ai-setup-handicap-label">{t('Handicap', '让子')}</InputLabel>
              <Select
                labelId="ai-setup-handicap-label"
                label={t('Handicap', '让子')}
                value={handicap}
                onChange={(e) => setHandicap(e.target.value as number)}
              >
                {Array.from({ length: 10 }, (_, v) => v).map((v) => (
                  <MenuItem key={v} value={v}>{v === 0 ? t('None', '无') : `${v}${t('stones', '子')}`}</MenuItem>
                ))}
              </Select>
            </FormControl>}

            {/* Komi — dropdown, free mode with no handicap only */}
            {!isRanked && handicap === 0 && (
              <FormControl size="small" fullWidth>
                <InputLabel id="ai-setup-komi-label">{t('Komi', '贴目')}</InputLabel>
                <Select
                  labelId="ai-setup-komi-label"
                  label={t('Komi', '贴目')}
                  value={komi}
                  onChange={(e) => setKomi(e.target.value as number)}
                >
                  {Array.from({ length: 15 }, (_, i) => 0.5 + i * 0.5).map((v) => (
                    <MenuItem key={v} value={v}>{v}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            )}

            {/* Time control — preset dropdown mapping onto existing timeEnabled/mainTime/byoyomi state */}
            <FormControl size="small" fullWidth>
              <InputLabel id="ai-setup-time-label">{t('Time Control', '用时')}</InputLabel>
              <Select
                labelId="ai-setup-time-label"
                label={t('Time Control', '用时')}
                value={currentTimeKey}
                onChange={(e) => applyTimePreset(e.target.value)}
              >
                {timePresets
                  .filter((p) => !isRanked || p.key !== 'untimed')
                  .map((p) => (
                    <MenuItem key={p.key} value={p.key}>{p.label}</MenuItem>
                  ))}
              </Select>
            </FormControl>
          </Box>

          <Box data-testid={isRanked ? 'ranked-start-action' : undefined} sx={{ mt: 'auto', pt: isRanked ? 1 : 2, flexShrink: 0 }}>
            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
            <Button
              variant="contained"
              fullWidth
              size="large"
              startIcon={<PlayArrow />}
              disabled={loading || (isRanked && !canStartAiLadderGame(aiLadderStatus))}
              onClick={handleStart}
              sx={{
                minHeight: isRanked ? 48 : 56, py: isRanked ? 1 : 2, fontSize: isRanked ? '1rem' : '1.1rem',
                bgcolor: 'primary.main',
                '&:hover': { bgcolor: 'primary.dark' },
              }}
            >
              {loading ? t('Creating...', '创建中...') : t('Start Game', '开始对弈')}
            </Button>
          </Box>
          </>
          )}
          </Box>
        </div>
      </div>
    </Box>
  );
};

export default AiSetupPage;
