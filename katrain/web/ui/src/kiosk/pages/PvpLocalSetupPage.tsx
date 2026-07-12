import { useState } from 'react';
import { Box, Typography, Button, Slider, Switch, FormControlLabel, Alert, TextField } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { PlayArrow, ArrowBack } from '@mui/icons-material';
import OptionChips from '../components/common/OptionChips';
import { API } from '../../api';
import { useTranslation } from '../../hooks/useTranslation';
import { useAuth } from '../../context/AuthContext';
import LiveBoard from '../../components/live/LiveBoard';
import { writeActiveSession } from '../utils/activeSession';

// Local (同板双人) setup page — mirrors AiSetupPage's canonical kiosk setup skeleton
// (left LiveBoard preview + right token-themed form), dropping AI strategy/rank/color
// and adding black/white player-name fields plus a client-side move-sound toggle.
const PvpLocalSetupPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { token } = useAuth();

  // Board & rules
  const [boardSize, setBoardSize] = useState(19);
  const [rules, setRules] = useState<'chinese' | 'japanese' | 'korean' | 'aga'>('chinese');

  // Player names
  const [blackName, setBlackName] = useState('');
  const [whiteName, setWhiteName] = useState('');

  // Handicap & komi
  const [handicap, setHandicap] = useState(0);
  const [komi, setKomi] = useState(6.5);

  // Time control
  const [timeEnabled, setTimeEnabled] = useState(false);
  const [mainTime, setMainTime] = useState(0);
  const [byoyomiTime, setByoyomiTime] = useState(30);
  const [byoyomiPeriods, setByoyomiPeriods] = useState(3);

  // Move sound — client-side preference, persisted in localStorage (shared useGameSession.playSound reads it)
  const [confirmSound, setConfirmSound] = useState(localStorage.getItem('kioskPlaySound') !== '0');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleStart = async () => {
    setError('');
    setLoading(true);
    try {
      localStorage.setItem('kioskPlaySound', confirmSound ? '1' : '0');
      const { session_id } = await API.createSession(token ?? undefined);
      await API.gameSetup(session_id, 'pvp_local', {
        board_size: boardSize,
        rules,
        handicap,
        komi,
        black_name: blackName,
        white_name: whiteName,
        time_enabled: timeEnabled,
        main_time: mainTime,
        byo_length: byoyomiTime,
        byo_periods: byoyomiPeriods,
      });
      writeActiveSession({
        kind: 'game',
        label: `${blackName || t('Black', '黑方')} vs ${whiteName || t('White', '白方')}`,
        route: `/kiosk/play/pvp/local/game/${session_id}`,
        ts: Date.now(),
      });
      navigate(`/kiosk/play/pvp/local/game/${session_id}`);
    } catch (e: any) {
      setError(e.message || t('Failed to create game', '创建对局失败'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ display: 'flex', height: '100%' }}>
      {/* Left: board preview console — fixed 322px width (matches artifact .console).
          Board wrapper below stays flex:1 so LiveBoard renders a square that fits this width. */}
      <Box
        sx={{
          width: 322, height: '100%', flexShrink: 0, overflow: 'hidden',
          bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider',
          borderRadius: 3, p: 2, display: 'flex', flexDirection: 'column',
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

      {/* Right: settings form */}
      <Box sx={{ flex: 1, p: 3, overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 3 }}>
          <Button
            onClick={() => navigate('/kiosk/play')}
            startIcon={<ArrowBack />}
            sx={{ minWidth: 40, p: 0.5 }}
          />
          <Typography variant="h5" sx={{ color: 'text.primary' }}>
            {t('Local Game', '本地对局')}
          </Typography>
        </Box>

        {/* Player names */}
        <Box sx={{ display: 'flex', gap: 2, mb: 2.5 }}>
          <TextField
            data-testid="black-name-input"
            label={t('Black player', '黑方姓名')}
            value={blackName}
            onChange={(e) => setBlackName(e.target.value)}
            fullWidth
            size="small"
          />
          <TextField
            data-testid="white-name-input"
            label={t('White player', '白方姓名')}
            value={whiteName}
            onChange={(e) => setWhiteName(e.target.value)}
            fullWidth
            size="small"
          />
        </Box>

        {/* Board size */}
        <OptionChips
          label={t('Board', '棋盘')}
          options={[{ value: 9, label: t('9x9', '9路') }, { value: 13, label: t('13x13', '13路') }, { value: 19, label: t('19x19', '19路') }]}
          value={boardSize}
          onChange={setBoardSize}
        />

        {/* Ruleset */}
        <OptionChips
          label={t('Rules', '规则')}
          options={[
            { value: 'chinese' as const, label: t('Chinese', '中国') },
            { value: 'japanese' as const, label: t('Japanese', '日本') },
            { value: 'korean' as const, label: t('Korean', '韩国') },
            { value: 'aga' as const, label: 'AGA' },
          ]}
          value={rules}
          onChange={setRules}
        />

        {/* Handicap */}
        <Box sx={{ mb: 2.5 }}>
          <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
            {t('Handicap', '让子')}: {handicap === 0 ? t('None', '无') : `${handicap}${t('stones', '子')}`}
          </Typography>
          <Slider
            value={handicap}
            onChange={(_, v) => setHandicap(v as number)}
            min={0}
            max={9}
            step={1}
            valueLabelDisplay="auto"
            valueLabelFormat={(v) => (v === 0 ? t('None', '无') : `${v}${t('stones', '子')}`)}
          />
        </Box>

        {/* Komi (no handicap only) */}
        {handicap === 0 && (
          <Box sx={{ mb: 2.5 }}>
            <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
              {t('Komi', '贴目')}: {komi}
            </Typography>
            <Slider
              value={komi}
              onChange={(_, v) => setKomi(v as number)}
              min={0.5}
              max={7.5}
              step={0.5}
              valueLabelDisplay="auto"
            />
          </Box>
        )}

        {/* Time control */}
        <Box sx={{ mb: 2.5 }}>
          <FormControlLabel
            control={
              <Switch
                checked={timeEnabled}
                onChange={(_, checked) => setTimeEnabled(checked)}
              />
            }
            label={t('Time Control', '用时')}
          />
        </Box>

        {timeEnabled && (
          <>
            <Box sx={{ mb: 2.5 }}>
              <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
                {t('Main Time', '主时间')}: {mainTime === 0 ? t('Unlimited', '不限') : `${mainTime}${t('min', '分')}`}
              </Typography>
              <Slider
                value={mainTime}
                onChange={(_, v) => setMainTime(v as number)}
                min={0}
                max={60}
                step={null}
                marks={[
                  { value: 0, label: t('Unlimited', '不限') },
                  { value: 5, label: `5${t('min', '分')}` },
                  { value: 10, label: `10${t('min', '分')}` },
                  { value: 20, label: `20${t('min', '分')}` },
                  { value: 30, label: `30${t('min', '分')}` },
                  { value: 60, label: `60${t('min', '分')}` },
                ]}
              />
            </Box>

            <Box sx={{ mb: 2.5 }}>
              <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
                {t('Byoyomi', '读秒时间')}: {byoyomiTime}{t('sec', '秒')}
              </Typography>
              <Slider
                value={byoyomiTime}
                onChange={(_, v) => setByoyomiTime(v as number)}
                min={10}
                max={60}
                step={null}
                marks={[
                  { value: 10, label: `10${t('sec', '秒')}` },
                  { value: 20, label: `20${t('sec', '秒')}` },
                  { value: 30, label: `30${t('sec', '秒')}` },
                  { value: 60, label: `60${t('sec', '秒')}` },
                ]}
              />
            </Box>

            <Box sx={{ mb: 2.5 }}>
              <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
                {t('Byoyomi Periods', '读秒次数')}: {byoyomiPeriods}{t('times', '次')}
              </Typography>
              <Slider
                value={byoyomiPeriods}
                onChange={(_, v) => setByoyomiPeriods(v as number)}
                min={1}
                max={5}
                step={null}
                marks={[
                  { value: 1, label: `1${t('times', '次')}` },
                  { value: 3, label: `3${t('times', '次')}` },
                  { value: 5, label: `5${t('times', '次')}` },
                ]}
              />
            </Box>
          </>
        )}

        {/* Move sound */}
        <Box sx={{ mb: 2.5 }}>
          <FormControlLabel
            control={
              <Switch
                checked={confirmSound}
                onChange={(_, checked) => setConfirmSound(checked)}
              />
            }
            label={t('Move sound', '落子提示音')}
          />
        </Box>

        <Box sx={{ mt: 'auto', pt: 2 }}>
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
          <Button
            variant="contained"
            fullWidth
            size="large"
            startIcon={<PlayArrow />}
            disabled={loading}
            onClick={handleStart}
            sx={{
              minHeight: 56, py: 2, fontSize: '1.1rem',
              bgcolor: 'primary.main',
              '&:hover': { bgcolor: 'primary.dark' },
            }}
          >
            {loading ? t('Creating...', '创建中...') : t('Start Game', '开始对弈')}
          </Button>
        </Box>
      </Box>
    </Box>
  );
};

export default PvpLocalSetupPage;
