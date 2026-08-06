import FormatListNumberedIcon from '@mui/icons-material/FormatListNumbered';
import GridOnIcon from '@mui/icons-material/GridOn';
import MapIcon from '@mui/icons-material/Map';
import TipsAndUpdatesIcon from '@mui/icons-material/TipsAndUpdates';
import TouchAppIcon from '@mui/icons-material/TouchApp';
import { Box, Button, ToggleButton, Tooltip, Typography } from '@mui/material';
import type { ReactNode } from 'react';

import { useTranslation } from '../../../hooks/useTranslation';

export interface LiveMatchDisplayControlsProps {
  tryMoveMode: boolean;
  showTerritory: boolean;
  showMoveNumbers: boolean;
  showAiMarkers: boolean;
  showCoordinates: boolean;
  ownershipAvailable: boolean;
  tryMoves: string[];
  onTryMoveToggle: () => void;
  onTerritoryToggle: () => void;
  onMoveNumbersToggle: () => void;
  onAiMarkersToggle: () => void;
  onCoordinatesToggle: () => void;
  onClearTryMoves: () => void;
}

interface DisplayToggleProps {
  label: string;
  tooltip: string;
  accessibleName?: string;
  value: string;
  selected: boolean;
  onChange: () => void;
  icon: ReactNode;
  disabled?: boolean;
}

function DisplayToggle({
  label,
  tooltip,
  accessibleName = tooltip,
  value,
  selected,
  onChange,
  icon,
  disabled = false,
}: DisplayToggleProps) {
  return (
    <Tooltip title={tooltip}>
      <span style={{ display: 'block', minWidth: 0 }}>
        <ToggleButton
          aria-label={accessibleName}
          value={value}
          selected={selected}
          disabled={disabled}
          onChange={onChange}
          sx={{ width: '100%', minWidth: 0, minHeight: 40, px: 1, py: 0.5 }}
        >
          {icon}
          <Typography variant="caption" sx={{ ml: 0.5 }} noWrap>
            {label}
          </Typography>
        </ToggleButton>
      </span>
    </Tooltip>
  );
}

export default function LiveMatchDisplayControls({
  tryMoveMode,
  showTerritory,
  showMoveNumbers,
  showAiMarkers,
  showCoordinates,
  ownershipAvailable,
  tryMoves,
  onTryMoveToggle,
  onTerritoryToggle,
  onMoveNumbersToggle,
  onAiMarkersToggle,
  onCoordinatesToggle,
  onClearTryMoves,
}: LiveMatchDisplayControlsProps) {
  const { t } = useTranslation();
  const tryTooltip = t('live:try_move', 'Try Move');
  const territoryLabel = t('live:territory', 'Territory');
  const territoryTooltip = ownershipAvailable
    ? territoryLabel
    : t('live:territory_needs_analysis', 'Territory (needs analysis)');
  const moveNumbersTooltip = t('live:move_numbers', 'Move Numbers');
  const adviceTooltip = showAiMarkers
    ? t('live:hide_advice', 'Hide Advice')
    : t('live:show_advice', 'Show Advice');
  const coordinatesLabel = t('live:coordinates', 'Coordinates');

  return (
    <Box sx={{ px: 2, py: 1.5, borderBottom: 1, borderColor: 'divider', bgcolor: 'rgba(255,255,255,0.03)' }}>
      <Box
        data-testid="live-match-display-controls-grid"
        sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 0.5 }}
      >
        <DisplayToggle
          label={t('live:try', 'TRY')}
          tooltip={tryTooltip}
          value="tryMove"
          selected={tryMoveMode}
          onChange={onTryMoveToggle}
          icon={<TouchAppIcon fontSize="small" />}
        />
        <DisplayToggle
          label={t('live:territory', 'TERRITORY')}
          tooltip={territoryTooltip}
          accessibleName={territoryLabel}
          value="territory"
          selected={showTerritory}
          disabled={!ownershipAvailable}
          onChange={onTerritoryToggle}
          icon={<MapIcon fontSize="small" />}
        />
        <DisplayToggle
          label={t('live:move_numbers', 'Numbers')}
          tooltip={moveNumbersTooltip}
          value="numbers"
          selected={showMoveNumbers}
          onChange={onMoveNumbersToggle}
          icon={<FormatListNumberedIcon fontSize="small" />}
        />
        <DisplayToggle
          label={t('Advice', 'Advice')}
          tooltip={adviceTooltip}
          value="aiMarkers"
          selected={showAiMarkers}
          onChange={onAiMarkersToggle}
          icon={<TipsAndUpdatesIcon fontSize="small" />}
        />
        <DisplayToggle
          label={coordinatesLabel}
          tooltip={coordinatesLabel}
          value="coordinates"
          selected={showCoordinates}
          onChange={onCoordinatesToggle}
          icon={<GridOnIcon fontSize="small" />}
        />
      </Box>

      {tryMoveMode && tryMoves.length > 0 && (
        <Box sx={{ mt: 1, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1 }}>
          <Typography variant="caption" color="text.secondary" sx={{ minWidth: 0, overflowWrap: 'anywhere' }}>
            {t('live:try', 'TRY')}: {tryMoves.join(' → ')}
          </Typography>
          <Button size="small" onClick={onClearTryMoves} sx={{ minHeight: 40, flexShrink: 0 }}>
            {t('live:clear', 'Clear')}
          </Button>
        </Box>
      )}
    </Box>
  );
}
