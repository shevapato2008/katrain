import { Box, Typography, Divider, Tooltip, Stack, Switch, FormControlLabel, IconButton, Button } from '@mui/material';
import { useState, useEffect } from 'react';
import PlayerCard from '../../../components/PlayerCard';
import ScoreGraph from '../../../components/ScoreGraph';
import TimelineIcon from '@mui/icons-material/Timeline';
import VisibilityIcon from '@mui/icons-material/Visibility';
import TipsAndUpdatesIcon from '@mui/icons-material/TipsAndUpdates';
import MapIcon from '@mui/icons-material/Map';
import SkipPreviousIcon from '@mui/icons-material/SkipPrevious';
import FastRewindIcon from '@mui/icons-material/FastRewind';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import FastForwardIcon from '@mui/icons-material/FastForward';
import SkipNextIcon from '@mui/icons-material/SkipNext';
import RotateRightIcon from '@mui/icons-material/RotateRight';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import PsychologyIcon from '@mui/icons-material/Psychology';
import FlagIcon from '@mui/icons-material/Flag';
import UndoIcon from '@mui/icons-material/Undo';
import { type GameState, API } from '../../../api';
import { useAuth } from '../../context/AuthContext';
import { i18n } from '../../../i18n';

interface RightSidebarPanelProps {
    gameState: GameState;
    analysisToggles: Record<string, boolean>;
    onToggleChange: (setting: string) => void;
    onNavigate: (nodeId: number) => void;
    onAction?: (action: string) => void;
    isRated?: boolean;
}

