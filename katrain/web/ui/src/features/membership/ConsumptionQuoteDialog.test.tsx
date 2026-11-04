import { act, fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { API } from '../../api';
import { i18n } from '../../i18n';
import { ConsumptionQuoteDialog } from './ConsumptionQuoteDialog';
import type { BillingQuote } from './types';

describe('ConsumptionQuoteDialog', () => {
  it.each([false, true])('names the quoted API maximum in the wallet action (kiosk=%s)', kiosk => {
    const confirm = vi.fn();
    const quote = { kind: 'report', profile: 'advanced', source: 'wallet', units: 99999, wallet_max_credits: 1, wallet_max_display_points: '12.34' } as BillingQuote;
    const view = render(<ConsumptionQuoteDialog kiosk={kiosk} quote={quote} onConfirm={confirm} onCancel={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: '使用API积分，最多扣12.34', exact: true }));
    expect(confirm).toHaveBeenCalledOnce();
    view.rerender(<ConsumptionQuoteDialog kiosk={kiosk} quote={quote} busy onConfirm={confirm} onCancel={vi.fn()} />);
    const processing = screen.getByRole('button', { name: '处理中…', exact: true });
    expect(processing).toBeDisabled();
    fireEvent.click(processing);
    expect(confirm).toHaveBeenCalledOnce();
  });

  it.each(['membership', 'free_report', 'owned'] as const)('retains the accurate %s source without claiming a wallet charge', source => {
    render(<ConsumptionQuoteDialog quote={{ kind: 'report', source, wallet_max_display_points: '3.01' } as BillingQuote} onConfirm={vi.fn()} onCancel={vi.fn()} />);
    const sourceCopy = { membership: '当前预计使用会员额度', free_report: '当前预计使用每周免费报告资格', owned: '本次结果已拥有' };
    expect(screen.getByRole('dialog')).toHaveTextContent(sourceCopy[source]);
    expect(screen.getByRole('button', { name: '确认并开始', exact: true })).toBeEnabled();
    expect(screen.queryByRole('button', { name: /使用API积分/ })).not.toBeInTheDocument();
  });

  it('keeps kiosk confirmation inside its canvas and uses the server maximum', () => {
    const cancel = vi.fn();
    const { container } = render(<div data-testid="canvas"><ConsumptionQuoteDialog kiosk quote={{ kind: 'position', profile: 'normal', source: 'membership', wallet_max_display_points: '0.01' } as BillingQuote} onConfirm={vi.fn()} onCancel={cancel} /></div>);
    expect(container.querySelector('[role="dialog"]')).not.toBeNull();
    expect(screen.getByRole('dialog').textContent).toContain('最多 0.01 积分');
    fireEvent.click(screen.getByRole('button', { name: '取消' }));
    expect(cancel).toHaveBeenCalledOnce();
  });
});

describe('consumption quote copy', () => {
  it('updates an open quote with a complete translated template and display-only localized points', async () => {
    vi.spyOn(API, 'getTranslations').mockResolvedValue({ translations: {} });
    vi.spyOn(i18n, 'loadLiveTranslations').mockResolvedValue(undefined);
    await act(async () => { await i18n.loadTranslations('cn'); });
    const confirm = vi.fn();
    const quote = { kind: 'report', source: 'wallet', wallet_max_display_points: '3.01' } as BillingQuote;
    render(<ConsumptionQuoteDialog kiosk quote={quote} onConfirm={confirm} onCancel={vi.fn()} />);
    expect(screen.getByRole('button', { name: '使用API积分，最多扣3.01' })).toBeInTheDocument();
    vi.spyOn(API, 'getTranslations').mockResolvedValue({ translations: { 'membership:confirm_wallet_consumption': 'API-Punkte verwenden, höchstens {points}', 'membership:consumption_policy': 'Mitgliedschaft zuerst, sonst bis zu {points} API-Punkte.' } });
    await act(async () => { await i18n.loadTranslations('de'); });
    expect(screen.getByRole('button', { name: 'API-Punkte verwenden, höchstens 3,01' })).toBeInTheDocument();
    expect(screen.getByText('Mitgliedschaft zuerst, sonst bis zu 3,01 API-Punkte.')).toBeInTheDocument();
    expect(confirm).not.toHaveBeenCalled();
    expect(quote.wallet_max_display_points).toBe('3.01');
    vi.restoreAllMocks();
  });
});
