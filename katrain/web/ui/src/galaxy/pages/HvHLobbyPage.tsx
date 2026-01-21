import { useState, useEffect, useRef } from 'react';
import { Box, Typography, Button, Avatar, Chip, Stack, CircularProgress, Alert, Divider, Dialog, DialogTitle, DialogContent, DialogActions, Card, CardContent, Snackbar } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import PeopleIcon from '@mui/icons-material/People';
import SportsEsportsIcon from '@mui/icons-material/SportsEsports';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { useAuth } from '../context/AuthContext';
import FriendsPanel from '../components/FriendsPanel';
import { i18n } from '../../../i18n';

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

const HvHLobbyPage = () => {
    const navigate = useNavigate();
    const { user, token } = useAuth();
    const [onlineUsers, setOnlineUsers] = useState<OnlineUser[]>([]);
    const [activeGames, setActiveGames] = useState<ActiveGame[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isMatching, setIsRatedMatching] = useState(false);
    const [queueTime, setQueueTime] = useState(0);
    const [invitation, setInvitation] = useState<{from_id: number, from_name: string, mode: string} | null>(null);
    const [snackbar, setSnackbar] = useState<{message: string, severity: 'info' | 'error' | 'success'} | null>(null);
    const wsRef = useRef<WebSocket | null>(null);
    const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const fetchOnlineUsers = async () => {
        if (!token) return;
        try {
            const response = await fetch('/api/v1/users/online', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.ok) {
                const data = await response.json();
                setOnlineUsers(data);
            } else {
                setError("Failed to fetch online users");
            }
        } catch (err) {
            setError("Network error");
        }
    };

    const fetchActiveGames = async () => {
        try {
            const response = await fetch('/api/v1/games/active/multiplayer', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.ok) {
                const data = await response.json();
                setActiveGames(data);
            }
        } catch (err) {
            console.error("Failed to fetch active games", err);
        }
    };

    const fetchData = async () => {
        setLoading(true);
        await Promise.all([fetchOnlineUsers(), fetchActiveGames()]);
        setLoading(false);
    };

    useEffect(() => {
        if (!token) return;
        
        fetchData();
        const refreshInterval = setInterval(() => {
            fetchOnlineUsers();
            fetchActiveGames();
        }, 10000);
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/lobby?token=${token}`;
        console.log("Connecting to Lobby WebSocket:", wsUrl);
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
            console.log("Lobby WebSocket connected");
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'match_found') {
                setIsRatedMatching(false);
                // Redirect to room
                console.log("Match Found!", data);
                navigate(`/galaxy/play/human/room/${data.session_id}`);
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
            alert("You must complete your AI Rating series (3 games) before playing Rated HvH matches.");
            navigate('/galaxy/play/ai?mode=rated');
            return;
        }

        wsRef.current.send(JSON.stringify({ type: 'start_matchmaking', game_type: gameType }));
        setIsRatedMatching(true);
        setQueueTime(0);
        timerRef.current = setInterval(() => {
            setQueueTime(prev => prev + 1);
        }, 1000);
    };

    const stopMatchmaking = () => {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: 'stop_matchmaking' }));
        }
        setIsRatedMatching(false);
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
        <Box sx={{ p: 4, height: '100%', overflow: 'auto' }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 4 }}>
                <Box>
                    <Typography variant="h4" fontWeight="bold" gutterBottom>{i18n.t('lobby:title', 'Multiplayer Lobby')}</Typography>
                    <Typography variant="body1" color="text.secondary">{i18n.t('lobby:subtitle', 'Play against other humans or watch live games.')}</Typography>
                </Box>
                <Stack direction="row" spacing={2}>
                    <Button variant="contained" color="primary" size="large" startIcon={<SportsEsportsIcon />} onClick={() => startMatchmaking('rated')}>
                        {i18n.t('lobby:quick_match_rated', 'Quick Match (Rated)')}
                    </Button>
                    <Button variant="outlined" color="primary" size="large" onClick={() => startMatchmaking('free')}>
                        {i18n.t('lobby:custom_game', 'Custom Game')}
                    </Button>
                </Stack>
            </Stack>

            <Dialog open={isMatching} onClose={stopMatchmaking} maxWidth="xs" fullWidth>
                <DialogTitle sx={{ textAlign: 'center', pt: 4 }}>{i18n.t('lobby:finding_opponent', 'Finding Opponent...')}</DialogTitle>
                <DialogContent sx={{ textAlign: 'center', pb: 4 }}>
                    <CircularProgress size={60} sx={{ my: 3 }} />
                    <Typography variant="h6">{formatQueueTime(queueTime)}</Typography>
                    <Typography variant="body2" color="text.secondary">{i18n.t('lobby:matching_desc', 'Looking for a suitable match for you.')}</Typography>
                </DialogContent>
                <DialogActions sx={{ justifyContent: 'center', pb: 3 }}>
                    <Button onClick={stopMatchmaking} color="error" variant="outlined">{i18n.t('cancel', 'Cancel')}</Button>
                </DialogActions>
            </Dialog>

            <Box sx={{ display: 'flex', gap: 4, flexDirection: { xs: 'column', md: 'row' } }}>
                {/* Online Players Section */}
                <Box sx={{ width: { xs: '100%', md: '30%' }, minWidth: 250 }}>
                    <Card sx={{ bgcolor: 'background.paper', height: '100%' }}>
                        <CardContent>
                            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
                                <PeopleIcon color="primary" />
                                <Typography variant="h6">{i18n.t('lobby:online_players', 'Online Players')} ({onlineUsers.length})</Typography>
                            </Stack>
                            <Divider sx={{ mb: 2 }} />
                            
                            {loading && onlineUsers.length === 0 ? (
                                <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}><CircularProgress /></Box>
                            ) : error ? (
                                <Alert severity="error">{error}</Alert>
                            ) : (
                                <Stack spacing={2}>
                                    {onlineUsers.map((u) => (
                                        <Box key={u.id} sx={{ p: 1.5, borderRadius: 2, bgcolor: 'background.default', display: 'flex', alignItems: 'center', gap: 2, border: u.id === user?.id ? '1px solid rgba(74, 107, 92, 0.5)' : 'none' }}>
                                            <Avatar sx={{ bgcolor: u.id === user?.id ? 'secondary.main' : 'primary.main' }}>{u.username[0].toUpperCase()}</Avatar>
                                            <Box sx={{ flexGrow: 1 }}>
                                                <Typography variant="subtitle2">
                                                    {u.username} {u.id === user?.id && <Typography component="span" variant="caption" color="secondary">({i18n.t('lobby:you', 'You')})</Typography>}
                                                </Typography>
                                                <Chip 
                                                    label={(u.rank === '20k' && (!u.elo_points || u.elo_points === 0)) ? i18n.t('lobby:no_rank', 'No Rank') : u.rank} 
                                                    size="small" 
                                                    variant="outlined" 
                                                    sx={{ height: 20 }} 
                                                />
                                            </Box>
                                            {u.id !== user?.id && (
                                                <Button size="small" variant="text" onClick={() => handleInvite(u.id)}>{i18n.t('lobby:invite', 'Invite')}</Button>
                                            )}
                                        </Box>
                                    ))}
                                    {onlineUsers.length === 0 && (
                                        <Typography variant="body2" color="text.secondary" textAlign="center">{i18n.t('lobby:no_players', 'No other players online.')}</Typography>
                                    )}
                                </Stack>
                            )}
                        </CardContent>
                    </Card>
                </Box>

                {/* Active Games Section */}
                <Box sx={{ flexGrow: 1 }}>
                    <Card sx={{ bgcolor: 'background.paper', height: '100%' }}>
                        <CardContent>
                            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
                                <SportsEsportsIcon color="secondary" />
                                <Typography variant="h6">{i18n.t('lobby:active_games', 'Active Games')}</Typography>
                            </Stack>
                            <Divider sx={{ mb: 2 }} />
                            
                            {activeGames.length === 0 ? (
                                <Box sx={{ p: 4, textAlign: 'center', bgcolor: 'background.default', borderRadius: 2 }}>
                                    <Typography variant="body1" color="text.secondary">{i18n.t('lobby:no_active_games', 'No active games at the moment.')}</Typography>
                                    <Typography variant="caption" color="text.secondary">{i18n.t('lobby:active_games_desc', 'Games will appear here once matchmaking is functional.')}</Typography>
                                </Box>
                            ) : (
                                <Stack spacing={2}>
                                    {activeGames.map((game) => (
                                        <Card key={game.session_id} variant="outlined" sx={{ bgcolor: 'background.default' }}>
                                            <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
                                                <Stack direction="row" justifyContent="space-between" alignItems="center">
                                                    <Box>
                                                        <Typography variant="subtitle2">
                                                            {game.player_b} (B) vs {game.player_w} (W)
                                                        </Typography>
                                                        <Typography variant="caption" color="text.secondary">
                                                            {i18n.t('Moves', 'Moves')}: {game.move_count} | {i18n.t('Spectators', 'Spectators')}: {game.spectator_count}
                                                        </Typography>
                                                    </Box>
                                                    <Button 
                                                        size="small" 
                                                        variant="contained" 
                                                        color="secondary"
                                                        startIcon={<VisibilityIcon />}
                                                        onClick={() => navigate(`/galaxy/play/human/room/${game.session_id}`)}
                                                    >
                                                        {i18n.t('lobby:watch', 'Watch')}
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

                {/* Friends Panel */}
                <Box sx={{ width: { xs: '100%', md: '300px' }, flexShrink: 0, display: { xs: 'none', lg: 'block' } }}>
                    <FriendsPanel />
                </Box>
            </Box>

            <Dialog open={!!invitation} onClose={() => setInvitation(null)}>
                <DialogTitle>{i18n.t('lobby:invitation_title', 'Game Invitation')}</DialogTitle>
                <DialogContent>
                    <Typography>
                        {i18n.t('lobby:invitation_text', '{{name}} invited you to a game.').replace('{{name}}', invitation?.from_name || '')}
                    </Typography>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setInvitation(null)}>{i18n.t('lobby:decline', 'Decline')}</Button>
                    <Button onClick={handleAcceptInvite} variant="contained">{i18n.t('lobby:accept', 'Accept')}</Button>
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

export default HvHLobbyPage;
