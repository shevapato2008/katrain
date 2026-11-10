import { useSyncExternalStore } from 'react';

/**
 * Publishable board and stone appearance definitions and reactive store,
 * strictly pure 2D and independent of Three.js.
 */
export type StoneStyleId = 'clamshell-slate' | 'yunzi' | 'jade-agate' | 'minimal';
export type StoneAppearanceId = StoneStyleId | 'shell-slate';
export type BoardStyleId = 'kaya' | 'shin-kaya' | 'bamboo' | 'walnut';
export type ChineseFontId = 'wenkai' | 'kaiti' | 'lishu' | 'heiti';

export const STONE_STYLE_IDS: readonly StoneStyleId[] = [
  'clamshell-slate',
  'yunzi',
  'jade-agate',
  'minimal',
];

export const BOARD_STYLE_IDS: readonly BoardStyleId[] = [
  'kaya',
  'shin-kaya',
  'bamboo',
  'walnut',
];

export const CHINESE_FONT_IDS: readonly ChineseFontId[] = [
  'wenkai',
  'kaiti',
  'lishu',
  'heiti',
];

export interface StoneStyleOption {
  readonly id: StoneStyleId;
  readonly label: string;
  readonly labelEn: string;
  readonly subtitle: string;
  readonly blackSwatch: string;
  readonly whiteSwatch: string;
  readonly rimColor?: string;
}

export const STONE_STYLE_OPTIONS: readonly StoneStyleOption[] = [
  {
    id: 'clamshell-slate',
    label: '蛤碁石',
    labelEn: 'Clamshell & Slate',
    subtitle: '日向蛤白 · 那智黑石',
    blackSwatch: '#181a1c',
    whiteSwatch: '#f5f1e6',
  },
  {
    id: 'yunzi',
    label: '云子',
    labelEn: 'Yunzi',
    subtitle: '温润象牙 · 翠玉绿光',
    blackSwatch: '#111715',
    whiteSwatch: '#efe9d8',
    rimColor: '#10b981',
  },
  {
    id: 'jade-agate',
    label: '玉石玛瑙',
    labelEn: 'Jade & Agate',
    subtitle: '冰种白玛瑙 · 黑曜玛瑙',
    blackSwatch: '#0d1014',
    whiteSwatch: '#eef6f2',
    rimColor: '#f5e6c4',
  },
  {
    id: 'minimal',
    label: '简约',
    labelEn: 'Minimal',
    subtitle: '哑光防眩 · 专注读谱',
    blackSwatch: '#1e2229',
    whiteSwatch: '#f5f3ee',
  },
];

export interface BoardStyleOption {
  readonly id: BoardStyleId;
  readonly label: string;
  readonly labelEn: string;
  readonly subtitle: string;
  readonly swatch: string;
  readonly borderColor: string;
  readonly textureUrl: string;
}

export const BOARD_STYLE_OPTIONS: readonly BoardStyleOption[] = [
  {
    id: 'kaya',
    label: '日式本榧',
    labelEn: 'Hon-Kaya',
    subtitle: '金黄直纹 · 温润醇厚',
    swatch: '#deb368',
    borderColor: '#8c6228',
    textureUrl: '/assets/textures/kaya-veneer-2k.jpg',
  },
  {
    id: 'shin-kaya',
    label: '新榧云杉',
    labelEn: 'Shin-Kaya Spruce',
    subtitle: '浅米细纹 · 清雅明亮',
    swatch: '#edd39c',
    borderColor: '#a88952',
    textureUrl: '/assets/textures/shinkaya-veneer-2k.jpg',
  },
  {
    id: 'bamboo',
    label: '碳化楠竹',
    labelEn: 'Carbonized Bamboo',
    subtitle: '暖琥珀色 · 竹节纹理',
    swatch: '#c88c46',
    borderColor: '#7a4b19',
    textureUrl: '/assets/textures/bamboo-veneer-2k.jpg',
  },
  {
    id: 'walnut',
    label: '胡桃沉香',
    labelEn: 'Dark Walnut',
    subtitle: '深棕护眼 · 沉稳低眩',
    swatch: '#5c402c',
    borderColor: '#2e1d11',
    textureUrl: '/assets/textures/walnut-veneer-2k.jpg',
  },
];

