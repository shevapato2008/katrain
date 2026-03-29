import { Snackbar, Alert } from '@mui/material';
import { Warning as WarningIcon } from '@mui/icons-material';

interface AmbiguousStoneAlertProps {
  open: boolean;
  onClose: () => void;
}

const AmbiguousStoneAlert = ({ open, onClose }: AmbiguousStoneAlertProps) => (
  <Snackbar
    open={open}
    autoHideDuration={5000}
    onClose={onClose}
    anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
  >
    <Alert
      severity="warning"
      icon={<WarningIcon />}
      onClose={onClose}
      sx={{ width: '100%', fontSize: '1rem' }}
    >
      无法确定落子位置，请调整棋子
    </Alert>
  </Snackbar>
);

export default AmbiguousStoneAlert;
