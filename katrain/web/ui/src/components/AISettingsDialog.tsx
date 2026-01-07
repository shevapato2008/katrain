import React, { useState, useEffect } from 'react';
import {
  Dialog, DialogTitle, DialogContent, DialogActions,
  Button, TextField, MenuItem, Box, Typography, Divider,
  Slider, Checkbox, FormControlLabel, CircularProgress
} from '@mui/material';
import { API, type GameState } from '../api';
import { useTranslation } from '../hooks/useTranslation';
import { useDebounce } from '../hooks/useDebounce';

interface AISettingsDialogProps {
  open: boolean;
  gameState: GameState | null;
  sessionId: string;
  onClose: () => void;
}

interface AIConstants {
  strategies: string[];
  options: Record<string, any>;
  key_properties: string[];
  default_strategy: string;
}

const AISettingsDialog: React.FC<AISettingsDialogProps> = ({ open, gameState, sessionId, onClose }) => {
  const { t } = useTranslation();
  const [constants, setConstants] = useState<AIConstants | null>(null);
  const [selectedStrategy, setSelectedStrategy] = useState<string>('');
  const [settings, setSettings] = useState<Record<string, any>>({});
  const [estimatedRank, setEstimatedRank] = useState<string>('...');
  const [loading, setLoading] = useState(false);

  // Fetch constants on mount
  useEffect(() => {
    if (open && !constants) {
      setLoading(true);
      API.getAIConstants()
        .then(data => {
          setConstants(data);
          // Initial strategy selection logic
          if (gameState) {
            // Try to find a non-default strategy used by any player
            const strategies = Object.values(gameState.players_info).map(p => p.player_subtype);
            const active = strategies.find(s => s !== 'ai:default' && s.startsWith('ai:'));
            setSelectedStrategy(active || data.default_strategy || 'ai:default');
          } else {
            setSelectedStrategy(data.default_strategy || 'ai:default');
          }
        })
        .catch(err => console.error("Failed to load AI constants", err))
        .finally(() => setLoading(false));
    }
  }, [open, constants, gameState]);

  // Fetch settings when strategy changes
  useEffect(() => {
    if (open && sessionId && selectedStrategy) {
      setLoading(true);
      API.getConfig(sessionId, `ai/${selectedStrategy}`)
        .then(data => {
          setSettings(data || {}); // data is the value dict
        })
        .catch(err => console.error("Failed to load AI settings", err))
        .finally(() => setLoading(false));
    }
  }, [open, sessionId, selectedStrategy]);

  // Estimate rank when settings change (debounced)
  const debouncedSettings = useDebounce(settings, 500);
  const debouncedStrategy = useDebounce(selectedStrategy, 500);

  useEffect(() => {
    if (sessionId && debouncedStrategy && Object.keys(debouncedSettings).length > 0) {
      API.estimateRank(debouncedStrategy, debouncedSettings)
        .then(data => setEstimatedRank(data.rank))
        .catch(err => console.error("Rank estimation failed", err));
    } else {
        setEstimatedRank("...");
    }
  }, [sessionId, debouncedStrategy, debouncedSettings]);

  const handleSettingChange = (key: string, value: any) => {
    setSettings(prev => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    if (!sessionId || !selectedStrategy) return;
    try {
      // We need to save the whole dict or individual keys?
      // API.updateConfig takes "ai/strategy/key" or just "ai/strategy" if value is dict.
      // Kivy update_config does it key by key usually, but session.katrain.update_config handles dicts if path splits.
      // Let's try updating the whole strategy dict.
      await API.updateConfig(sessionId, `ai/${selectedStrategy}`, settings);
      onClose();
    } catch (error) {
      console.error("Failed to save AI settings", error);
    }
  };

  if (!constants) return null;

  const renderOption = (key: string, value: any, spec: any) => {
    const isKeyProp = constants.key_properties.includes(key);
    
    if (spec === 'bool') {
      return (
        <FormControlLabel
          control={
            <Checkbox
              checked={!!value}
              onChange={(e) => handleSettingChange(key, e.target.checked)}
            />
          }
          label={
            <Typography variant="body2" fontWeight={isKeyProp ? 'bold' : 'normal'}>
              {key}
            </Typography>
          }
        />
      );
    }

    if (Array.isArray(spec)) {
      // It's a list of values (or tuples)
      const isTuple = Array.isArray(spec[0]);
      const values = isTuple ? spec.map((x: any) => x[0]) : spec;
      const labels = isTuple ? spec.map((x: any) => x[1]) : spec.map(String);
      
      // Map labels using translation if they contain [brackets]
      // Or just simple mapping. Kivy does re.sub(r"\[(.*?)]", lambda m: i18n._(m[1]), l)
      const translatedLabels = labels.map((l: string) => {
          return l.replace(/\[(.*?)\]/g, (_, key) => t(key));
      });

      // Find index of current value
      // Note: value might be close but not exact due to float precision, or explicitly exact.
      // Kivy uses index.
      let currentIndex = values.indexOf(value);
      if (currentIndex === -1) {
          // Try fuzzy match for floats
          currentIndex = values.findIndex((v: number) => Math.abs(v - value) < 1e-9);
      }
      if (currentIndex === -1) currentIndex = 0;

      return (
        <Box sx={{ width: '100%', px: 1 }}>
          <Typography variant="caption" color="textSecondary" gutterBottom>
            {key} {isKeyProp && '*'}
          </Typography>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Slider
              value={currentIndex}
              min={0}
              max={values.length - 1}
              step={1}
              marks={values.length <= 10} // Only show ticks if few options
              onChange={(_, val) => {
                  const idx = val as number;
                  handleSettingChange(key, values[idx]);
              }}
              valueLabelDisplay="auto"
              valueLabelFormat={(idx) => translatedLabels[idx]}
              size="small"
            />
            <Typography variant="body2" sx={{ minWidth: 40, textAlign: 'right' }}>
              {translatedLabels[currentIndex]}
            </Typography>
          </Box>
        </Box>
      );
    }

    // Default to text input if unknown spec (shouldn't happen for AI options)
    return (
        <TextField
            label={key}
            value={value}
            onChange={(e) => handleSettingChange(key, e.target.value)}
            fullWidth
            size="small"
        />
    );
  };

  const currentOptions = Object.keys(settings).sort().filter(k => k in constants.options);
  const otherOptions = Object.keys(settings).sort().filter(k => !(k in constants.options));

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>{t("AI Settings")}</DialogTitle>
      <DialogContent>
        {loading && <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}><CircularProgress /></Box>}
        
        <Box sx={{ mt: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <TextField
            select
            label={t("Select AI")}
            value={selectedStrategy}
            onChange={(e) => setSelectedStrategy(e.target.value)}
            fullWidth
            size="small"
          >
            {constants.strategies.map(strategy => (
              <MenuItem key={strategy} value={strategy}>
                {t(strategy)}
              </MenuItem>
            ))}
          </TextField>

          <Typography variant="body2" color="textSecondary" sx={{ bgcolor: '#f5f5f5', p: 1, borderRadius: 1 }}>
            {t(selectedStrategy.replace('ai:', 'aihelp:'))}
          </Typography>

          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', bgcolor: '#e3f2fd', p: 1, borderRadius: 1 }}>
             <Typography variant="subtitle2">{t("estimated strength")}</Typography>
             <Typography variant="h6" color="primary">{estimatedRank}</Typography>
          </Box>

          <Divider />

          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {currentOptions.map(key => (
              <Box key={key}>
                {renderOption(key, settings[key], constants.options[key])}
              </Box>
            ))}
            
            {/* Fallback for options not in AI_OPTION_VALUES but present in config */}
            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
            {otherOptions.map(key => (
                 <Box key={key}>
                    <TextField
                        label={key}
                        value={settings[key]}
                        onChange={(e) => {
                            const v = parseFloat(e.target.value);
                            handleSettingChange(key, isNaN(v) ? e.target.value : v);
                        }}
                        fullWidth
                        size="small"
                        type="number"
                        inputProps={{ step: "any" }}
                    />
                 </Box>
            ))}
            </Box>
          </Box>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t("Cancel")}</Button>
        <Button onClick={handleSave} variant="contained">{t("update ai settings")}</Button>
      </DialogActions>
    </Dialog>
  );
};

export default AISettingsDialog;