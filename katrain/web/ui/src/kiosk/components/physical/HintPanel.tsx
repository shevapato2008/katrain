import { useEffect } from 'react';
import { Button, Card, CardActions, CardContent, Stack, Typography } from '@mui/material';
import { useTranslation } from '../../../hooks/useTranslation';
import type { HintMove } from '../../../api';

interface Props {
  moves: HintMove[];
  timeoutS: number;
  onClose: () => void; // 关闭/超时 → API.hintDismiss()
}

/** 白灯闪烁期间的屏幕同步面板：各选点胜率/目差（PRD §3.3）。 */
const HintPanel = ({ moves, timeoutS, onClose }: Props) => {
  const { t } = useTranslation();
  useEffect(() => {
    const timer = setTimeout(onClose, timeoutS * 1000);
    return () => clearTimeout(timer);
  }, [timeoutS, onClose]);
  return (
    <Card sx={{ position: 'absolute', top: 56, right: 8, zIndex: 130, minWidth: 240 }}>
      <CardContent>
        <Typography variant="subtitle1">{t('AI suggestions (white lamps)', 'AI 支招（白灯闪烁处）')}</Typography>
        <Stack spacing={0.5} sx={{ mt: 1 }}>
          {moves.map((m) => (
            <Typography key={m.gtp} variant="body2">
              {m.gtp} · {t('winrate', '胜率')} {m.winrate != null ? `${(m.winrate * 100).toFixed(1)}%` : '—'} ·{' '}
              {t('score', '目差')} {m.score_lead != null ? m.score_lead.toFixed(1) : '—'}
            </Typography>
          ))}
        </Stack>
      </CardContent>
      <CardActions>
        <Button fullWidth variant="contained" onClick={onClose}>{t('Close', '关闭')}</Button>
      </CardActions>
    </Card>
  );
};

export default HintPanel;
