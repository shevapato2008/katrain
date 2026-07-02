import { useEffect, useState } from 'react';
import {
  Box, Typography, Button, Alert, CircularProgress,
  FormControl, InputLabel, Select, MenuItem, type SelectChangeEvent,
} from '@mui/material';
import { useParams, useNavigate } from 'react-router-dom';
import { PlayArrow, ArrowBack } from '@mui/icons-material';
import OptionChips from '../components/common/OptionChips';
import { API, type EngineLevel } from '../../api';
import { useTranslation } from '../../hooks/useTranslation';
import { useAuth } from '../../context/AuthContext';

const PlatformEngineSetupPage = () => {
  const { platform } = useParams<{ platform: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { token } = useAuth();

  const [levels, setLevels] = useState<EngineLevel[]>([]);
  const [levelsLoading, setLevelsLoading] = useState(true);
  const [levelsError, setLevelsError] = useState('');

  const [level, setLevel] = useState<number | null>(null);
  const [humanColor, setHumanColor] = useState<'B' | 'W'>('B');

  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState('');

  useEffect(() => {
    let cancelled = false;
    const fetchLevels = async () => {
      if (!platform || !token) return;
      setLevelsLoading(true);
      setLevelsError('');
      try {
        const { levels: fetched } = await API.platformEngineLevels(platform, token);
        if (cancelled) return;
        setLevels(fetched);
        // Default to a mid/weak level: prefer level_name === '1级', else first row.
        const defaultRow = fetched.find((l) => l.level_name === '1级') || fetched[0];
        if (defaultRow) setLevel(defaultRow.elo_score);
      } catch (e: any) {
        if (!cancelled) setLevelsError(e.message || t('Failed to load levels', '加载棋力等级失败'));
      } finally {
        if (!cancelled) setLevelsLoading(false);
      }
    };
    fetchLevels();
    return () => { cancelled = true; };
  }, [platform, token]);

  const handleLevelChange = (e: SelectChangeEvent<number>) => {
    setLevel(Number(e.target.value));
  };

  const handleStart = async () => {
    if (!platform || !token || level === null) return;
    setStartError('');
    setStarting(true);
    try {
      const { session_id } = await API.platformEngineStart(platform, { level, human_color: humanColor }, token);
      navigate(`/kiosk/play/cross-platform/engine/game/${session_id}`);
    } catch (e: any) {
      setStartError(e.message || t('Failed to start game', '创建对局失败'));
    } finally {
      setStarting(false);
    }
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', p: 3, gap: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <Button
          onClick={() => navigate('/kiosk/play/cross-platform')}
          startIcon={<ArrowBack />}
          sx={{ minWidth: 40, p: 0.5 }}
        />
        <Typography variant="h5">{t('Play vs AI', '人机对弈')}</Typography>
      </Box>

      <Box sx={{ flex: 1, maxWidth: 480, display: 'flex', flexDirection: 'column' }}>
        {levelsLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
            <CircularProgress />
          </Box>
        ) : levelsError ? (
          <Alert severity="error" sx={{ mb: 2 }}>{levelsError}</Alert>
        ) : (
          <>
            {/* Level selector */}
            <Box sx={{ mb: 2.5 }}>
              <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
                {t('AI Level', '棋力等级')}
              </Typography>
              <FormControl fullWidth>
                <InputLabel id="engine-level-label">{t('Level', '等级')}</InputLabel>
                <Select
                  labelId="engine-level-label"
                  label={t('Level', '等级')}
                  value={level ?? ''}
                  onChange={handleLevelChange}
                  sx={{ minHeight: 56 }}
                >
                  {levels.map((l) => (
                    <MenuItem key={l.elo_score} value={l.elo_score}>
                      {`${l.name} · ${l.level_name}`}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Box>

            {/* Color */}
            <OptionChips
              label={t('My Color', '我执')}
              options={[
                { value: 'B' as const, label: t('Black Stone', '● 黑') },
                { value: 'W' as const, label: t('White Stone', '○ 白') },
              ]}
              value={humanColor}
              onChange={setHumanColor}
            />

            {/* Fixed rules info (display only, not editable) */}
            <Typography variant="body2" sx={{ color: 'text.secondary', mb: 2.5 }}>
              {t('Rules: Chinese · Komi 7.5 · 19x19 · Untimed', '规则: 中国 · 贴目 7.5 · 19路 · 不计时')}
            </Typography>

            <Box sx={{ mt: 'auto', pt: 2 }}>
              {startError && <Alert severity="error" sx={{ mb: 2 }}>{startError}</Alert>}
              <Button
                variant="contained"
                fullWidth
                size="large"
                startIcon={<PlayArrow />}
                disabled={starting || level === null}
                onClick={handleStart}
                sx={{ minHeight: 56, py: 2, fontSize: '1.1rem' }}
              >
                {starting ? t('Creating...', '创建中...') : t('Start Game', '开始对弈')}
              </Button>
            </Box>
          </>
        )}
      </Box>
    </Box>
  );
};

export default PlatformEngineSetupPage;
