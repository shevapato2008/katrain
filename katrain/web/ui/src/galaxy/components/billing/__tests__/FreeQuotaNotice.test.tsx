import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { SettingsProvider } from '../../../../context/SettingsContext';
import { API } from '../../../../api';
import FreeQuotaNotice from '../FreeQuotaNotice';

let authFixture: { user: { id: number; username: string; phone_bound: boolean } | null;
                   refreshUser: ReturnType<typeof vi.fn> };
function setBound(bound: boolean) {
  authFixture = { user: { id: 1, username: 'u', phone_bound: bound }, refreshUser: vi.fn() };
}
setBound(false);
vi.mock('../../../../context/AuthContext', () => ({ useAuth: () => authFixture }));

const quota = (free: { used: number; allowance: number; blocked_reason: string | null }) => ({
  credits: 0, free_weekly: free, billing_enforced: true, billing_online: true,
});

const renderNotice = () => render(
  <MemoryRouter><SettingsProvider><FreeQuotaNotice /></SettingsProvider></MemoryRouter>,
);

describe('FreeQuotaNotice', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    setBound(false);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ translations: {} }) }));
  });

  it('未绑号（blocked_reason=phone_required）：说得出为什么没有额度，并给得出入口', async () => {
    vi.spyOn(API, 'getBillingQuota').mockResolvedValue(
      quota({ used: 0, allowance: 0, blocked_reason: 'phone_required' }));
    renderNotice();
    await waitFor(() => expect(screen.getByText(/绑定手机号后可享每周免费普通复盘/)).toBeInTheDocument());
    expect(screen.getByRole('button', { name: '绑定手机号' })).toBeInTheDocument();
    // allowance=0 不是"这周用完了" —— 把没资格说成额度耗尽，用户会等到下周（spec §3.1 状态诚实）
    expect(screen.queryByText(/已用完/)).toBeNull();
  });

  it('已绑号且还有额度：报剩余次数，并写明只有普通复盘免费', async () => {
    setBound(true);
    vi.spyOn(API, 'getBillingQuota').mockResolvedValue(
      quota({ used: 0, allowance: 1, blocked_reason: null }));
    renderNotice();
    /* 「普通」两个字不是润色：`endpoints/billing.py:99-102` 明写「前端不得把 free_weekly
       显示在深度复盘按钮旁边，那会让用户以为这次免费、实际照价扣费」——
       而这行文案下面紧跟的列表里，每张卡都带「普通/深度」两个按钮。 */
    await waitFor(() => expect(screen.getByText(/本周剩余 1 次免费普通复盘/)).toBeInTheDocument());
    expect(screen.queryByRole('button', { name: '绑定手机号' })).toBeNull();
  });

  it('已绑号但本周用完：说"已用完"，不说"去绑手机"', async () => {
    setBound(true);
    vi.spyOn(API, 'getBillingQuota').mockResolvedValue(
      quota({ used: 1, allowance: 1, blocked_reason: null }));
    renderNotice();
    await waitFor(() => expect(screen.getByText(/本周免费普通复盘次数已用完/)).toBeInTheDocument());
    expect(screen.queryByRole('button', { name: '绑定手机号' })).toBeNull();
  });

  it('取不到额度时说"取不到"，不装成 0 次也不装成有额度', async () => {
    vi.spyOn(API, 'getBillingQuota').mockRejectedValue(new Error('boom'));
    renderNotice();
    await waitFor(() => expect(screen.getByText(/额度信息暂时取不到/)).toBeInTheDocument());
  });

  it('绑定之后当场重新取数、文案翻面 —— 这就是 Task 18 验收第 4 项', async () => {
    const get = vi.spyOn(API, 'getBillingQuota')
      .mockResolvedValueOnce(quota({ used: 0, allowance: 0, blocked_reason: 'phone_required' }))
      .mockResolvedValueOnce(quota({ used: 0, allowance: 1, blocked_reason: null }));
    const { rerender } = renderNotice();
    await waitFor(() => expect(screen.getByText(/绑定手机号后可享每周免费普通复盘/)).toBeInTheDocument());
    setBound(true);      // BindPhoneDialog 成功后 refreshUser() 造成的那次翻面
    rerender(
      <MemoryRouter><SettingsProvider><FreeQuotaNotice /></SettingsProvider></MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/本周剩余 1 次免费普通复盘/)).toBeInTheDocument());
    expect(get).toHaveBeenCalledTimes(2);
  });
});
