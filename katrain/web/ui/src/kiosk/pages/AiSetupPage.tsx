import { useState } from 'react';
import { Box, Typography, Button, Slider, Switch, FormControlLabel } from '@mui/material';
import { useParams, useNavigate } from 'react-router-dom';
import { PlayArrow, ArrowBack } from '@mui/icons-material';
import OptionChips from '../components/common/OptionChips';

const rankLabel = (value: number): string => {
  if (value < 20) return `${20 - value}k`;
  return `${value - 19}d`;
};

const AiSetupPage = () => {
  const { mode } = useParams<{ mode: string }>();
  const navigate = useNavigate();
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

  const showRankSlider = isRanked || aiStrategy === 'ai:human';

  const handleStart = () => {
    // TODO: POST /api/new-game → get sessionId → navigate to game
    navigate('/kiosk/play/ai/game/mock-session');
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
          <Typography variant="h5">{isRanked ? '升降级对弈' : '自由对弈'}</Typography>
        </Box>

        {/* Board size */}
        <OptionChips
          label="棋盘"
          options={[{ value: 9, label: '9路' }, { value: 13, label: '13路' }, { value: 19, label: '19路' }]}
          value={boardSize}
          onChange={setBoardSize}
        />

        {/* Ruleset */}
        <OptionChips
          label="规则"
          options={[
            { value: 'chinese' as const, label: '中国' },
            { value: 'japanese' as const, label: '日本' },
            { value: 'korean' as const, label: '韩国' },
            { value: 'aga' as const, label: 'AGA' },
          ]}
          value={rules}
          onChange={setRules}
        />

        {/* Color */}
        <OptionChips
          label="我执"
          options={[{ value: 'black' as const, label: '● 黑' }, { value: 'white' as const, label: '○ 白' }]}
          value={color}
          onChange={setColor}
        />

        {/* AI strategy (free mode only) */}
        {!isRanked && (
          <OptionChips
            label="AI 策略"
            options={[
              { value: 'ai:human', label: '拟人' },
              { value: 'ai:default', label: 'KataGo' },
              { value: 'ai:territory', label: '实地' },
              { value: 'ai:influence', label: '厚势' },
              { value: 'ai:policy', label: '策略' },
            ]}
            value={aiStrategy}
            onChange={setAiStrategy}
          />
        )}

        {/* Rank slider (free+human or ranked) */}
        {showRankSlider && (
          <Box sx={{ mb: 2.5 }}>
            <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
              AI 棋力: {rankLabel(rank)}
            </Typography>
            <Slider
              value={rank}
              onChange={(_, v) => setRank(v as number)}
              min={0}
              max={28}
              step={1}
              valueLabelDisplay="auto"
              valueLabelFormat={rankLabel}
            />
          </Box>
        )}

        {/* Handicap */}
        <Box sx={{ mb: 2.5 }}>
          <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
            让子: {handicap === 0 ? '无' : `${handicap}子`}
          </Typography>
          <Slider
            value={handicap}
            onChange={(_, v) => setHandicap(v as number)}
            min={0}
            max={9}
            step={1}
            valueLabelDisplay="auto"
            valueLabelFormat={(v) => (v === 0 ? '无' : `${v}子`)}
          />
        </Box>

        {/* Komi (free mode, no handicap only) */}
        {!isRanked && handicap === 0 && (
          <Box sx={{ mb: 2.5 }}>
            <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
              贴目: {komi}
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
            label="用时"
          />
        </Box>

        {(isRanked || timeEnabled) && (
          <>
            <Box sx={{ mb: 2.5 }}>
              <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
                主时间: {mainTime === 0 ? '不限' : `${mainTime}分`}
              </Typography>
              <Slider
                value={mainTime}
                onChange={(_, v) => setMainTime(v as number)}
                min={0}
                max={60}
                step={null}
                marks={[
                  { value: 0, label: '不限' },
                  { value: 5, label: '5分' },
                  { value: 10, label: '10分' },
                  { value: 20, label: '20分' },
                  { value: 30, label: '30分' },
                  { value: 60, label: '60分' },
                ]}
              />
            </Box>

            <Box sx={{ mb: 2.5 }}>
              <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
                读秒时间: {byoyomiTime}秒
              </Typography>
              <Slider
                value={byoyomiTime}
                onChange={(_, v) => setByoyomiTime(v as number)}
                min={10}
                max={60}
                step={null}
                marks={[
                  { value: 10, label: '10秒' },
                  { value: 20, label: '20秒' },
                  { value: 30, label: '30秒' },
                  { value: 60, label: '60秒' },
                ]}
              />
            </Box>

            <Box sx={{ mb: 2.5 }}>
              <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
                读秒次数: {byoyomiPeriods}次
              </Typography>
              <Slider
                value={byoyomiPeriods}
                onChange={(_, v) => setByoyomiPeriods(v as number)}
                min={1}
                max={5}
                step={null}
                marks={[
                  { value: 1, label: '1次' },
                  { value: 3, label: '3次' },
                  { value: 5, label: '5次' },
                ]}
              />
            </Box>
          </>
        )}

        <Box sx={{ mt: 'auto', pt: 2 }}>
          <Button variant="contained" fullWidth size="large" startIcon={<PlayArrow />} onClick={handleStart} sx={{ minHeight: 56, py: 2, fontSize: '1.1rem' }}>
            开始对弈
          </Button>
        </Box>
      </Box>
    </Box>
  );
};

export default AiSetupPage;
