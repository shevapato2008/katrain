import { useState, type MouseEvent } from 'react';
import { IconButton, Popover, Box, ButtonBase, Typography } from '@mui/material';
import { ScreenRotation as RotationIcon } from '@mui/icons-material';
import { useOrientation, type Rotation } from '../../context/OrientationContext';

const OPTIONS: { value: Rotation; label: string; desc: string }[] = [
  { value: 0, label: '0°', desc: '横屏' },
  { value: 90, label: '90°', desc: '竖屏' },
  { value: 180, label: '180°', desc: '横屏翻转' },
  { value: 270, label: '270°', desc: '竖屏翻转' },
];

interface RotationSelectorProps {
  variant?: 'default' | 'compact';
}

const RotationSelector = ({ variant = 'default' }: RotationSelectorProps) => {
  const { rotation, setRotation } = useOrientation();
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);

  const handleOpen = (e: MouseEvent<HTMLElement>) => setAnchorEl(e.currentTarget);
  const handleClose = () => setAnchorEl(null);
  const handleSelect = (v: Rotation) => {
    setRotation(v);
    handleClose();
  };

  return (
    <>
      <IconButton
        data-testid="rotation-selector-button"
        onClick={handleOpen}
        size={variant === 'compact' ? 'small' : 'medium'}
        sx={{ color: 'text.secondary' }}
      >
        <RotationIcon fontSize={variant === 'compact' ? 'small' : 'medium'} />
      </IconButton>
      <Popover
        open={!!anchorEl}
        anchorEl={anchorEl}
        onClose={handleClose}
        anchorOrigin={{ vertical: 'center', horizontal: 'right' }}
        transformOrigin={{ vertical: 'center', horizontal: 'left' }}
        slotProps={{ paper: { sx: { bgcolor: 'background.paper', p: 0.5 } } }}
      >
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, minWidth: 120 }}>
          {OPTIONS.map((opt) => {
            const selected = rotation === opt.value;
            return (
              <ButtonBase
                key={opt.value}
                data-selected={selected}
                onClick={() => handleSelect(opt.value)}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1,
                  px: 1.5,
                  py: 1,
                  borderRadius: 1,
                  color: selected ? 'primary.main' : 'text.primary',
                  bgcolor: selected ? 'rgba(92, 181, 122, 0.08)' : 'transparent',
                  '&:hover': { bgcolor: 'action.hover' },
                }}
              >
                <Typography variant="body2" sx={{ fontWeight: selected ? 600 : 400, minWidth: 32 }}>
                  {opt.label}
                </Typography>
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                  {opt.desc}
                </Typography>
              </ButtonBase>
            );
          })}
        </Box>
      </Popover>
    </>
  );
};

export default RotationSelector;
