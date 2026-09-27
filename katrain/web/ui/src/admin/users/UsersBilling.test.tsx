import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AdminApiError, createAdminApi } from '../api/client';
import AuditPage from './AuditPage';
import UsersBillingPage from './UsersBillingPage';

const user = { id: 3, username: 'chenjing', rank: '1d', credits: 330, is_admin: false, created_at: '2026-06-20T02:00:00Z' };
function mockApi() {
  const api = createAdminApi();
  api.users = vi.fn(async () => ({ items: [user], total: 1, page: 1, page_size: 20 }));
  api.user = vi.fn(async () => ({ ...user, uuid: 'e'.repeat(32), reserved: { amount: 30, count: 1 }, admin_adjust_total: 0 }));
  api.userLedger = vi.fn(async () => ({ items: [
    { id: 9, created_at: '2026-09-26T13:14:00Z', reason: 'report', delta: -30, status: 'reserved', balance_after: 330, ref_id: 'report:4411' },
    { id: 8, created_at: '2026-09-18T08:33:00Z', reason: 'hints', delta: -10, status: 'refunded', balance_after: 350, ref_id: 'hints:7710' },
  ], next_before_id: null }));
  api.adjustCredits = vi.fn(async () => ({ balance: 280, transaction_id: 12, replayed: false }));
  api.redeemCodes = vi.fn(async () => ({ batches: [], codes: [] }));
  api.generateCodes = vi.fn(async () => ({ codes: Array.from({ length: 20 }, (_, i) => i.toString(16).padStart(32, 'a')), count: 20, credits: 100, expires_at: '2026-12-26T00:00:00Z' }));
  return api;
}
beforeEach(() => {
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value: function (this: HTMLDialogElement) { this.setAttribute('open', ''); } });
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value: function (this: HTMLDialogElement) { this.removeAttribute('open'); } });
});

