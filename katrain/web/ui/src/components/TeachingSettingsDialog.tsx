import React from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  FormControlLabel,
  Checkbox,
  Box,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Switch,
  Divider,
} from '@mui/material';
import { useTranslation } from '../hooks/useTranslation';
import { useSessionSettings } from '../hooks/useSessionSettings';

interface TeachingSettingsDialogProps {
  open: boolean;
  onClose: () => void;
}

const TeachingSettingsDialog: React.FC<TeachingSettingsDialogProps> = ({ open, onClose }) => {
  const { t } = useTranslation();
  const { teachingSettings, updateTeachingSettings } = useSessionSettings();

  const handleArrayToggle = (field: 'showDots' | 'saveFeedback', index: number) => {
    const newArray = [...teachingSettings[field]];
    newArray[index] = !newArray[index];
    updateTeachingSettings({ [field]: newArray });
  };

  const handleThresholdChange = (index: number, value: string) => {
    const numValue = parseFloat(value);
    if (!isNaN(numValue)) {
      const newThresholds = [...teachingSettings.evalThresholds];
      newThresholds[index] = numValue;
      updateTeachingSettings({ evalThresholds: newThresholds });
    }
  };

  const handleVisitChange = (field: 'fast' | 'low' | 'max', value: string) => {
    const numValue = parseInt(value, 10);
    if (!isNaN(numValue)) {
      updateTeachingSettings({
        visits: { ...teachingSettings.visits, [field]: numValue },
      });
    }
  };

  const dotColors = [
    { label: t('Best'), color: '#30a06e' },
    { label: t('Very Good'), color: '#5b9bd5' },
    { label: t('Good'), color: '#e89639' },
    { label: t('Slack'), color: '#e16b5c' },
    { label: t('Mistake'), color: '#9c27b0' },
    { label: t('Blunder'), color: '#7a7772' },
  ];

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>{t('teacher settings')}</DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, mt: 1 }}>
          
          {/* Dot Settings Table */}
          <TableContainer component={Paper} variant="outlined" sx={{ bgcolor: 'transparent' }}>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>{t('dot color')}</TableCell>
                  <TableCell align="center">{t('point loss threshold')}</TableCell>
                  <TableCell align="center">{t('show dots')}</TableCell>
                  <TableCell align="center">{t('save dots')}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {dotColors.map((dot, index) => (
                  <TableRow key={index}>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Box sx={{ width: 12, height: 12, borderRadius: '50%', bgcolor: dot.color }} />
                        <Typography variant="body2">{dot.label}</Typography>
                      </Box>
                    </TableCell>
                    <TableCell align="center">
                      {index < 5 ? (
                        <TextField
                          type="number"
                          size="small"
                          value={teachingSettings.evalThresholds[index]}
                          onChange={(e) => handleThresholdChange(index, e.target.value)}
                          sx={{ width: 80 }}
                          inputProps={{ step: 0.5, min: 0 }}
                        />
                      ) : (
                        '-'
                      )}
                    </TableCell>
                    <TableCell align="center">
                      <Checkbox
                        checked={teachingSettings.showDots[index]}
                        onChange={() => handleArrayToggle('showDots', index)}
                        size="small"
                        inputProps={{ 'aria-label': t('show dots') }}
                      />
                    </TableCell>
                    <TableCell align="center">
                      <Checkbox
                        checked={teachingSettings.saveFeedback[index]}
                        onChange={() => handleArrayToggle('saveFeedback', index)}
                        size="small"
                        inputProps={{ 'aria-label': t('save dots') }}
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          <Divider />

          {/* AI and Visit Settings */}
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 3 }}>
            <Box sx={{ flex: '1 1 300px', display: 'flex', flexDirection: 'column', gap: 2 }}>
              <Typography variant="subtitle2" color="primary">{t('Analysis Settings')}</Typography>
              <FormControlLabel
                control={
                  <Switch
                    checked={teachingSettings.showAI}
                    onChange={(e) => updateTeachingSettings({ showAI: e.target.checked })}
                  />
                }
                label={t('show ai dots')}
              />
              <FormControl fullWidth size="small">
                <InputLabel>{t('stats on top move')}</InputLabel>
                <Select
                  value={teachingSettings.topMovesShow}
                  label={t('stats on top move')}
                  onChange={(e) => updateTeachingSettings({ topMovesShow: e.target.value })}
                >
                  <MenuItem value="top_move_delta_score">{t('top_move_delta_score')}</MenuItem>
                  <MenuItem value="top_move_score">{t('top_move_score')}</MenuItem>
                  <MenuItem value="top_move_delta_winrate">{t('top_move_delta_winrate')}</MenuItem>
                  <MenuItem value="top_move_winrate">{t('top_move_winrate')}</MenuItem>
                  <MenuItem value="top_move_visits">{t('top_move_visits')}</MenuItem>
                  <MenuItem value="top_move_nothing">{t('top_move_nothing')}</MenuItem>
                </Select>
              </FormControl>
            </Box>

            <Box sx={{ flex: '1 1 300px', display: 'flex', flexDirection: 'column', gap: 2 }}>
              <Typography variant="subtitle2" color="primary">{t('Visits Settings')}</Typography>
              <TextField
                label={t('engine:fast_visits')}
                type="number"
                size="small"
                value={teachingSettings.visits.fast}
                onChange={(e) => handleVisitChange('fast', e.target.value)}
                fullWidth
              />
              <TextField
                label={t('low_visits', 'Low Visits')}
                type="number"
                size="small"
                value={teachingSettings.visits.low}
                onChange={(e) => handleVisitChange('low', e.target.value)}
                fullWidth
              />
              <TextField
                label={t('engine:max_visits')}
                type="number"
                size="small"
                value={teachingSettings.visits.max}
                onChange={(e) => handleVisitChange('max', e.target.value)}
                fullWidth
              />
            </Box>
          </Box>

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

export default TeachingSettingsDialog;
