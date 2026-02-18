import { useState } from 'react';
import {
  Box, Typography, TextField, Select, MenuItem, FormControl, InputLabel,
  Button, Divider, Stack,
} from '@mui/material';
import {
  Science as ScienceIcon,
  FormatListNumbered, PanToolAlt, OpenWith, DeleteForever,
  TipsAndUpdates, Map as MapIcon, FolderOpen, Save,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import MockBoard from '../components/game/MockBoard';
import ItemToggle from '../components/game/ItemToggle';
import { useResearchSession } from '../../hooks/useResearchSession';

const inputSx = {
  '& .MuiInputBase-root': { fontSize: '0.9rem' },
  '& .MuiInputLabel-root': { fontSize: '0.9rem' },
};
const menuItemSx = { fontSize: '0.9rem' };

const ResearchPage = () => {
  const [playerBlack, setPlayerBlack] = useState('');
  const [playerWhite, setPlayerWhite] = useState('');
  const [boardSize, setBoardSize] = useState(19);
  const [rules, setRules] = useState('chinese');
  const [komi, setKomi] = useState(7.5);
  const [handicap, setHandicap] = useState(0);
  const [currentMove] = useState(0);
  const [totalMoves] = useState(0);

  const { createSession } = useResearchSession();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);

  const handleStartResearch = async () => {
    setLoading(true);
    try {
      const sessionId = await createSession();
      if (sessionId) {
        navigate(`/kiosk/research/session/${sessionId}`);
      }
    } catch {
      // Session creation failed
    } finally {
      setLoading(false);
    }
  };

  const [toggles, setToggles] = useState({
    numbers: false,
    hints: false,
    territory: false,
  });
  const toggle = (key: keyof typeof toggles) =>
    setToggles(prev => ({ ...prev, [key]: !prev[key] }));

  return (
    <Box sx={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* Left: Board + Bottom Navigation */}
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', bgcolor: '#0f0f0f' }}>
        <Box sx={{ flexGrow: 1, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
          <MockBoard moveNumber={currentMove} />
        </Box>

        {/* Bottom navigation */}
        <Box
          data-testid="move-navigation"
          sx={{
            px: 3, py: 1.5, bgcolor: '#1a1a1a',
            borderTop: '1px solid rgba(255,255,255,0.05)',
            display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 1,
          }}
        >
          <Button size="small" disabled={currentMove === 0} sx={{ minWidth: 32, color: 'text.secondary' }}>
            ⏮
          </Button>
          <Button size="small" disabled={currentMove === 0} sx={{ minWidth: 32, color: 'text.secondary' }}>
            ◀
          </Button>
          <Typography
            variant="body2"
            sx={{
              mx: 2,
              fontFamily: '"JetBrains Mono", monospace',
              color: 'text.secondary',
              minWidth: 80,
              textAlign: 'center',
            }}
          >
            {currentMove} / {totalMoves} 手
          </Typography>
          <Button size="small" disabled={currentMove >= totalMoves} sx={{ minWidth: 32, color: 'text.secondary' }}>
            ▶
          </Button>
          <Button size="small" disabled={currentMove >= totalMoves} sx={{ minWidth: 32, color: 'text.secondary' }}>
            ⏭
          </Button>
        </Box>
      </Box>

      {/* Right panel */}
      <Box
        sx={{
          flex: 1, display: 'flex', flexDirection: 'column',
          bgcolor: 'background.paper',
          borderLeft: '1px solid rgba(255,255,255,0.05)',
        }}
      >
        <Box sx={{ flexGrow: 1, overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
          {/* Header */}
          <Box sx={{ px: 2, pt: 2, pb: 1 }}>
            <Typography variant="h5">研究</Typography>
          </Box>

          {/* Game Info */}
          <Box sx={{ p: 2 }}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1, fontWeight: 600, letterSpacing: 0.5 }}>
              对局信息
            </Typography>
            <Stack spacing={1.5}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                <Box sx={{ width: 14, height: 14, borderRadius: '50%', bgcolor: '#1a1a1a', border: '1px solid rgba(255,255,255,0.2)', flexShrink: 0 }} />
                <TextField
                  size="small" fullWidth placeholder="黑方"
                  value={playerBlack} onChange={e => setPlayerBlack(e.target.value)}
                  sx={inputSx}
                />
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                <Box sx={{ width: 14, height: 14, borderRadius: '50%', bgcolor: '#f5f5f5', border: '1px solid #666', flexShrink: 0 }} />
                <TextField
                  size="small" fullWidth placeholder="白方"
                  value={playerWhite} onChange={e => setPlayerWhite(e.target.value)}
                  sx={inputSx}
                />
              </Box>
            </Stack>
          </Box>

          <Divider />

          {/* Rules Settings */}
          <Box sx={{ p: 2 }}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5, fontWeight: 600, letterSpacing: 0.5 }}>
              规则设置
            </Typography>
            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.5 }}>
              <FormControl size="small" fullWidth sx={inputSx}>
                <InputLabel>棋盘大小</InputLabel>
                <Select value={boardSize} label="棋盘大小" onChange={e => setBoardSize(Number(e.target.value))}>
                  <MenuItem value={9} sx={menuItemSx}>9x9</MenuItem>
                  <MenuItem value={13} sx={menuItemSx}>13x13</MenuItem>
                  <MenuItem value={19} sx={menuItemSx}>19x19</MenuItem>
                </Select>
              </FormControl>

              <FormControl size="small" fullWidth sx={inputSx}>
                <InputLabel>规则</InputLabel>
                <Select value={rules} label="规则" onChange={e => setRules(e.target.value)}>
                  <MenuItem value="chinese" sx={menuItemSx}>中国规则</MenuItem>
                  <MenuItem value="japanese" sx={menuItemSx}>日本规则</MenuItem>
                  <MenuItem value="korean" sx={menuItemSx}>韩国规则</MenuItem>
                </Select>
              </FormControl>

              <TextField
                size="small" fullWidth label="贴目" type="number"
                value={komi} onChange={e => setKomi(Number(e.target.value))}
                inputProps={{ step: 0.5 }} sx={inputSx}
              />

              <FormControl size="small" fullWidth sx={inputSx}>
                <InputLabel>让子</InputLabel>
                <Select value={handicap} label="让子" onChange={e => setHandicap(Number(e.target.value))}>
                  {[0, 2, 3, 4, 5, 6, 7, 8, 9].map(h => (
                    <MenuItem key={h} value={h} sx={menuItemSx}>{h === 0 ? '无' : `${h}子`}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Box>
          </Box>

          <Divider />

          {/* Edit Tools */}
          <Box sx={{ p: 2 }}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1, fontWeight: 600, letterSpacing: 0.5 }}>
              编辑工具
            </Typography>
            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)' }}>
              <ItemToggle icon={<FormatListNumbered sx={{ fontSize: 26 }} />} label="手数" active={toggles.numbers} onClick={() => toggle('numbers')} />
              <ItemToggle icon={<PanToolAlt sx={{ fontSize: 26 }} />} label="停一手" onClick={() => {}} />
              <ItemToggle icon={<OpenWith sx={{ fontSize: 26 }} />} label="移动" onClick={() => {}} />
              <ItemToggle icon={<DeleteForever sx={{ fontSize: 26 }} />} label="删除" onClick={() => {}} isDestructive />
              <ItemToggle icon={<TipsAndUpdates sx={{ fontSize: 26 }} />} label="建议" active={toggles.hints} onClick={() => toggle('hints')} />
              <ItemToggle icon={<MapIcon sx={{ fontSize: 26 }} />} label="领地" active={toggles.territory} onClick={() => toggle('territory')} />
              <ItemToggle icon={<FolderOpen sx={{ fontSize: 26 }} />} label="打开" onClick={() => {}} />
              <ItemToggle icon={<Save sx={{ fontSize: 26 }} />} label="保存" onClick={() => {}} />
            </Box>
          </Box>
        </Box>

        {/* Bottom: Start Research button */}
        <Box sx={{ p: 2, borderTop: '1px solid rgba(255,255,255,0.05)' }}>
          <Button
            variant="contained"
            fullWidth
            size="large"
            startIcon={<ScienceIcon />}
            onClick={handleStartResearch}
            disabled={loading}
            sx={{
              bgcolor: 'success.main',
              color: '#fff',
              fontWeight: 700,
              fontSize: '1rem',
              py: 1.5,
              '&:hover': { bgcolor: 'success.dark' },
            }}
          >
            {loading ? '创建中...' : '开始研究'}
          </Button>
        </Box>
      </Box>
    </Box>
  );
};

export default ResearchPage;
