import React, { useState } from 'react';
import { 
  Dialog, DialogTitle, DialogContent, DialogActions, 
  Button, TextField, MenuItem, Box 
} from '@mui/material';
import { i18n } from '../i18n';

interface NewGameDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: (settings: any) => void;
}

const NewGameDialog: React.FC<NewGameDialogProps> = ({ open, onClose, onConfirm }) => {
  const [size, setSize] = useState(19);
  const [handicap, setHandicap] = useState(0);
  const [komi, setKomi] = useState(6.5);

  const handleConfirm = () => {
    onConfirm({ size, handicap, komi });
  };

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle>{i18n.t("New Game title")}</DialogTitle>
      <DialogContent>
        <Box sx={{ mt: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <TextField
            select
            label={i18n.t("Board Size")}
            value={size}
            onChange={(e) => setSize(Number(e.target.value))}
            fullWidth
          >
            <MenuItem value={9}>9x9</MenuItem>
            <MenuItem value={13}>13x13</MenuItem>
            <MenuItem value={19}>19x19</MenuItem>
          </TextField>
          
          <TextField
            label={i18n.t("Handicap")}
            type="number"
            value={handicap}
            onChange={(e) => setHandicap(Number(e.target.value))}
            fullWidth
            inputProps={{ min: 0, max: 9 }}
          />

          <TextField
            label={i18n.t("komi")}
            type="number"
            value={komi}
            onChange={(e) => setKomi(Number(e.target.value))}
            fullWidth
            inputProps={{ step: 0.5 }}
          />
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>{i18n.t("Cancel")}</Button>
        <Button onClick={handleConfirm} variant="contained">{i18n.t("Start")}</Button>
      </DialogActions>
    </Dialog>
  );
};

export default NewGameDialog;