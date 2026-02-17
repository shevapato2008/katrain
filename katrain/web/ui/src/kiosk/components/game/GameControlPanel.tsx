import { Box, Typography, Button, LinearProgress, Divider } from '@mui/material';
import { Undo, PanTool, Calculate, Flag, Settings, Close } from '@mui/icons-material';

interface Props {
  blackPlayer: string;
  whitePlayer: string;
  blackCaptures: number;
  whiteCaptures: number;
  winRate: number;
  bestMove: string;
  bestMoveProb: number;
  altMove: string;
  altMoveProb: number;
  moveNumber: number;
}

const GameControlPanel = (props: Props) => (
  <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', p: 2, gap: 1.5 }}>
    {/* Players */}
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
        <Typography variant="body1" sx={{ fontWeight: 600 }}>● {props.blackPlayer}</Typography>
        <Typography variant="caption">○提: {props.blackCaptures}</Typography>
      </Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
        <Typography variant="body1" sx={{ fontWeight: 600 }}>○ {props.whitePlayer}</Typography>
        <Typography variant="caption">●提: {props.whiteCaptures}</Typography>
      </Box>
    </Box>

    <Divider />

    {/* Win rate */}
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>胜率</Typography>
        <Typography variant="body1" sx={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}>
          {props.winRate.toFixed(1)}%
        </Typography>
      </Box>
      <LinearProgress
        variant="determinate"
        value={props.winRate}
        sx={{
          height: 8, borderRadius: 4, bgcolor: 'rgba(232,228,220,0.1)',
          '& .MuiLinearProgress-bar': { bgcolor: props.winRate > 50 ? 'success.main' : 'error.main', borderRadius: 4 },
        }}
      />
    </Box>

    {/* AI suggestion */}
    <Box>
      <Typography variant="body2" sx={{ color: 'text.secondary', mb: 0.5 }}>AI 推荐</Typography>
      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
        <Typography sx={{ color: 'primary.main', fontWeight: 600 }}>{props.bestMove}</Typography>
        <Typography variant="caption" sx={{ fontFamily: "'JetBrains Mono', monospace" }}>{props.bestMoveProb.toFixed(1)}%</Typography>
      </Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>{props.altMove}</Typography>
        <Typography variant="caption" sx={{ fontFamily: "'JetBrains Mono', monospace", color: 'text.secondary' }}>{props.altMoveProb.toFixed(1)}%</Typography>
      </Box>
    </Box>

    <Typography variant="caption" sx={{ color: 'text.secondary' }}>第 {props.moveNumber} 手</Typography>

    <Box sx={{ mt: 'auto' }} />

    {/* Controls — 3x2 grid */}
    <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 1 }}>
      <Button variant="outlined" startIcon={<Undo />} sx={{ minHeight: 48 }}>悔棋</Button>
      <Button variant="outlined" startIcon={<PanTool />} sx={{ minHeight: 48 }}>跳过</Button>
      <Button variant="outlined" startIcon={<Calculate />} sx={{ minHeight: 48 }}>计数</Button>
      <Button variant="outlined" color="error" startIcon={<Flag />} sx={{ minHeight: 48 }}>认输</Button>
      <Button variant="outlined" startIcon={<Settings />} sx={{ minHeight: 48 }}>设置</Button>
      <Button variant="outlined" startIcon={<Close />} sx={{ minHeight: 48 }}>退出</Button>
    </Box>
  </Box>
);

export default GameControlPanel;
