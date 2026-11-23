import { useEffect } from 'react';
import { Box, Button, Card, CardActions, CardContent, Stack, Typography } from '@mui/material';
import { useTranslation } from '../../../hooks/useTranslation';
import type { HintMove } from '../../../api';

interface Props {
  moves: HintMove[];
  timeoutS: number;
  onClose: () => void; // 关闭/超时 → API.hintDismiss()
  physicalLamps?: boolean;
}

const HINT_RANK_BADGES = [
  { color: '#ef4444', textColor: '#ffffff', key: 'game:hint_rank_1', label: '红 · 首选' },
  { color: '#eab308', textColor: '#101412', key: 'game:hint_rank_2', label: '黄 · 次选' },
  { color: '#22c55e', textColor: '#0c130f', key: 'game:hint_rank_3', label: '绿 · 三选' },
] as const;

/** 红/黄/绿三色灯闪烁期间的屏幕同步面板：各选点颜色/胜率/目差（PRD §3.3）。 */
const HintPanel = ({ moves, timeoutS, onClose, physicalLamps = true }: Props) => {
  const { t } = useTranslation();
  useEffect(() => {
    const timer = setTimeout(onClose, timeoutS * 1000);
    return () => clearTimeout(timer);
  }, [timeoutS, onClose]);
  return (
    <Card sx={{ position: 'absolute', top: 56, right: 8, zIndex: 130, minWidth: 268 }}>
      <CardContent>
        <Typography variant="subtitle1">
          {physicalLamps
            ? t('game:hint_colored_lamps', 'AI 支招（红 / 黄 / 绿灯闪烁处）')
            : t('Suggest', '支招')}
        </Typography>
        <Stack spacing={0.75} sx={{ mt: 1 }}>
          {moves.map((m, idx) => {
            const badge = HINT_RANK_BADGES[idx];
            return (
              <Typography key={m.gtp} variant="body2" sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                {badge && (
                  <Box
                    component="span"
                    data-testid={`hint-rank-badge-${idx + 1}`}
                    sx={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      px: 0.75,
                      py: 0.125,
                      borderRadius: 1,
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      lineHeight: 1.4,
                      bgcolor: badge.color,
                      color: badge.textColor,
                      flexShrink: 0,
                    }}
                  >
                    {t(badge.key, badge.label)}
                  </Box>
                )}
                {m.gtp} · {t('winrate', '胜率')} {m.winrate != null ? `${(m.winrate * 100).toFixed(1)}%` : '—'} ·{' '}
                {t('score', '目差')} {m.score_lead != null ? m.score_lead.toFixed(1) : '—'}
              </Typography>
            );
          })}
        </Stack>
      </CardContent>
      <CardActions>
        <Button fullWidth variant="contained" onClick={onClose}>{t('Close', '关闭')}</Button>
      </CardActions>
    </Card>
  );
};

export default HintPanel;
