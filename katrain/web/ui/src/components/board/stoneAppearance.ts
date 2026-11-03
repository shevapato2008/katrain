/**
 * Publishable board artwork, independent of React, Canvas and Three.js.
 * The default sprites are rendered from the repository's original shell/slate
 * model and photo-free procedural material (see assets/shell-slate/README.md).
 */
export interface StoneMaterialRecipe {
  readonly color: string;
  readonly roughness: number;
  readonly metalness: number;
  readonly clearcoat: number;
  readonly clearcoatRoughness: number;
  readonly shell?: {
    readonly color: string;
    readonly opacity: number;
    readonly frequency: number;
    readonly warp: number;
  };
}

export interface StoneAppearance {
  readonly id: string;
  readonly sprites: { readonly B: string; readonly W: readonly [string, ...string[]] };
  readonly diameterRatio: { readonly B: number; readonly W: number };
  readonly material3d?: { readonly B: StoneMaterialRecipe; readonly W: StoneMaterialRecipe };
}

export const DEFAULT_STONE_APPEARANCE_ID = 'shell-slate';

export const DEFAULT_STONE_APPEARANCE: StoneAppearance & {
  readonly material3d: NonNullable<StoneAppearance['material3d']>;
} = {
  id: DEFAULT_STONE_APPEARANCE_ID,
  sprites: {
    B: new URL('./assets/shell-slate/black.png', import.meta.url).href,
    W: [
      new URL('./assets/shell-slate/white-00.png', import.meta.url).href,
      new URL('./assets/shell-slate/white-01.png', import.meta.url).href,
      new URL('./assets/shell-slate/white-02.png', import.meta.url).href,
      new URL('./assets/shell-slate/white-03.png', import.meta.url).href,
      new URL('./assets/shell-slate/white-04.png', import.meta.url).href,
      new URL('./assets/shell-slate/white-05.png', import.meta.url).href,
      new URL('./assets/shell-slate/white-06.png', import.meta.url).href,
      new URL('./assets/shell-slate/white-07.png', import.meta.url).href,
    ],
  },
  diameterRatio: { B: 1, W: 1 },
  material3d: {
    B: { color: '#17191b', roughness: 0.42, metalness: 0, clearcoat: 0.12, clearcoatRoughness: 0.48 },
    W: {
      color: '#f4f1e8', roughness: 0.32, metalness: 0, clearcoat: 0.18, clearcoatRoughness: 0.38,
      shell: { color: '#b9b09d', opacity: 0.22, frequency: 28, warp: 0.035 },
    },
  },
};

export const STONE_APPEARANCES: Readonly<Record<string, StoneAppearance>> = {
  [DEFAULT_STONE_APPEARANCE_ID]: DEFAULT_STONE_APPEARANCE,
};

export function getStoneAppearance(id?: string | null): StoneAppearance {
  return id && Object.prototype.hasOwnProperty.call(STONE_APPEARANCES, id)
    ? STONE_APPEARANCES[id]
    : DEFAULT_STONE_APPEARANCE;
}

/** Stable full-board coordinates keep grain fixed through replay, resize and reload. */
export function stoneVariant(seed: string | number, col: number, row: number, count = 32): number {
  const key = `${seed}|${col},${row}`;
  let hash = 2166136261;
  for (let i = 0; i < key.length; i++) hash = Math.imul(hash ^ key.charCodeAt(i), 16777619);
  hash ^= hash >>> 16;
  hash = Math.imul(hash, 0x7feb352d);
  hash ^= hash >>> 15;
  hash = Math.imul(hash, 0x846ca68b);
  hash ^= hash >>> 16;
  return (hash >>> 0) % Math.max(1, Math.floor(count));
}

/** A stable per-intersection angle, so shell grain looks naturally placed without spinning on redraw. */
export function stoneRotationDegrees(seed: string | number, col: number, row: number): number {
  return stoneVariant(`rotation:${seed}`, col, row, 360);
}

/** URLs work unchanged as Canvas Image.src and SVG image href. */
export function stoneSpriteUrl(
  color: 'B' | 'W', seed: string | number, col: number, row: number, appearanceId?: string,
): string {
  const { sprites } = getStoneAppearance(appearanceId);
  return color === 'B' ? sprites.B : sprites.W[stoneVariant(seed, col, row, sprites.W.length)];
}
