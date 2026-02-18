import { Box, Typography } from '@mui/material';

export interface ItemToggleProps {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
  onClick: () => void;
  disabled?: boolean;
  isDestructive?: boolean;
}

const ItemToggle = ({ icon, label, active, onClick, disabled, isDestructive }: ItemToggleProps) => {
  const activeColor = isDestructive ? 'error.main' : 'primary.main';
  return (
    <Box
      onClick={disabled ? undefined : onClick}
      sx={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        gap: 0.5, py: 1.5, borderRadius: 2, cursor: disabled ? 'default' : 'pointer',
        border: '1px solid',
        borderColor: active ? activeColor : 'rgba(255,255,255,0.1)',
        bgcolor: active ? (isDestructive ? 'rgba(196,93,62,0.15)' : 'rgba(92,181,122,0.15)') : 'transparent',
        opacity: disabled ? 0.3 : 1,
        color: active ? activeColor : 'text.secondary',
        transition: 'all 0.15s ease',
        '&:hover': disabled ? {} : { borderColor: activeColor, bgcolor: isDestructive ? 'rgba(196,93,62,0.08)' : 'rgba(92,181,122,0.08)' },
      }}
    >
      {icon}
      <Typography variant="caption" sx={{ fontSize: '0.8rem', lineHeight: 1 }}>{label}</Typography>
    </Box>
  );
};

export default ItemToggle;
