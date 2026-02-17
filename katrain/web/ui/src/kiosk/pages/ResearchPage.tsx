import { Box, Typography, Divider } from '@mui/material';
import MockBoard from '../components/game/MockBoard';
import { mockGameState } from '../data/mocks';

const ResearchPage = () => {
  return (
    <Box sx={{ display: 'flex', height: '100%' }}>
      <Box sx={{ height: '100%', aspectRatio: '1', flexShrink: 0 }}>
        <MockBoard moveNumber={0} />
      </Box>
      <Box sx={{ flex: 1, p: 2, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 1.5 }}>
        <Typography variant="h5">研究</Typography>
        <Divider />
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
          导入 SGF 或开始空白棋盘研究
        </Typography>
        <Box sx={{ mt: 1 }}>
          <Typography variant="body2" sx={{ color: 'text.secondary', mb: 0.5 }}>AI 推荐</Typography>
          <Typography sx={{ color: 'primary.main', fontWeight: 600 }}>{mockGameState.bestMove}</Typography>
          <Typography variant="caption" sx={{ fontFamily: "'JetBrains Mono', monospace" }}>
            {mockGameState.bestMoveProb.toFixed(1)}%
          </Typography>
        </Box>
        <Box sx={{ mt: 1 }}>
          <Typography variant="body2" sx={{ color: 'text.secondary', mb: 0.5 }}>胜率</Typography>
          <Typography sx={{ fontFamily: "'JetBrains Mono', monospace", fontWeight: 600 }}>
            {mockGameState.winRate.toFixed(1)}%
          </Typography>
        </Box>
      </Box>
    </Box>
  );
};

export default ResearchPage;
