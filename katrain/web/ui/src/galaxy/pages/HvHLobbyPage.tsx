import { useState, useEffect, useRef } from 'react';
import { Box, Typography, Button, Avatar, Chip, Stack, CircularProgress, Alert, Divider, Dialog, DialogTitle, DialogContent, DialogActions, Card, CardContent } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import PeopleIcon from '@mui/icons-material/People';
import SportsEsportsIcon from '@mui/icons-material/SportsEsports';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { useAuth } from '../context/AuthContext';
import FriendsPanel from '../components/FriendsPanel';

interface OnlineUser {
    id: number;
    username: string;
    rank: string;
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

    const formatQueueTime = (s: number) => {
        const m = Math.floor(s / 60);
        const sec = s % 60;
        return `${m}:${sec.toString().padStart(2, '0')}`;
    };

    return (
        <Box sx={{ p: 4, height: '100%', overflow: 'auto' }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 4 }}>
                <Box>
                    <Typography variant="h4" fontWeight="bold" gutterBottom>Multiplayer Lobby</Typography>
                    <Typography variant="body1" color="text.secondary">Play against other humans or watch live games.</Typography>
                </Box>
                <Stack direction="row" spacing={2}>
                    <Button variant="contained" color="primary" size="large" startIcon={<SportsEsportsIcon />} onClick={() => startMatchmaking('rated')}>
                        Quick Match (Rated)
                    </Button>
                    <Button variant="outlined" color="primary" size="large" onClick={() => startMatchmaking('free')}>
                        Custom Game
                    </Button>
                </Stack>
            </Stack>

            <Dialog open={isMatching} onClose={stopMatchmaking} maxWidth="xs" fullWidth>
                <DialogTitle sx={{ textAlign: 'center', pt: 4 }}>Finding Opponent...</DialogTitle>
                <DialogContent sx={{ textAlign: 'center', pb: 4 }}>
                    <CircularProgress size={60} sx={{ my: 3 }} />
                    <Typography variant="h6">{formatQueueTime(queueTime)}</Typography>
                    <Typography variant="body2" color="text.secondary">Looking for a suitable match for you.</Typography>
                </DialogContent>
                <DialogActions sx={{ justifyContent: 'center', pb: 3 }}>
                    <Button onClick={stopMatchmaking} color="error" variant="outlined">Cancel</Button>
                </DialogActions>
            </Dialog>

            <Box sx={{ display: 'flex', gap: 4, flexDirection: { xs: 'column', md: 'row' } }}>
                {/* Online Players Section */}
                <Box sx={{ width: { xs: '100%', md: '30%' }, minWidth: 250 }}>
                    <Card sx={{ bgcolor: 'background.paper', height: '100%' }}>
                        <CardContent>
                            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
                                <PeopleIcon color="primary" />
                                <Typography variant="h6">Online Players ({onlineUsers.length})</Typography>
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
                                                    {u.username} {u.id === user?.id && <Typography component="span" variant="caption" color="secondary">(You)</Typography>}
                                                </Typography>
                                                <Chip label={u.rank} size="small" variant="outlined" sx={{ height: 20 }} />
                                            </Box>
                                            {u.id !== user?.id && (
                                                <Button size="small" variant="text">Invite</Button>
                                            )}
                                        </Box>
                                    ))}
                                    {onlineUsers.length === 0 && (
                                        <Typography variant="body2" color="text.secondary" textAlign="center">No other players online.</Typography>
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
                                <Typography variant="h6">Active Games</Typography>
                            </Stack>
                            <Divider sx={{ mb: 2 }} />
                            
                            {activeGames.length === 0 ? (
                                <Box sx={{ p: 4, textAlign: 'center', bgcolor: 'background.default', borderRadius: 2 }}>
                                    <Typography variant="body1" color="text.secondary">No active games at the moment.</Typography>
                                    <Typography variant="caption" color="text.secondary">Games will appear here once matchmaking is functional.</Typography>
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
                                                            Moves: {game.move_count} | Spectators: {game.spectator_count}
                                                        </Typography>
                                                    </Box>
                                                    <Button 
                                                        size="small" 
                                                        variant="contained" 
                                                        color="secondary"
                                                        startIcon={<VisibilityIcon />}
                                                        onClick={() => navigate(`/galaxy/play/human/room/${game.session_id}`)}
                                                    >
                                                        Watch
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
        </Box>
    );
};

export default HvHLobbyPage;
