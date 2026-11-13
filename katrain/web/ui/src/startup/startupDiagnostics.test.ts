import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { recordStartupFailure } from './startupDiagnostics';

const storageKey = 'katrain:startup-failures';

beforeEach(() => {
  sessionStorage.clear();
  window.history.replaceState({}, '', '/kiosk/play/private-game?token=private#private');
});

afterEach(() => {
  vi.restoreAllMocks();
  window.history.replaceState({}, '', '/');
});

describe('startup diagnostic privacy and bounds', () => {
  it('keeps only five records with the four allowlisted fields and safe surface names', () => {
    sessionStorage.setItem(storageKey, JSON.stringify([{
      buildId: 'older-build', timestamp: '2026-11-13T10:00:00.000Z',
      category: 'render', surface: 'galaxy', message: 'private', props: { token: 'private' },
    }]));
    recordStartupFailure('preload');
    const sanitized = JSON.parse(sessionStorage.getItem(storageKey)!);
    expect(sanitized).toHaveLength(2);
    expect(sanitized[0]).not.toHaveProperty('message');
    expect(sanitized[0]).not.toHaveProperty('props');

    for (let index = 0; index < 8; index += 1) recordStartupFailure('render');
    const records = JSON.parse(sessionStorage.getItem(storageKey)!);
    expect(records).toHaveLength(5);
    for (const record of records) {
      expect(Object.keys(record).sort()).toEqual(['buildId', 'category', 'surface', 'timestamp']);
      expect(record.buildId).toMatch(/^[A-Za-z0-9_-]{1,80}$/);
      expect(record.timestamp).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/);
      expect(record.category).toBe('render');
      expect(record.surface).toBe('kiosk');
    }
    expect(JSON.stringify(records)).not.toMatch(/private|token|props|message|https|\/kiosk/);
    expect(sessionStorage.getItem(storageKey)!.length).toBeLessThan(1500);
  });

  it('rejects unknown categories and drops invalid prior diagnostic data', () => {
    recordStartupFailure('https://example.test/?token=private' as 'render');
    expect(sessionStorage.getItem(storageKey)).toBeNull();
    sessionStorage.setItem(storageKey, JSON.stringify([{
      buildId: 'private?token=value', timestamp: 'private', category: 'render', surface: '/user/private',
    }]));
    recordStartupFailure('render');
    expect(JSON.parse(sessionStorage.getItem(storageKey)!)).toHaveLength(1);
    expect(sessionStorage.getItem(storageKey)).not.toContain('private');
  });

  it('replaces corrupt diagnostic data without clearing unrelated session state', () => {
    sessionStorage.setItem(storageKey, '{broken');
    sessionStorage.setItem('unrelated-session-state', 'preserved');
    recordStartupFailure('render');
    expect(JSON.parse(sessionStorage.getItem(storageKey)!)).toHaveLength(1);
    expect(sessionStorage.getItem('unrelated-session-state')).toBe('preserved');
  });

  it('does not throw if session storage cannot be read or written', () => {
    const get = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('unavailable'); });
    expect(() => recordStartupFailure('render')).not.toThrow();
    get.mockRestore();
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('quota'); });
    expect(() => recordStartupFailure('preload')).not.toThrow();
  });
});