export interface ChineseFontOption {
  readonly id: ChineseFontId;
  readonly label: string;
  readonly subtitle: string;
  readonly fontFamily: string;
}

export const CHINESE_FONT_OPTIONS: readonly ChineseFontOption[] = [
  {
    id: 'wenkai',
    label: '霞鹜楷体',
    subtitle: '温润手写楷书',
    fontFamily: `'LXGW WenKai', "SmartBox Kai", "Kaiti SC", serif`,
  },
  {
    id: 'kaiti',
    label: '楷体',
    subtitle: '传统正楷字形',
    fontFamily: `"SmartBox CNS Kai", "Kaiti SC", "STKaiti", serif`,
  },
  {
    id: 'lishu',
    label: '隶书',
    subtitle: '古朴刀隶笔意',
    fontFamily: `"SmartBox DaoLi", "LiSu", "STLiti", serif`,
  },
  {
    id: 'heiti',
    label: '黑体',
    subtitle: '现代无衬线体',
    fontFamily: `"SmartBox Noto Sans CJK", "PingFang SC", "Microsoft YaHei", sans-serif`,
  },
];

export const STONE_STYLE_STORAGE_KEY = 'katrain_stone_style';
export const BOARD_STYLE_STORAGE_KEY = 'katrain_board_style';
export const CHINESE_FONT_STORAGE_KEY = 'katrain_chinese_font';

export function normalizeStoneStyleId(id?: string | null): StoneStyleId {
  if (id === 'shell-slate' || id === 'clamshell-slate') return 'clamshell-slate';
  if (id === 'yunzi' || id === 'jade-agate' || id === 'minimal') return id;
  return 'clamshell-slate';
}

export function normalizeBoardStyleId(id?: string | null): BoardStyleId {
  if (id === 'kaya' || id === 'shin-kaya' || id === 'bamboo' || id === 'walnut') return id;
  return 'kaya';
}

export function normalizeChineseFontId(id?: string | null): ChineseFontId {
  if (id === 'wenkai' || id === 'kaiti' || id === 'lishu' || id === 'heiti') return id;
  return 'wenkai';
}

let activeStoneStyle: StoneStyleId = 'clamshell-slate';
let activeBoardStyle: BoardStyleId = 'kaya';
const appearanceListeners = new Set<() => void>();

function emitBoardAppearanceChange(): void {
  appearanceListeners.forEach(listener => listener());
}

export function getActiveStoneStyle(): StoneStyleId {
  try {
    if (typeof localStorage !== 'undefined') {
      const stored = localStorage.getItem(STONE_STYLE_STORAGE_KEY);
      activeStoneStyle = normalizeStoneStyleId(stored);
    }
  } catch {
    // Ignore storage access errors in restricted environments
  }
  return activeStoneStyle;
}

export function setActiveStoneStyle(style: StoneAppearanceId | string): void {
  const prev = getActiveStoneStyle();
  const next = normalizeStoneStyleId(style);
  activeStoneStyle = next;
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(STONE_STYLE_STORAGE_KEY, next);
    }
  } catch {
    // Ignore storage write errors
  }
  if (prev !== next) {
    emitBoardAppearanceChange();
  }
}

export function getActiveBoardStyle(): BoardStyleId {
  try {
    if (typeof localStorage !== 'undefined') {
      const stored = localStorage.getItem(BOARD_STYLE_STORAGE_KEY);
      activeBoardStyle = normalizeBoardStyleId(stored);
    }
  } catch {
    // Ignore storage access errors in restricted environments
  }
  return activeBoardStyle;
}

export function setActiveBoardStyle(style: BoardStyleId | string): void {
  const prev = getActiveBoardStyle();
  const next = normalizeBoardStyleId(style);
  activeBoardStyle = next;
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(BOARD_STYLE_STORAGE_KEY, next);
    }
  } catch {
    // Ignore storage write errors
  }
  if (prev !== next) {
    emitBoardAppearanceChange();
  }
}

