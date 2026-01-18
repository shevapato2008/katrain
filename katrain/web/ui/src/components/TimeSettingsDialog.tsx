import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  FormControlLabel,
  Checkbox,
  Box,
  Typography,
} from '@mui/material';
import { useTranslation } from '../hooks/useTranslation';
import { useSessionSettings } from '../hooks/useSessionSettings';

interface TimeSettingsDialogProps {
  open: boolean;
  onClose: () => void;
}

const TimeSettingsDialog: React.FC<TimeSettingsDialogProps> = ({ open, onClose }) => {
  const { t } = useTranslation();
  const { timeSettings, updateTimeSettings } = useSessionSettings();

  const handleChange = (field: keyof typeof timeSettings) => (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseInt(event.target.value, 10);
    if (!isNaN(value)) {
      updateTimeSettings({ [field]: value });
    }
  };

  const handleToggle = (field: keyof typeof timeSettings) => (event: React.ChangeEvent<HTMLInputElement>) => {
    updateTimeSettings({ [field]: event.target.checked });
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>{t('Time Settings')}</DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
          <TextField
            label={t('Main Time (minutes)')}
            type="number"
            value={timeSettings.mainTime}
            onChange={handleChange('mainTime')}
            fullWidth
            size="small"
          />
          <TextField
            label={t('Byoyomi Length (seconds)')}
            type="number"
            value={timeSettings.byoyomiLength}
            onChange={handleChange('byoyomiLength')}
            fullWidth
            size="small"
          />
          <TextField
            label={t('Byoyomi Periods')}
            type="number"
            value={timeSettings.byoyomiPeriods}
            onChange={handleChange('byoyomiPeriods')}
            fullWidth
            size="small"
          />
          <TextField
            label={t('Minimal time usage (seconds)')}
            type="number"
            value={timeSettings.minimalTimeUsage}
            onChange={handleChange('minimalTimeUsage')}
            fullWidth
            size="small"
          />
          <FormControlLabel
            control={
              <Checkbox
                checked={timeSettings.sound}
                onChange={handleToggle('sound')}
              />
            }
            label={t('Sound')}
          />
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} color="primary">
          {t('Close')}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default TimeSettingsDialog;
