import { useState, useEffect } from 'react';
import { Box, Typography, Button, List, ListItem, ListItemButton, ListItemText, Divider, IconButton } from '@mui/material';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import FolderIcon from '@mui/icons-material/Folder';
import { useAuth } from '../../context/AuthContext';

interface Game {
    id: number;
    result: string;
    game_type: string;
    started_at: string;
    sgf_content: string;
}

interface CloudSGFPanelProps {
    onLoadGame?: (sgf: string) => void;
    onSave?: () => Promise<void>; // Optional external save trigger if needed
}

const CloudSGFPanel = ({ onLoadGame }: CloudSGFPanelProps) => {
    const { token } = useAuth();
    const [games, setGames] = useState<Game[]>([]);
    const [loading, setLoading] = useState(false);

    const fetchGames = async () => {
        if (!token) return;
        try {
            const response = await fetch('/api/v1/games/', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.ok) {
                const data = await response.json();
                setGames(data);
            }
        } catch (error) {
            console.error("Failed to fetch games", error);
        }
    };

    const handleSave = async () => {
        if (!token) return;
        setLoading(true);
        // Mock save current game (in real app, get sgf from gameState)
        const mockSGF = "(;GM[1]FF[4]CA[UTF-8]AP[KaTrain:1.17.1];B[dp];W[pd])";
        try {
            const response = await fetch('/api/v1/games/', {
                method: 'POST',
                headers: { 
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    sgf_content: mockSGF,
                    result: '?',
                    game_type: 'free'
                })
            });
            if (response.ok) {
                fetchGames();
            }
        } catch (error) {
            console.error("Failed to save game", error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchGames();
    }, [token]);

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            <Box sx={{ p: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="h6">Cloud Library</Typography>
                <Button 
                    startIcon={<CloudUploadIcon />} 
                    variant="contained" 
                    size="small" 
                    onClick={handleSave}
                    disabled={loading || !token}
                >
                    Save to Cloud
                </Button>
            </Box>
            <Divider />
            <List sx={{ flexGrow: 1, overflow: 'auto' }}>
                {games.map((game) => (
                    <ListItem key={game.id} disablePadding>
                        <ListItemButton onClick={() => onLoadGame && onLoadGame(game.sgf_content)}>
                            <IconButton size="small" sx={{ mr: 1 }}><FolderIcon /></IconButton>
                            <ListItemText 
                                primary={`Game #${game.id} - ${game.result || 'Unknown'}`} 
                                secondary={new Date(game.started_at).toLocaleString()} 
                            />
                        </ListItemButton>
                    </ListItem>
                ))}
                {games.length === 0 && (
                    <Box sx={{ p: 3, textAlign: 'center', color: 'text.secondary' }}>
                        No games found.
                    </Box>
                )}
            </List>
        </Box>
    );
};

export default CloudSGFPanel;
