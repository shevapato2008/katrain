import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const uiRoot = resolve(import.meta.dirname, '../../..');

describe('legacy kiosk home injection', () => {
  it('is absent from the KaTrain UI source and public assets', () => {
    expect(readFileSync(resolve(uiRoot, 'index.html'), 'utf8')).not.toContain('kiosk-home-button.js');
    expect(existsSync(resolve(uiRoot, 'public/kiosk-home-button.js'))).toBe(false);
  });
});
