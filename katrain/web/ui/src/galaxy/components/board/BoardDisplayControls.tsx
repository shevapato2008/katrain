import FormatListNumberedIcon from '@mui/icons-material/FormatListNumbered';
import GridOnIcon from '@mui/icons-material/GridOn';
import ViewInArIcon from '@mui/icons-material/ViewInAr';
import { Box } from '@mui/material';

import { useTranslation } from '../../../hooks/useTranslation';
import ToolGridButton from './ToolGridButton';

interface BoardDisplayControlsProps {
  numbers: boolean;
  coordinates: boolean;
  view3d: boolean;
  onNumbers: () => void;
  onCoordinates: () => void;
  on3d: () => void;
}

/** The same three board display controls on game, live, and report rails. */
export default function BoardDisplayControls({ numbers, coordinates, view3d, onNumbers, onCoordinates, on3d }: BoardDisplayControlsProps) {
  const { t } = useTranslation();
  return <Box data-testid="board-display-controls" sx={{ display: 'grid', gridTemplateColumns: 'repeat(3,minmax(0,1fr))', gap: '6px', minWidth: 0 }}>
    <ToolGridButton icon={<FormatListNumberedIcon />} label={t('Move Numbers', '手数')} toggle active={numbers} onClick={onNumbers} />
    <ToolGridButton icon={<GridOnIcon />} label={t('Coordinates', '坐标')} toggle active={coordinates} onClick={onCoordinates} />
    <ToolGridButton icon={<ViewInArIcon />} label={t('3D', '3D')} toggle active={view3d} onClick={on3d} />
  </Box>;
}
