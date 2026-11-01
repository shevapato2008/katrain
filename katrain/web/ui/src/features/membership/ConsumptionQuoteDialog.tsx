import { Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle, Typography } from '@mui/material';
import { useTranslation } from '../../hooks/useTranslation';
import type { BillingQuote } from './types';

interface Props { kiosk?: boolean; quote: BillingQuote | null; busy?: boolean; error?: string | null; onConfirm: () => void; onCancel: () => void }
export function ConsumptionQuoteDialog({ kiosk = false, quote, busy = false, error, onConfirm, onCancel }: Props) {
  const { t } = useTranslation();
  if (!quote) return null;
  const title = quote.kind === 'report' ? t('membership:confirm_report', '确认生成报告') : t('membership:confirm_position', '确认分析当前局面');
  const policy = t('membership:consumption_policy', '会员优先，不足时整次使用API积分，最多 {points} 积分').replace('{points}', quote.wallet_max_display_points);
  const source = quote.source === 'membership' ? t('membership:source_membership', '当前预计使用会员额度')
    : quote.source === 'wallet' ? t('membership:source_wallet', '当前预计使用API积分')
      : quote.source === 'free_report' ? t('membership:source_free', '当前预计使用每周免费报告资格')
        : t('membership:source_owned', '本次结果已拥有');
  const confirmLabel = busy ? t('membership:processing', '处理中…') : t('membership:confirm_consumption', '确认并开始');
  if (kiosk) return <div className="cdlg" role="dialog" aria-modal="true" aria-labelledby="consumption-quote-title" data-testid="consumption-quote">
    <div className="cdlg__box"><h3 id="consumption-quote-title">{title}</h3><p>{policy}</p><p>{source}</p>
      {error && <p role="alert">{error}</p>}
      <div className="cdlg__acts"><button type="button" className="ghost" disabled={busy} onClick={onCancel}>{t('common:cancel', '取消')}</button>
        <button type="button" className="main" disabled={busy} onClick={onConfirm}>{confirmLabel}</button></div>
    </div>
  </div>;
  return <Dialog open onClose={busy ? undefined : onCancel} maxWidth="xs" fullWidth data-testid="consumption-quote">
    <DialogTitle>{title}</DialogTitle><DialogContent><Typography>{policy}</Typography><Typography sx={{ mt: 1 }}>{source}</Typography>
      {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}</DialogContent>
    <DialogActions><Button disabled={busy} onClick={onCancel} sx={{ color: 'text.primary', minHeight: 44 }}>{t('common:cancel', '取消')}</Button><Button variant="contained" disabled={busy} onClick={onConfirm} sx={{ minHeight: 44 }}>{confirmLabel}</Button></DialogActions>
  </Dialog>;
}
