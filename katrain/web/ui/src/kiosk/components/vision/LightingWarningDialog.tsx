import { Button, Dialog, DialogActions, DialogContent, DialogTitle } from '@mui/material';
import type { LightingReason } from '../../../api/geometryApi';
import { useTranslation } from '../../../hooks/useTranslation';

export default function LightingWarningDialog({ reason, onClose }: {
  reason: LightingReason | null;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  return <Dialog open={reason !== null} onClose={onClose} maxWidth="xs" fullWidth className="kiosk-game-side-dialog">
    <DialogTitle>{reason === 'frame_overexposed'
      ? t('vision:lighting_overexposed_title', '画面过亮，暂时无法可靠识别')
      : t('vision:lighting_underexposed_title', '画面过暗，暂时无法可靠识别')}</DialogTitle>
    <DialogContent>{t('vision:lighting_warning_body', '请移开遮挡；仍有提示时，请换到光线均匀、合适的地方再试。')}</DialogContent>
    <DialogActions><Button onClick={onClose}>{t('game:local_got_it', '知道了')}</Button></DialogActions>
  </Dialog>;
}
