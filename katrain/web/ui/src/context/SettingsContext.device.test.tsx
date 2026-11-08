import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
const mocks = vi.hoisted(() => ({ strict: true, load: vi.fn().mockResolvedValue(undefined) }));
vi.mock('../kiosk/shell/boxUrls', () => ({ get isStrictBoxKiosk() { return mocks.strict; } }));
vi.mock('../i18n', () => ({ i18n: { loadTranslations: mocks.load, subscribe: () => () => {} } }));
import { SettingsProvider, useSettings } from './SettingsContext';
function Probe() {
  const state = useSettings();
  return <><output>{JSON.stringify({ language: state.language, appearance: state.deviceAppearance, error: state.appearanceError, loading: state.appearanceLoading })}</output>
    <button onClick={state.refreshAppearance}>Retry</button><button onClick={() => state.setLanguage('en')}>Local</button></>;
}
beforeEach(() => { mocks.strict = true; mocks.load.mockClear(); localStorage.setItem('katrain_language', 'en'); });
afterEach(() => vi.unstubAllGlobals());
it('waits for the authority, maps all five locales and keeps local storage independent', async () => {
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ language: 'ja', font: 'kai' }) });
  vi.stubGlobal('fetch', fetch);
  render(<SettingsProvider><Probe /></SettingsProvider>);
  await waitFor(() => expect(screen.getByRole('status').textContent).toContain('"language":"jp"'));
  expect(mocks.load.mock.calls[0][0]).toBe('jp');
  fireEvent.click(screen.getByText('Local'));
  expect(localStorage.getItem('katrain_language')).toBe('en');
  expect(mocks.load).not.toHaveBeenCalledWith('en');
  for (const [language, expected] of [['zh', 'cn'], ['zh-TW', 'tw'], ['en', 'en'], ['ko', 'ko']]) {
    fetch.mockResolvedValue({ ok: true, json: async () => ({ language, font: 'hei' }) });
    fireEvent.click(screen.getByText('Retry'));
    await waitFor(() => expect(screen.getByRole('status').textContent).toContain(`"language":"${expected}"`));
  }
});
it('reports initial failure, retries and retains last valid preferences on refresh failure', async () => {
  const fetch = vi.fn().mockResolvedValueOnce({ ok: false, status: 503 }).mockResolvedValueOnce({ ok: true, json: async () => ({ language: 'ko', font: 'daoli' }) }).mockRejectedValue(new Error('offline'));
  vi.stubGlobal('fetch', fetch);
  render(<SettingsProvider><Probe /></SettingsProvider>);
  await waitFor(() => expect(screen.getByRole('status').textContent).toContain('"error":true'));
  expect(screen.getByRole('status').textContent).toContain('"appearance":null');
  fireEvent.click(screen.getByText('Retry'));
  await waitFor(() => expect(screen.getByRole('status').textContent).toContain('"language":"ko"'));
  act(() => window.dispatchEvent(new Event('focus')));
  await waitFor(() => expect(screen.getByRole('status').textContent).toContain('"error":true'));
  expect(screen.getByRole('status').textContent).toContain('"font":"daoli"');
});
it('keeps standalone saved preferences working without requesting the box authority', async () => {
  mocks.strict = false;
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
  render(<SettingsProvider><Probe /></SettingsProvider>);
  await waitFor(() => expect(mocks.load).toHaveBeenCalledWith('en'));
  expect(fetch).not.toHaveBeenCalled();
});
it('ignores an older settings reply after a newer language has arrived', async () => {
  let finish!: (value: unknown) => void;
  const fetch = vi.fn().mockReturnValueOnce(new Promise(resolve => { finish = resolve; }))
    .mockResolvedValue({ ok: true, json: async () => ({ language: 'ko', font: 'hei' }) });
  vi.stubGlobal('fetch', fetch);
  render(<SettingsProvider><Probe /></SettingsProvider>);
  fireEvent.click(screen.getByText('Retry'));
  await waitFor(() => expect(screen.getByRole('status').textContent).toContain('"language":"ko"'));
  await act(async () => finish({ ok: true, json: async () => ({ language: 'ja', font: 'kai' }) }));
  expect(screen.getByRole('status').textContent).toContain('"language":"ko"');
  expect(mocks.load.mock.calls.some(([language]) => language === 'jp')).toBe(false);
});
