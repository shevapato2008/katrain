import { Box, Typography, Divider, Tooltip, Stack, Switch, FormControlLabel, IconButton, keyframes } from '@mui/material';
import { useState, useEffect } from 'react';
import PlayerCard from '../../../components/PlayerCard';
import ScoreGraph from '../../../components/ScoreGraph';
import TimelineIcon from '@mui/icons-material/Timeline';
import TipsAndUpdatesIcon from '@mui/icons-material/TipsAndUpdates';
import MapIcon from '@mui/icons-material/Map';
import SkipPreviousIcon from '@mui/icons-material/SkipPrevious';
import FastRewindIcon from '@mui/icons-material/FastRewind';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import FastForwardIcon from '@mui/icons-material/FastForward';
import SkipNextIcon from '@mui/icons-material/SkipNext';
import FlagIcon from '@mui/icons-material/Flag';
import UndoIcon from '@mui/icons-material/Undo';
import PanToolAltIcon from '@mui/icons-material/PanToolAlt';
import CalculateIcon from '@mui/icons-material/Calculate';
import { type GameState, API } from '../../../api';
import { useAuth } from '../../context/AuthContext';
import { useSettings } from '../../context/SettingsContext';
import { useTranslation } from '../../../hooks/useTranslation';

// Blinking animation for loading state
const blink = keyframes`
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
`;

interface RightSidebarPanelProps {
    gameState: GameState;
    analysisToggles: Record<string, boolean>;
    onToggleChange: (setting: string) => void;
    onNavigate: (nodeId: number) => void;
    onAction?: (action: string) => void;
    isRated?: boolean;
    onTimeout?: () => void;
    onPauseTimer?: () => void;
    onPlaySound?: (sound: string) => void;
    isAnalysisPending?: boolean;  // True when waiting for KataGo analysis
}