const RightSidebarPanel = ({
    gameState,
    analysisToggles,
    onToggleChange,
    onNavigate,
    onAction = () => {},
    isRated = false
}: RightSidebarPanelProps) => {
    const { user, token } = useAuth();
    const [followingNames, setFollowingNames] = useState<Set<string>>(new Set());

    useEffect(() => {
        const fetchFollowing = async () => {
            if (token) {
                try {
                    const following = await API.getFollowing(token);
                    setFollowingNames(new Set(following.map(f => f.username)));
                } catch (err) {
                    console.error("Failed to fetch following list", err);
                }
            }
        };
        fetchFollowing();
    }, [token]);

    const handleToggleFollow = async (username: string) => {
        if (!token || !username) return;
        try {
            if (followingNames.has(username)) {
                await API.unfollowUser(token, username);
                setFollowingNames(prev => {
                    const next = new Set(prev);
                    next.delete(username);
                    return next;
                });
            } else {
                await API.followUser(token, username);
                setFollowingNames(prev => {
                    const next = new Set(prev);
                    next.add(username);
                    return next;
                });
            }
        } catch (err) {
            console.error("Follow toggle failed", err);
        }
    };

    const isGameOver = !!gameState.end_result;
    const canShowAnalysis = !isRated || isGameOver;

    const winrate = gameState.analysis?.winrate !== undefined ? (gameState.analysis.winrate * 100).toFixed(1) : '--';
    const score = gameState.analysis?.score !== undefined
        ? (gameState.analysis.score >= 0 ? `B+${gameState.analysis.score.toFixed(1)}` : `W+${Math.abs(gameState.analysis.score).toFixed(1)}`)
        : '--';

    const iconButtonStyle = {
        color: 'text.secondary',
        '&:hover': { color: 'text.primary', bgcolor: 'rgba(255,255,255,0.05)' }
    };

    return (
        <Box sx={{ width: 400, height: '100%', display: 'flex', flexDirection: 'column', bgcolor: 'background.paper', borderLeft: '1px solid rgba(255,255,255,0.05)' }}>
            <Box sx={{ flexGrow: 1, overflow: 'auto', display: 'flex', flexDirection: 'column' }}>
                {/* Players */}
                <Box sx={{ p: 2 }}>
                    <Stack direction="row" spacing={1}>
                        <PlayerCard
                            player="B"
                            info={gameState.players_info.B}
                            captures={gameState.prisoner_count.B}
                            active={gameState.player_to_move === 'B'}
                            timer={gameState.timer}
                            showFollowButton={gameState.players_info.B.player_type === 'human' && gameState.players_info.B.name !== user?.username}
                            isFollowed={followingNames.has(gameState.players_info.B.name)}
                            onToggleFollow={() => handleToggleFollow(gameState.players_info.B.name)}
                        />
                        <PlayerCard
                            player="W"
                            info={gameState.players_info.W}
                            captures={gameState.prisoner_count.W}
                            active={gameState.player_to_move === 'W'}
                            timer={gameState.timer}
                            showFollowButton={gameState.players_info.W.player_type === 'human' && gameState.players_info.W.name !== user?.username}
                            isFollowed={followingNames.has(gameState.players_info.W.name)}
                            onToggleFollow={() => handleToggleFollow(gameState.players_info.W.name)}
                        />
                    </Stack>
                </Box>

                {/* Game Info: Ruleset & Komi */}
                <Box sx={{ px: 2, py: 1, bgcolor: 'rgba(0,0,0,0.15)' }}>
                    <Stack direction="row" justifyContent="space-between" alignItems="center">
                        <Typography variant="caption" color="text.secondary">
                            {i18n.t(gameState.ruleset, gameState.ruleset.charAt(0).toUpperCase() + gameState.ruleset.slice(1))} {i18n.t('Rules', 'Rules')}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                            {i18n.t('Komi', 'Komi')}: {gameState.komi}
                        </Typography>
                    </Stack>
                </Box>

                <Divider />

                {/* Analysis Items (道具) */}
                <Box sx={{ p: 2 }}>
                    <Typography variant="overline" color="text.secondary" sx={{ fontWeight: 'bold' }}>{i18n.t('Items', 'Items')}</Typography>
                    <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1, mt: 1 }}>
                        <ItemToggle
                            icon={<MapIcon />}
                            label={i18n.t('Territory', 'Territory')}
                            active={analysisToggles.ownership}
                            onClick={() => onToggleChange('ownership')}
                            disabled={!canShowAnalysis}
                        />
                        <ItemToggle
                            icon={<TipsAndUpdatesIcon />}
                            label={i18n.t('Advice', 'Advice')}
                            active={analysisToggles.hints}
                            onClick={() => onToggleChange('hints')}
                            disabled={!canShowAnalysis}
                        />
                        <ItemToggle
                            icon={<TimelineIcon />}
                            label={i18n.t('Graph', 'Graph')}
                            active={analysisToggles.score}
                            onClick={() => onToggleChange('score')}
                            disabled={!canShowAnalysis}
                        />
                        <ItemToggle
                            icon={<VisibilityIcon />}
                            label={i18n.t('Policy', 'Policy')}
                            active={analysisToggles.policy}
                            onClick={() => onToggleChange('policy')}
                            disabled={!canShowAnalysis}
                        />
                    </Box>
                    {isRated && !isGameOver && (
                        <Typography variant="caption" color="error" sx={{ display: 'block', mt: 1, textAlign: 'center' }}>
                            {i18n.t('items_disabled_rated', 'Items disabled during Rated Game')}
                        </Typography>
                    )}
                </Box>

                <Divider />

                {/* Stats & Graph */}
                <Box sx={{ p: 2, bgcolor: 'rgba(0,0,0,0.1)', flexGrow: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                    <Stack direction="row" justifyContent="space-between" sx={{ mb: 1 }}>
                        <Box>
                            <Typography variant="caption" color="text.secondary">{i18n.t('Win Rate', 'Win Rate')}</Typography>
                            <Typography variant="h6" color="primary.main">{canShowAnalysis ? `${winrate}%` : '??%'}</Typography>
                        </Box>
                        <Box sx={{ textAlign: 'right' }}>
                            <Typography variant="caption" color="text.secondary">{i18n.t('Score Lead', 'Score Lead')}</Typography>
                            <Typography variant="h6" color="secondary.main">{canShowAnalysis ? score : '??'}</Typography>
                        </Box>
                    </Stack>

                    {analysisToggles.score && canShowAnalysis && (
                        <Box sx={{ mt: 'auto' }}>
                            <ScoreGraph
                                gameState={gameState}
                                onNavigate={onNavigate}
                                showScore={analysisToggles.score}
                                showWinrate={analysisToggles.winrate}
                            />
                        </Box>
                    )}
                </Box>

                <Divider />

                {/* Other Settings */}
                <Box sx={{ p: 2 }}>
                    <FormControlLabel
                        control={<Switch size="small" checked={analysisToggles.coords} onChange={() => onToggleChange('coords')} />}
                        label={<Typography variant="body2">{i18n.t('Coordinates', 'Coordinates')}</Typography>}
                    />
                    <FormControlLabel
                        control={<Switch size="small" checked={analysisToggles.numbers} onChange={() => onToggleChange('numbers')} />}
                        label={<Typography variant="body2">{i18n.t('Move Numbers', 'Move Numbers')}</Typography>}
                    />
                </Box>

                {/* Game Result Progress (If Rated) */}
                {isRated && (
                    <Box sx={{ p: 2, textAlign: 'center', bgcolor: 'primary.dark' }}>
                        <Typography variant="subtitle2" sx={{ color: '#fff' }}>
                            {i18n.t('rated_mode_active', 'Rated Mode: Progressing')}
                        </Typography>
                        <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)' }}>
                            {i18n.t('rated_mode_desc', 'Net wins tracked for rank update')}
                        </Typography>
                    </Box>
                )}
            </Box>

            {/* Fixed Controls Section */}
            <Divider />
            <Box sx={{ p: 2, bgcolor: '#1a1a1a' }}>
                {/* Navigation Row */}
                <Stack direction="row" justifyContent="space-between" sx={{ mb: 1.5 }}>
                    <IconButton size="small" onClick={() => onAction('start')} sx={iconButtonStyle}><SkipPreviousIcon /></IconButton>
                    <IconButton size="small" onClick={() => onAction('back-10')} sx={iconButtonStyle}><FastRewindIcon /></IconButton>
                    <IconButton size="small" onClick={() => onAction('back')} sx={iconButtonStyle}><ArrowBackIcon /></IconButton>
                    <IconButton size="small" onClick={() => onAction('forward')} sx={iconButtonStyle}><ArrowForwardIcon /></IconButton>
                    <IconButton size="small" onClick={() => onAction('forward-10')} sx={iconButtonStyle}><FastForwardIcon /></IconButton>
                    <IconButton size="small" onClick={() => onAction('end')} sx={iconButtonStyle}><SkipNextIcon /></IconButton>
                </Stack>

                {/* Analysis Row */}
                <Stack direction="row" justifyContent="space-between" sx={{ mb: 1.5 }}>
                    <Tooltip title={i18n.t("Undo (Smart)")}><IconButton size="small" onClick={() => onAction('undo')} sx={{ color: 'primary.main', '&:hover': { bgcolor: 'rgba(74, 107, 92, 0.1)' } }}><UndoIcon /></IconButton></Tooltip>
                    <Tooltip title={i18n.t("Previous Mistake")}><IconButton size="small" onClick={() => onAction('mistake-prev')} sx={iconButtonStyle}><WarningAmberIcon /></IconButton></Tooltip>
                    <Tooltip title={i18n.t("Rotate Board")}><IconButton size="small" onClick={() => onAction('rotate')} sx={iconButtonStyle}><RotateRightIcon /></IconButton></Tooltip>
                    <Tooltip title={i18n.t("AI Move")}><IconButton size="small" onClick={() => onAction('ai-move')} sx={iconButtonStyle}><PsychologyIcon /></IconButton></Tooltip>
                    <Tooltip title={i18n.t("Next Mistake")}><IconButton size="small" onClick={() => onAction('mistake-next')} sx={iconButtonStyle}><WarningAmberIcon /></IconButton></Tooltip>
                </Stack>

                {/* Actions Row */}
                <Stack direction="row" spacing={1}>
                    <Button 
                        variant="outlined" 
                        color="inherit" 
                        fullWidth 
                        onClick={() => onAction('pass')}
                        sx={{ color: 'text.secondary', borderColor: 'rgba(255,255,255,0.2)' }}
                    >
                        {i18n.t("PASS")}
                    </Button>
                    <Button 
                        variant="outlined" 
                        color="error" 
                        fullWidth 
                        onClick={() => onAction('resign')}
                        startIcon={<FlagIcon />}
                    >
                        {i18n.t("RESIGN")}
                    </Button>
                </Stack>
            </Box>
        </Box>
    );
};
const ItemToggle = ({ icon, label, active, onClick, disabled }: any) => (
    <Tooltip title={disabled ? "Locked during game" : label}>
        <Box 
            onClick={() => !disabled && onClick()}
            sx={{ 
                p: 1, 
                display: 'flex', 
                flexDirection: 'column', 
                alignItems: 'center', 
                borderRadius: 2, 
                cursor: disabled ? 'default' : 'pointer',
                bgcolor: active && !disabled ? 'primary.main' : 'background.default',
                color: active && !disabled ? 'primary.contrastText' : 'text.primary',
                opacity: disabled ? 0.3 : 1,
                border: '1px solid',
                borderColor: active && !disabled ? 'primary.main' : 'rgba(255,255,255,0.1)',
                '&:hover': {
                    bgcolor: disabled ? 'background.default' : (active ? 'primary.dark' : 'rgba(255,255,255,0.05)')
                }
            }}
        >
            {icon}
            <Typography variant="caption" sx={{ mt: 0.5 }}>{label}</Typography>
        </Box>
    </Tooltip>
);

export default RightSidebarPanel;