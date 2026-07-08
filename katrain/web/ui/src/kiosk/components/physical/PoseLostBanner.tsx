import { useState } from 'react';
import { Alert, Button, Typography } from '@mui/material';
import { useTranslation } from '../../../hooks/useTranslation';
import { GeometryAPI } from '../../../api/geometryApi';
import { API } from '../../../api';

interface Props {
  visible: boolean;
}

/** Shown when board pose is lost mid-game. Recalibration (LED fiducials) is
 * STRICTLY user-triggered — hard rule D2③: LEDs never flash for geometry automatically. */
const PoseLostBanner = ({ visible }: Props) => {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!visible) return null;
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
  return (
    <Alert
      severity="warning"
      sx={{ position: 'absolute', top: 48, left: '50%', transform: 'translateX(-50%)', zIndex: 110 }}
      action={
        <Button color="inherit" size="small" disabled={busy} onClick={recalibrate}>
          {t('Re-align board', '重新定位')}
        </Button>
      }
    >
      {t('Board may have moved — recognition paused', '棋盘可能被移动，识别已暂停')}
      {error && (
        <Typography variant="caption" color="error" component="div">
          {error}
        </Typography>
      )}
    </Alert>
  );
};

export default PoseLostBanner;
