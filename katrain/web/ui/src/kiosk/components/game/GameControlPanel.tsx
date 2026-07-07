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
import { useTranslation } from '../../../hooks/useTranslation';

interface Props {
  gameState: GameState;
  onAction: (action: string) => void;
  onNavigate: (nodeId: number) => void;
  analysisToggles: Record<string, boolean>;
  onToggleAnalysis: (key: string) => void;
  isGameOver?: boolean;
  disableUndo?: boolean;
  disableSpecialActions?: boolean;
  /** Golaxy 人机对弈: replace the local analysis toggles with the three star阵-tunnel buttons. */
  engineMode?: boolean;
  activeEngineKind?: 'area' | 'options' | 'variation' | null;
  onEngineAnalysis?: (kind: 'area' | 'options' | 'variation') => void;
}

const GameControlPanel = ({
  gameState, onAction, onNavigate, analysisToggles, onToggleAnalysis, isGameOver = false,
  disableUndo = false, disableSpecialActions = false, engineMode = false, activeEngineKind = null,
  onEngineAnalysis,
}: Props) => {
  const { t } = useTranslation();
  // golaxy 人机对弈 has no winrate chart — never shown in engineMode, regardless of the toggle state.
  const showScore = !engineMode && !!analysisToggles.score;

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
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>{gameState.ruleset} {t('Rules', '规则')}</Typography>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>{t('Komi', '贴目')}: {gameState.komi}</Typography>
        </Box>

        <Divider />

        {/* 4. ItemToggle grid */}
        <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1, p: 2 }}>
          {engineMode ? (
            <>
              {/* 星阵道具 (Golaxy paid tunnel analysis) — 领地/支招/变化图, mutually exclusive. */}
              <ItemToggle icon={<MapIcon />} label={t('Territory', '领地')} active={activeEngineKind === 'area'} onClick={() => onEngineAnalysis?.('area')} />
              <ItemToggle icon={<TipsAndUpdates />} label={t('Suggest', '支招')} active={activeEngineKind === 'options'} onClick={() => onEngineAnalysis?.('options')} />
              <ItemToggle icon={<Timeline />} label={t('Variation Line', '变化图')} active={activeEngineKind === 'variation'} onClick={() => onEngineAnalysis?.('variation')} />
            </>
          ) : (
            <>
              <ItemToggle icon={<MapIcon />} label={t('Territory', '领地')} active={!!analysisToggles.ownership} onClick={() => onToggleAnalysis('ownership')} />
              <ItemToggle icon={<TipsAndUpdates />} label={t('Hints', '建议')} active={!!analysisToggles.hints} onClick={() => onToggleAnalysis('hints')} />
              <ItemToggle icon={<Timeline />} label={t('Chart', '图表')} active={showScore} onClick={() => onToggleAnalysis('score')} />
            </>
          )}
          {!disableUndo && (
            <ItemToggle icon={<Undo />} label={t('Undo', '悔棋')} onClick={() => onAction('undo')} disabled={isGameOver} />
          )}
          <ItemToggle icon={<PanToolAlt />} label={t('Pass', '停一手')} onClick={() => onAction('pass')} disabled={isGameOver || disableSpecialActions} />
          <ItemToggle icon={<Flag />} label={t('Resign', '认输')} onClick={() => onAction('resign')} isDestructive disabled={isGameOver} />
          <ItemToggle icon={<Calculate />} label={t('Score', '数子')} onClick={() => onAction('count')} disabled={isGameOver || disableSpecialActions} />
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
            control={<Switch size="small" checked={!!analysisToggles.coords} onChange={() => onToggleAnalysis('coords')} />}
            label={<Typography variant="body2">{t('Coordinates', '坐标')}</Typography>}
          />
          <FormControlLabel
            control={<Switch size="small" checked={!!analysisToggles.numbers} onChange={() => onToggleAnalysis('numbers')} />}
            label={<Typography variant="body2">{t('Move Numbers', '手数')}</Typography>}
          />
        </Box>
      </Box>

      {/* Fixed bottom: navigation controls */}
      <Divider />
      <Box data-testid="nav-controls" sx={{ display: 'flex', justifyContent: 'center', gap: 0.5, px: 2, py: 1 }}>
        {!disableUndo && (
          <>
            <IconButton size="small" onClick={() => onAction('start')} disabled={!isGameOver}><SkipPrevious /></IconButton>
            <IconButton size="small" onClick={() => onAction('back-10')} disabled={!isGameOver}><FastRewind /></IconButton>
            <IconButton size="small" onClick={() => onAction('back')} disabled={!isGameOver}><ArrowBack /></IconButton>
          </>
        )}
        <IconButton size="small" onClick={() => onAction('forward')} disabled={!isGameOver}><ArrowForward /></IconButton>
        <IconButton size="small" onClick={() => onAction('forward-10')} disabled={!isGameOver}><FastForward /></IconButton>
        <IconButton size="small" onClick={() => onAction('end')} disabled={!isGameOver}><SkipNext /></IconButton>
      </Box>
    </Box>
  );
};

export default GameControlPanel;
