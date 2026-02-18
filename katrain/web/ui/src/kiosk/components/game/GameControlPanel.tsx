import { Box, Typography, Divider, Stack, Switch, FormControlLabel, IconButton } from '@mui/material';
import {
  Map as MapIcon, TipsAndUpdates, Timeline, Undo,
  PanToolAlt, Flag, Calculate,
  SkipPrevious, FastRewind, ArrowBack, ArrowForward, FastForward, SkipNext,
} from '@mui/icons-material';
import PlayerCard from '../../../components/PlayerCard';
import ScoreGraph from '../../../components/ScoreGraph';
import ItemToggle from './ItemToggle';
import type { GameState } from '../../../api';

interface Props {
  gameState: GameState;
  onAction: (action: string) => void;
  onNavigate: (nodeId: number) => void;
  analysisToggles: Record<string, boolean>;
  onToggleAnalysis: (key: string) => void;
}

const GameControlPanel = ({ gameState, onAction, onNavigate, analysisToggles, onToggleAnalysis }: Props) => {
  const showScore = analysisToggles.show_score !== false;  // default true if not set

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <Box sx={{ flexGrow: 1, overflow: 'auto' }}>
        {/* 1. Dual PlayerCards */}
        <Box sx={{ p: 2 }}>
          <Stack direction="row" spacing={1.5}>
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

        {/* 2. Game info bar */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', px: 2, py: 1, bgcolor: 'rgba(0,0,0,0.15)' }}>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>{gameState.ruleset} 规则</Typography>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>贴目: {gameState.komi}</Typography>
        </Box>

        <Divider />

        {/* 4. ItemToggle grid */}
        <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1, p: 2 }}>
          <ItemToggle icon={<MapIcon />} label="领地" active={!!analysisToggles.show_ownership} onClick={() => onToggleAnalysis('show_ownership')} />
          <ItemToggle icon={<TipsAndUpdates />} label="建议" active={!!analysisToggles.show_hints} onClick={() => onToggleAnalysis('show_hints')} />
          <ItemToggle icon={<Timeline />} label="图表" active={showScore} onClick={() => onToggleAnalysis('show_score')} />
          <ItemToggle icon={<Undo />} label="悔棋" onClick={() => onAction('undo')} />
          <ItemToggle icon={<PanToolAlt />} label="停一手" onClick={() => onAction('pass')} />
          <ItemToggle icon={<Flag />} label="认输" onClick={() => onAction('resign')} isDestructive />
          <ItemToggle icon={<Calculate />} label="数子" onClick={() => onAction('count')} />
        </Box>

        <Divider />

        {/* 6. ScoreGraph */}
        {showScore && (
          <Box sx={{ px: 2, py: 1, bgcolor: 'rgba(0,0,0,0.1)' }} data-testid="score-graph">
            <ScoreGraph gameState={gameState} onNavigate={onNavigate} />
          </Box>
        )}

        <Divider />

        {/* 8. Switch settings */}
        <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 0.5 }}>
          <FormControlLabel
            control={<Switch size="small" checked={!!analysisToggles.show_coordinates} onChange={() => onToggleAnalysis('show_coordinates')} />}
            label={<Typography variant="body2">坐标</Typography>}
          />
          <FormControlLabel
            control={<Switch size="small" checked={!!analysisToggles.show_move_numbers} onChange={() => onToggleAnalysis('show_move_numbers')} />}
            label={<Typography variant="body2">手数</Typography>}
          />
        </Box>
      </Box>

      {/* Fixed bottom: navigation controls */}
      <Divider />
      <Box data-testid="nav-controls" sx={{ display: 'flex', justifyContent: 'center', gap: 0.5, px: 2, py: 1 }}>
        <IconButton size="small" onClick={() => onAction('start')}><SkipPrevious /></IconButton>
        <IconButton size="small" onClick={() => onAction('back-10')}><FastRewind /></IconButton>
        <IconButton size="small" onClick={() => onAction('back')}><ArrowBack /></IconButton>
        <IconButton size="small" onClick={() => onAction('forward')}><ArrowForward /></IconButton>
        <IconButton size="small" onClick={() => onAction('forward-10')}><FastForward /></IconButton>
        <IconButton size="small" onClick={() => onAction('end')}><SkipNext /></IconButton>
      </Box>
    </Box>
  );
};

export default GameControlPanel;
