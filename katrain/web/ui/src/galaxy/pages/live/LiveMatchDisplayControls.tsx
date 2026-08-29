/**
 * 棋盘页右栏的显示开关组 —— 直播观战页与复盘·报告详情页共用。
 *
 * 两页的显示开关是同一组（试下 / 领地 / 手数 / 建议 / 坐标），所以共用一个组件；
 * 复盘页迁统一版式（S3）时不再另写一份，直接消费这里。
 *
 * 2026-08-22 换成工具格：四个开关做成 `ToolGridButton` 的四列一行，坐标单独一行开关，
 * 与死活题页右栏逐格相同。依据是 Fan 的裁定「除『离开对局』这种按钮和滑轨类以外，
 * 其他按钮一律按对局室右栏那种带标签的方格键来设计」。原来是两列的 `ToggleButton`，
 * 那是这条裁定之前的写法。
 *
 * 坐标为什么不进工具格：它和另外四个不是一类 —— 那四个改的是**棋盘上画什么分析信息**，
 * 坐标改的是棋盘本身的刻度。死活题页已经是「四格 + 一条坐标开关」，这里跟它对齐。
 */

import FormatListNumberedIcon from '@mui/icons-material/FormatListNumbered';
import MapIcon from '@mui/icons-material/Map';
import TipsAndUpdatesIcon from '@mui/icons-material/TipsAndUpdates';
import TouchAppIcon from '@mui/icons-material/TouchApp';
import { Box, Button, Divider, Switch, Typography } from '@mui/material';

import ToolGridButton from '../../components/board/ToolGridButton';
import { useTranslation } from '../../../hooks/useTranslation';
import { railToggleRowSx } from '../../../components/railStyles';

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
  const territoryLabel = t('live:territory', 'Territory');
  const coordinatesLabel = t('Coordinates', 'Coordinates');

  return (
    <Box sx={{ px: 2, py: 1.5, borderBottom: 1, borderColor: 'divider', bgcolor: 'rgba(255,255,255,0.03)' }}>
      <Box
        data-testid="live-match-display-controls-grid"
        sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: '6px' }}
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
          icon={<FormatListNumberedIcon />}
          label={t('live:move_numbers', 'Numbers')}
          ariaLabel={t('live:move_numbers', 'Move Numbers')}
          toggle
          active={showMoveNumbers}
          onClick={onMoveNumbersToggle}
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

      <Divider sx={{ mt: 1.5, mx: -2 }} />
      <Box sx={{ mt: 0.5, ...railToggleRowSx }}>
        <Typography variant="body2" color="text.secondary">{coordinatesLabel}</Typography>
        <Switch
          data-testid="live-coordinate-toggle"
          size="small"
          checked={showCoordinates}
          onChange={onCoordinatesToggle}
          /* MUI v7：`inputProps` 到不了里面那个 input，可及名要走 `slotProps.input`。 */
          slotProps={{ input: { 'aria-label': coordinatesLabel } }}
        />
      </Box>
    </Box>
  );
}
