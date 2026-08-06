import { useState } from 'react';
import { Box, Typography, Button, Alert, FormControl, InputLabel, Select, MenuItem } from '@mui/material';
import { useParams, useNavigate } from 'react-router-dom';
import { PlayArrow } from '@mui/icons-material';
import OptionChips from '../components/common/OptionChips';
import SubPageBar from '../components/layout/SubPageBar';
import { API } from '../../api';
import { internalToRank, sliderToInternal } from '../../utils/rankUtils';
import { useTranslation } from '../../hooks/useTranslation';
import { useAuth } from '../../context/AuthContext';
import LiveBoard from '../../components/live/LiveBoard';
import { writeActiveSession } from '../utils/activeSession';
import AiLadderSetupOpponent from '../../features/aiLadder/AiLadderSetupOpponent';
import { startAiLadderGame } from '../../features/aiLadder/api';
import { useAiLadderStatus } from '../../features/aiLadder/useAiLadderStatus';
import { canStartAiLadderGame } from '../../features/aiLadder/startGate';
import { saveAiLadderBefore } from '../../features/aiLadder/settlement';

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
  const { status: aiLadderStatus, retry: retryAiLadderStatus } = useAiLadderStatus(token ?? undefined, isRanked);

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

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <SubPageBar
        title={isRanked ? t('Ranked Game', '升降级对弈') : t('Free Game', '自由对弈')}
        to="/kiosk/play"
      />
      <Box sx={{ display: 'flex', flex: 1, minHeight: 0 }}>
        {/* Left: board preview console — fixed 322px width (matches artifact .console).
            Board wrapper below stays flex:1 so LiveBoard renders a square that fits this width. */}
        <Box
          sx={{
            width: isRanked ? 290 : 322, flexShrink: 0, overflow: 'hidden', m: isRanked ? 1.5 : 2, mr: 0,
            bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider',
            borderRadius: 3, p: isRanked ? 1.5 : 2, display: 'flex', flexDirection: 'column',
          }}
        >
          <Typography variant="overline" sx={{ color: 'text.secondary', mb: 1 }}>
            {t('Board Preview', '盘面预览')}
          </Typography>
          <Box sx={{ flex: 1, minHeight: 0 }}>
            <LiveBoard
              moves={[]}
              currentMove={0}
              boardSize={boardSize}
              showCoordinates={true}
            />
          </Box>
        </Box>

        {/* Right: compact 2-column settings form — structurally no-scroll (overflow:hidden). */}
        <Box data-testid={isRanked ? 'ranked-settings-panel' : undefined} sx={{ flex: 1, p: isRanked ? 2 : 3, overflow: 'hidden', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
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
        </Box>
      </Box>
    </Box>
  );
};

export default AiSetupPage;
