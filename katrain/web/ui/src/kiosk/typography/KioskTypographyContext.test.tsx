import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { KioskTypographyProvider, useKioskTypography } from './KioskTypographyContext';

function Controls() {
  const { preference, setPreference, loading, saving, error, retry } = useKioskTypography();
  return <>
    <output data-testid="choice">{`${preference.font}/${preference.size}`}</output>
    <output data-testid="status">{loading ? 'loading' : saving ? 'saving' : error ?? 'ready'}</output>
    <button onClick={() => setPreference({ font: 'kaiti' })}>Kai</button>
    <button onClick={() => setPreference({ size: 'small' })}>Small</button>
    <button onClick={retry}>Retry</button>
  </>;
}

afterEach(() => {
  vi.unstubAllGlobals();
  document.body.style.removeProperty('--kiosk-cjk-font');
  document.body.style.removeProperty('--kiosk-size-step');
});

describe('KioskTypographyProvider', () => {
  it('loads the device preference and applies a CJK-only face and size step', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ font: 'heiti', size: 'medium' }) }));
    render(<KioskTypographyProvider language="cn"><Controls /></KioskTypographyProvider>);
    await waitFor(() => expect(screen.getByTestId('choice').textContent).toBe('heiti/medium'));
    expect(document.body.style.getPropertyValue('--kiosk-cjk-font')).toBe('"SmartBox Noto Sans CJK"');
    expect(document.body.style.getPropertyValue('--kiosk-size-step')).toBe('2px');
  });

  it('serializes quick edits and leaves the final pair on disk', async () => {
    let releaseFirst!: () => void;
    const firstWrite = new Promise<void>(resolve => { releaseFirst = resolve; });
    const writes: string[] = [];
    const fetch = vi.fn().mockImplementation((_url: string, options?: RequestInit) => {
      if (!options) return Promise.resolve({ ok: true, json: async () => ({ font: 'wenkai', size: 'large' }) });
      writes.push(String(options.body));
      return writes.length === 1 ? firstWrite.then(() => ({ ok: true })) : Promise.resolve({ ok: true });
    });
    vi.stubGlobal('fetch', fetch);
    render(<KioskTypographyProvider language="cn"><Controls /></KioskTypographyProvider>);
    await waitFor(() => expect(screen.getByTestId('status').textContent).toBe('ready'));
    fireEvent.click(screen.getByText('Kai'));
    fireEvent.click(screen.getByText('Small'));
    await waitFor(() => expect(writes).toHaveLength(1));
    releaseFirst();
    await waitFor(() => expect(writes).toHaveLength(2));
    expect(JSON.parse(writes[1])).toEqual({ font: 'kaiti', size: 'small' });
    await waitFor(() => expect(screen.getByTestId('status').textContent).toBe('ready'));
  });

  it('does not let a late GET overwrite a local font choice', async () => {
    let finishGet!: (response: { ok: boolean; json: () => Promise<unknown> }) => void;
    const delayedGet = new Promise<{ ok: boolean; json: () => Promise<unknown> }>(resolve => { finishGet = resolve; });
    vi.stubGlobal('fetch', vi.fn().mockImplementation((_url: string, options?: RequestInit) =>
      options ? Promise.resolve({ ok: true }) : delayedGet));
    render(<KioskTypographyProvider language="cn"><Controls /></KioskTypographyProvider>);
    fireEvent.click(screen.getByText('Kai'));
    await act(async () => finishGet({ ok: true, json: async () => ({ font: 'heiti', size: 'small' }) }));
    await waitFor(() => expect(screen.getByTestId('status').textContent).toBe('ready'));
    expect(screen.getByTestId('choice').textContent).toBe('kaiti/large');
  });

  it('retries a failed read without overwriting the stored choice', async () => {
    const fetch = vi.fn()
      .mockResolvedValueOnce({ ok: false, status: 503 })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ font: 'lishu', size: 'small' }) });
    vi.stubGlobal('fetch', fetch);
    render(<KioskTypographyProvider language="cn"><Controls /></KioskTypographyProvider>);
    await waitFor(() => expect(screen.getByTestId('status').textContent).toContain('无法读取'));
    fireEvent.click(screen.getByText('Retry'));
    await waitFor(() => expect(screen.getByTestId('choice').textContent).toBe('lishu/small'));
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(fetch.mock.calls.every(([, options]) => options === undefined)).toBe(true);
  });
});
