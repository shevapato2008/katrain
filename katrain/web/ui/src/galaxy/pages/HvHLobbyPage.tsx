import { useState, useEffect } from 'react';
import { Box, Typography, Button, Grid, Card, CardContent, Avatar, Chip, Stack, CircularProgress, Alert, Divider } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import PeopleIcon from '@mui/icons-material/People';
import SportsEsportsIcon from '@mui/icons-material/SportsEsports';
import VisibilityIcon from '@mui/icons-material/Visibility';
import { useAuth } from '../context/AuthContext';

interface OnlineUser {
    id: number;
    username: string;
    rank: string;
    avatar_url?: string;
}

const HvHLobbyPage = () => {
    const navigate = useNavigate();
    const { user, token } = useAuth();
    const [onlineUsers, setOnlineUsers] = useState<OnlineUser[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

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
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchOnlineUsers();
        const interval = setInterval(fetchOnlineUsers, 10000); // Refresh every 10s
        return () => clearInterval(interval);
    }, [token]);

    return (
        <Box sx={{ p: 4, height: '100%', overflow: 'auto' }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 4 }}>
                <Box>
                    <Typography variant="h4" fontWeight="bold" gutterBottom>Multiplayer Lobby</Typography>
                    <Typography variant="body1" color="text.secondary">Play against other humans or watch live games.</Typography>
                </Box>
                <Stack direction="row" spacing={2}>
                    <Button variant="contained" color="primary" size="large" startIcon={<SportsEsportsIcon />}>
                        Quick Match (Rated)
                    </Button>
                    <Button variant="outlined" color="primary" size="large">
                        Custom Game
                    </Button>
                </Stack>
            </Stack>

            <Grid container spacing={4}>
                {/* Online Players Section */}
                <Grid item xs={12} md={4}>
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
                                        <Box key={u.id} sx={{ p: 1.5, borderRadius: 2, bgcolor: 'background.default', display: 'flex', alignItems: 'center', gap: 2 }}>
                                            <Avatar sx={{ bgcolor: 'primary.main' }}>{u.username[0].toUpperCase()}</Avatar>
                                            <Box sx={{ flexGrow: 1 }}>
                                                <Typography variant="subtitle2">{u.username}</Typography>
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
                </Grid>

                {/* Active Games Section */}
                <Grid item xs={12} md={8}>
                    <Card sx={{ bgcolor: 'background.paper', height: '100%' }}>
                        <CardContent>
                            <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
                                <SportsEsportsIcon color="secondary" />
                                <Typography variant="h6">Active Games</Typography>
                            </Stack>
                            <Divider sx={{ mb: 2 }} />
                            
                            <Box sx={{ p: 4, textAlign: 'center', bgcolor: 'background.default', borderRadius: 2 }}>
                                <Typography variant="body1" color="text.secondary">No active games at the moment.</Typography>
                                <Typography variant="caption" color="text.secondary">Games will appear here once matchmaking is functional.</Typography>
                            </Box>
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>
        </Box>
    );
};

export default HvHLobbyPage;
