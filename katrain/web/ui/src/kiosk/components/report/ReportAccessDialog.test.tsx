import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ReportAccessDialog } from './ReportAccessDialog';

vi.mock('../../../hooks/useTranslation', () => ({ useTranslation: () => ({
  lang: 'en', t: (_key: string, fallback: string) => fallback,
}) }));

describe('ReportAccessDialog', () => {
  it('renders nothing without an access issue', () => {
    render(<ReportAccessDialog issue={null} onClose={vi.fn()} onAccount={vi.fn()} />);
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it.each([
    ['insufficient', 'Report allowance insufficient', 'Membership and top-up', 'There is not enough available allowance to start this report. You can review membership benefits or top up points.'],
    ['verification_required', 'Free report unavailable', 'View account and allowance', 'Free report eligibility is unavailable, so this report has not started. You can check membership and points on your account page.'],
  ] as const)('explains %s and delegates only the selected action', (issue, title, action, body) => {
    const onClose = vi.fn();
    const onAccount = vi.fn();
    render(<ReportAccessDialog issue={issue} onClose={onClose} onAccount={onAccount} />);
    const dialog = screen.getByRole('dialog', { name: title, description: body });
    expect(dialog).toHaveClass('cdlg');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    fireEvent.click(screen.getByRole('button', { name: '取消' }));
    expect(onClose).toHaveBeenCalledOnce();
    expect(onAccount).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: action }));
    expect(onAccount).toHaveBeenCalledOnce();
    expect(onClose).toHaveBeenCalledOnce();
  });
});
