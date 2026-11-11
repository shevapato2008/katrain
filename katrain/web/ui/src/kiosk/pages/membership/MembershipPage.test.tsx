import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { BillingOrder, MembershipCatalog, MembershipUsage } from '../../../features/membership/types';
import { API } from '../../../api';
import { i18n } from '../../../i18n';
import MembershipPage from './MembershipPage';

const { auth, api } = vi.hoisted(() => ({
  auth: { identityKey: 'account-a' as string | null, status: 'authenticated', token: null as string | null,
    user: null as { username: string; is_admin: boolean } | null, isGuest: false, isStrictBoxKiosk: false },
  api: { getCatalog: vi.fn(), getUsage: vi.fn(), createOrder: vi.fn(), getOrder: vi.fn(), getOrders: vi.fn(), cancelOrder: vi.fn() },
}));
vi.mock('../../../context/AuthContext', () => ({ useAuth: () => auth }));
vi.mock('../../../api/membershipApi', () => ({ membershipApi: api }));

const capabilities = { membership: true, usage: true, quotes: true, positions: true, orders: true, can_claim_free_report: false };
const catalog = (): MembershipCatalog => ({
  catalog_version: 'v1', server_now: '2026-11-02T00:00:00Z', environment: 'TEST', membership_mode: 'enabled',
  capabilities, payments_mode: 'mock',
  plans: [
    { code: 'plus', name: 'Plus', amount_fen: 3900, term_days: 30, term_units: 9030, week_units: 3010, term_report_reference: 30, week_report_reference: 10, full_use_savings_percent: 56.8, sale_enabled: true },
    { code: 'pro', name: 'Pro', amount_fen: 9900, term_days: 30, term_units: 27090, week_units: 9030, term_report_reference: 90, week_report_reference: 30, full_use_savings_percent: 63.5, sale_enabled: true },
    { code: 'max', name: 'Max', amount_fen: 19900, term_days: 30, term_units: 72240, week_units: 24080, term_report_reference: 240, week_report_reference: 80, full_use_savings_percent: 72.5, sale_enabled: false },
  ],
  topups: [{ sku: 'topup_10', amount_fen: 1000, credits: 1000, display_points: '10.00' }, { sku: 'topup_30', amount_fen: 3000, credits: 3000, display_points: '30.00' }],
  profiles: { normal: { visits: 500, credits_per_position: 1, display_points_per_position: '0.01' }, advanced: { visits: 2000, credits_per_position: 4, display_points_per_position: '0.04' } },
});
const usage = (): MembershipUsage => ({
  catalog_version: 'v1', server_now: '2026-11-02T00:00:00Z', environment: 'TEST', revision: 1,
  capabilities, payments_mode: 'mock',
  plan: { current: { code: 'pro', name: 'Pro', starts_at: '2026-11-01T00:00:00Z', ends_at: '2026-12-01T00:00:00Z' }, next: null },
  term: { limit: 27090, used: 15172, reserved: 1082, remaining: 10836, percent: 40, reset_at: '2026-12-01T00:00:00Z' },
  week: { limit: 9030, used: 1505, reserved: 301, remaining: 7224, percent: 80, reset_at: '2026-11-08T16:00:00Z' },
  wallet: { credits: 1000, display_points: '10.00' }, free: null,
});
const order = (status: BillingOrder['status'] = 'pending'): BillingOrder => ({
  id: 'own-order-a', sku: 'topup_30', kind: 'topup', status, amount_fen: 3000, currency: 'CNY',
  payments_mode: 'mock', provider: 'mock', created_at: '2026-11-02T00:00:00Z', expires_at: '2026-11-02T00:15:00Z',
  paid_at: status === 'paid' ? '2026-11-02T00:01:00Z' : null,
  fulfillment: status === 'paid' ? { credits: 3000, display_points: '30.00' } : null,
});
const flush = async () => { await act(async () => { await Promise.resolve(); await Promise.resolve(); await Promise.resolve(); }); };
const mount = () => render(<MemoryRouter><MembershipPage /></MemoryRouter>);
const openTopup = () => fireEvent.click(screen.getByRole('tab', { name: 'API充值' }));

