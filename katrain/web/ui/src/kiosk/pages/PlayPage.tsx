import { Box, Typography, ButtonBase } from '@mui/material';
import { SmartToy, SportsEsports, Hub, Groups, Public } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import ModeCard from '../components/common/ModeCard';
import { useTranslation } from '../../hooks/useTranslation';
import { useAuth } from '../../context/AuthContext';
import { readActiveSession } from '../utils/activeSession';

// Brand serif (artifact `--serif`), used only for the greeting h1.
const SERIF = "'Newsreader','Noto Serif SC',serif";

// Small section label — artifact renders these as a quiet caption above each grid,
// NOT a big heading (variant h6 pushed the cards down and out of the viewport).
const sectionLabelSx = { fontSize: 13, fontWeight: 600, color: 'text.secondary', mt: 0.5 } as const;

/**
 * Route: play — the 对弈 hub. Layout mirrors play-hub-states.html §01 (基准态·横屏 1024×600):
 * greeting → optional 继续上一局 resume bar → 人机对弈 (3 compact cards) → 人人对弈 (3 compact cards),
 * all sized to fit the 464px content area without scrolling. The left 智能棋盘 console is rendered
 * by KioskLayout (not here); this page owns only the right column.
 */
const PlayPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user } = useAuth();
  const resume = readActiveSession('game');

  const hour = new Date().getHours();
  const [greetKey, greetZh] =
    hour < 6 ? ['Late night', '夜深了'] :
    hour < 11 ? ['Good morning', '早上好'] :
    hour < 13 ? ['Good noon', '中午好'] :
    hour < 18 ? ['Good afternoon', '下午好'] :
    ['Good evening', '晚上好'];

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.25, px: 2.5, py: 2, height: '100%', overflow: 'hidden' }}>
      {/* Greeting (artifact .greet: serif h1 + sub) */}
      <Box>
        <Typography component="h1" sx={{ fontFamily: SERIF, fontWeight: 500, fontSize: 20, color: 'text.primary', lineHeight: 1.2 }}>
          {t(greetKey, greetZh)}
          {user?.username && (
            <>
              ，<Box component="span" sx={{ color: 'primary.main', fontWeight: 600 }}>{user.username}</Box>
            </>
          )}
        </Typography>
        <Typography sx={{ fontSize: 12, color: 'text.secondary', mt: '2px' }}>
          {t('Choose a way to start playing', '选择一种方式开始对弈')}
        </Typography>
      </Box>

      {/* 继续上一局 — compact resume bar (artifact .resume), only when a game is in progress */}
      {resume && (
        <ButtonBase
          onClick={() => navigate(resume.route)}
          data-testid="resume-game-bar"
          sx={{
            display: 'flex', alignItems: 'center', gap: 1.5, width: '100%', textAlign: 'left',
            px: '13px', py: '9px', borderRadius: '12px', border: '1px solid', borderColor: 'divider',
            bgcolor: 'var(--raise2)',
          }}
        >
          <Box sx={{ width: 6, height: 28, borderRadius: '5px', bgcolor: 'warning.main', flexShrink: 0 }} />
          <Box sx={{ minWidth: 0, flex: 1 }}>
            <Typography sx={{ fontSize: 13, fontWeight: 600, color: 'text.primary' }}>
              {t('Resume last game', '继续上一局')}
            </Typography>
            <Typography sx={{ fontSize: 11, color: 'text.secondary', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {resume.label}
            </Typography>
          </Box>
          <Box sx={{ fontSize: 11.5, color: 'warning.main', border: '1px solid', borderColor: 'rgba(224,162,74,.4)', px: 1.25, py: 0.5, borderRadius: '20px', flexShrink: 0 }}>
            {t('Resume', '恢复')}
          </Box>
        </ButtonBase>
      )}

      {/* 人机对弈 */}
      <Typography sx={sectionLabelSx}>{t('Play vs AI', '人机对弈')}</Typography>
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1.5 }}>
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

      {/* 人人对弈 */}
      <Typography sx={sectionLabelSx}>{t('Play vs Human', '人人对弈')}</Typography>
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1.5 }}>
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

      {/* 对局历史 — compact secondary entry, mirrors the resume-bar ButtonBase style.
          Deliberately not a 4th ModeCard: the grid above is a fixed repeat(3,1fr). */}
      <ButtonBase
        onClick={() => navigate('/kiosk/play/pvp/history')}
        data-testid="game-history-entry"
        sx={{
          mt: 0.5, alignSelf: 'flex-start', px: 1.5, py: 0.75, borderRadius: '10px',
          border: '1px solid', borderColor: 'divider', color: 'text.secondary', fontSize: 13,
        }}
      >
        {t('Game History', '对局历史')} ›
      </ButtonBase>
    </Box>
  );
};

export default PlayPage;
