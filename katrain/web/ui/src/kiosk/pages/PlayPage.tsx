import { Box, Typography } from '@mui/material';
import { SportsEsports, EmojiEvents, Handshake, Public } from '@mui/icons-material';
import ModeCard from '../components/common/ModeCard';

const PlayPage = () => {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, p: 3, height: '100%', overflow: 'auto' }}>
      <Typography variant="h5" sx={{ color: 'text.secondary' }}>人机对弈</Typography>
      <Box sx={{ display: 'flex', gap: 3, flex: 1 }}>
        <ModeCard
          title="自由对弈"
          subtitle="随意选择AI强度和棋盘设置"
          icon={<SportsEsports fontSize="inherit" />}
          to="/kiosk/play/ai/setup/free"
        />
        <ModeCard
          title="升降级对弈"
          subtitle="根据实力自动匹配AI难度"
          icon={<EmojiEvents fontSize="inherit" />}
          to="/kiosk/play/ai/setup/ranked"
        />
      </Box>
      <Typography variant="h5" sx={{ color: 'text.secondary' }}>人人对弈</Typography>
      <Box sx={{ display: 'flex', gap: 3, flex: 1 }}>
        <ModeCard
          title="本地对局"
          subtitle="两人在智能棋盘上面对面对弈"
          icon={<Handshake fontSize="inherit" />}
          to="/kiosk/play/pvp/setup"
        />
        <ModeCard
          title="在线大厅"
          subtitle="匹配网络上的对手进行对弈"
          icon={<Public fontSize="inherit" />}
          to="/kiosk/play/pvp/lobby"
        />
      </Box>
    </Box>
  );
};

export default PlayPage;
