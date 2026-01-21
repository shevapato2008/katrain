import { useState, useEffect } from 'react';
import { Box, Typography, List, ListItem, ListItemAvatar, ListItemText, Avatar, Divider, Chip, CircularProgress, Alert, IconButton } from '@mui/material';
import PersonRemoveIcon from '@mui/icons-material/PersonRemove';
import { useAuth } from '../context/AuthContext';
import { i18n } from '../../i18n';

interface Friend {
    id: number;
    username: string;
    rank: string;
    avatar_url?: string;
}

const FriendsPanel = ({ noBorder }: { noBorder?: boolean }) => {
    const { user, token } = useAuth();
    const [following, setFollowing] = useState<Friend[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchFollowing = async () => {
        if (!token) return;
        setLoading(true);
        try {
            const response = await fetch('/api/v1/users/following', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.ok) {
                const data = await response.json();
                setFollowing(data);
            } else {
                setError("Failed to fetch friends");
            }
        } catch (err) {
            setError("Network error");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchFollowing();
    }, [token]);

    const handleUnfollow = async (username: string) => {
        try {
            const response = await fetch(`/api/v1/users/follow/${username}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.ok) {
                setFollowing(prev => prev.filter(f => f.username !== username));
            }
        } catch (err) {
            console.error("Failed to unfollow", err);
        }
    };

    if (!user) return null;

    return (
        <Box sx={{
            width: 300,
            height: '100%',
            bgcolor: 'background.paper',
            border: 'none',
            borderLeft: noBorder ? 'none' : '1px solid rgba(255,255,255,0.05)',
            boxShadow: 'none',
            display: 'flex',
            flexDirection: 'column'
        }}>
            <Box sx={{ p: 2, bgcolor: 'rgba(0,0,0,0.1)' }}>
                <Typography variant="h6" fontWeight="bold">{i18n.t('Friends & Following', 'Friends & Following')}</Typography>
            </Box>
            <Divider />
            
            {loading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}><CircularProgress size={24} /></Box>
            ) : error ? (
                <Alert severity="error" sx={{ m: 1 }}>{i18n.t(error, error)}</Alert>
            ) : following.length === 0 ? (
                <Box sx={{ p: 3, textAlign: 'center' }}>
                    <Typography variant="body2" color="text.secondary">{i18n.t('no_friends_desc', 'You are not following anyone yet.')}</Typography>
                </Box>
            ) : (
                <List sx={{ flexGrow: 1, overflow: 'auto' }}>
                    {following.map((friend) => (
                        <ListItem 
                            key={friend.id}
                            secondaryAction={
                                <IconButton edge="end" size="small" onClick={() => handleUnfollow(friend.username)}>
                                    <PersonRemoveIcon fontSize="small" />
                                </IconButton>
                            }
                        >
                            <ListItemAvatar>
                                <Avatar src={friend.avatar_url} sx={{ bgcolor: 'primary.main' }}>
                                    {friend.username[0].toUpperCase()}
                                </Avatar>
                            </ListItemAvatar>
                            <ListItemText 
                                primary={friend.username}
                                secondary={
                                    <Chip label={friend.rank} size="small" variant="outlined" sx={{ height: 16, fontSize: '0.65rem' }} />
                                }
                            />
                        </ListItem>
                    ))}
                </List>
            )}
        </Box>
    );
};

export default FriendsPanel;