export function subscribeBoardAppearance(listener: () => void): () => void {
  appearanceListeners.add(listener);
  return () => {
    appearanceListeners.delete(listener);
  };
}

export function useBoardAppearance(): {
  stoneStyle: StoneStyleId;
  boardStyle: BoardStyleId;
  setStoneStyle: (style: StoneAppearanceId) => void;
  setBoardStyle: (style: BoardStyleId) => void;
} {
  const stoneStyle = useSyncExternalStore(
    subscribeBoardAppearance,
    getActiveStoneStyle,
    () => 'clamshell-slate' as StoneStyleId,
  );
  const boardStyle = useSyncExternalStore(
    subscribeBoardAppearance,
    getActiveBoardStyle,
    () => 'kaya' as BoardStyleId,
  );
  return {
    stoneStyle,
    boardStyle,
    setStoneStyle: setActiveStoneStyle,
    setBoardStyle: setActiveBoardStyle,
  };
}

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

export const DEFAULT_STONE_APPEARANCE_ID = 'clamshell-slate';

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
      new URL('./assets/shell-slate/white-08.png', import.meta.url).href,
      new URL('./assets/shell-slate/white-09.png', import.meta.url).href,
      new URL('./assets/shell-slate/white-10.png', import.meta.url).href,
      new URL('./assets/shell-slate/white-11.png', import.meta.url).href,
      new URL('./assets/shell-slate/white-12.png', import.meta.url).href,
      new URL('./assets/shell-slate/white-13.png', import.meta.url).href,
      new URL('./assets/shell-slate/white-14.png', import.meta.url).href,
      new URL('./assets/shell-slate/white-15.png', import.meta.url).href,
      new URL('./assets/shell-slate/white-16.png', import.meta.url).href,
      new URL('./assets/shell-slate/white-17.png', import.meta.url).href,
      new URL('./assets/shell-slate/white-18.png', import.meta.url).href,
      new URL('./assets/shell-slate/white-19.png', import.meta.url).href,
      new URL('./assets/shell-slate/white-20.png', import.meta.url).href,
      new URL('./assets/shell-slate/white-21.png', import.meta.url).href,
      new URL('./assets/shell-slate/white-22.png', import.meta.url).href,
      new URL('./assets/shell-slate/white-23.png', import.meta.url).href,
      new URL('./assets/shell-slate/white-24.png', import.meta.url).href,
      new URL('./assets/shell-slate/white-25.png', import.meta.url).href,
      new URL('./assets/shell-slate/white-26.png', import.meta.url).href,
      new URL('./assets/shell-slate/white-27.png', import.meta.url).href,
      new URL('./assets/shell-slate/white-28.png', import.meta.url).href,
      new URL('./assets/shell-slate/white-29.png', import.meta.url).href,
      new URL('./assets/shell-slate/white-30.png', import.meta.url).href,
      new URL('./assets/shell-slate/white-31.png', import.meta.url).href,
    ],
  },
  diameterRatio: { B: 1, W: 1 },
  material3d: {
    B: { color: '#17191b', roughness: 0.42, metalness: 0, clearcoat: 0.12, clearcoatRoughness: 0.48 },
    W: {
      color: '#f4f1e8',
      roughness: 0.32,
      metalness: 0,
      clearcoat: 0.18,
      clearcoatRoughness: 0.38,
      shell: { color: '#b9b09d', opacity: 0.22, frequency: 28, warp: 0.035 },
    },
  },
};

