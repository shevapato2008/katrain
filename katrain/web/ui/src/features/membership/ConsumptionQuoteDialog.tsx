import { Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle, Typography } from '@mui/material';
import { useMembershipI18n } from './useMembershipI18n';
import type { BillingQuote } from './types';

interface Props { kiosk?: boolean; quote: BillingQuote | null; busy?: boolean; error?: string | null; onConfirm: () => void; onCancel: () => void }
export function ConsumptionQuoteDialog({ kiosk = false, quote, busy = false, error, onConfirm, onCancel }: Props) {
  const { t, number } = useMembershipI18n();
  if (!quote) return null;
  const quoteChanged = quote.source === 'free_report';
  const title = quoteChanged ? t('membership:quote_changed', '报价已更新，请重新发起分析')
    : quote.kind === 'report' ? t('membership:confirm_report', '确认生成报告') : t('membership:confirm_position', '确认分析当前局面');
  const closeLabel = quoteChanged ? t('membership:close', '关闭') : t('membership:cancel', '取消');
  const canClose = quoteChanged || !busy;
  const points = number(Number(quote.wallet_max_display_points), { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const policy = t('membership:consumption_policy', '会员优先，不足时整次使用API积分，最多 {points} 积分', { points });
  const source = quote.source === 'membership' ? t('membership:source_membership', '当前预计使用会员额度')
    : quote.source === 'wallet' ? t('membership:source_wallet', '当前预计使用API积分')
      : quote.source === 'owned' ? t('membership:source_owned', '本次结果已拥有') : null;
  const confirmLabel = busy ? t('membership:processing', '处理中…')
    : quote.source === 'wallet' ? t('membership:confirm_wallet_consumption', '使用API积分，最多扣{points}', { points })
      : t('membership:confirm_consumption', '确认并开始');
  if (kiosk) return <div className="cdlg" role="dialog" aria-modal="true" aria-labelledby="consumption-quote-title" data-testid="consumption-quote">
    <div className="cdlg__box"><h3 id="consumption-quote-title">{title}</h3>
      {!quoteChanged && <><p>{policy}</p><p>{source}</p>{error && <p role="alert">{error}</p>}</>}
      <div className="cdlg__acts"><button type="button" className="ghost" disabled={!canClose} onClick={onCancel}>{closeLabel}</button>
        {!quoteChanged && <button type="button" className="main" disabled={busy} onClick={onConfirm}>{confirmLabel}</button>}</div>
    </div>
  </div>;
  return <Dialog open onClose={canClose ? onCancel : undefined} maxWidth="xs" fullWidth data-testid="consumption-quote">
    <DialogTitle>{title}</DialogTitle>
    {!quoteChanged && <DialogContent><Typography>{policy}</Typography><Typography sx={{ mt: 1 }}>{source}</Typography>
      {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}</DialogContent>}
    <DialogActions><Button disabled={!canClose} onClick={onCancel} sx={{ color: 'text.primary', minHeight: 44 }}>{closeLabel}</Button>
      {!quoteChanged && <Button variant="contained" disabled={busy} onClick={onConfirm} sx={{ minHeight: 44 }}>{confirmLabel}</Button>}</DialogActions>
  </Dialog>;
}
