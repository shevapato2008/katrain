import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';

// Guard: the kiosk tutorial module is a READ-ONLY mirror. No file under
// src/kiosk/** may reference any tutorial write method. Kiosk pages must consume
// TutorialReadAPI (read-only view), never TutorialAPI's write methods.
const WRITE_METHODS = ['saveBoardPayload', 'saveNarration', 'generateFigureAudio', 'verifyFigure'];

const KIOSK_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../../kiosk');

function collectSourceFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...collectSourceFiles(full));
    } else if (/\.(ts|tsx)$/.test(entry.name)) {
      out.push(full);
    }
  }
  return out;
}

describe('kiosk tutorial is read-only', () => {
  it('no kiosk source references tutorial write methods', () => {
    const offenders: string[] = [];
    for (const file of collectSourceFiles(KIOSK_ROOT)) {
      const src = readFileSync(file, 'utf8');
      for (const method of WRITE_METHODS) {
        if (src.includes(method)) offenders.push(`${file}: ${method}`);
      }
    }
    expect(offenders).toEqual([]);
  });
});