function svgToDataUrl(svg: string): string {
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg.trim())}`;
}

function renderProceduralDataUrl(
  size: number,
  draw: (ctx: CanvasRenderingContext2D, size: number) => void,
  fallbackSvg: string,
): string {
  if (typeof document !== 'undefined') {
    try {
      const canvas = document.createElement('canvas');
      canvas.width = size;
      canvas.height = size;
      const ctx = canvas.getContext('2d');
      if (ctx && typeof ctx.createRadialGradient === 'function') {
        draw(ctx, size);
        const url = canvas.toDataURL('image/png');
        if (url && url.startsWith('data:image/png') && url.length > 64) {
          return url;
        }
      }
    } catch {
      // Fallback to deterministic SVG data URL when Canvas 2D is unavailable
    }
  }
  return svgToDataUrl(fallbackSvg);
}

function createYunziBlackSprite(): string {
  const fallback = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" data-style="yunzi-b">
    <defs>
      <radialGradient id="yb" cx="36%" cy="32%" r="64%">
        <stop offset="0%" stop-color="#283430"/>
        <stop offset="68%" stop-color="#111715"/>
        <stop offset="92%" stop-color="#070a09"/>
        <stop offset="100%" stop-color="#10b981" stop-opacity="0.36"/>
      </radialGradient>
    </defs>
    <circle cx="64" cy="64" r="60" fill="url(#yb)" stroke="rgba(16,185,129,0.36)" stroke-width="2"/>
  </svg>`;
  return renderProceduralDataUrl(128, (ctx, size) => {
    const cx = size / 2;
    const cy = size / 2;
    const r = size * 0.465;

    ctx.save();
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.clip();

    const baseGrad = ctx.createRadialGradient(
      cx - r * 0.28,
      cy - r * 0.3,
      r * 0.05,
      cx,
      cy,
      r,
    );
    baseGrad.addColorStop(0, '#283430');
    baseGrad.addColorStop(0.62, '#111715');
    baseGrad.addColorStop(0.92, '#070a09');
    baseGrad.addColorStop(1, '#0d261e');
    ctx.fillStyle = baseGrad;
    ctx.fillRect(0, 0, size, size);

    // Subtle emerald-teal translucent rim glow characteristic of Yunnan Yunzi
    const rimGrad = ctx.createRadialGradient(cx, cy, r * 0.78, cx, cy, r);
    rimGrad.addColorStop(0, 'rgba(16, 185, 129, 0)');
    rimGrad.addColorStop(0.85, 'rgba(16, 185, 129, 0.18)');
    rimGrad.addColorStop(1, 'rgba(16, 185, 129, 0.36)');
    ctx.fillStyle = rimGrad;
    ctx.fillRect(0, 0, size, size);

    // Soft satin sheen in upper-left
    const spec = ctx.createRadialGradient(
      cx - r * 0.34,
      cy - r * 0.36,
      1,
      cx - r * 0.32,
      cy - r * 0.34,
      r * 0.42,
    );
    spec.addColorStop(0, 'rgba(220, 245, 235, 0.22)');
    spec.addColorStop(1, 'rgba(220, 245, 235, 0)');
    ctx.fillStyle = spec;
    ctx.fillRect(0, 0, size, size);
    ctx.restore();
  }, fallback);
}

