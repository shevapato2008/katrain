import { afterEach, expect, it, vi } from 'vitest';

// Fresh module instances isolate the process-wide URL cache between cases.
afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
  vi.resetModules();
});

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

it('draws the selected Canvas sprite at its board point without rotating the lit image', async () => {
  const { drawStoneSprite } = await import('./boardUtils');
  const image = {} as HTMLImageElement;
  const ctx = { drawImage: vi.fn(), rotate: vi.fn(), translate: vi.fn(), save: vi.fn(), restore: vi.fn() };
  drawStoneSprite(ctx as unknown as CanvasRenderingContext2D, image, 100, 120, 9, 19, 3, 7);
  expect(ctx.drawImage).toHaveBeenCalledWith(image, 91, 111, 18, 18);
  expect(ctx.rotate).not.toHaveBeenCalled();
  expect(ctx.translate).not.toHaveBeenCalled();
});

it('loads board texture and stone sprites by boardStyle and stoneStyle and applies palette colors', async () => {
  class FakeImage {
    onload?: () => void;
    srcValue = '';
    set src(url: string) { this.srcValue = url; queueMicrotask(() => this.onload?.()); }
  }
  vi.stubGlobal('Image', FakeImage);
  const {
    calculateBoardLayout,
    drawBoardBackground,
    drawBoardGrid,
    drawStone,
    loadBoardImages,
    stoneImage,
  } = await import('./boardUtils');

  const assets = await loadBoardImages('walnut', 'jade-agate');
  expect(assets.board).toBeTruthy();
  expect(assets.blackStone).toBeTruthy();
  expect(assets.whiteStone).toBeTruthy();
  expect(stoneImage('W', 2, 2, 19, null, 'jade-agate')).toBeTruthy();

  const layout = calculateBoardLayout(600, 600, 19);
  const ctx = {
    fillStyle: '',
    strokeStyle: '',
    lineWidth: 1,
    lineCap: 'butt',
    font: '',
    textAlign: 'left',
    textBaseline: 'alphabetic',
    fillRect: vi.fn(),
    drawImage: vi.fn(),
    beginPath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    stroke: vi.fn(),
    arc: vi.fn(),
    fill: vi.fn(),
    fillText: vi.fn(),
    save: vi.fn(),
    restore: vi.fn(),
  };

  drawBoardBackground(ctx as unknown as CanvasRenderingContext2D, layout, null, 'walnut');
  expect(ctx.fillStyle).toBe('#5c402c');
  expect(ctx.fillRect).toHaveBeenCalled();

  drawBoardGrid(ctx as unknown as CanvasRenderingContext2D, layout, 19, undefined, 'walnut');
  expect(ctx.fillStyle).toBe('#d9c3ac');

  drawStone(ctx as unknown as CanvasRenderingContext2D, layout, 3, 3, 19, 'W', assets.blackStone ?? null, assets.whiteStone ?? null, 'jade-agate');
  expect(ctx.fillStyle).toBe('rgba(255, 243, 210, 0.28)');
  expect(ctx.drawImage).toHaveBeenCalled();
});
