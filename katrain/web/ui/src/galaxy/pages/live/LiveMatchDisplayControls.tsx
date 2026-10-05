/**
 * 棋盘页右栏的显示开关组 —— 直播观战页与复盘·报告详情页共用。
 *
 * 试下、领地、支招、清空属于操作区；手数、坐标、3D 属于棋盘显示区。
 * 报告和直播复用相同按钮，显示区也与对弈页共用 BoardDisplayControls。
 */

import MapIcon from '@mui/icons-material/Map';
import TipsAndUpdatesIcon from '@mui/icons-material/TipsAndUpdates';
import TouchAppIcon from '@mui/icons-material/TouchApp';
import ClearIcon from '@mui/icons-material/Clear';
import { Box, Typography } from '@mui/material';

import ToolGridButton from '../../components/board/ToolGridButton';
import BoardDisplayControls from '../../components/board/BoardDisplayControls';
import { useTranslation } from '../../../hooks/useTranslation';
import { toolGridSx } from '../../../components/railStyles';

export interface LiveMatchDisplayControlsProps {
  tryMoveMode: boolean;
  showTerritory: boolean;
  showMoveNumbers: boolean;
  showAiMarkers: boolean;
  showCoordinates: boolean;
  view3d: boolean;
  ownershipAvailable: boolean;
  tryMoves: string[];
  onTryMoveToggle: () => void;
  onTerritoryToggle: () => void;
  onMoveNumbersToggle: () => void;
  onAiMarkersToggle: () => void;
  onCoordinatesToggle: () => void;
  on3dToggle: () => void;
  onClearTryMoves: () => void;
  reportMode?: boolean;
}

export default function LiveMatchDisplayControls({
  tryMoveMode,
  showTerritory,
  showMoveNumbers,
  showAiMarkers,
  showCoordinates,
  view3d,
  ownershipAvailable,
  tryMoves,
  onTryMoveToggle,
  onTerritoryToggle,
  onMoveNumbersToggle,
  onAiMarkersToggle,
  onCoordinatesToggle,
  on3dToggle,
  onClearTryMoves,
  reportMode = false,
}: LiveMatchDisplayControlsProps) {
  const { t } = useTranslation();
  const territoryLabel = t('live:territory', 'Territory');
  const displayControls = <BoardDisplayControls numbers={showMoveNumbers} coordinates={showCoordinates} view3d={view3d} onNumbers={onMoveNumbersToggle} onCoordinates={onCoordinatesToggle} on3d={on3dToggle} />;

  if (reportMode) return (
    <Box data-testid="report-display-controls" sx={{ display: 'grid', gridTemplateRows: '40px 40px', gap: '6px', minHeight: 0 }}>
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(4,minmax(0,1fr))', gap: '6px' }}>
        <ToolGridButton icon={<TouchAppIcon />} label={t('live:try', '试下')} toggle active={tryMoveMode} onClick={onTryMoveToggle} />
        <ToolGridButton icon={<MapIcon />} label={territoryLabel} tooltip={ownershipAvailable ? territoryLabel : t('live:territory_needs_analysis', '领地需要分析结果')} toggle active={showTerritory} disabled={!ownershipAvailable} onClick={onTerritoryToggle} />
        <ToolGridButton icon={<TipsAndUpdatesIcon />} label={t('Advice', '支招')} toggle active={showAiMarkers} onClick={onAiMarkersToggle} />
        <ToolGridButton icon={<ClearIcon />} label={t('live:clear', '清空')} disabled={!tryMoveMode || tryMoves.length === 0} onClick={onClearTryMoves} />
      </Box>
      {displayControls}
    </Box>
  );

  return (
    <Box sx={{ py: 1.5, borderBottom: 1, borderColor: 'divider', bgcolor: 'rgba(255,255,255,0.03)' }}>
      <Box
        data-testid="live-match-display-controls-grid"
        sx={toolGridSx}
      >
        <ToolGridButton
          icon={<TouchAppIcon />}
          label={t('live:try', 'TRY')}
          ariaLabel={t('live:try_move', 'Try Move')}
          toggle
          active={tryMoveMode}
          onClick={onTryMoveToggle}
        />
        <ToolGridButton
          icon={<MapIcon />}
          label={territoryLabel}
          ariaLabel={territoryLabel}
          /* 这一条**连 disabled 一起显示** —— 「要先有分析才能看领地」这句解释，
             恰恰只在键是灰的时候才有用。 */
          tooltip={ownershipAvailable
            ? territoryLabel
            : t('live:territory_needs_analysis', 'Territory (needs analysis)')}
          toggle
          active={showTerritory}
          disabled={!ownershipAvailable}
          onClick={onTerritoryToggle}
        />
        <ToolGridButton
          icon={<TipsAndUpdatesIcon />}
          label={t('Advice', 'Advice')}
          /* 标签不随状态变（格子宽度不能跳），随状态变的只有可及名。 */
          ariaLabel={showAiMarkers
            ? t('live:hide_advice', 'Hide Advice')
            : t('live:show_advice', 'Show Advice')}
          toggle
          active={showAiMarkers}
          onClick={onAiMarkersToggle}
        />
        <ToolGridButton icon={<ClearIcon />} label={t('live:clear', '清空')} disabled={!tryMoveMode || tryMoves.length === 0} onClick={onClearTryMoves} />
      </Box>

      {tryMoveMode && tryMoves.length > 0 && (
        <Box sx={{ mt: 1, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1 }}>
          <Typography variant="caption" color="text.secondary" sx={{ minWidth: 0, overflowWrap: 'anywhere' }}>
            {t('live:try', 'TRY')}: {tryMoves.join(' → ')}
          </Typography>
        </Box>
      )}

      <Box sx={{ mt: 1.5, pt: 1.5, borderTop: 1, borderColor: 'divider' }}>{displayControls}</Box>
    </Box>
  );
}