function createYunziWhiteSprite(variant: number): string {
  const angle = (variant / 8) * Math.PI * 2;
  const ox = Math.cos(angle) * 2.2;
  const oy = Math.sin(angle) * 2.2;
  const fallback = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" data-style="yunzi-w-${variant}">
    <defs>
      <radialGradient id="yw${variant}" cx="${36 + (variant % 4)}%" cy="${34 + (variant % 3)}%" r="65%">
        <stop offset="0%" stop-color="#fbf8ef"/>
        <stop offset="65%" stop-color="#efe9d8"/>
        <stop offset="100%" stop-color="#d6cdb8"/>
      </radialGradient>
    </defs>
    <circle cx="64" cy="64" r="60" fill="url(#yw${variant})"/>
  </svg>`;
  return renderProceduralDataUrl(128, (ctx, size) => {
    const cx = size / 2;
    const cy = size / 2;
    const r = size * 0.465;

    ctx.save();
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.clip();

    const grad = ctx.createRadialGradient(
      cx - r * 0.26 + ox,
      cy - r * 0.28 + oy,
      r * 0.08,
      cx,
      cy,
      r,
    );
    grad.addColorStop(0, '#fbf8ef');
    grad.addColorStop(0.64, '#efe9d8');
    grad.addColorStop(0.9, '#dfd7c4');
    grad.addColorStop(1, '#d6cdb8');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, size, size);

    // Warm inner porcelain subsurface glow
    const glow = ctx.createRadialGradient(
      cx + r * 0.14,
      cy + r * 0.16,
      r * 0.05,
      cx + r * 0.1,
      cy + r * 0.12,
      r * 0.65,
    );
    glow.addColorStop(0, 'rgba(255, 250, 235, 0.28)');
    glow.addColorStop(1, 'rgba(255, 250, 235, 0)');
    ctx.fillStyle = glow;
    ctx.fillRect(0, 0, size, size);

    // Subtle specular sheen
    const spec = ctx.createRadialGradient(
      cx - r * 0.32 + ox * 0.4,
      cy - r * 0.34 + oy * 0.4,
      1,
      cx - r * 0.3,
      cy - r * 0.32,
      r * 0.38,
    );
    spec.addColorStop(0, 'rgba(255, 255, 255, 0.55)');
    spec.addColorStop(1, 'rgba(255, 255, 255, 0)');
    ctx.fillStyle = spec;
    ctx.fillRect(0, 0, size, size);
    ctx.restore();
  }, fallback);
}

function createJadeAgateBlackSprite(): string {
  const fallback = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" data-style="jade-agate-b">
    <defs>
      <radialGradient id="jab" cx="34%" cy="30%" r="66%">
        <stop offset="0%" stop-color="#323a45"/>
        <stop offset="48%" stop-color="#12161c"/>
        <stop offset="100%" stop-color="#06080b"/>
      </radialGradient>
    </defs>
    <circle cx="64" cy="64" r="60" fill="url(#jab)"/>
    <ellipse cx="46" cy="44" rx="14" ry="7" transform="rotate(-32 46 44)" fill="rgba(255,255,255,0.75)"/>
  </svg>`;
  return renderProceduralDataUrl(128, (ctx, size) => {
    const cx = size / 2;
    const cy = size / 2;
    const r = size * 0.465;

    ctx.save();
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.clip();

    const grad = ctx.createRadialGradient(
      cx - r * 0.28,
      cy - r * 0.3,
      r * 0.04,
      cx,
      cy,
      r,
    );
    grad.addColorStop(0, '#323a45');
    grad.addColorStop(0.45, '#12161c');
    grad.addColorStop(0.88, '#06080b');
    grad.addColorStop(1, '#1c232d');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, size, size);

    // Subtle agate internal ring
    ctx.strokeStyle = 'rgba(148, 163, 184, 0.08)';
    ctx.lineWidth = 2.2;
    ctx.beginPath();
    ctx.arc(cx + 2, cy + 1, r * 0.64, 0, Math.PI * 2);
    ctx.stroke();

    // Crisp upper-left crescent vitreous highlight
    ctx.save();
    ctx.translate(cx - r * 0.34, cy - r * 0.34);
    ctx.rotate(-Math.PI / 4);
    const spec = ctx.createRadialGradient(0, 0, 0.5, 0, 0, r * 0.32);
    spec.addColorStop(0, 'rgba(255, 255, 255, 0.88)');
    spec.addColorStop(0.55, 'rgba(255, 255, 255, 0.28)');
    spec.addColorStop(1, 'rgba(255, 255, 255, 0)');
    ctx.fillStyle = spec;
    ctx.scale(1.4, 0.68);
    ctx.beginPath();
    ctx.arc(0, 0, r * 0.32, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    ctx.restore();
  }, fallback);
}

