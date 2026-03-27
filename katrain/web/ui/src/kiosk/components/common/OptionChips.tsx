import { Box, ButtonBase, Typography } from '@mui/material';

interface OptionChipsProps<T extends string | number> {
  label: string;
  options: { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
}

function OptionChips<T extends string | number>({
  label,
  options,
  value,
  onChange,
}: OptionChipsProps<T>) {
  return (
    <Box sx={{ mb: 2.5 }}>
      <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
        {label}
      </Typography>
      <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
        {options.map((opt) => (
          <ButtonBase
            key={String(opt.value)}
            onClick={() => onChange(opt.value)}
            sx={{
              minWidth: 64,
              minHeight: 48,
              px: 2,
              borderRadius: 2,
              bgcolor: value === opt.value ? 'primary.dark' : 'background.paper',
              border: '1px solid',
              borderColor: value === opt.value ? 'primary.main' : 'divider',
              transition: 'all 100ms ease-out',
              '&:active': { transform: 'scale(0.96)' },
            }}
          >
            <Typography
              variant="body1"
              sx={{
                fontWeight: value === opt.value ? 600 : 400,
                color: value === opt.value ? 'primary.main' : 'text.primary',
              }}
            >
              {opt.label}
            </Typography>
          </ButtonBase>
        ))}
      </Box>
    </Box>
  );
}

export default OptionChips;
