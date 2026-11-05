import { Box, Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, Typography } from '@mui/material';
import { useTranslation } from '../../../hooks/useTranslation';

interface Props {
  source: 'ranked' | 'star';
  open: boolean;
  phase: 'idle' | 'loading' | 'result' | 'error';
  lead?: number | null;
  winrate?: number | null;
  blackArea?: number;
  whiteArea?: number;
  quotaNote: string;
  error?: string;
  onRetry?: () => void;
  onClose: () => void;
}

/** A local view of an already requested estimate; this component never queries or ends a game. */
export default function TerritoryDialog({ source, open, phase, lead, winrate, blackArea, whiteArea, quotaNote, error, onRetry, onClose }: Props) {
  const { t } = useTranslation();
  const finiteLead = typeof lead === 'number' && Number.isFinite(lead);
  const summary = !finiteLead ? t('game:territory_lead_missing', '暂未取得领先判断')
    : lead === 0 ? t('game:territory_even', '接近均势')
    : (lead > 0 ? t('game:territory_black_lead', '预计黑领先 {n} 目')
      : t('game:territory_white_lead', '预计白领先 {n} 目')).replace('{n}', Math.abs(lead).toFixed(1));
  return <Dialog open={open} onClose={onClose} className="kiosk-game-side-dialog" aria-labelledby="territory-dialog-title" data-testid="territory-dialog">
    <DialogTitle id="territory-dialog-title">{t('game:territory_title', '领地判断')}</DialogTitle>
    <DialogContent>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        {source === 'ranked' ? t('game:territory_ranked_source', '升降级 · 云端参考') : t('game:territory_star_source', '星阵 · 账号道具')}
      </Typography>
      <Box role="status" aria-live="polite" data-testid={open && source === 'star' && phase === 'result' ? 'engine-analysis-summary' : undefined}>
        {phase === 'loading' ? <>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, my: 2 }}>
            <CircularProgress size={24} />
            <Typography>{t('game:territory_loading', '正在请求领地判断…')}</Typography>
          </Box>
          <Typography variant="body2" color="text.secondary">{t('game:territory_query_note', '关闭仅隐藏；离开页面后重新查询可能使用额度。')}</Typography>
        </> : phase === 'error' ? <>
          <Typography sx={{ fontSize: 20, mb: 1 }}>{t('game:territory_error', '暂时无法取得领地判断')}</Typography>
          <Typography variant="body2" color="text.secondary">{error}</Typography>
        </> : <>
          <Typography sx={{ fontSize: 24, lineHeight: 1.35, fontWeight: 600, mb: 1 }}>{summary}</Typography>
          {source === 'star' && typeof winrate === 'number' && Number.isFinite(winrate) && winrate >= 0 && winrate <= 1 &&
            <Typography variant="body2" sx={{ mb: 1 }}>{t('live:black_winrate', '黑棋胜率')} {(winrate * 100).toFixed(1)}%</Typography>}
          {[[blackArea, t('game:territory_black_region', '黑方较确定区域 {n} 点')],
            [whiteArea, t('game:territory_white_region', '白方较确定区域 {n} 点')]].map(([count, label], index) => (
            typeof count === 'number' && Number.isFinite(count) && count >= 0
              ? <Typography key={index} variant="body2">{String(label).replace('{n}', String(count))}</Typography> : null
          ))}
        </>}
      </Box>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>{quotaNote}</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>{t('game:territory_reference', '局中参考，正式胜负以终局数子为准')}</Typography>
    </DialogContent>
    <DialogActions>
      {phase === 'error' && onRetry && <Button variant="outlined" onClick={onRetry}>{t('game:retry', '重试')}</Button>}
      <Button variant="contained" onClick={onClose} sx={{ flex: 1, minHeight: 44 }}>{t('game:territory_close', '关闭领地，继续下棋')}</Button>
    </DialogActions>
  </Dialog>;
}
