import { useState } from 'react';
import { Button, Dialog, DialogActions, DialogContent, DialogTitle, Typography } from '@mui/material';
import { Warning as WarningIcon } from '@mui/icons-material';
import { useTranslation } from '../../../hooks/useTranslation';
import type { GameType } from '../../../api';
import { useParams } from 'react-router-dom';
import { useOptionalGeometry } from '../../context/GeometryContext';

interface Props {
  open: boolean;
  onClose: () => void;
  gameType?: GameType;
}

/** State B (design.md §5.1): blocking amber modal shown when board pose is lost mid-game.
 * Promoted from the old PoseLostBanner top Alert to a Dialog so board-loss surfaces can be
 * arbitrated one-visible-at-a-time (see the precedence comment in GamePage.tsx).
 * Recalibration (LED fiducials) is STRICTLY user-triggered — hard rule D2③: LEDs never
 * flash for geometry automatically. Body copy says so explicitly (aligns
 * [[feedback_no_auto_led_geometry]]).
 *
 * `dismissed` (仍要继续) is local component state rather than something the parent tracks:
 * `open` is otherwise driven purely by GamePage's recalOpen (visionStatus.poseLocked), which
 * won't itself change just because the user clicked through. GamePage remounts this component
 * with `key={String(visionStatus.poseLocked)}` so a fresh pose-loss cycle clears the dismiss
 * (React's "reset state via key" pattern — avoids a useEffect/ref reset). */
const RecalibrationModal = ({ open, onClose, gameType }: Props) => {
  const { t } = useTranslation();
  const geometry = useOptionalGeometry();
  const { sessionId } = useParams<{ sessionId: string }>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState(false);

  // Shared guard takes over while calibration runs; reset follows the original bind.
  const recalibrate = async () => {
    setBusy(true);
    setError(null);
    try {
      if (!geometry) throw new Error('Geometry provider unavailable');
      await geometry.startCalibration('manual', sessionId, gameType);
    } catch {
      setError(t('Re-align failed — try again', '重新定位失败，请重试'));
    } finally {
      setBusy(false);
    }
  };

  // Shared by the "仍要继续" button AND the Dialog's own onClose (backdrop click / Escape) —
  // both must set `dismissed` locally, or the Dialog would stay stuck open (open&&!dismissed)
  // after a backdrop click since the external `onClose` prop alone doesn't change `open`.
  const handleDismiss = () => {
    setDismissed(true);
    onClose();
  };

  return (
    <Dialog open={open && !dismissed} onClose={handleDismiss} maxWidth="xs" fullWidth className="kiosk-game-side-dialog">
      <DialogTitle sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1, textAlign: 'center' }}>
        <WarningIcon sx={{ color: 'warning.main', fontSize: 30 }} />
        {t('Board may have moved', '棋盘可能被移动')}
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" sx={{ textAlign: 'center', color: 'text.secondary' }}>
          {t('game:recalibrate_needs_empty_board', '重新标定会亮灯，而且要先把棋盘上的子全部拿走；棋盘没被挪过的话，点「仍要继续」')}
        </Typography>
        {error && (
          <Typography variant="caption" color="error" component="div" sx={{ textAlign: 'center', mt: 1 }}>
            {error}
          </Typography>
        )}
      </DialogContent>
      <DialogActions sx={{ justifyContent: 'center', gap: 1.5, pb: 2.5 }}>
        <Button onClick={handleDismiss} sx={{ color: 'text.secondary' }}>
          {t('Continue anyway', '仍要继续')}
        </Button>
        <Button variant="contained" color="warning" disabled={busy} onClick={recalibrate}>
          {t('Recalibrate', '重新标定')}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default RecalibrationModal;
