import { Box, Typography, ButtonBase } from '@mui/material';
import { SmartToy, SportsEsports, Hub, Groups, Public, PlayArrow } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import ModeCard from '../components/common/ModeCard';
import { useTranslation } from '../../hooks/useTranslation';
import { readActiveSession } from '../utils/activeSession';

const PlayPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const resume = readActiveSession('game');

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, p: 3, height: '100%', overflow: 'auto' }}>
      {resume && (
        <ButtonBase
          onClick={() => navigate(resume.route)}
          data-testid="resume-game-bar"
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 1.5,
            px: 2,
            py: 1.5,
            borderRadius: 2,
            border: '1px solid',
            borderColor: 'warning.main',
            bgcolor: 'var(--raise2)',
            width: '100%',
          }}
        >
          <Typography sx={{ color: 'text.primary' }}>
            {t('Resume last game', '继续上一局')} · {resume.label}
          </Typography>
          <PlayArrow sx={{ color: 'warning.main' }} />
        </ButtonBase>
      )}
      <Typography variant="h6" sx={{ color: 'text.secondary' }}>{t('Play vs AI', '人机对弈')}</Typography>
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 3fr)', gap: 2 }}>
        <ModeCard
          title={t('Free Game', '自由对弈')}
          subtitle={t('Choose AI strength and board settings freely', '随意选择AI强度和棋盘设置')}
          icon={<SmartToy fontSize="inherit" />}
          to="/kiosk/play/ai/setup/free"
          variant="primary"
        />
        <ModeCard
          title={t('Ranked Game', '升降级对弈')}
          subtitle={t('Auto-match AI difficulty based on your skill', '根据实力自动匹配AI难度')}
          icon={<SportsEsports fontSize="inherit" />}
          to="/kiosk/play/ai/setup/ranked"
        />
        <ModeCard
          title={t('Cross-Platform', '跨平台对弈')}
          subtitle={t('Play on OGS, Fox, and more', '连接 OGS、野狐等平台')}
          icon={<Hub fontSize="inherit" />}
          to="/kiosk/play/cross-platform"
        />
      </Box>
      <Typography variant="h6" sx={{ color: 'text.secondary' }}>{t('Play vs Human', '人人对弈')}</Typography>
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 3fr)', gap: 2 }}>
        <ModeCard
          title={t('Local Game', '本地对局')}
          subtitle={t('Play face-to-face on the smart board', '两人在智能棋盘上面对面对弈')}
          icon={<Groups fontSize="inherit" />}
          to="/kiosk/play/pvp/setup"
        />
        <ModeCard
          title={t('Online Lobby', '在线大厅')}
          subtitle={t('Match with online opponents', '匹配网络上的对手进行对弈')}
          icon={<Public fontSize="inherit" />}
          to="/kiosk/play/pvp/lobby"
        />
        <ModeCard
          title={t('Cross-Platform', '跨平台对弈')}
          subtitle={t('Play on OGS, Fox, and more', '连接 OGS、野狐等平台')}
          icon={<Hub fontSize="inherit" />}
          to="/kiosk/play/cross-platform"
        />
      </Box>
    </Box>
  );
};

export default PlayPage;
