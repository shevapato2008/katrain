import { act, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import QRCode from 'qrcode';
import { WechatNativePayment } from './WechatNativePayment';
import type { BillingOrder } from './types';

const translations = vi.hoisted(() => ({} as Record<string, string>));
vi.mock('../../hooks/useTranslation', () => ({ useTranslation: () => ({ lang: 'cn', t: (key: string, fallback: string) => translations[key] ?? fallback }) }));
const order = (): BillingOrder => ({ id: 'native-test', sku: 'topup_10', kind: 'topup', status: 'pending', amount_fen: 1000, currency: 'CNY', provider: 'wechat', payments_mode: 'live', created_at: '2026-11-08T00:00:00Z', expires_at: '2026-11-08T00:15:00Z', paid_at: null, fulfillment: null, payment_url: 'weixin://wxpay/bizpayurl?pr=fixture-raw%2Bvalue', payment_state: 'ready' });
const flush = async () => act(async () => { await Promise.resolve(); await Promise.resolve(); });
beforeEach(() => { vi.useFakeTimers(); vi.setSystemTime(new Date('2026-11-08T00:00:00Z')); Object.keys(translations).forEach(key => delete translations[key]); });
afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); });

describe('WeChat Native payment presentation', () => {
  it('encodes the unchanged Native URL locally into a black and white image with a four-module quiet zone', async () => {
    const encode = vi.spyOn(QRCode, 'toString');
    render(<WechatNativePayment order={order()} />);
    await flush();
    const image = screen.getByRole('img', { name: '微信支付二维码' });
    expect(image.getAttribute('src')).toMatch(/^data:image\/svg\+xml;charset=utf-8,/);
    expect(encode).toHaveBeenCalledWith(order().payment_url, expect.objectContaining({ margin: 4, width: 224, color: { dark: '#000000ff', light: '#ffffffff' } }));
    expect(screen.getByRole('status')).toHaveTextContent('等待微信支付确认');
    expect(screen.getByText('二维码剩余 15:00')).toBeInTheDocument();
    expect(screen.getByText(/另一块屏幕/)).toBeInTheDocument();
  });

  it.each([
    'weixin://wxpay/bizpayurl/up?pr=NwY5Mz9&groupid=00',
    'weixin://pay.weixin.qq.com/bizpayurl/up?pr=NwY5Mz9&groupid=00',
    'weixin://wxpay/bizpayurl?pr=JyC91EIz1',
  ])('preserves official Native URL forms: %s', async payment_url => {
    const encode = vi.spyOn(QRCode, 'toString');
    render(<WechatNativePayment order={{ ...order(), payment_url }} />);
    await flush();
    expect(encode).toHaveBeenCalledWith(payment_url, expect.any(Object));
    expect(screen.getByRole('img')).toBeInTheDocument();
  });

  it('uses server remaining time even when the device clock is a day ahead', async () => {
    vi.setSystemTime(new Date('2026-11-09T00:00:00Z'));
    render(<WechatNativePayment order={{ ...order(), server_now: '2026-11-08T00:00:00Z' }} />);
    await flush();
    expect(screen.getByRole('img')).toBeInTheDocument();
    expect(screen.getByText('二维码剩余 15:00')).toBeInTheDocument();
    await act(async () => { vi.advanceTimersByTime(900000); });
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('正在确认支付结果');
  });

  it('hides the QR at the local cutoff while continuing to describe pending as confirming', async () => {
    render(<WechatNativePayment order={order()} />);
    await flush();
    await act(async () => { vi.advanceTimersByTime(15 * 60 * 1000); });
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('正在确认支付结果，请勿重复下单。');
    expect(screen.queryByText('订单已过期')).not.toBeInTheDocument();
  });

  it.each(['paid', 'failed', 'expired', 'cancelled'] as const)('renders a translated %s receipt without a QR', async status => {
    translations[`membership:order_${status}`] = `translated-${status}`;
    translations['membership:wechat_paid'] = 'translated-paid';
    render(<WechatNativePayment order={{ ...order(), status }} />);
    await flush();
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent(`translated-${status}`);
  });

  it('does not encode an external URL or a cancelled pending order', async () => {
    const encode = vi.spyOn(QRCode, 'toString');
    const view = render(<WechatNativePayment order={{ ...order(), payment_url: 'https://external.example/qr' }} />);
    await flush();
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
    expect(encode).not.toHaveBeenCalled();
    view.rerender(<WechatNativePayment order={{ ...order(), cancel_requested: true, payment_state: 'confirming' }} />);
    await flush();
    expect(screen.getByRole('status')).toHaveTextContent('正在确认取消结果');
    expect(encode).not.toHaveBeenCalled();
  });
});
