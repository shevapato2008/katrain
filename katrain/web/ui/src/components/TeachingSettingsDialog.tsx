import React, { useEffect } from 'react';
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
import { API } from '../api';
import { useTranslation } from '../hooks/useTranslation';
import { useSessionSettings } from '../hooks/useSessionSettings';
import { DEFAULT_TEACHING_SETTINGS } from '../types/settings';
import type { GameState } from '../api';

interface TeachingSettingsDialogProps {
  open: boolean;
  sessionId: string | null;
  gameState: GameState | null;
  onClose: () => void;
}

const TeachingSettingsDialog: React.FC<TeachingSettingsDialogProps> = ({ open, sessionId, gameState, onClose }) => {
  const { t } = useTranslation();
  const { teachingSettings, updateTeachingSettings } = useSessionSettings();
  const wasOpen = React.useRef(open);

  useEffect(() => {
    if (open && !wasOpen.current && gameState?.trainer_settings) {
      const ts = gameState.trainer_settings;
      updateTeachingSettings({
        evalThresholds: ts.eval_thresholds,
        showDots: ts.show_dots,
        saveFeedback: ts.save_feedback,
        saveMarks: ts.save_marks,
        showAI: ts.eval_show_ai,
        lockAI: ts.lock_ai,
        topMovesShow: ts.top_moves_show,
        maxTopMovesOnBoard: ts.max_top_moves_on_board || DEFAULT_TEACHING_SETTINGS.maxTopMovesOnBoard,
        visits: {
          low: ts.low_visits,
          fast: ts.fast_visits || DEFAULT_TEACHING_SETTINGS.visits.fast,
          max: ts.max_visits || DEFAULT_TEACHING_SETTINGS.visits.max
        }
      });
    }
    wasOpen.current = open;
  }, [open, gameState, updateTeachingSettings]); // Added missing dependencies

  const handleUpdate = async () => {
    if (!sessionId) return;
    try {
      await API.updateConfigBulk(sessionId, {
        'trainer/eval_thresholds': teachingSettings.evalThresholds,
        'trainer/show_dots': teachingSettings.showDots,
        'trainer/save_feedback': teachingSettings.saveFeedback,
        'trainer/save_marks': teachingSettings.saveMarks,
        'trainer/eval_show_ai': teachingSettings.showAI,
        'trainer/lock_ai': teachingSettings.lockAI,
        'trainer/top_moves_show': teachingSettings.topMovesShow,
        'trainer/max_top_moves_on_board': teachingSettings.maxTopMovesOnBoard,
        'trainer/low_visits': teachingSettings.visits.low,
        'engine/fast_visits': teachingSettings.visits.fast,
        'engine/max_visits': teachingSettings.visits.max,
      });
      onClose();
    } catch (error) {
      console.error("Failed to update teaching settings", error);
    }
  };

  const handleArrayToggle = (field: 'showDots' | 'saveFeedback' | 'saveMarks', index: number) => {
    const newArray = [...teachingSettings[field]];
    newArray[index] = !newArray[index];
    updateTeachingSettings({ [field]: newArray });
  };

  const handleThresholdChange = (index: number, value: string) => {
    if (value === '' || /^\d*\.?\d*$/.test(value)) {
      const numValue = parseFloat(value);
      const newThresholds = [...teachingSettings.evalThresholds];
      newThresholds[index] = isNaN(numValue) ? 0 : numValue;
      updateTeachingSettings({ evalThresholds: newThresholds });
    }
  };

  const handleVisitChange = (field: 'fast' | 'low' | 'max', value: string) => {
    if (value === '' || /^\d+$/.test(value)) {
      const numValue = parseInt(value, 10);
      updateTeachingSettings({
        visits: { ...teachingSettings.visits, [field]: isNaN(numValue) ? 0 : numValue },
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
                  <TableCell align="center">{t('save marks')}</TableCell>
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
                          size="small"
                          value={teachingSettings.evalThresholds[index]}
                          onChange={(e) => handleThresholdChange(index, e.target.value)}
                          sx={{ width: 80 }}
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
                    <TableCell align="center">
                      <Checkbox
                        checked={teachingSettings.saveMarks[index]}
                        onChange={() => handleArrayToggle('saveMarks', index)}
                        size="small"
                        inputProps={{ 'aria-label': t('save marks') }}
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
              <FormControlLabel
                control={
                  <Switch
                    checked={teachingSettings.lockAI}
                    onChange={(e) => updateTeachingSettings({ lockAI: e.target.checked })}
                  />
                }
                label={t('lock ai')}
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
              <TextField
                label={t('max top moves on board', 'Max Top Moves on Board')}
                size="small"
                type="number"
                value={teachingSettings.maxTopMovesOnBoard}
                onChange={(e) => {
                    const val = parseInt(e.target.value, 10);
                    updateTeachingSettings({ maxTopMovesOnBoard: isNaN(val) ? 1 : val });
                }}
                fullWidth
              />
            </Box>

            <Box sx={{ flex: '1 1 300px', display: 'flex', flexDirection: 'column', gap: 2 }}>
              <Typography variant="subtitle2" color="primary">{t('Visits Settings')}</Typography>
              <TextField
                label={t('engine:fast_visits')}
                size="small"
                value={teachingSettings.visits.fast}
                onChange={(e) => handleVisitChange('fast', e.target.value)}
                fullWidth
              />
              <TextField
                label={t('low_visits', 'Low Visits')}
                size="small"
                value={teachingSettings.visits.low}
                onChange={(e) => handleVisitChange('low', e.target.value)}
                fullWidth
              />
              <TextField
                label={t('engine:max_visits')}
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
          {t('cancel')}
        </Button>
        <Button onClick={handleUpdate} color="primary" variant="contained">
          {t('update teacher')}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default TeachingSettingsDialog;
