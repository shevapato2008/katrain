import { useState } from 'react';
import { Box, Typography, Divider, Stack, Switch, FormControlLabel, IconButton } from '@mui/material';
import {
  Map as MapIcon, TipsAndUpdates, Timeline, Undo,
  PanToolAlt, Flag, Calculate,
  SkipPrevious, FastRewind, ArrowBack, ArrowForward, FastForward, SkipNext,
} from '@mui/icons-material';
import KioskPlayerCard from './KioskPlayerCard';
import KioskScoreGraph from './KioskScoreGraph';
import ItemToggle from './ItemToggle';
import type { KioskTimerState, KioskAnalysisPoint } from '../../data/mocks';

interface Props {
  blackName: string;
  blackRank: string;
  whiteName: string;
  whiteRank: string;
  blackCaptures: number;
  whiteCaptures: number;
  blackTimer: KioskTimerState;
  whiteTimer: KioskTimerState;
  ruleset: string;
  komi: number;
  currentWinrate: number;
  currentScore: number;
  moveNumber: number;
  currentMoveIndex: number;
  analysisHistory: KioskAnalysisPoint[];
}

/* ── GameControlPanel ── */

const GameControlPanel = (props: Props) => {
  const [toggles, setToggles] = useState({
    ownership: false,
    hints: false,
    score: true,
    coords: true,
    numbers: false,
  });

  const toggle = (key: keyof typeof toggles) =>
    setToggles((prev) => ({ ...prev, [key]: !prev[key] }));

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Scrollable area */}
      <Box sx={{ flexGrow: 1, overflow: 'auto' }}>
        {/* 1. Dual PlayerCards */}
        <Box sx={{ p: 2 }}>
          <Stack direction="row" spacing={1.5}>
            <KioskPlayerCard
              player="B" name={props.blackName} rank={props.blackRank}
              mainTimeLeft={props.blackTimer.mainTimeLeft}
              byoyomiLeft={props.blackTimer.byoyomiLeft}
              periodsLeft={props.blackTimer.periodsLeft}
              captures={props.blackCaptures} active={props.blackTimer.isActive}
              isWarning={props.blackTimer.isWarning} isCritical={props.blackTimer.isCritical}
            />
            <KioskPlayerCard
              player="W" name={props.whiteName} rank={props.whiteRank}
              mainTimeLeft={props.whiteTimer.mainTimeLeft}
              byoyomiLeft={props.whiteTimer.byoyomiLeft}
              periodsLeft={props.whiteTimer.periodsLeft}
              captures={props.whiteCaptures} active={props.whiteTimer.isActive}
              isWarning={props.whiteTimer.isWarning} isCritical={props.whiteTimer.isCritical}
            />
          </Stack>
        </Box>

        {/* 2. Game info bar */}
        <Box sx={{ display: 'flex', justifyContent: 'space-between', px: 2, py: 1, bgcolor: 'rgba(0,0,0,0.15)' }}>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>{props.ruleset} 规则</Typography>
          <Typography variant="caption" sx={{ color: 'text.secondary' }}>贴目: {props.komi}</Typography>
        </Box>

        {/* 3. Divider */}
        <Divider />

        {/* 4. ItemToggle grid (2 columns × 4 rows) */}
        <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1, p: 2 }}>
          <ItemToggle icon={<MapIcon />} label="领地" active={toggles.ownership} onClick={() => toggle('ownership')} />
          <ItemToggle icon={<TipsAndUpdates />} label="建议" active={toggles.hints} onClick={() => toggle('hints')} />
          <ItemToggle icon={<Timeline />} label="图表" active={toggles.score} onClick={() => toggle('score')} />
          <ItemToggle icon={<Undo />} label="悔棋" onClick={() => {}} />
          <ItemToggle icon={<PanToolAlt />} label="停一手" onClick={() => {}} />
          <ItemToggle icon={<Flag />} label="认输" onClick={() => {}} isDestructive />
          <ItemToggle icon={<Calculate />} label="数子" onClick={() => {}} />
        </Box>

        {/* 5. Divider */}
        <Divider />

        {/* 6. ScoreGraph (shown when score toggle is on) */}
        {toggles.score && (
          <Box sx={{ px: 2, py: 1, bgcolor: 'rgba(0,0,0,0.1)' }}>
            <KioskScoreGraph
              history={props.analysisHistory}
              currentMoveIndex={props.currentMoveIndex}
              currentWinrate={props.currentWinrate}
              currentScore={props.currentScore}
            />
          </Box>
        )}

        {/* 7. Divider */}
        <Divider />

        {/* 8. Switch settings */}
        <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 0.5 }}>
          <FormControlLabel
            control={<Switch size="small" checked={toggles.coords} onChange={() => toggle('coords')} />}
            label={<Typography variant="body2">坐标</Typography>}
          />
          <FormControlLabel
            control={<Switch size="small" checked={toggles.numbers} onChange={() => toggle('numbers')} />}
            label={<Typography variant="body2">手数</Typography>}
          />
        </Box>
      </Box>

      {/* Fixed bottom: navigation controls */}
      <Divider />
      <Box data-testid="nav-controls" sx={{ display: 'flex', justifyContent: 'center', gap: 0.5, px: 2, py: 1 }}>
        <IconButton size="small"><SkipPrevious /></IconButton>
        <IconButton size="small"><FastRewind /></IconButton>
        <IconButton size="small"><ArrowBack /></IconButton>
        <IconButton size="small"><ArrowForward /></IconButton>
        <IconButton size="small"><FastForward /></IconButton>
        <IconButton size="small"><SkipNext /></IconButton>
      </Box>
    </Box>
  );
};

export default GameControlPanel;
