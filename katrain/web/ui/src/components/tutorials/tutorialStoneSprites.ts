export const TUTORIAL_WHITE_VARIANT_COUNT = 32;
/** Tight per-color sprite bounds: apply this once to the white baseline diameter. */
export const TUTORIAL_STONE_DIAMETER_RATIO = { W: 1, B: 22.2 / 21.9 } as const;

/** Figure identity + full-board coordinates keep grain fixed through reloads and replay seeks. */
export function stoneVariant(seed: string | number, col: number, row: number): number {
  const key = `${seed}|${col},${row}`;
  let hash = 2166136261;
  for (let i = 0; i < key.length; i++) hash = Math.imul(hash ^ key.charCodeAt(i), 16777619);
  hash ^= hash >>> 16;
  hash = Math.imul(hash, 0x7feb352d);
  hash ^= hash >>> 15;
  hash = Math.imul(hash, 0x846ca68b);
  hash ^= hash >>> 16;
  return (hash >>> 0) % TUTORIAL_WHITE_VARIANT_COUNT;
}

// Explicit URL literals keep these assets in Vite builds, including the recorder (publicDir:false).
export const TUTORIAL_STONE_SPRITE_URLS = {
  B: new URL('../../assets/tutorial-stones/black.png', import.meta.url).href,
  W: [
    new URL('../../assets/tutorial-stones/white-00.png', import.meta.url).href,
    new URL('../../assets/tutorial-stones/white-01.png', import.meta.url).href,
    new URL('../../assets/tutorial-stones/white-02.png', import.meta.url).href,
    new URL('../../assets/tutorial-stones/white-03.png', import.meta.url).href,
    new URL('../../assets/tutorial-stones/white-04.png', import.meta.url).href,
    new URL('../../assets/tutorial-stones/white-05.png', import.meta.url).href,
    new URL('../../assets/tutorial-stones/white-06.png', import.meta.url).href,
    new URL('../../assets/tutorial-stones/white-07.png', import.meta.url).href,
    new URL('../../assets/tutorial-stones/white-08.png', import.meta.url).href,
    new URL('../../assets/tutorial-stones/white-09.png', import.meta.url).href,
    new URL('../../assets/tutorial-stones/white-10.png', import.meta.url).href,
    new URL('../../assets/tutorial-stones/white-11.png', import.meta.url).href,
    new URL('../../assets/tutorial-stones/white-12.png', import.meta.url).href,
    new URL('../../assets/tutorial-stones/white-13.png', import.meta.url).href,
    new URL('../../assets/tutorial-stones/white-14.png', import.meta.url).href,
    new URL('../../assets/tutorial-stones/white-15.png', import.meta.url).href,
    new URL('../../assets/tutorial-stones/white-16.png', import.meta.url).href,
    new URL('../../assets/tutorial-stones/white-17.png', import.meta.url).href,
    new URL('../../assets/tutorial-stones/white-18.png', import.meta.url).href,
    new URL('../../assets/tutorial-stones/white-19.png', import.meta.url).href,
    new URL('../../assets/tutorial-stones/white-20.png', import.meta.url).href,
    new URL('../../assets/tutorial-stones/white-21.png', import.meta.url).href,
    new URL('../../assets/tutorial-stones/white-22.png', import.meta.url).href,
    new URL('../../assets/tutorial-stones/white-23.png', import.meta.url).href,
    new URL('../../assets/tutorial-stones/white-24.png', import.meta.url).href,
    new URL('../../assets/tutorial-stones/white-25.png', import.meta.url).href,
    new URL('../../assets/tutorial-stones/white-26.png', import.meta.url).href,
    new URL('../../assets/tutorial-stones/white-27.png', import.meta.url).href,
    new URL('../../assets/tutorial-stones/white-28.png', import.meta.url).href,
    new URL('../../assets/tutorial-stones/white-29.png', import.meta.url).href,
    new URL('../../assets/tutorial-stones/white-30.png', import.meta.url).href,
    new URL('../../assets/tutorial-stones/white-31.png', import.meta.url).href,
  ],
} as const;

export function tutorialStoneSpriteUrl(color: 'B' | 'W', seed: string | number, col: number, row: number): string {
  return color === 'B' ? TUTORIAL_STONE_SPRITE_URLS.B : TUTORIAL_STONE_SPRITE_URLS.W[stoneVariant(seed, col, row)];
}