const RightSidebarPanel = ({
    gameState,
    analysisToggles,
    onToggleChange,
    onNavigate,
    onAction = () => {},
    isRated = false,
    onTimeout,
    onPauseTimer,
    onPlaySound,
    isAnalysisPending = false
}: RightSidebarPanelProps) => {
    const { user, token } = useAuth();
    useSettings(); // Subscribe to translation changes for re-render
    const { t } = useTranslation();
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

    const iconButtonStyle = {
        color: 'text.secondary',
        '&:hover': { color: 'text.primary', bgcolor: 'rgba(255,255,255,0.05)' }
    };

    return (
        <Box sx={{ width: 500, height: '100%', display: 'flex', flexDirection: 'column', bgcolor: 'background.paper', borderLeft: '1px solid rgba(255,255,255,0.05)' }}>
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
                            onPauseTimer={onPauseTimer}
                            onPlaySound={onPlaySound}
                            onTimeout={gameState.player_to_move === 'B' ? onTimeout : undefined}
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
                            onPauseTimer={onPauseTimer}
                            onPlaySound={onPlaySound}
                            onTimeout={gameState.player_to_move === 'W' ? onTimeout : undefined}
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
                            {t(gameState.ruleset, gameState.ruleset.charAt(0).toUpperCase() + gameState.ruleset.slice(1))} {t('Rules', 'Rules')}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                            {t('Komi', 'Komi')}: {gameState.komi}
                        </Typography>
                    </Stack>
                </Box>

                <Divider />

                {/* Tools area - Analysis toggles + Action buttons */}
                <Box sx={{ p: 2 }}>
                    <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1 }}>
                        <ItemToggle
                            icon={<MapIcon />}
                            label={t('Territory', 'Territory')}
                            active={analysisToggles.ownership}
                            onClick={() => onToggleChange('ownership')}
                            disabled={!canShowAnalysis}
                        />
                        <ItemToggle
                            icon={<TipsAndUpdatesIcon />}
                            label={t('Advice', 'Advice')}
                            active={analysisToggles.hints}
                            onClick={() => onToggleChange('hints')}
                            disabled={!canShowAnalysis}
                            loading={isAnalysisPending && analysisToggles.hints}
                        />
                        <ItemToggle
                            icon={<TimelineIcon />}
                            label={t('Graph', 'Graph')}
                            active={analysisToggles.score}
                            onClick={() => onToggleChange('score')}
                            disabled={!canShowAnalysis}
                        />
                        <ItemToggle
                            icon={<UndoIcon />}
                            label={t('Undo', 'Undo')}
                            active={false}
                            onClick={() => onAction('undo')}
                            disabled={isGameOver}
                        />
                        <ItemToggle
                            icon={<PanToolAltIcon />}
                            label={t('PASS', 'Pass')}
                            active={false}
                            onClick={() => onAction('pass')}
                            disabled={isGameOver}
                        />
                        <ItemToggle
                            icon={<FlagIcon />}
                            label={t('RESIGN', 'Resign')}
                            active={false}
                            onClick={() => onAction('resign')}
                            disabled={isGameOver}
                            isDestructive={true}
                        />
                        <ItemToggle
                            icon={<CalculateIcon />}
                            label={t('COUNT', 'Count')}
                            active={false}
                            onClick={() => onAction('count')}
                            disabled={isGameOver || gameState.history.length < 100}
                        />
                    </Box>
                    {isRated && !isGameOver && (
                        <Typography variant="caption" color="error" sx={{ display: 'block', mt: 1, textAlign: 'center' }}>
                            {t('items_disabled_rated', 'Items disabled during Rated Game')}
                        </Typography>
                    )}
                </Box>

                <Divider />

                {/* Score Graph */}
                {analysisToggles.score && canShowAnalysis && (
                    <Box sx={{ px: 2, py: 1, bgcolor: 'rgba(0,0,0,0.1)' }}>
                        <ScoreGraph
                            gameState={gameState}
                            onNavigate={onNavigate}
                            showScore={analysisToggles.score}
                            showWinrate={analysisToggles.winrate}
                        />
                    </Box>
                )}

                <Divider />

                {/* Other Settings */}
                <Box sx={{ p: 2 }}>
                    <FormControlLabel
                        control={<Switch size="small" checked={analysisToggles.coords} onChange={() => onToggleChange('coords')} />}
                        label={<Typography variant="body2">{t('Coordinates', 'Coordinates')}</Typography>}
                    />
                    <FormControlLabel
                        control={<Switch size="small" checked={analysisToggles.numbers} onChange={() => onToggleChange('numbers')} />}
                        label={<Typography variant="body2">{t('Move Numbers', 'Move Numbers')}</Typography>}
                    />
                </Box>

                {/* Game Result Progress (If Rated) */}
                {isRated && (
                    <Box sx={{ p: 2, textAlign: 'center', bgcolor: 'primary.dark' }}>
                        <Typography variant="subtitle2" sx={{ color: '#fff' }}>
                            {t('rated_mode_active', 'Rated Mode: Progressing')}
                        </Typography>
                        <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)' }}>
                            {t('rated_mode_desc', 'Net wins tracked for rank update')}
                        </Typography>
                    </Box>
                )}
            </Box>

            {/* Fixed Controls Section - Navigation only */}
            <Divider />
            <Box sx={{ p: 2, bgcolor: '#1a1a1a' }}>
                {/* Navigation Row - disabled during active game, enabled after game ends */}
                <Stack direction="row" justifyContent="center" spacing={0.5}>
                    <IconButton
                        size="small"
                        onClick={() => onAction('start')}
                        disabled={!isGameOver}
                        sx={isGameOver ? iconButtonStyle : { color: 'text.disabled' }}
                    >
                        <SkipPreviousIcon />
                    </IconButton>
                    <IconButton
                        size="small"
                        onClick={() => onAction('back-10')}
                        disabled={!isGameOver}
                        sx={isGameOver ? iconButtonStyle : { color: 'text.disabled' }}
                    >
                        <FastRewindIcon />
                    </IconButton>
                    <IconButton
                        size="small"
                        onClick={() => onAction('back')}
                        disabled={!isGameOver}
                        sx={isGameOver ? iconButtonStyle : { color: 'text.disabled' }}
                    >
                        <ArrowBackIcon />
                    </IconButton>
                    <IconButton
                        size="small"
                        onClick={() => onAction('forward')}
                        disabled={!isGameOver}
                        sx={isGameOver ? iconButtonStyle : { color: 'text.disabled' }}
                    >
                        <ArrowForwardIcon />
                    </IconButton>
                    <IconButton
                        size="small"
                        onClick={() => onAction('forward-10')}
                        disabled={!isGameOver}
                        sx={isGameOver ? iconButtonStyle : { color: 'text.disabled' }}
                    >
                        <FastForwardIcon />
                    </IconButton>
                    <IconButton
                        size="small"
                        onClick={() => onAction('end')}
                        disabled={!isGameOver}
                        sx={isGameOver ? iconButtonStyle : { color: 'text.disabled' }}
                    >
                        <SkipNextIcon />
                    </IconButton>
                </Stack>
            </Box>
        </Box>
    );
};
const ItemToggle = ({ icon, label, active, onClick, disabled, loading, isDestructive }: {
    icon: React.ReactNode;
    label: string;
    active: boolean;
    onClick: () => void;
    disabled?: boolean;
    loading?: boolean;
    isDestructive?: boolean;
}) => (
    <Tooltip title={disabled ? "" : label}>
        <Box
            onClick={() => !disabled && onClick()}
            sx={{
                p: 1,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                borderRadius: 2,
                cursor: disabled ? 'default' : 'pointer',
                bgcolor: active && !disabled
                    ? (isDestructive ? 'error.main' : 'primary.main')
                    : 'background.default',
                color: active && !disabled
                    ? (isDestructive ? 'error.contrastText' : 'primary.contrastText')
                    : (isDestructive ? 'error.main' : 'text.primary'),
                opacity: disabled ? 0.3 : 1,
                border: '1px solid',
                borderColor: active && !disabled
                    ? (isDestructive ? 'error.main' : 'primary.main')
                    : 'rgba(255,255,255,0.1)',
                animation: loading ? `${blink} 1s ease-in-out infinite` : 'none',
                '&:hover': {
                    bgcolor: disabled
                        ? 'background.default'
                        : (active
                            ? (isDestructive ? 'error.dark' : 'primary.dark')
                            : (isDestructive ? 'rgba(211, 47, 47, 0.15)' : 'rgba(255,255,255,0.05)'))
                }
            }}
        >
            {icon}
            <Typography variant="caption" sx={{ mt: 0.5 }}>{label}</Typography>
        </Box>
    </Tooltip>
);

export default RightSidebarPanel;