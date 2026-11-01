import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { BillingQuote } from './types';
import { ConsumptionQuoteDialog } from './ConsumptionQuoteDialog';

describe('ConsumptionQuoteDialog', () => {
  it('keeps kiosk confirmation inside its canvas and uses the server maximum', () => {
    const cancel = vi.fn();
    const { container } = render(<div data-testid="canvas"><ConsumptionQuoteDialog kiosk quote={{ kind: 'position', profile: 'normal', source: 'membership', wallet_max_display_points: '0.01' } as BillingQuote} onConfirm={vi.fn()} onCancel={cancel} /></div>);
    expect(container.querySelector('[role="dialog"]')).not.toBeNull();
    expect(screen.getByRole('dialog').textContent).toContain('最多 0.01 积分');
    fireEvent.click(screen.getByRole('button', { name: '取消' }));
    expect(cancel).toHaveBeenCalledOnce();
  });
});
