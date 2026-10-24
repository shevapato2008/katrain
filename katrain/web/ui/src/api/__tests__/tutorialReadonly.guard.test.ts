import { afterEach, describe, it, expect, vi } from 'vitest';
import { readdirSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';
import { TutorialAPI, TutorialReadAPI } from '../tutorialApi';

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

  it('exports OGS course reads without tutorial writes', () => {
    expect(TutorialReadAPI.getOgsCourse).toBeTypeOf('function');
    expect(TutorialReadAPI.getOgsStep).toBeTypeOf('function');
    for (const method of WRITE_METHODS) {
      expect(TutorialReadAPI).not.toHaveProperty(method);
    }
  });
});

afterEach(() => vi.unstubAllGlobals());

it('uses the public OGS course URLs on the current surface', async () => {
  const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response('{}')));
  vi.stubGlobal('fetch', fetchMock);

  await TutorialReadAPI.getOgsCourse();
  await TutorialReadAPI.getOgsStep(12, 'en');

  const base = __KIOSK_2D_ONLY__ ? '/api/v1/board/tutorials' : '/api/v1/tutorials';
  expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
    `${base}/ogs-course?lang=zh-cn`,
    `${base}/ogs-course/steps/12?lang=en`,
  ]);
});


it('opts only the Kiosk read into 19-line steps while ordinary and source URLs stay original', async () => {
  const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response('{}')));
  vi.stubGlobal('fetch', fetchMock);
  await TutorialReadAPI.getOgsStep(73, 'zh-cn', 'kiosk19');
  await TutorialAPI.getOgsStep(73);
  const base = __KIOSK_2D_ONLY__ ? '/api/v1/board/tutorials' : '/api/v1/tutorials';
  expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
    `${base}/ogs-course/steps/73?lang=zh-cn&board_variant=kiosk19`,
    `${base}/ogs-course/steps/73?lang=zh-cn`,
  ]);
  expect(TutorialReadAPI.assetUrl('book/source.sgf')).toBe(`${base}/assets/book/source.sgf`);
});
