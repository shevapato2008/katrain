import { useEffect, useMemo, useState } from 'react';
import QRCode from 'qrcode';
import type { BillingOrder } from './types';
import { useMembershipI18n } from './useMembershipI18n';
import './WechatNativePayment.css';

/** Validate the Native transport, while encoding the provider's original bytes unchanged. */
function nativeUrl(value?: string | null): value is string {
  return typeof value === 'string' && value.length <= 2048 && value.length > 9
    && value.startsWith('weixin://') && !/[\x00-\x20\x7f]/.test(value);
}

/** Presentation only: time expiry never establishes an accounting terminal state. */
export function WechatNativePayment({ order, layout = 'galaxy' }: { order: BillingOrder; layout?: 'galaxy' | 'kiosk' }) {
  const { t, number } = useMembershipI18n();
  const [, setTick] = useState(0);
  const clock = useMemo(() => ({
    remainingMs: Date.parse(order.expires_at) - (order.server_now && Number.isFinite(Date.parse(order.server_now)) ? Date.parse(order.server_now) : Date.now()),
    startedAt: performance.now(),
  }), [order.id, order.expires_at, order.server_now]);
  const [qr, setQr] = useState<{ url: string; src: string } | null>(null);
  const [qrError, setQrError] = useState(false);
  const remaining = Math.max(0, Math.ceil((clock.remainingMs - (performance.now() - clock.startedAt)) / 1000));
  const payable = order.status === 'pending' && remaining > 0 && !order.cancel_requested && order.payment_state !== 'confirming';
  const url = payable && nativeUrl(order.payment_url) ? order.payment_url : null;
  useEffect(() => {
    if (order.status !== 'pending') return;
    const tick = () => setTick(value => value + 1);
    tick();
    const timer = window.setInterval(tick, 1000);
    document.addEventListener('visibilitychange', tick);
    return () => { window.clearInterval(timer); document.removeEventListener('visibilitychange', tick); };
  }, [order.id, order.status]);
  useEffect(() => {
    let stopped = false;
    setQr(null); setQrError(false);
    if (url) void QRCode.toString(url, { type: 'svg', width: 224, margin: 4, errorCorrectionLevel: 'M', color: { dark: '#000000ff', light: '#ffffffff' } }).then(svg => {
      if (!stopped) setQr({ url, src: `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}` });
    }).catch(() => { if (!stopped) setQrError(true); });
    return () => { stopped = true; };
  }, [url]);
  const terminal = {
    paid: t('membership:wechat_paid', '微信支付成功，正在同步账户。'),
    failed: t('membership:order_failed', '订单未完成'),
    expired: t('membership:order_expired', '订单已过期'),
    cancelled: t('membership:order_cancelled', '订单已取消'),
    refunded: t('membership:order_refunded', '已退款'),
  };
  const confirming = !payable || order.payment_state === 'confirming';
  const status = order.status !== 'pending' ? terminal[order.status]
    : order.cancel_requested ? t('membership:wechat_cancel_confirming', '正在确认取消结果；如已支付，将以支付回执为准。')
      : confirming ? t('membership:wechat_confirming', '正在确认支付结果，请勿重复下单。')
        : qrError ? t('membership:wechat_qr_error', '二维码暂时无法显示，请重试确认订单。')
          : !url ? t('membership:wechat_qr_unavailable', '二维码暂未准备好，正在确认订单。')
            : t('membership:wechat_waiting', '等待微信支付确认');
  const time = `${number(Math.floor(remaining / 60), { minimumIntegerDigits: 2 })}:${number(remaining % 60, { minimumIntegerDigits: 2 })}`;
  const countdown = url && <p className="wechat-native__countdown">{t('membership:wechat_valid_for', '二维码剩余 {time}', { time })}</p>;
  return <section className={`wechat-native wechat-native--${layout}`} aria-label={t('membership:wechat_scan', '扫码支付')}>
    {order.status === 'pending' && <div className="wechat-native__visual">
      {url && qr?.url === url ? <img className="wechat-native__qr" src={qr.src} width={224} height={224} alt={t('membership:wechat_qr_alt', '微信支付二维码')} /> : <div className="wechat-native__placeholder" aria-hidden="true" />}
      {layout === 'galaxy' && countdown}
    </div>}
    <div className="wechat-native__copy">
<p className="wechat-native__status" role="status" aria-live="polite">{status}</p>
      {layout === 'kiosk' && countdown}
      {order.status === 'pending' && <>
        {url && <p>{t('membership:wechat_scan_help', '请用手机微信“扫一扫”扫描二维码。')}</p>}
        <p className="wechat-native__phone-help">{t('membership:wechat_another_screen', '手机浏览时，请在另一块屏幕打开本页，再用手机微信扫码。')}</p>
        <p>{t('membership:wechat_close_help', '关闭仅隐藏此页，可从订单记录继续查看。')}</p>
      </>}
    </div>
  </section>;
}
