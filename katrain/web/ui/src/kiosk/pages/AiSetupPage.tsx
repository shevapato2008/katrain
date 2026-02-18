import { useState } from 'react';
import { Box, Typography, Button, Slider, Switch, FormControlLabel, Alert } from '@mui/material';
import { useParams, useNavigate } from 'react-router-dom';
import { PlayArrow, ArrowBack } from '@mui/icons-material';
import OptionChips from '../components/common/OptionChips';
import { API } from '../../api';
import { internalToRank, sliderToInternal } from '../../utils/rankUtils';
import { useTranslation } from '../../hooks/useTranslation';

const AiSetupPage = () => {
  const { mode } = useParams<{ mode: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const isRanked = mode === 'ranked';

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

  const showRankSlider = isRanked || aiStrategy === 'ai:human';

  const handleStart = async () => {
    setError('');
    setLoading(true);
    try {
      const { session_id } = await API.createSession();
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
      navigate(`/kiosk/play/ai/game/${session_id}`);
    } catch (e: any) {
      setError(e.message || t('Failed to create game', '创建对局失败'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ display: 'flex', height: '100%' }}>
      {/* Left: board preview placeholder */}
      <Box
        sx={{
          aspectRatio: '1',
          height: '100%',
          bgcolor: '#8b7355',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
        }}
      >
        <Typography sx={{ color: 'rgba(0,0,0,0.3)' }}>{boardSize}x{boardSize}</Typography>
      </Box>

      {/* Right: settings form */}
      <Box sx={{ flex: 1, p: 3, overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 3 }}>
          <Button
            onClick={() => navigate('/kiosk/play')}
            startIcon={<ArrowBack />}
            sx={{ minWidth: 40, p: 0.5 }}
          />
          <Typography variant="h5">{isRanked ? t('Ranked Game', '升降级对弈') : t('Free Game', '自由对弈')}</Typography>
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

        {/* Color */}
        <OptionChips
          label={t('My Color', '我执')}
          options={[{ value: 'black' as const, label: t('Black Stone', '● 黑') }, { value: 'white' as const, label: t('White Stone', '○ 白') }]}
          value={color}
          onChange={setColor}
        />

        {/* AI strategy (free mode only) */}
        {!isRanked && (
          <OptionChips
            label={t('AI Strategy', 'AI 策略')}
            options={[
              { value: 'ai:human', label: t('Human-like', '拟人') },
              { value: 'ai:default', label: 'KataGo' },
              { value: 'ai:territory', label: t('Territory', '实地') },
              { value: 'ai:influence', label: t('Influence', '厚势') },
              { value: 'ai:policy', label: t('Policy', '策略') },
            ]}
            value={aiStrategy}
            onChange={setAiStrategy}
          />
        )}

        {/* Rank slider (free+human or ranked) */}
        {showRankSlider && (
          <Box sx={{ mb: 2.5 }}>
            <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
              {t('AI Strength', 'AI 棋力')}: {internalToRank(sliderToInternal(rank))}
            </Typography>
            <Slider
              value={rank}
              onChange={(_, v) => setRank(v as number)}
              min={0}
              max={28}
              step={1}
              valueLabelDisplay="auto"
              valueLabelFormat={(v) => internalToRank(sliderToInternal(v))}
            />
          </Box>
        )}

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

        {/* Komi (free mode, no handicap only) */}
        {!isRanked && handicap === 0 && (
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
                checked={isRanked || timeEnabled}
                onChange={(_, checked) => !isRanked && setTimeEnabled(checked)}
                disabled={isRanked}
              />
            }
            label={t('Time Control', '用时')}
          />
        </Box>

        {(isRanked || timeEnabled) && (
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

        <Box sx={{ mt: 'auto', pt: 2 }}>
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
          <Button variant="contained" fullWidth size="large" startIcon={<PlayArrow />} disabled={loading} onClick={handleStart} sx={{ minHeight: 56, py: 2, fontSize: '1.1rem' }}>
            {loading ? t('Creating...', '创建中...') : t('Start Game', '开始对弈')}
          </Button>
        </Box>
      </Box>
    </Box>
  );
};

export default AiSetupPage;