function createJadeAgateWhiteSprite(variant: number): string {
  // Alpha between 0.85 and 0.91 so wood grain and grid lines subtly show through
  const alpha = Number((0.85 + (variant % 7) * 0.01).toFixed(2));
  const mode = variant % 4; // 0: icy pure, 1: warm honey-mutton-fat, 2: misty cloud, 3: concentric agate silk bands
  const tintTop = mode === 1 ? 'rgba(255, 252, 244, 0.91)' : mode === 0 ? 'rgba(246, 252, 250, 0.88)' : 'rgba(250, 253, 251, 0.89)';
  const tintMid = mode === 1 ? `rgba(244, 236, 220, ${alpha})` : `rgba(232, 242, 238, ${alpha})`;
  const tintEdge = mode === 1 ? 'rgba(218, 205, 182, 0.86)' : 'rgba(198, 214, 208, 0.85)';

  const fallback = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" data-style="jade-agate-w-${variant}" data-alpha="${alpha}">
    <defs>
      <radialGradient id="jaw${variant}" cx="35%" cy="32%" r="65%">
        <stop offset="0%" stop-color="#fcfffe" stop-opacity="${alpha}"/>
        <stop offset="62%" stop-color="#e8f2ee" stop-opacity="${alpha}"/>
        <stop offset="100%" stop-color="#c6d6d0" stop-opacity="0.86"/>
      </radialGradient>
    </defs>
    <circle cx="64" cy="64" r="60" fill="url(#jaw${variant})"/>
    <circle cx="74" cy="76" r="34" fill="rgba(255, 244, 214, 0.42)"/>
    <ellipse cx="45" cy="43" rx="15" ry="7.5" transform="rotate(-32 45 43)" fill="rgba(255, 255, 255, 0.92)"/>
  </svg>`;

  return renderProceduralDataUrl(128, (ctx, size) => {
    const cx = size / 2;
    const cy = size / 2;
    const r = size * 0.465;

    ctx.save();
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.clip();

    // Semi-transparent chalcedony body (alpha 0.85-0.91)
    const bodyGrad = ctx.createRadialGradient(
      cx - r * 0.24,
      cy - r * 0.26,
      r * 0.06,
      cx,
      cy,
      r,
    );
    bodyGrad.addColorStop(0, tintTop);
    bodyGrad.addColorStop(0.62, tintMid);
    bodyGrad.addColorStop(1, tintEdge);
    ctx.fillStyle = bodyGrad;
    ctx.fillRect(0, 0, size, size);

    // Natural mineral variations across the 16 variants
    if (mode === 2 || mode === 0) {
      // Misty cloud inclusions (棉絮云雾)
      const cloudAngle = (variant * 1.1) % (Math.PI * 2);
      const cloudX = cx + Math.cos(cloudAngle) * r * 0.18;
      const cloudY = cy + Math.sin(cloudAngle) * r * 0.18;
      const cloudGrad = ctx.createRadialGradient(cloudX, cloudY, 2, cloudX, cloudY, r * 0.48);
      cloudGrad.addColorStop(0, 'rgba(255, 255, 255, 0.32)');
      cloudGrad.addColorStop(1, 'rgba(255, 255, 255, 0)');
      ctx.fillStyle = cloudGrad;
      ctx.fillRect(0, 0, size, size);
    }

    if (mode === 3 || mode === 1) {
      // Fine concentric agate silk bands (缠丝玛瑙细纹)
      ctx.save();
      ctx.translate(cx + ((variant % 3) - 1) * 3, cy + ((variant % 2) - 0.5) * 3);
      ctx.rotate((variant * Math.PI) / 8);
      for (const bandFactor of [0.42, 0.58, 0.74]) {
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.22)';
        ctx.lineWidth = 1.25;
        ctx.beginPath();
        ctx.ellipse(0, 0, r * bandFactor, r * bandFactor * 0.88, 0, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.restore();
    }

    // Warm lower-right internal lens caustic glow
    const caustic = ctx.createRadialGradient(
      cx + r * 0.22,
      cy + r * 0.25,
      r * 0.04,
      cx + r * 0.18,
      cy + r * 0.2,
      r * 0.62,
    );
    caustic.addColorStop(0, 'rgba(255, 244, 214, 0.42)');
    caustic.addColorStop(1, 'rgba(255, 244, 214, 0)');
    ctx.fillStyle = caustic;
    ctx.fillRect(0, 0, size, size);

    // Crisp upper-left vitreous glass-luster crescent highlight
    ctx.save();
    ctx.translate(cx - r * 0.33, cy - r * 0.33);
    ctx.rotate(-Math.PI / 4);
    const crescent = ctx.createRadialGradient(0, 0, 0.5, 0, 0, r * 0.34);
    crescent.addColorStop(0, 'rgba(255, 255, 255, 0.92)');
    crescent.addColorStop(0.5, 'rgba(255, 255, 255, 0.36)');
    crescent.addColorStop(1, 'rgba(255, 255, 255, 0)');
    ctx.fillStyle = crescent;
    ctx.scale(1.45, 0.65);
    ctx.beginPath();
    ctx.arc(0, 0, r * 0.34, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    ctx.restore();
  }, fallback);
}

function createMinimalBlackSprite(): string {
  const fallback = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" data-style="minimal-b">
    <circle cx="64" cy="64" r="59" fill="#1e2229" stroke="#383e48" stroke-width="2.5"/>
  </svg>`;
  return renderProceduralDataUrl(128, (ctx, size) => {
    const cx = size / 2;
    const cy = size / 2;
    const r = size * 0.46;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fillStyle = '#1e2229';
    ctx.fill();
    ctx.strokeStyle = '#383e48';
    ctx.lineWidth = 2.5;
    ctx.stroke();
  }, fallback);
}