describe('users & billing', () => {
  it('does not count a refunded reservation in the running balance', async () => {
    render(<UsersBillingPage api={mockApi()} environment="test" environmentLabel="测试环境" onUnauthorized={vi.fn()} />);
    expect(await screen.findByText('hints:7710')).toBeInTheDocument();
    const refunded = screen.getByText('hints:7710').closest('.ub-lrow')!;
    expect(within(refunded as HTMLElement).getByText('—')).toBeInTheDocument();
    expect(screen.getByText('另预扣 30')).toBeInTheDocument();
  });

  it('submits an adjustment only after the re-typed username and amount match, then reports the ledger row', async () => {
    const api = mockApi(); const u = userEvent.setup();
    render(<UsersBillingPage api={api} environment="prod" environmentLabel="生产环境" onUnauthorized={vi.fn()} />);
    await u.click(await screen.findByRole('button', { name: '调整积分' }));
    const dialog = within(screen.getByRole('dialog'));
    expect(dialog.getByText('生产环境')).toBeInTheDocument();
    const [amount, reason, again, againAmount] = dialog.getAllByRole('textbox');
    await u.type(amount, '-400');
    expect(dialog.getByText('余额只有 330，不能扣到负数')).toBeInTheDocument();
    await u.clear(amount); await u.type(amount, '-50'); await u.type(reason, '误发补偿退回');
    await u.type(again, 'chenjin'); await u.type(againAmount, '-50');
    await u.click(dialog.getByRole('checkbox'));
    expect(dialog.getByText(/两次输入不一致/)).toBeInTheDocument();
    expect(dialog.getByRole('button', { name: '确认调整' })).toBeDisabled();
    await u.type(again, 'g');
    await u.click(dialog.getByRole('button', { name: '确认调整' }));
    await waitFor(() => expect(api.adjustCredits).toHaveBeenCalledWith(3, expect.objectContaining({ amount: -50, reason: '误发补偿退回', confirm_username: 'chenjing', confirm_amount: -50, idempotency_key: expect.stringMatching(/^[0-9a-f]{32}$/) })));
    expect(await screen.findByText('已追加账本行 #12：-50，余额 280。')).toBeInTheDocument();
  });

  it('keeps the same idempotency key when a submit is retried after a failure', async () => {
    const api = mockApi(); const u = userEvent.setup();
    api.adjustCredits = vi.fn().mockRejectedValueOnce(new AdminApiError(0, '网络连接失败，请重试。')).mockResolvedValueOnce({ balance: 430, transaction_id: 13, replayed: true });
    render(<UsersBillingPage api={api} environment="test" environmentLabel="测试环境" onUnauthorized={vi.fn()} />);
    await u.click(await screen.findByRole('button', { name: '调整积分' }));
    const dialog = within(screen.getByRole('dialog'));
    const [amount, reason, again, againAmount] = dialog.getAllByRole('textbox');
    await u.type(amount, '100'); await u.type(reason, '活动奖励发放'); await u.type(again, 'chenjing'); await u.type(againAmount, '100'); await u.click(dialog.getByRole('checkbox'));
    await u.click(dialog.getByRole('button', { name: '确认调整' }));
    expect(await dialog.findByText('网络连接失败，请重试。')).toBeInTheDocument();
    await u.click(dialog.getByRole('button', { name: '确认调整' }));
    expect(await screen.findByText(/这笔调整已经处理过（余额 430），没有重复入账/)).toBeInTheDocument();
    const keys = vi.mocked(api.adjustCredits).mock.calls.map(([, body]) => body.idempotency_key);
    expect(keys[0]).toBe(keys[1]);
  });

  it('shows every generated code once and cannot be closed before they are saved', async () => {
    const api = mockApi(); const u = userEvent.setup();
    render(<UsersBillingPage api={api} environment="test" environmentLabel="测试环境" onUnauthorized={vi.fn()} />);
    await u.click(screen.getByRole('tab', { name: '兑换码' }));
    const generate = await screen.findByRole('button', { name: '生成' });
    expect(generate).toBeDisabled();
    await u.type(screen.getByLabelText(/用途/), '九月线下活动奖品');
    await u.click(generate);
    const dialog = within(await screen.findByRole('dialog'));
    expect(dialog.getByLabelText('本批兑换码').textContent!.split('\n')).toHaveLength(20);
    expect(dialog.getByRole('button', { name: '关闭' })).toBeDisabled();
    await u.click(dialog.getByRole('checkbox'));
    await u.click(dialog.getByRole('button', { name: '关闭' }));
    await waitFor(() => expect(api.redeemCodes).toHaveBeenCalledTimes(2));
  });

  it('hands an expired session back to login', async () => {
    const api = mockApi(); const onUnauthorized = vi.fn();
    api.users = vi.fn(async () => { throw new AdminApiError(401, 'expired'); });
    render(<UsersBillingPage api={api} environment="test" environmentLabel="测试环境" onUnauthorized={onUnauthorized} />);
    await waitFor(() => expect(onUnauthorized).toHaveBeenCalled());
  });
});

describe('audit page', () => {
  it('filters by action and target user and summarises each write', async () => {
    const api = createAdminApi(); const u = userEvent.setup();
    api.audit = vi.fn(async () => ({ items: [{ id: 1, created_at: '2026-09-27T01:12:04Z', actor_username: 'admin:fan', action: 'credit_adjust', target_type: 'user', target_id: 3, target_label: 'chenjing', success: true, detail: { amount: -50, reason: '误发补偿退回', balance_before: 330, balance_after: 280, key: 'k' } }], total: 1, page: 1, page_size: 50 }));
    render(<AuditPage api={api} onUnauthorized={vi.fn()} />);
    expect(await screen.findByText('-50 · 误发补偿退回 · 余额 330→280')).toBeInTheDocument();
    expect(screen.getByText('用户 3 · chenjing')).toBeInTheDocument();
    await u.selectOptions(screen.getByLabelText('动作'), 'credit_adjust');
    await u.type(screen.getByLabelText('目标用户 id'), '3');
    await u.click(screen.getByRole('button', { name: '筛选' }));
    await waitFor(() => expect(api.audit).toHaveBeenLastCalledWith(expect.objectContaining({ action: 'credit_adjust', target_user_id: '3', page: 1 }), expect.any(AbortSignal)));
  });
});
