import { Box, FormControlLabel, Switch, Typography } from '@mui/material';
import { ViewInAr } from '@mui/icons-material';

interface PhysicalModeToggleProps {
  checked: boolean;
  onChange: (v: boolean) => void;
  capable: boolean;
}

const PhysicalModeToggle = ({ checked, onChange, capable }: PhysicalModeToggleProps) => (
  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, opacity: capable ? 1 : 0.6 }} data-testid="physical-mode-toggle">
    <ViewInAr sx={{ color: capable ? 'warning.main' : 'text.disabled' }} />
    <FormControlLabel
      sx={{ ml: 0 }}
      control={
        <Switch
          color="warning"
          checked={checked && capable}
          disabled={!capable}
          onChange={(e) => onChange(e.target.checked)}
          inputProps={{ 'aria-label': '使用物理棋盘' }}
        />
      }
      label={<Typography variant="body2">{capable ? '使用物理棋盘' : '未检测到实体棋盘'}</Typography>}
    />
  </Box>
);

export default PhysicalModeToggle;
