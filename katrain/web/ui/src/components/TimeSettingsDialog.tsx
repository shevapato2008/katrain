import React, { useEffect } from 'react';
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
} from '@mui/material';
import { API } from '../api';
import { useTranslation } from '../hooks/useTranslation';
import { useSessionSettings } from '../hooks/useSessionSettings';
import type { GameState } from '../api';

interface TimeSettingsDialogProps {
  open: boolean;
  sessionId: string | null;
  gameState: GameState | null;
  onClose: () => void;
}

const TimeSettingsDialog: React.FC<TimeSettingsDialogProps> = ({ open, sessionId, gameState, onClose }) => {
  const { t } = useTranslation();
  const { timeSettings, updateTimeSettings } = useSessionSettings();

  const wasOpen = React.useRef(open);

  useEffect(() => {
    if (open && !wasOpen.current && gameState?.timer?.settings) {
      const s = gameState.timer.settings;
      updateTimeSettings({
        mainTime: s.main_time,
        byoyomiLength: s.byo_length,
        byoyomiPeriods: s.byo_periods,
        minimalTimeUsage: s.minimal_use, // Fixed: backend uses minimal_use
        sound: s.sound
      });
    }
    wasOpen.current = open;
  }, [open, gameState, updateTimeSettings]);

  const handleUpdate = async () => {
    if (!sessionId) return;
    try {
      await API.updateConfigBulk(sessionId, {
        'timer/main_time': timeSettings.mainTime,
        'timer/byo_length': timeSettings.byoyomiLength,
        'timer/byo_periods': timeSettings.byoyomiPeriods,
        'timer/minimal_use': timeSettings.minimalTimeUsage,
        'timer/sound': timeSettings.sound,
      });
      onClose();
    } catch (error) {
      console.error("Failed to update timer settings", error);
    }
  };

  const handleChange = (field: keyof typeof timeSettings) => (event: React.ChangeEvent<HTMLInputElement>) => {
    const rawValue = event.target.value;
    if (rawValue === '') {
      updateTimeSettings({ [field]: 0 as any });
      return;
    }
    const value = parseInt(rawValue, 10);
    if (/^\d+$/.test(rawValue) && !isNaN(value)) {
      updateTimeSettings({ [field]: value });
    }
  };

  const handleToggle = (field: keyof typeof timeSettings) => (event: React.ChangeEvent<HTMLInputElement>) => {
    updateTimeSettings({ [field]: event.target.checked });
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>{t('timer settings')}</DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mt: 1 }}>
          <TextField
            label={t('main time')}
            value={timeSettings.mainTime}
            onChange={handleChange('mainTime')}
            fullWidth
            size="small"
          />
          <TextField
            label={t('byoyomi length')}
            value={timeSettings.byoyomiLength}
            onChange={handleChange('byoyomiLength')}
            fullWidth
            size="small"
          />
          <TextField
            label={t('byoyomi periods')}
            value={timeSettings.byoyomiPeriods}
            onChange={handleChange('byoyomiPeriods')}
            fullWidth
            size="small"
          />
          <TextField
            label={t('minimal time use')}
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
            label={t('count down sound')}
          />
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} color="primary">
          {t('cancel')}
        </Button>
        <Button onClick={handleUpdate} color="primary" variant="contained">
          {t('update timer')}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default TimeSettingsDialog;
