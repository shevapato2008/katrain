import { act, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { API } from '../../api';
import { i18n } from '../../i18n';
import { AccessPrompt } from './AccessPrompt';
import { ProtectedOutline } from './ProtectedOutline';

describe('membership access copy', () => {
  it('updates the open membership guard and protected outline when language changes', async () => {
    vi.spyOn(API, 'getTranslations').mockResolvedValue({ translations: {} });
    vi.spyOn(i18n, 'loadLiveTranslations').mockResolvedValue(undefined);
    await act(async () => { await i18n.loadTranslations('cn'); });
    render(<><AccessPrompt open surface="kiosk" status="checking" feature="membership" onPrimary={vi.fn()} onBack={vi.fn()} /><ProtectedOutline surface="kiosk" feature="membership" /></>);
    expect(screen.getByRole('heading', { name: '正在确认登录状态' })).toBeInTheDocument();
    vi.spyOn(API, 'getTranslations').mockResolvedValue({ translations: {
      'membership:auth_checking_title': 'Checking login status',
      'membership:auth_checking_description': 'Please wait. You will continue automatically.',
      'membership:auth_checking_note': 'Account content stays private while checking.',
      'membership:auth_checking_action': 'Checking',
      'membership:auth_label': 'Membership and usage',
      'membership:back_to_play': 'Back to play',
      'membership:auth_after_login': 'Available after login',
    } });
    await act(async () => { await i18n.loadTranslations('en'); });
    expect(screen.getByRole('heading', { name: 'Checking login status' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Back to play' })).toBeInTheDocument();
    expect(screen.getByText('Available after login')).toBeInTheDocument();
    expect(screen.getByText('Please wait. You will continue automatically.')).toBeInTheDocument();
    vi.restoreAllMocks();
  });
});