beforeEach(async () => {
  vi.useFakeTimers();
  Object.assign(auth, { identityKey: 'account-a', status: 'authenticated', token: null, user: null, isGuest: false, isStrictBoxKiosk: false });
  Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' });
  for (const fn of Object.values(api)) fn.mockReset();
  api.getCatalog.mockResolvedValue(catalog());
  api.getUsage.mockResolvedValue(usage());
  api.createOrder.mockResolvedValue(order());
  api.getOrder.mockResolvedValue(order());
  api.getOrders.mockResolvedValue({ orders: [] });
  vi.spyOn(API, 'getTranslations').mockResolvedValue({ lang: 'cn', translations: {} });
  vi.spyOn(i18n, 'loadLiveTranslations').mockResolvedValue();
  await i18n.loadTranslations('cn');
});
afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); });

describe('Kiosk membership', () => {
  it('opens binding from the existing account area without touching the membership balance', async () => {
    auth.user = { username: 'existing-player', is_admin: false };
    const phoneStatus = vi.spyOn(API, 'phoneStatus').mockResolvedValue({ bound: false });
    mount(); await flush();
    fireEvent.click(screen.getByRole('button', { name: '绑定手机号' })); await flush();
    expect(screen.getByLabelText('当前账号密码')).toBeInTheDocument();
    expect(phoneStatus).toHaveBeenCalledWith(null, expect.any(AbortSignal));
    expect(api.getUsage).toHaveBeenCalledTimes(1);
    expect(api.createOrder).not.toHaveBeenCalled();
  });
  it('sends a strict kiosk account to launcher management instead of a local binding form', async () => {
    auth.user = { username: 'existing-player', is_admin: false }; auth.isStrictBoxKiosk = true;
    const phoneStatus = vi.spyOn(API, 'phoneStatus');
    mount(); await flush();
    expect(screen.getByRole('button', { name: '在主页管理手机号' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '绑定手机号' })).not.toBeInTheDocument();
    expect(phoneStatus).not.toHaveBeenCalled();
  });
  const switchLanguage = async (lang: string, translations: Record<string, string>) => {
    vi.mocked(API.getTranslations).mockResolvedValue({ lang, translations });
    await act(async () => { await i18n.loadTranslations(lang); });
  };

  it('localizes a comma-decimal display while keeping raw numeric progress and the current account snapshot', async () => {
    api.getUsage.mockResolvedValue({ ...usage(), term: { ...usage().term!, percent: 65.6 } });
    mount();
    await flush();
    await switchLanguage('de', { 'membership:kiosk_term_remaining_aria': 'Verbleibendes Kontingent im Zeitraum' });
    const progress = screen.getByRole('progressbar', { name: 'Verbleibendes Kontingent im Zeitraum' });
    expect(progress).toHaveAttribute('aria-valuenow', '65.6');
    expect(progress.firstElementChild).toHaveStyle({ width: '65.6%' });
    expect(screen.getByText(/^65,6\s*%$/)).toBeInTheDocument();
    expect(api.getCatalog).toHaveBeenCalledTimes(1);
    expect(api.getUsage).toHaveBeenCalledTimes(1);
  });

  it('updates an open order receipt and controls when language changes without recreating its order', async () => {
    mount();
    await flush();
    openTopup();
    fireEvent.click(screen.getByRole('button', { name: /^充值/ }));
    await flush();
    await switchLanguage('en', {
      'membership:kiosk_order_confirmation': 'Order confirmation',
      'membership:kiosk_order_waiting_server': 'Waiting for server payment confirmation',
      'membership:kiosk_return_selection': 'Back to selection',
      'membership:close': 'Close',
    });
    const dialog = screen.getByRole('dialog', { name: 'Order confirmation' });
    expect(dialog).toHaveTextContent('Waiting for server payment confirmation');
    expect(within(dialog).getByRole('button', { name: 'Back to selection' })).toBeInTheDocument();
    expect(within(dialog).getByRole('button', { name: 'Close' })).toBeInTheDocument();
    expect(api.createOrder).toHaveBeenCalledTimes(1);
    expect(api.getUsage).toHaveBeenCalledTimes(1);
    expect(api.getOrder).not.toHaveBeenCalled();
  });

  it('translates an already-present uncertain order error without retrying a purchase', async () => {
    api.createOrder.mockRejectedValue(new Error('offline'));
    mount();
    await flush();
    openTopup();
    fireEvent.click(screen.getByRole('button', { name: /^充值/ }));
    await flush();
    expect(screen.getByRole('dialog')).toHaveTextContent('订单结果未确认，请先查看订单记录，避免重复创建。');
    await switchLanguage('en', { 'membership:kiosk_order_uncertain': 'Order result unknown. Check order history before trying again.' });
    expect(screen.getByRole('dialog')).toHaveTextContent('Order result unknown. Check order history before trying again.');
    expect(api.createOrder).toHaveBeenCalledTimes(1);
  });

  it('translates an open history error without requesting history again', async () => {
    api.getOrders.mockRejectedValue(new Error('offline'));
    mount();
    await flush();
    fireEvent.click(screen.getByRole('button', { name: '订单记录' }));
    await flush();
    expect(screen.getByRole('dialog')).toHaveTextContent('订单记录暂未同步，请稍后重试。');
    await switchLanguage('en', { 'membership:kiosk_history_error': 'Order history could not sync. Try again later.' });
    expect(screen.getByRole('dialog')).toHaveTextContent('Order history could not sync. Try again later.');
    expect(api.getOrders).toHaveBeenCalledTimes(1);
  });

  it('keeps unknown balances and percentages unknown and blocks purchases', async () => {
    api.getUsage.mockRejectedValue(new Error('offline'));
    mount();
    await flush();
    expect(screen.getByText('暂时无法同步用量')).toBeInTheDocument();
    expect(screen.queryByText('0.00')).not.toBeInTheDocument();
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    openTopup();
    expect(screen.getByRole('button', { name: /^充值/ })).toBeDisabled();
    expect(api.createOrder).not.toHaveBeenCalled();
  });

  it('shows term and weekly remaining percentages separately', async () => {
    mount();
    await flush();
    expect(screen.getByRole('progressbar', { name: '本期剩余比例' })).toHaveAttribute('aria-valuenow', '40');
    expect(screen.getByRole('progressbar', { name: '本周剩余比例' })).toHaveAttribute('aria-valuenow', '80');
    expect(screen.getByText('40.0%')).toBeInTheDocument();
    expect(screen.getByText('80.0%')).toBeInTheDocument();
    expect(screen.queryByText(/标准单位|会员等值积分|每日次数/)).not.toBeInTheDocument();
  });

  it('does not invent a free allowance before eligibility is verified', async () => {
    api.getUsage.mockResolvedValue({ ...usage(), plan: { current: null, next: null }, term: null, week: null, free: null });
    mount();
    await flush();
    expect(screen.getByText('免费报告资格待核验')).toBeInTheDocument();
    expect(screen.queryByText(/剩余\s*0\s*\//)).not.toBeInTheDocument();
  });

  it('honors disabled payments even when Max is sale-enabled, without creating an order', async () => {
    const disabled = catalog();
    disabled.plans[2].sale_enabled = true;
    api.getCatalog.mockResolvedValue({ ...disabled, payments_mode: 'disabled' });
    api.getUsage.mockResolvedValue({ ...usage(), payments_mode: 'disabled' });
    mount();
    await flush();
    fireEvent.click(screen.getByRole('tab', { name: '会员' }));
    expect(screen.getByRole('button', { name: '选择 Plus' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '续费 Pro' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '选择 Max' })).toBeDisabled();
    expect(screen.getByText('支付暂未开放')).toBeInTheDocument();
    openTopup();
    expect(screen.getByRole('button', { name: /^充值/ })).toBeDisabled();
    expect(api.createOrder).not.toHaveBeenCalled();
  });

  it.each(['live', 'mock'] as const)('labels the TEST top-up footnote by payment mode: %s', async paymentsMode => {
    api.getCatalog.mockResolvedValue({ ...catalog(), payments_mode: paymentsMode });
    api.getUsage.mockResolvedValue({ ...usage(), payments_mode: paymentsMode });
    mount();
    await flush();
    openTopup();
    expect(screen.getByText('TEST · 测试环境')).toBeInTheDocument();
    if (paymentsMode === 'live') {
      expect(screen.queryByText('TEST模拟订单 · 不会真实收款')).not.toBeInTheDocument();
      expect(screen.getByText('付款前核对订单金额')).toBeInTheDocument();
    } else {
      expect(screen.getByText('TEST模拟订单 · 不会真实收款')).toBeInTheDocument();
      expect(screen.queryByText('付款前核对订单金额')).not.toBeInTheDocument();
    }
    expect(api.createOrder).not.toHaveBeenCalled();
  });

  it('keeps Max unavailable while a catalog-approved TEST plan is purchasable', async () => {
    const serviceCatalog = catalog();
    serviceCatalog.plans[0].term_days = 28;
    serviceCatalog.plans[0].term_report_reference = 37;
    api.getCatalog.mockResolvedValue(serviceCatalog);
    mount();
    await flush();
    fireEvent.click(screen.getByRole('tab', { name: '会员' }));
    expect(screen.getByRole('button', { name: '选择 Plus' })).toBeEnabled();
    expect(screen.getByRole('button', { name: '暂未开放' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '选择 Plus' }).closest('.km-plan')).toHaveTextContent('28天共约37盘');
    expect(screen.getByTestId('kiosk-membership-page')).not.toHaveTextContent(/标准单位|9030|72240/);
  });

  it('selects sale-enabled Max and previews its catalog-priced 199 yuan order', async () => {
    const serviceCatalog = catalog();
    serviceCatalog.plans[2].sale_enabled = true;
    api.getCatalog.mockResolvedValue(serviceCatalog);
    api.createOrder.mockResolvedValue({ ...order(), sku: 'membership_max', kind: 'membership', amount_fen: 19900 });
    mount();
    await flush();
    fireEvent.click(screen.getByRole('tab', { name: '会员' }));
    fireEvent.click(screen.getByRole('button', { name: '选择 Max' }));
    await flush();
    expect(api.createOrder).toHaveBeenCalledWith({ sku: 'membership_max', provider: 'mock', idempotency_key: expect.any(String) }, null, expect.any(AbortSignal));
    expect(screen.getByRole('dialog')).toHaveTextContent('¥199');
  });

  it('blocks a live or production mock checkout in this TEST-only release', async () => {
    api.getCatalog.mockResolvedValue({ ...catalog(), environment: 'production' });
    api.getUsage.mockResolvedValue({ ...usage(), environment: 'production' });
    mount();
    await flush();
    openTopup();
    expect(screen.getByRole('button', { name: /^充值/ })).toBeDisabled();
  });

  it('can recover an existing own pending order without creating another order', async () => {
    api.getOrders.mockResolvedValue({ orders: [order()] });
    mount();
    await flush();
    fireEvent.click(screen.getByRole('button', { name: '订单记录' }));
    await flush();
    expect(api.getOrders).toHaveBeenCalledWith(null, expect.any(AbortSignal));
    fireEvent.click(screen.getByRole('button', { name: /查看订单 own-order-a/ }));
    expect(screen.getByRole('dialog')).toHaveTextContent('等待服务端支付确认');
    expect(api.createOrder).not.toHaveBeenCalled();
    await act(async () => { vi.advanceTimersByTime(3000); });
    expect(api.getOrder).toHaveBeenCalledWith('own-order-a', null, expect.any(AbortSignal));
  });

  it('creates a cookie-authenticated order with only sku/provider/idempotency and refreshes after confirmed payment', async () => {
    mount();
    await flush();
    openTopup();
    fireEvent.click(screen.getByRole('button', { name: '¥30 30.00积分' }));
    fireEvent.click(screen.getByRole('button', { name: '充值 ¥30' }));
    await flush();
    expect(api.createOrder).toHaveBeenCalledWith({ sku: 'topup_30', provider: 'mock', idempotency_key: expect.any(String) }, null, expect.any(AbortSignal));
    expect(screen.getByRole('dialog')).toHaveTextContent('TEST模拟订单 · 不会真实收款');
    expect(screen.queryByRole('button', { name: /我已付款|TEST确认|模拟确认/ })).not.toBeInTheDocument();
    expect(api.getUsage).toHaveBeenCalledTimes(1);
    api.getOrder.mockResolvedValue(order('paid'));
    api.getUsage.mockResolvedValue({ ...usage(), revision: 2, wallet: { credits: 4000, display_points: '40.00' } });
    await act(async () => { vi.advanceTimersByTime(3000); });
    await flush();
    expect(api.getOrder).toHaveBeenCalledWith('own-order-a', null, expect.any(AbortSignal));
    expect(screen.getByRole('dialog')).toHaveTextContent('服务端已确认支付');
    expect(api.getUsage).toHaveBeenCalledTimes(2);
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: '返回用量' }));
    expect(screen.getByText('40.00 积分')).toBeInTheDocument();
  });

  it('clears private orders on an identity switch and aborts/ignores the previous poll', async () => {
    const view = mount();
    await flush();
    openTopup();
    fireEvent.click(screen.getByRole('button', { name: /^充值/ }));
    await flush();
    let resolve!: (data: BillingOrder) => void;
    api.getOrder.mockReturnValue(new Promise(r => { resolve = r; }));
    await act(async () => { vi.advanceTimersByTime(3000); });
    const signal = api.getOrder.mock.calls[0][2] as AbortSignal;
    auth.identityKey = 'account-b';
    api.getUsage.mockReturnValue(new Promise(() => {}));
    view.rerender(<MemoryRouter><MembershipPage /></MemoryRouter>);
    expect(signal.aborted).toBe(true);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    await act(async () => { resolve(order('paid')); });
    expect(screen.queryByText('own-order-a')).not.toBeInTheDocument();
    expect(screen.queryByText('服务端已确认支付')).not.toBeInTheDocument();
  });
  it('confirms live purchases explicitly with WeChat Pay, retries the same attempt and separates cancelling from closing', async () => {
    api.getCatalog.mockResolvedValue({ ...catalog(), environment: 'production', payments_mode: 'live' });
    api.getUsage.mockResolvedValue({ ...usage(), environment: 'production', payments_mode: 'live' });
    const native = { ...order(), provider: 'wechat', payments_mode: 'live', expires_at: new Date(Date.now() + 900000).toISOString(), payment_url: 'weixin://wxpay/bizpayurl?pr=fixture', payment_state: 'ready' };
    api.createOrder.mockRejectedValueOnce(new Error('timeout')).mockResolvedValue(native);
    api.cancelOrder.mockResolvedValue({ ...native, status: 'cancelled', payment_url: null });
    mount(); await flush(); openTopup();
    fireEvent.click(screen.getByRole('button', { name: /^充值/ }));
    expect(api.createOrder).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '微信支付' })); await flush();
    fireEvent.click(screen.getByRole('button', { name: '安全重试' })); await flush();
    expect(api.createOrder.mock.calls[1][0]).toEqual(api.createOrder.mock.calls[0][0]);
    expect(api.createOrder.mock.calls[0][0].provider).toBe('wechat');
    fireEvent.click(screen.getByRole('button', { name: '取消订单' })); await flush();
    expect(api.cancelOrder).toHaveBeenCalledWith('own-order-a', null, expect.any(AbortSignal));
    expect(screen.getByRole('dialog')).toHaveTextContent('订单已取消');
    fireEvent.click(screen.getByRole('button', { name: '返回选择' }));
    expect(api.cancelOrder).toHaveBeenCalledTimes(1);
  });

});
