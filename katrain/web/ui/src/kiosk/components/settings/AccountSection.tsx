import { useState } from 'react';
import { Box, Typography, Button, Chip, Dialog, DialogContent, DialogTitle, LinearProgress, Stack } from '@mui/material';
import LogoutIcon from '@mui/icons-material/Logout';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../../context/AuthContext';
import { useTranslation } from '../../../hooks/useTranslation';
import { useAiLadderStatus } from '../../../features/aiLadder/useAiLadderStatus';
import AiLadderStatusCard from '../../../features/aiLadder/AiLadderStatusCard';

export default function AccountSection() {
  const { user, logout, token } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { status, retry } = useAiLadderStatus(token ?? undefined, Boolean(user));
  const [detailsOpen, setDetailsOpen] = useState(false);

  const handleLogout = async () => {
    await logout();
    navigate('/kiosk/login', { replace: true });
  };

  return (
    <Box>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          bgcolor: 'background.paper',
          border: '1px solid',
          borderColor: 'divider',
          borderRadius: 2,
          px: 2,
          py: 1.5,
          mb: 1.5,
        }}
      >
        <Box>
          <Typography variant="body1" sx={{ color: 'text.primary', fontWeight: 600 }}>
            {user?.username ?? t('Guest', '访客')}
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            {t('Signed in', '已登录')} · {t('StellaBox account', '智星盒账户')}
          </Typography>
        </Box>
      </Box>
      {user && status.view_state === 'ready' && (() => {
        const placement = status.placement_state;
        const entry = placement.phase === 'placed' ? placement.rung : status.current_opponent;
        const score = status.net_score > 0 ? `+${status.net_score}` : String(status.net_score);
        return <Box data-testid="ai-ladder-account-summary" sx={{ maxHeight: 132, overflow: 'hidden', mb: 1 }}>
          <Stack spacing={0.5}>
            <Stack direction="row" justifyContent="space-between" alignItems="center">
              <Typography fontWeight={700}>{placement.phase === 'placed' ? `AI段位：${placement.rung.rank_name}` : `定级进度 ${placement.completed_games}/5`}</Typography>
              <Typography fontWeight={700}>累计净胜分：{score}</Typography>
            </Stack>
            <LinearProgress variant="determinate" value={((status.net_score + 3) / 6) * 100} aria-label="累计净胜分进度" />
            {entry && <Stack direction="row" spacing={0.75}>
              <Chip size="small" label={entry.certification_status === 'certified' ? '已认证' : '认证中'} />
              <Chip size="small" label={entry.route === 'local' ? '本地对弈' : '服务器对弈'} />
            </Stack>}
            <Button size="small" variant="text" onClick={() => setDetailsOpen(true)} sx={{ alignSelf: 'flex-start', minHeight: 30 }}>查看AI段位详情</Button>
          </Stack>
        </Box>;
      })()}
      {user && status.view_state !== 'ready' && <Box sx={{ mb: 1 }}><AiLadderStatusCard status={status} onRetry={retry} compact /></Box>}
      <Dialog open={detailsOpen} onClose={() => setDetailsOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>AI段位详情</DialogTitle>
        <DialogContent><AiLadderStatusCard status={status} onRetry={retry} compact /></DialogContent>
      </Dialog>
      <Button
        variant="outlined"
        color="error"
        startIcon={<LogoutIcon />}
        onClick={handleLogout}
        data-testid="settings-logout"
        fullWidth
      >
        {t('Sign out', '退出登录')}
      </Button>
    </Box>
  );
}
