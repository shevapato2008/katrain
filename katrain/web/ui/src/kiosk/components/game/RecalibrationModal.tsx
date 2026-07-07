import { useState } from 'react';
import { Button, Dialog, DialogActions, DialogContent, DialogTitle, Typography } from '@mui/material';
import { Warning as WarningIcon } from '@mui/icons-material';
import { useTranslation } from '../../../hooks/useTranslation';
import { GeometryAPI } from '../../../api/geometryApi';
import { API } from '../../../api';

interface Props {
  open: boolean;
  onClose: () => void;
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
const RecalibrationModal = ({ open, onClose }: Props) => {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState(false);

  // Lifted verbatim from PoseLostBanner.tsx (pre-B1.4).
  const recalibrate = async () => {
    setBusy(true);
    setError(null);
    try {
      // 签名 calibrate(trigger: 'auto' | 'manual') — geometryApi.ts:85（评审 Codex I4）。
      // 'manual' 显式声明这是用户触发（D2③ 硬规则的代码级痕迹）。
      await GeometryAPI.calibrate('manual'); // POST /api/v1/geometry/calibrate (202)
      await API.visionResetSync();
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
    <Dialog open={open && !dismissed} onClose={handleDismiss} maxWidth="xs" fullWidth>
      <DialogTitle sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1, textAlign: 'center' }}>
        <WarningIcon sx={{ color: 'warning.main', fontSize: 30 }} />
        {t('Board may have moved', '棋盘可能被移动')}
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" sx={{ textAlign: 'center', color: 'text.secondary' }}>
          {t('No LED needed — just align the outer frame', '无需 LED，对齐外框即可')}
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
