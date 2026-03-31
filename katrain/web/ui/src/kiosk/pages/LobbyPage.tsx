import { useState, useEffect, useRef } from 'react';
import {
  Box, Typography, Button, Avatar, Chip, Stack, CircularProgress, Alert,
  Divider, Dialog, DialogTitle, DialogContent, DialogActions, Card,
  CardContent, Snackbar
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { ArrowBack } from '@mui/icons-material';
import PeopleIcon from '@mui/icons-material/People';
import SportsEsportsIcon from '@mui/icons-material/SportsEsports';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { useAuth } from '../../context/AuthContext';
import { i18n } from '../../i18n';

interface OnlineUser {
  id: number;
  username: string;
  rank: string;
  elo_points?: number;
  avatar_url?: string;
}

interface ActiveGame {
  session_id: string;
  player_b: string;
  player_w: string;
  spectator_count: number;
  move_count: number;
}

const LobbyPage = () => {
  const navigate = useNavigate();
  const { user, token } = useAuth();
  const [onlineUsers, setOnlineUsers] = useState<OnlineUser[]>([]);
  const [activeGames, setActiveGames] = useState<ActiveGame[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isMatching, setIsMatching] = useState(false);
  const [queueTime, setQueueTime] = useState(0);
  const [invitation, setInvitation] = useState<{ from_id: number; from_name: string; mode: string } | null>(null);
  const [snackbar, setSnackbar] = useState<{ message: string; severity: 'info' | 'error' | 'success' } | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  if (!token) {
    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2, mt: 8 }}>
        <Alert severity="warning">{i18n.t('lobby:auth_required', '请先登录后使用在线大厅')}</Alert>
        <Button variant="outlined" onClick={() => navigate('/kiosk/login')}>
          {i18n.t('Login', '登录')}
        </Button>
      </Box>
    );
  }

  const fetchOnlineUsers = async () => {
    try {
      const response = await fetch('/api/v1/users/online', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        if (Array.isArray(data)) setOnlineUsers(data);
      } else {
        setError(i18n.t('lobby:fetch_error', '获取在线用户失败'));
      }
    } catch {
      setError(i18n.t('lobby:network_error', '网络错误'));
    }
  };

  const fetchActiveGames = async () => {
    try {
      const response = await fetch('/api/v1/games/active/multiplayer', {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        if (Array.isArray(data)) setActiveGames(data);
      }
    } catch (err) {
      console.error('Failed to fetch active games', err);
    }
  };

  const fetchData = async () => {
    setLoading(true);
    await Promise.all([fetchOnlineUsers(), fetchActiveGames()]);
    setLoading(false);
  };

  useEffect(() => {
    fetchData();
    const refreshInterval = setInterval(() => {
      fetchOnlineUsers();
      fetchActiveGames();
    }, 10000);

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/lobby?token=${token}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'match_found') {
        setIsMatching(false);
        navigate(`/kiosk/play/pvp/room/${data.session_id}`);
      } else if (data.type === 'lobby_update') {
        fetchOnlineUsers();
      } else if (data.type === 'invitation') {
        setInvitation({ from_id: data.from_id, from_name: data.from_name, mode: data.mode });
      } else if (data.type === 'info') {
        setSnackbar({ message: data.message, severity: 'info' });
      } else if (data.type === 'error') {
        setSnackbar({ message: data.message, severity: 'error' });
      }
    };

    return () => {
      ws.close();
      clearInterval(refreshInterval);
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [token]);

  const startMatchmaking = (gameType: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

    if (gameType === 'rated' && user?.rank === '20k') {
      alert(i18n.t('lobby:rank_required', '请先完成AI定级赛（3局）后再进行排位对局'));
      navigate('/kiosk/play/ai/setup/ranked');
      return;
    }

    wsRef.current.send(JSON.stringify({ type: 'start_matchmaking', game_type: gameType }));
    setIsMatching(true);
    setQueueTime(0);
    timerRef.current = setInterval(() => {
      setQueueTime(prev => prev + 1);
    }, 1000);
  };

  const stopMatchmaking = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'stop_matchmaking' }));
    }
    setIsMatching(false);
    if (timerRef.current) clearInterval(timerRef.current);
  };

  const handleInvite = (targetId: number) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'invite', target_id: targetId }));
    }
  };

  const handleAcceptInvite = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN && invitation) {
      wsRef.current.send(JSON.stringify({ type: 'accept_invite', target_id: invitation.from_id }));
      setInvitation(null);
    }
  };

  const formatQueueTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, '0')}`;
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, px: 2, pt: 2, pb: 1 }}>
        <Button onClick={() => navigate('/kiosk/play')} startIcon={<ArrowBack />} sx={{ minWidth: 40, p: 0.5 }} />
        <Box sx={{ flex: 1 }}>
          <Typography variant="h5">{i18n.t('lobby:title', '在线大厅')}</Typography>
          <Typography variant="body2" color="text.secondary">{i18n.t('lobby:subtitle', '与其他玩家对弈或观战')}</Typography>
        </Box>
        <Stack direction="row" spacing={1}>
          <Button variant="contained" size="small" startIcon={<SportsEsportsIcon />} onClick={() => startMatchmaking('rated')}>
            {i18n.t('lobby:quick_match_rated', '排位赛')}
          </Button>
          <Button variant="outlined" size="small" onClick={() => startMatchmaking('free')}>
            {i18n.t('lobby:custom_game', '自由对局')}
          </Button>
        </Stack>
      </Box>

      {/* Matchmaking dialog */}
      <Dialog open={isMatching} onClose={stopMatchmaking} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ textAlign: 'center', pt: 3 }}>{i18n.t('lobby:finding_opponent', '正在匹配...')}</DialogTitle>
        <DialogContent sx={{ textAlign: 'center', pb: 3 }}>
          <CircularProgress size={48} sx={{ my: 2 }} />
          <Typography variant="h6">{formatQueueTime(queueTime)}</Typography>
          <Typography variant="body2" color="text.secondary">{i18n.t('lobby:matching_desc', '正在为您寻找合适的对手')}</Typography>
        </DialogContent>
        <DialogActions sx={{ justifyContent: 'center', pb: 2 }}>
          <Button onClick={stopMatchmaking} color="error" variant="outlined">{i18n.t('cancel', '取消')}</Button>
        </DialogActions>
      </Dialog>

      {/* Content: two-column layout */}
      <Box sx={{ flex: 1, overflow: 'auto', display: 'flex', gap: 2, p: 2, pt: 1 }}>
        {/* Online Players */}
        <Card sx={{ width: '40%', minWidth: 200, flexShrink: 0, bgcolor: 'rgba(255,255,255,0.05)' }}>
          <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
              <PeopleIcon color="primary" fontSize="small" />
              <Typography variant="subtitle1">{i18n.t('lobby:online_players', '在线玩家')} ({onlineUsers.length})</Typography>
            </Stack>
            <Divider sx={{ mb: 1 }} />

            {loading && onlineUsers.length === 0 ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}><CircularProgress size={32} /></Box>
            ) : error ? (
              <Alert severity="error" sx={{ fontSize: '0.75rem' }}>{error}</Alert>
            ) : (
              <Stack spacing={1}>
                {onlineUsers.map((u) => (
                  <Box key={u.id} sx={{
                    p: 1, borderRadius: 1.5, bgcolor: 'rgba(255,255,255,0.03)',
                    display: 'flex', alignItems: 'center', gap: 1,
                    border: u.id === user?.id ? '1px solid rgba(74, 107, 92, 0.5)' : 'none'
                  }}>
                    <Avatar sx={{ width: 32, height: 32, fontSize: '0.875rem', bgcolor: u.id === user?.id ? 'secondary.main' : 'primary.main' }}>
                      {u.username?.[0]?.toUpperCase() || '?'}
                    </Avatar>
                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Typography variant="body2" noWrap>
                        {u.username} {u.id === user?.id && <Typography component="span" variant="caption" color="secondary">({i18n.t('lobby:you', '你')})</Typography>}
                      </Typography>
                      <Chip
                        label={(u.rank === '20k' && (!u.elo_points || u.elo_points === 0)) ? i18n.t('lobby:no_rank', '无段位') : u.rank}
                        size="small" variant="outlined" sx={{ height: 18, fontSize: '0.65rem' }}
                      />
                    </Box>
                    {u.id !== user?.id && (
                      <Button size="small" variant="text" sx={{ minWidth: 'auto', px: 1, fontSize: '0.75rem' }} onClick={() => handleInvite(u.id)}>
                        {i18n.t('lobby:invite', '邀请')}
                      </Button>
                    )}
                  </Box>
                ))}
                {onlineUsers.length === 0 && (
                  <Typography variant="body2" color="text.secondary" textAlign="center" sx={{ py: 2 }}>
                    {i18n.t('lobby:no_players', '暂无其他在线玩家')}
                  </Typography>
                )}
              </Stack>
            )}
          </CardContent>
        </Card>

        {/* Active Games */}
        <Card sx={{ flex: 1, bgcolor: 'rgba(255,255,255,0.05)' }}>
          <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
              <SportsEsportsIcon color="secondary" fontSize="small" />
              <Typography variant="subtitle1">{i18n.t('lobby:active_games', '进行中的对局')}</Typography>
            </Stack>
            <Divider sx={{ mb: 1 }} />

            {activeGames.length === 0 ? (
              <Box sx={{ p: 3, textAlign: 'center' }}>
                <Typography variant="body2" color="text.secondary">{i18n.t('lobby:no_active_games', '暂无进行中的对局')}</Typography>
              </Box>
            ) : (
              <Stack spacing={1}>
                {activeGames.map((game) => (
                  <Card key={game.session_id} variant="outlined" sx={{ bgcolor: 'rgba(255,255,255,0.03)' }}>
                    <CardContent sx={{ py: 1, px: 1.5, '&:last-child': { pb: 1 } }}>
                      <Stack direction="row" justifyContent="space-between" alignItems="center">
                        <Box>
                          <Typography variant="body2">{game.player_b} (B) vs {game.player_w} (W)</Typography>
                          <Typography variant="caption" color="text.secondary">
                            {i18n.t('Moves', '手数')}: {game.move_count} | {i18n.t('Spectators', '观众')}: {game.spectator_count}
                          </Typography>
                        </Box>
                        <Button
                          size="small" variant="contained" color="secondary"
                          startIcon={<VisibilityIcon />}
                          onClick={() => navigate(`/kiosk/play/pvp/room/${game.session_id}`)}
                          sx={{ minWidth: 'auto', px: 1.5 }}
                        >
                          {i18n.t('lobby:watch', '观战')}
                        </Button>
                      </Stack>
                    </CardContent>
                  </Card>
                ))}
              </Stack>
            )}
          </CardContent>
        </Card>
      </Box>

      {/* Invitation dialog */}
      <Dialog open={!!invitation} onClose={() => setInvitation(null)} maxWidth="xs" fullWidth>
        <DialogTitle>{i18n.t('lobby:invitation_title', '对局邀请')}</DialogTitle>
        <DialogContent>
          <Typography>
            {i18n.t('lobby:invitation_text', '{{name}} 邀请你对弈').replace('{{name}}', invitation?.from_name || '')}
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setInvitation(null)}>{i18n.t('lobby:decline', '拒绝')}</Button>
          <Button onClick={handleAcceptInvite} variant="contained">{i18n.t('lobby:accept', '接受')}</Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={!!snackbar}
        autoHideDuration={6000}
        onClose={() => setSnackbar(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity={snackbar?.severity || 'info'} onClose={() => setSnackbar(null)}>
          {snackbar?.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default LobbyPage;