function createMinimalWhiteSprite(): string {
  const fallback = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" data-style="minimal-w">
    <circle cx="64" cy="64" r="59" fill="#f5f3ee" stroke="#c8c2b6" stroke-width="2.5"/>
  </svg>`;
  return renderProceduralDataUrl(128, (ctx, size) => {
    const cx = size / 2;
    const cy = size / 2;
    const r = size * 0.46;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fillStyle = '#f5f3ee';
    ctx.fill();
    ctx.strokeStyle = '#c8c2b6';
    ctx.lineWidth = 2.5;
    ctx.stroke();
  }, fallback);
}

const proceduralAppearanceCache = new Map<StoneStyleId, StoneAppearance>();

function buildStoneAppearance(styleId: StoneStyleId): StoneAppearance {
  if (styleId === 'clamshell-slate') {
    return DEFAULT_STONE_APPEARANCE;
  }
  const cached = proceduralAppearanceCache.get(styleId);
  if (cached) return cached;

  let appearance: StoneAppearance;
  if (styleId === 'yunzi') {
    const whiteSprites = Array.from({ length: 8 }, (_, i) => createYunziWhiteSprite(i)) as [string, ...string[]];
    appearance = {
      id: 'yunzi',
      sprites: {
        B: createYunziBlackSprite(),
        W: whiteSprites,
      },
      diameterRatio: { B: 1, W: 1 },
      material3d: {
        B: { color: '#111715', roughness: 0.28, metalness: 0.02, clearcoat: 0.45, clearcoatRoughness: 0.24 },
        W: { color: '#efe9d8', roughness: 0.24, metalness: 0, clearcoat: 0.52, clearcoatRoughness: 0.22 },
      },
    };
  } else if (styleId === 'jade-agate') {
    const whiteSprites = Array.from({ length: 16 }, (_, i) => createJadeAgateWhiteSprite(i)) as [string, ...string[]];
    appearance = {
      id: 'jade-agate',
      sprites: {
        B: createJadeAgateBlackSprite(),
        W: whiteSprites,
      },
      diameterRatio: { B: 1, W: 1 },
      material3d: {
        B: { color: '#0d1014', roughness: 0.08, metalness: 0.02, clearcoat: 0.96, clearcoatRoughness: 0.06 },
        W: { color: '#eef6f2', roughness: 0.07, metalness: 0, clearcoat: 0.98, clearcoatRoughness: 0.05 },
      },
    };
  } else {
    appearance = {
      id: 'minimal',
      sprites: {
        B: createMinimalBlackSprite(),
        W: [createMinimalWhiteSprite()],
      },
      diameterRatio: { B: 1, W: 1 },
      material3d: {
        B: { color: '#1e2229', roughness: 0.78, metalness: 0, clearcoat: 0, clearcoatRoughness: 1 },
        W: { color: '#f5f3ee', roughness: 0.72, metalness: 0, clearcoat: 0, clearcoatRoughness: 1 },
      },
    };
  }

  proceduralAppearanceCache.set(styleId, appearance);
  return appearance;
}

export const STONE_APPEARANCES: Readonly<Record<string, StoneAppearance>> = {
  'clamshell-slate': DEFAULT_STONE_APPEARANCE,
  'shell-slate': DEFAULT_STONE_APPEARANCE,
};

export function getStoneAppearance(id?: StoneAppearanceId | string | null): StoneAppearance {
  const effectiveId = id === undefined ? getActiveStoneStyle() : normalizeStoneStyleId(id);
  return buildStoneAppearance(effectiveId);
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
  color: 'B' | 'W',
  seed: string | number,
  col: number,
  row: number,
  appearanceId: StoneAppearanceId | string = getActiveStoneStyle(),
): string {
  const { sprites } = getStoneAppearance(appearanceId);
  return color === 'B' ? sprites.B : sprites.W[stoneVariant(seed, col, row, sprites.W.length)];
}

export interface BoardStylePalette {
  readonly id: BoardStyleId;
  readonly label: string;
  readonly woodFill: string;
  readonly woodSecondary: string;
  readonly gridColor: string;
  readonly starColor: string;
  readonly coordColor: string;
  readonly borderColor: string;
  readonly textureUrl: string;
}

export type BoardStyleSpec = BoardStylePalette;

export const BOARD_STYLE_PALETTES: Readonly<Record<BoardStyleId, BoardStylePalette>> = {
  kaya: {
    id: 'kaya',
    label: '日式本榧',
    woodFill: '#e5ba70',
    woodSecondary: '#cc9c52',
    gridColor: '#1a120b',
    starColor: '#1a120b',
    coordColor: '#261a0f',
    borderColor: '#8c6228',
    textureUrl: '/assets/textures/kaya-veneer-2k.jpg',
  },
  'shin-kaya': {
    id: 'shin-kaya',
    label: '新榧云杉',
    woodFill: '#e5c687',
    woodSecondary: '#cca666',
    gridColor: '#1a120b',
    starColor: '#1a120b',
    coordColor: '#261a0f',
    borderColor: '#a88952',
    textureUrl: '/assets/textures/shinkaya-veneer-2k.jpg',
  },
  bamboo: {
    id: 'bamboo',
    label: '碳化楠竹',
    woodFill: '#c78c46',
    woodSecondary: '#b07634',
    gridColor: '#1a120b',
    starColor: '#1a120b',
    coordColor: '#261a0f',
    borderColor: '#7a4b19',
    textureUrl: '/assets/textures/bamboo-veneer-2k.jpg',
  },
  walnut: {
    id: 'walnut',
    label: '胡桃沉香',
    woodFill: '#876244',
    woodSecondary: '#6b472e',
    gridColor: '#e6c896',
    starColor: '#e6c896',
    coordColor: '#eedcb0',
    borderColor: '#4a3221',
    textureUrl: '/assets/textures/walnut-veneer-2k.jpg',
  },
};

export function getBoardStylePalette(
  boardStyle: BoardStyleId | string | null = getActiveBoardStyle(),
): BoardStylePalette {
  const id = normalizeBoardStyleId(boardStyle ?? getActiveBoardStyle());
  return BOARD_STYLE_PALETTES[id];
}

export function getBoardTextureUrl(
  boardStyle: BoardStyleId | string | null = getActiveBoardStyle(),
): string {
  const id = normalizeBoardStyleId(boardStyle ?? getActiveBoardStyle());
  return BOARD_STYLE_PALETTES[id].textureUrl;
}

const boardTextureDataUrlCache = new Map<BoardStyleId, string>();

export function getBoardTextureDataUrl(
  boardStyle: BoardStyleId | string | null = getActiveBoardStyle(),
): string {
  const id = normalizeBoardStyleId(boardStyle ?? getActiveBoardStyle());
  const cached = boardTextureDataUrlCache.get(id);
  if (cached) return cached;

  const palette = BOARD_STYLE_PALETTES[id];
  const fallbackSvg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" data-board-style="${id}">
    <rect width="256" height="256" fill="${palette.woodFill}"/>
  </svg>`;

  const url = renderProceduralDataUrl(256, (ctx, size) => {
    ctx.fillStyle = palette.woodFill;
    ctx.fillRect(0, 0, size, size);
  }, fallbackSvg);

  boardTextureDataUrlCache.set(id, url);
  return url;
}
