import { Box, Typography, useTheme } from '@mui/material';
import { alpha } from '@mui/material/styles';

export interface ItemToggleProps {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
  onClick: () => void;
  disabled?: boolean;
  isDestructive?: boolean;
  /**
   * Remaining-uses badge (metered 星阵 道具). Omit for buttons with no count.
   * A number renders the count (0 shown in the error color = 次数不足); `null`
   * renders "—" (count unknown — a fetch/parse gap, distinct from 0).
   */
  badge?: number | null;
}

const ItemToggle = ({ icon, label, active, onClick, disabled, isDestructive, badge }: ItemToggleProps) => {
  const theme = useTheme();
  const activeColor = isDestructive ? 'error.main' : 'primary.main';
  const activeBg = isDestructive ? alpha(theme.palette.error.main, 0.15) : 'primary.dark';
  const showBadge = badge !== undefined;
  const badgeText = badge === null || badge === undefined ? '—' : String(badge);
  const badgeEmpty = badge === 0;
  return (
    <Box
      onClick={disabled ? undefined : onClick}
      sx={{
        position: 'relative',
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        gap: 0.5, py: 1.5, borderRadius: 2, cursor: disabled ? 'default' : 'pointer',
        border: '1px solid',
        borderColor: active ? activeColor : 'divider',
        bgcolor: active ? activeBg : 'transparent',
        opacity: disabled ? 0.3 : 1,
        color: active ? activeColor : 'text.secondary',
        transition: 'all 0.15s ease',
        '&:hover': disabled ? {} : { borderColor: activeColor },
      }}
    >
      {showBadge && (
        <Box
          data-testid="item-badge"
          sx={{
            position: 'absolute', top: 4, right: 4, minWidth: 18, px: 0.5, height: 18,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            borderRadius: 9, fontSize: '0.7rem', lineHeight: 1, fontWeight: 600,
            bgcolor: badgeEmpty ? 'error.main' : 'rgba(0,0,0,0.35)',
            color: badgeEmpty ? '#fff' : 'text.secondary',
          }}
        >
          {badgeText}
        </Box>
      )}
      {icon}
      <Typography variant="caption" sx={{ fontSize: '0.8rem', lineHeight: 1 }}>{label}</Typography>
    </Box>
  );
};

export default ItemToggle;
