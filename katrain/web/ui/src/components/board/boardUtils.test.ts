import { afterEach, expect, it, vi } from 'vitest';

// Fresh module instances isolate the process-wide URL cache between cases.
afterEach(() => { vi.unstubAllGlobals(); vi.resetModules(); });

it('preloads each sprite once across boards and selects stable coordinate variants', async () => {
  const requested: string[] = [];
  class FakeImage {
    onload?: () => void;
    set src(url: string) { requested.push(url); queueMicrotask(() => this.onload?.()); }
  }
  vi.stubGlobal('Image', FakeImage);
  const { loadBoardImages, stoneImage } = await import('./boardUtils');
  const { getStoneAppearance, stoneSpriteUrl } = await import('./stoneAppearance');
  await Promise.all([loadBoardImages({}), loadBoardImages({})]);
  const appearance = getStoneAppearance();
  expect(requested).toHaveLength(1 + appearance.sprites.W.length);
  const image = stoneImage('W', 3, 7, 19, null);
  expect(image).toBeTruthy();
  expect(stoneImage('W', 3, 7, 19, null)).toBe(image);
  expect(requested).toContain(stoneSpriteUrl('W', 19, 3, 11));
  expect(requested).toHaveLength(new Set(requested).size);
});

it('settles failed sprite loads and preserves legacy stone fallback', async () => {
  class FailedImage {
    onerror?: () => void;
    set src(_url: string) { queueMicrotask(() => this.onerror?.()); }
  }
  vi.stubGlobal('Image', FailedImage);
  const { loadBoardImages, stoneImage } = await import('./boardUtils');
  await expect(loadBoardImages({})).resolves.toEqual({});
  const fallback = {} as HTMLImageElement;
  expect(stoneImage('B', 0, 0, 19, fallback)).toBe(fallback);
  expect(stoneImage('W', 0, 0, 19, null)).toBeNull();
});

it('retries transient failures on the next load while retaining successful sprites', async () => {
  const attempts = new Map<string, number>();
  const { getStoneAppearance } = await import('./stoneAppearance');
  const failedUrl = getStoneAppearance().sprites.B;
  class TransientImage {
    onload?: () => void;
    onerror?: () => void;
    set src(url: string) {
      const attempt = (attempts.get(url) ?? 0) + 1;
      attempts.set(url, attempt);
      queueMicrotask(() => url === failedUrl && attempt === 1 ? this.onerror?.() : this.onload?.());
    }
  }
  vi.stubGlobal('Image', TransientImage);
  const { loadBoardImages, stoneImage } = await import('./boardUtils');
  await loadBoardImages({});
  expect(stoneImage('B', 0, 0, 19, null)).toBeNull();
  const white = stoneImage('W', 0, 0, 19, null);
  await loadBoardImages({});
  expect(stoneImage('B', 0, 0, 19, null)).toBeTruthy();
  expect(stoneImage('W', 0, 0, 19, null)).toBe(white);
  expect(attempts.get(failedUrl)).toBe(2);
  expect([...attempts].filter(([url]) => url !== failedUrl).every(([, count]) => count === 1)).toBe(true);
});
