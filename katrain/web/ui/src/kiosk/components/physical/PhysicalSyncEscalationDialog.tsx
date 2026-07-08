import { Button, Dialog, DialogActions, DialogContent, DialogTitle, Typography } from '@mui/material';
import { useTranslation } from '../../../hooks/useTranslation';
import { API } from '../../../api';

interface Props {
  open: boolean;
  toPlace: number[][];
  toRemove: number[][];
  onClose: () => void;
}

/** Review B escape hatch: after escalate_after_s of physical lag, force a decision
 * instead of stalling the game forever. '改用屏幕落子' unbinds vision (orchestrator
 * clears the lamps, detection stops) and the game continues via on-screen taps. */
const PhysicalSyncEscalationDialog = ({ open, toPlace, toRemove, onClose }: Props) => {
  const { t } = useTranslation();
  const restored = () => {
    API.visionResetSync().catch(() => undefined);
    onClose();
  };
  const screenPlay = () => {
    API.visionUnbind().catch(() => undefined);
    onClose();
  };
  return (
    <Dialog open={open} maxWidth="xs" fullWidth>
      <DialogTitle>{t('Physical board out of sync', '物理棋盘长时间未跟上对局')}</DialogTitle>
      <DialogContent>
        <Typography variant="body2">
          {t(
            'Place / remove the lit stones, then confirm — or continue on screen.',
            '请按亮灯指示摆放（红/绿灯）或拿除（蓝灯）棋子后确认；也可改用屏幕继续对局。'
          )}
        </Typography>
        <Typography variant="caption" sx={{ display: 'block', mt: 1 }}>
          {t('To place', '待摆放')}: {toPlace.length} · {t('To remove', '待拿除')}: {toRemove.length}
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={restored} variant="contained">{t('Board restored', '已按指示恢复')}</Button>
        <Button onClick={screenPlay} color="warning">{t('Continue on screen', '改用屏幕落子')}</Button>
        <Button onClick={onClose}>{t('Keep waiting', '继续等待')}</Button>
      </DialogActions>
    </Dialog>
  );
};

export default PhysicalSyncEscalationDialog;
