import { Box, Typography, Divider, Tooltip, Stack, Switch, FormControlLabel } from '@mui/material';
import PlayerCard from '../../../components/PlayerCard';
import ScoreGraph from '../../../components/ScoreGraph';
import TimelineIcon from '@mui/icons-material/Timeline';
import VisibilityIcon from '@mui/icons-material/Visibility';
import TipsAndUpdatesIcon from '@mui/icons-material/TipsAndUpdates';
import MapIcon from '@mui/icons-material/Map';
import { type GameState } from '../../../api';

interface RightSidebarPanelProps {
    gameState: GameState;
    analysisToggles: Record<string, boolean>;
    onToggleChange: (setting: string) => void;
    onNavigate: (nodeId: number) => void;
    isRated?: boolean;
}

const RightSidebarPanel = ({
    gameState,
    analysisToggles,
    onToggleChange,
    onNavigate,
    isRated = false
}: RightSidebarPanelProps) => {
    const isGameOver = !!gameState.end_result;
    const canShowAnalysis = !isRated || isGameOver;

    const winrate = gameState.analysis?.winrate !== undefined ? (gameState.analysis.winrate * 100).toFixed(1) : '--';
    const score = gameState.analysis?.score !== undefined
        ? (gameState.analysis.score >= 0 ? `B+${gameState.analysis.score.toFixed(1)}` : `W+${Math.abs(gameState.analysis.score).toFixed(1)}`)
        : '--';

    return (
        <Box sx={{ width: 400, height: '100%', display: 'flex', flexDirection: 'column', bgcolor: 'background.paper', borderLeft: '1px solid rgba(255,255,255,0.05)' }}>
            {/* Players */}
            <Box sx={{ p: 2 }}>
                <Stack direction="row" spacing={1}>
                    <PlayerCard
                        player="B"
                        info={gameState.players_info.B}
                        captures={gameState.prisoner_count.B}
                        active={gameState.player_to_move === 'B'}
                        timer={gameState.timer}
                    />
                    <PlayerCard
                        player="W"
                        info={gameState.players_info.W}
                        captures={gameState.prisoner_count.W}
                        active={gameState.player_to_move === 'W'}
                        timer={gameState.timer}
                    />
                </Stack>
            </Box>

            {/* Game Info: Ruleset & Komi */}
            <Box sx={{ px: 2, py: 1, bgcolor: 'rgba(0,0,0,0.15)' }}>
                <Stack direction="row" justifyContent="space-between" alignItems="center">
                    <Typography variant="caption" color="text.secondary">
                        {gameState.ruleset.charAt(0).toUpperCase() + gameState.ruleset.slice(1)} Rules
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                        Komi: {gameState.komi}
                    </Typography>
                </Stack>
            </Box>

            <Divider />

            {/* Analysis Items (道具) */}
            <Box sx={{ p: 2 }}>
                <Typography variant="overline" color="text.secondary" sx={{ fontWeight: 'bold' }}>Items</Typography>
                <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1, mt: 1 }}>
                    <ItemToggle
                        icon={<MapIcon />}
                        label="Territory"
                        active={analysisToggles.ownership}
                        onClick={() => onToggleChange('ownership')}
                        disabled={!canShowAnalysis}
                    />
                    <ItemToggle
                        icon={<TipsAndUpdatesIcon />}
                        label="Advice"
                        active={analysisToggles.hints}
                        onClick={() => onToggleChange('hints')}
                        disabled={!canShowAnalysis}
                    />
                    <ItemToggle
                        icon={<TimelineIcon />}
                        label="Graph"
                        active={analysisToggles.score}
                        onClick={() => onToggleChange('score')}
                        disabled={!canShowAnalysis}
                    />
                    <ItemToggle
                        icon={<VisibilityIcon />}
                        label="Policy"
                        active={analysisToggles.policy}
                        onClick={() => onToggleChange('policy')}
                        disabled={!canShowAnalysis}
                    />
                </Box>
                {isRated && !isGameOver && (
                    <Typography variant="caption" color="error" sx={{ display: 'block', mt: 1, textAlign: 'center' }}>
                        Items disabled during Rated Game
                    </Typography>
                )}
            </Box>

            <Divider />

            {/* Stats & Graph */}
            <Box sx={{ p: 2, bgcolor: 'rgba(0,0,0,0.1)', flexGrow: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                <Stack direction="row" justifyContent="space-between" sx={{ mb: 1 }}>
                    <Box>
                        <Typography variant="caption" color="text.secondary">Win Rate</Typography>
                        <Typography variant="h6" color="primary.main">{canShowAnalysis ? `${winrate}%` : '??%'}</Typography>
                    </Box>
                    <Box sx={{ textAlign: 'right' }}>
                        <Typography variant="caption" color="text.secondary">Score Lead</Typography>
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
                    label={<Typography variant="body2">Coordinates</Typography>}
                />
                <FormControlLabel
                    control={<Switch size="small" checked={analysisToggles.numbers} onChange={() => onToggleChange('numbers')} />}
                    label={<Typography variant="body2">Move Numbers</Typography>}
                />
            </Box>

            {/* Game Result Progress (If Rated) */}
            {isRated && (
                <Box sx={{ p: 2, textAlign: 'center', bgcolor: 'primary.dark' }}>
                    <Typography variant="subtitle2" sx={{ color: '#fff' }}>
                        Rated Mode: Progressing
                    </Typography>
                    <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)' }}>
                        Net wins tracked for rank update
                    </Typography>
                </Box>
            )}
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