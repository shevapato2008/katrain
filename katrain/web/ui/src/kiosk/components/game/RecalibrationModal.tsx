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
  onRetryBind?: () => Promise<boolean>;
  onEmptyCalibration?: () => void;
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
const RecalibrationModal = ({ open, onClose, gameType, onRetryBind, onEmptyCalibration }: Props) => {
  const { t } = useTranslation();
  const geometry = useOptionalGeometry();
  const { sessionId } = useParams<{ sessionId: string }>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const local = gameType === 'pvp_local' && !!onRetryBind;
  const restore = async (align: boolean) => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      if (align) await geometry?.relocate();
      if (!await onRetryBind?.()) throw new Error('bind unavailable');
    } catch {
      setError(t('local:recovery_failed', '识别还未恢复，请检查连接和盘面后重试'));
    } finally { setBusy(false); }
  };

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
    <Dialog open={open && !dismissed} onClose={local ? undefined : handleDismiss} maxWidth={local ? 'sm' : 'xs'} fullWidth className="kiosk-game-side-dialog">
      <DialogTitle sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1, textAlign: 'center' }}>
        <WarningIcon sx={{ color: 'warning.main', fontSize: 30 }} />
        {local ? t('local:recover_physical', '恢复实体盘识别') : t('Board may have moved', '棋盘可能被移动')}
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" sx={{ textAlign: 'center', color: 'text.secondary' }}>
          {local ? t('local:recover_confirmed_stones', '保留已确认的棋子，拿回还未确认的子；对齐外框后，按原棋谱重新检查识别。')
            : t('game:recalibrate_needs_empty_board', '重新标定会亮灯，而且要先把棋盘上的子全部拿走；棋盘没被挪过的话，点「仍要继续」')}
        </Typography>
        {local && <Typography variant="body2" sx={{ textAlign: 'center', color: 'text.secondary', mt: 1 }}>
          {t('local:recover_empty_option', '对齐外框不亮灯、不用清盘；空盘标定需要拿走全部棋子，完成后按棋谱摆回。')}
        </Typography>}
        {error && (
          <Typography variant="caption" color="error" component="div" sx={{ textAlign: 'center', mt: 1 }}>
            {error}
          </Typography>
        )}
      </DialogContent>
      <DialogActions sx={{ justifyContent: 'center', gap: local ? 1 : 1.5, pb: 2.5, ...(local ? { flexWrap: 'wrap', '& .MuiButton-root': { minHeight: 44 } } : {}) }}>
        {local ? <>
          <Button onClick={handleDismiss}>{t('game:exit_game', '退出对局')}</Button>
          <Button onClick={onEmptyCalibration} disabled={busy}>{t('local:empty_calibration', '空盘标定')}</Button>
          <Button onClick={() => void restore(false)} disabled={busy}>{t('local:retry_geometry', '重新检查')}</Button>
          <Button variant="contained" color="warning" onClick={() => void restore(true)} disabled={busy || geometry?.status?.capabilities.camera_ready === false}>
            {busy ? t('local:recovering', '检查中…') : t('vision:relocate', '对齐外框')}
          </Button>
        </> : <>
        <Button onClick={handleDismiss} sx={{ color: 'text.secondary' }}>
          {t('Continue anyway', '仍要继续')}
        </Button>
        <Button variant="contained" color="warning" disabled={busy} onClick={recalibrate}>
          {t('Recalibrate', '重新标定')}
        </Button>
        </>}
      </DialogActions>
    </Dialog>
  );
};

export default RecalibrationModal;
