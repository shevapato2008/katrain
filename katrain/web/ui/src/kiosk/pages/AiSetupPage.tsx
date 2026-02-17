import { useState } from 'react';
import { Box, Typography, Button, Slider } from '@mui/material';
import { useParams, useNavigate } from 'react-router-dom';
import { PlayArrow, ArrowBack } from '@mui/icons-material';
import OptionChips from '../components/common/OptionChips';

const AiSetupPage = () => {
  const { mode } = useParams<{ mode: string }>();
  const navigate = useNavigate();
  const isRanked = mode === 'ranked';

  const [boardSize, setBoardSize] = useState(19);
  const [color, setColor] = useState<'black' | 'white'>('black');
  const [aiStrength, setAiStrength] = useState(5);
  const [handicap, setHandicap] = useState(0);
  const [timeLimit, setTimeLimit] = useState(0);

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

        <OptionChips
          label="棋盘"
          options={[{ value: 9, label: '9路' }, { value: 13, label: '13路' }, { value: 19, label: '19路' }]}
          value={boardSize}
          onChange={setBoardSize}
        />

        <OptionChips
          label="我执"
          options={[{ value: 'black' as const, label: '● 黑' }, { value: 'white' as const, label: '○ 白' }]}
          value={color}
          onChange={setColor}
        />

        {!isRanked && (
          <Box sx={{ mb: 2.5 }}>
            <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
              AI 强度: ~{aiStrength}D
            </Typography>
            <Slider value={aiStrength} onChange={(_, v) => setAiStrength(v as number)} min={-20} max={9} step={1} />
          </Box>
        )}

        <OptionChips
          label="让子"
          options={[0, 2, 3, 4, 5, 6].map((n) => ({ value: n, label: n === 0 ? '无' : `${n}子` }))}
          value={handicap}
          onChange={setHandicap}
        />

        <OptionChips
          label="用时"
          options={[{ value: 0, label: '不限' }, { value: 10, label: '10分' }, { value: 20, label: '20分' }, { value: 30, label: '30分' }]}
          value={timeLimit}
          onChange={setTimeLimit}
        />

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
