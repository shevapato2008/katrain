import React, { useState, useEffect } from 'react';
import { 
  Dialog, DialogTitle, DialogContent, DialogActions, 
  Button, TextField, MenuItem, Box, Tabs, Tab, Typography, Divider, 
  FormControlLabel, Checkbox, Slider, ListSubheader
} from '@mui/material';
import { type GameState } from '../api';
import { useTranslation } from '../hooks/useTranslation';

interface NewGameDialogProps {
  open: boolean;
  gameState: GameState | null;
  onClose: () => void;
  onConfirm: (mode: string, settings: any) => void;
}

const NewGameDialog: React.FC<NewGameDialogProps> = ({ open, gameState, onClose, onConfirm }) => {
  const { t } = useTranslation();
  const [tabValue, setTabValue] = useState(0);

  // Form State
  const [size, setSize] = useState('19');
  const [handicap, setHandicap] = useState(0);
  const [komi, setKomi] = useState(6.5);
  const [rules, setRules] = useState('japanese');
  const [clearCache, setClearCache] = useState(false);
  
  const [blackName, setBlackName] = useState('');
  const [whiteName, setWhiteName] = useState('');
  
  const [blackType, setBlackType] = useState('player:human');
  const [whiteType, setWhiteType] = useState('player:human');
  
  const [blackSubtype, setBlackSubtype] = useState('game:normal');
  const [whiteSubtype, setWhiteSubtype] = useState('game:normal');

  const [setupAdvantage, setSetupAdvantage] = useState(0);
  const [setupMove, setSetupMove] = useState(100);

  useEffect(() => {
    if (open && gameState) {
      setSize(gameState.board_size[0].toString());
      setHandicap(gameState.handicap || 0);
      setKomi(gameState.komi);
      setRules(gameState.ruleset || 'japanese');
      setBlackName(gameState.players_info.B.name || '');
      setWhiteName(gameState.players_info.W.name || '');
      setBlackType(gameState.players_info.B.player_type);
      setWhiteType(gameState.players_info.W.player_type);
      setBlackSubtype(gameState.players_info.B.player_subtype);
      setWhiteSubtype(gameState.players_info.W.player_subtype);
    }
  }, [open, gameState]);

  const handleConfirm = () => {
    const modes = ['newgame', 'setupposition', 'editgame'];
    const mode = modes[tabValue];
    
    const settings = {
      size,
      handicap,
      komi,
      rules,
      clear_cache: clearCache,
      players: {
        B: { name: blackName, player_type: blackType, player_subtype: blackSubtype },
        W: { name: whiteName, player_type: whiteType, player_subtype: whiteSubtype }
      },
      setup_advantage: setupAdvantage,
      setup_move: setupMove
    };
    
    onConfirm(mode, settings);
  };

  const STRATEGY_GROUPS = [
    {
      label: t('Recommended'),
      options: [
        { value: 'ai:default', label: t('AI: Recommended') },
        { value: 'ai:human', label: t('AI: Human Style') },
        { value: 'ai:pro', label: t('AI: Pro Style') },
        { value: 'ai:p:rank', label: t('AI: Rank Based') },
      ]
    },
    {
      label: t('Strength Based'),
      options: [
        { value: 'ai:handicap', label: t('AI: Handicap') },
        { value: 'ai:scoreloss', label: t('AI: Score Loss') },
        { value: 'ai:simple', label: t('AI: Simple Ownership') },
      ]
    },
    {
      label: t('Policy Based'),
      options: [
        { value: 'ai:policy', label: t('AI: Policy') },
        { value: 'ai:p:weighted', label: t('AI: Weighted') },
        { value: 'ai:jigo', label: t('AI: Jigo') },
        { value: 'ai:antimirror', label: t('AI: Antimirror') },
      ]
    }
  ];

  const RULESETS = [
    { value: 'japanese', label: t('japanese') },
    { value: 'chinese', label: t('chinese') },
    { value: 'korean', label: t('korean') },
    { value: 'aga', label: t('aga') },
    { value: 'tromp-taylor', label: t('tromp-taylor') },
    { value: 'new zealand', label: t('new zealand') },
  ];

  const renderPlayerSubtypeSelect = (type: string, subtype: string, setSubtype: (v: string) => void) => {
    if (type === 'player:human') {
      return (
        <TextField
          select
          label={t("gametype")}
          value={subtype}
          onChange={(e) => setSubtype(e.target.value)}
          fullWidth
          size="small"
        >
          <MenuItem value="game:normal">{t("Normal Game")}</MenuItem>
          <MenuItem value="game:teach">{t("Teaching Game")}</MenuItem>
        </TextField>
      );
    } else {
      return (
        <TextField
          select
          label={t("aistrategy")}
          value={subtype}
          onChange={(e) => setSubtype(e.target.value)}
          fullWidth
          size="small"
        >
          {STRATEGY_GROUPS.map(group => [
            <ListSubheader key={group.label}>{group.label}</ListSubheader>,
            ...group.options.map(opt => (
              <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
            ))
          ])}
        </TextField>
      );
    }
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle>
        {tabValue === 0 ? t("New Game title") : tabValue === 1 ? t("setupposition") : t("editgame")}
      </DialogTitle>
      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs value={tabValue} onChange={(_, v) => setTabValue(v)} variant="fullWidth">
          <Tab label={t("newgame")} />
          <Tab label={t("setupposition")} />
          <Tab label={t("editgame")} />
        </Tabs>
      </Box>
      <DialogContent>
        <Box sx={{ mt: 2, display: 'flex', flexDirection: 'column', gap: 3 }}>
          {/* Player Setup Block */}
          <Box>
            <Typography variant="subtitle2" color="textSecondary" gutterBottom>{t("menu:playersetup").toUpperCase()}</Typography>
            <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
              <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                   <Box sx={{ width: 16, height: 16, borderRadius: '50%', bgcolor: 'black' }} />
                   <Typography variant="body2">{t("Black")}</Typography>
                </Box>
                <TextField
                  select
                  label={t("player:type")}
                  value={blackType}
                  onChange={(e) => {
                    setBlackType(e.target.value);
                    setBlackSubtype(e.target.value === 'player:human' ? 'game:normal' : 'ai:default');
                  }}
                  fullWidth
                  size="small"
                >
                  <MenuItem value="player:human">{t("Human")}</MenuItem>
                  <MenuItem value="player:ai">{t("AI")}</MenuItem>
                </TextField>
                {renderPlayerSubtypeSelect(blackType, blackSubtype, setBlackSubtype)}
                <TextField 
                  label={t("black player name hint")} 
                  value={blackName} 
                  onChange={e => setBlackName(e.target.value)} 
                  size="small" 
                  fullWidth 
                />
              </Box>
              <Divider orientation="vertical" flexItem />
              <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                   <Box sx={{ width: 16, height: 16, borderRadius: '50%', bgcolor: 'white', border: '1px solid #000' }} />
                   <Typography variant="body2">{t("White")}</Typography>
                </Box>
                <TextField
                  select
                  label={t("player:type")}
                  value={whiteType}
                  onChange={(e) => {
                    setWhiteType(e.target.value);
                    setWhiteSubtype(e.target.value === 'player:human' ? 'game:normal' : 'ai:default');
                  }}
                  fullWidth
                  size="small"
                >
                  <MenuItem value="player:human">{t("Human")}</MenuItem>
                  <MenuItem value="player:ai">{t("AI")}</MenuItem>
                </TextField>
                {renderPlayerSubtypeSelect(whiteType, whiteSubtype, setWhiteSubtype)}
                <TextField 
                  label={t("white player name hint")} 
                  value={whiteName} 
                  onChange={e => setWhiteName(e.target.value)} 
                  size="small" 
                  fullWidth 
                />
              </Box>
            </Box>
          </Box>

          <Divider />

          {/* Game Settings */}
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
            <TextField
              select
              label={t("ruleset")}
              value={rules}
              onChange={(e) => setRules(e.target.value)}
              sx={{ flex: '1 1 150px' }}
              size="small"
            >
              {RULESETS.map(r => <MenuItem key={r.value} value={r.value}>{r.label}</MenuItem>)}
            </TextField>

            <TextField
              label={t("komi")}
              type="number"
              value={komi}
              onChange={(e) => setKomi(Number(e.target.value))}
              sx={{ flex: '1 1 100px' }}
              size="small"
              inputProps={{ step: 0.5 }}
            />

            {tabValue !== 2 && (
              <>
                <TextField
                  label={t("board size")}
                  value={size}
                  onChange={(e) => setSize(e.target.value)}
                  sx={{ flex: '1 1 100px' }}
                  size="small"
                  helperText={t("non square board hint")}
                />
                <TextField
                  label={t("handicap")}
                  type="number"
                  value={handicap}
                  onChange={(e) => setHandicap(Number(e.target.value))}
                  sx={{ flex: '1 1 100px' }}
                  size="small"
                  inputProps={{ min: 0, max: 9 }}
                />
              </>
            )}
          </Box>

          {tabValue === 0 && (
            <FormControlLabel
              control={<Checkbox checked={clearCache} onChange={e => setClearCache(e.target.checked)} />}
              label={<Typography variant="body2">{t("clear cache")} ({t("avoids replaying")})</Typography>}
            />
          )}

          {tabValue === 1 && (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <Typography variant="body2" color="textSecondary">{t("setup position explanation")}</Typography>
              <Box>
                <Typography variant="caption">{t("setup position black score")}: {setupAdvantage > 0 ? `B+${setupAdvantage}` : setupAdvantage < 0 ? `W+${Math.abs(setupAdvantage)}` : '0'}</Typography>
                <Slider 
                  value={setupAdvantage} 
                  min={-150} max={150} 
                  onChange={(_, v) => setSetupAdvantage(v as number)} 
                  valueLabelDisplay="auto"
                />
              </Box>
              <Box>
                <Typography variant="caption">{t("setup position move number")}: {setupMove}</Typography>
                <Slider 
                  value={setupMove} 
                  min={0} max={400} 
                  onChange={(_, v) => setSetupMove(v as number)} 
                  valueLabelDisplay="auto"
                />
              </Box>
            </Box>
          )}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{t("Cancel")}</Button>
        <Button onClick={handleConfirm} variant="contained">
          {tabValue === 0 ? t("newgame") : tabValue === 1 ? t("setupposition") : t("editgame")}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default NewGameDialog;