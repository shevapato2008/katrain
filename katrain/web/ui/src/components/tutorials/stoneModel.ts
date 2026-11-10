import * as THREE from 'three';
import recipe from '../../../../../assets/board-equipment/go/stones/clamshell-slate/v1/source/recipe.json';
import { type StoneStyleId, normalizeStoneStyleId } from '../board/stoneAppearance';

/** Millimetres from the manufacturer's size 32 reference; shape is an artistic approximation. */
export const STONE_DIMENSIONS = recipe.dimensionsMm;
export const STONE_RECIPE = recipe;
export type StoneColor = keyof typeof STONE_DIMENSIONS;

function random(seed: number) {
  return () => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    return seed / 4294967296;
  };
}

/** A closed, symmetric lens: a broad dome flowing into a narrow, rounded equator. */
export function createStoneGeometry(
  color: StoneColor,
  detail: Partial<Pick<typeof recipe.geometry, 'radialSegments' | 'domeSegments' | 'edgeSegments'>> = {},
) {
  const { diameter, thickness } = STONE_DIMENSIONS[color];
  const radius = diameter / STONE_DIMENSIONS.W.diameter;
  const halfHeight = thickness / STONE_DIMENSIONS.W.diameter;
  const point = ([x, y]: number[]) => new THREE.Vector2(x * radius, y * halfHeight);
  const [d0, d1, d2, d3] = recipe.geometry.domeControlPoints.map(point);
  const [e0, e1, e2, e3] = recipe.geometry.edgeControlPoints.map(point);
  const dome = new THREE.CubicBezierCurve(
    d0, d1, d2, d3,
  );
  const edge = new THREE.CubicBezierCurve(
    e0, e1, e2, e3,
  );
  const upper = [...dome.getPoints(detail.domeSegments ?? recipe.geometry.domeSegments),
    ...edge.getPoints(detail.edgeSegments ?? recipe.geometry.edgeSegments).slice(1)];
  // Lathe winds from the lower pole to the upper pole. Both poles lie on the rotation axis.
  const profile = [...upper.map(p => new THREE.Vector2(p.x, -p.y)), ...upper.slice(0, -1).reverse()];
  const geometry = new THREE.LatheGeometry(profile, detail.radialSegments ?? recipe.geometry.radialSegments);
  const positions = geometry.getAttribute('position');
  const uv = geometry.getAttribute('uv');
  for (let i = 0; i < positions.count; i++) {
    uv.setXY(i, positions.getX(i) / (2 * radius) + .5, positions.getZ(i) / (2 * radius) + .5);
  }
  geometry.computeVertexNormals();
  return geometry;
}

interface ShellMaps { color: THREE.CanvasTexture; roughness: THREE.CanvasTexture; bump: THREE.CanvasTexture }
const shellMaps = new Map<string, ShellMaps>();
const jadeAgateWhiteMaps = new Map<string, THREE.CanvasTexture>();
const yunziWhiteMaps = new Map<string, THREE.CanvasTexture>();

function texture(canvas: HTMLCanvasElement, color = false) {
  const map = new THREE.CanvasTexture(canvas);
  map.colorSpace = color ? THREE.SRGBColorSpace : THREE.NoColorSpace;
  map.anisotropy = 4;
  return map;
}

/** Original shell growth lines, fixed in stone space: no photos, random frames, or polar rings. */
function createShellMaps(seed: number, size = 768): ShellMaps {
  const variant = ((seed % 8) + 8) % 8;
  const key = `${variant}:${size}`;
  const existing = shellMaps.get(key);
  if (existing) return existing;
  const rng = random(variant + 17);
  const canvases = Array.from({ length: 3 }, () => Object.assign(document.createElement('canvas'), { width: size, height: size }));
  const contexts = canvases.map(c => c.getContext('2d'));
  if (contexts.every((ctx): ctx is CanvasRenderingContext2D => Boolean(ctx && typeof ctx.createImageData === 'function'))) {
    const images = contexts.map(ctx => ctx.createImageData(size, size));
    const bands: { position: number; width: number; strength: number }[] = [];
    // At the workbench/video's 24–36 px diameter, the former ~25 hairlines averaged
    // away. Soft, irregular warm growth ribbons stay legible without carved grooves.
    for (let position = -1.65; position < 1.7; position += .22 + rng() * .12) {
      bands.push({ position, width: .055 + rng() * .025, strength: .55 + rng() * .4 });
    }
    const angle = .63 + (rng() - .5) * .18;
    const cs = Math.cos(angle), sn = Math.sin(angle);
    for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
      const u = x / (size - 1) * 2 - 1, v = y / (size - 1) * 2 - 1;
      const along = -u * sn + v * cs;
      const across = u * cs + v * sn + .055 * along * along + .014 * Math.sin(along * 3.2 + variant);
      let grain = 0;
      for (const band of bands) {
        const distance = (across - band.position) / band.width;
        if (Math.abs(distance) < 3) grain += Math.exp(-distance * distance) * band.strength;
      }
      const pearl = 1.8 * Math.sin(across * 8 + along * .7) + .7 * Math.sin(along * 5.1);
      const micro = (rng() - .5) * .6;
      const base = 246 + pearl + micro;
      const offset = (y * size + x) * 4;
      images[0].data.set([base + 1.4 - grain * 18,
        base + 1.1 - grain * 23,
        base - 1.4 - grain * 39, 255], offset);
      const roughness = 219 + grain * 4 + micro * 2;
      images[1].data.set([roughness, roughness, roughness, 255], offset);
      const relief = 128 + grain * 1.5;
      images[2].data.set([relief, relief, relief, 255], offset);
    }
    contexts.forEach((ctx, i) => ctx.putImageData(images[i], 0, 0));
  }
  const maps = { color: texture(canvases[0], true), roughness: texture(canvases[1]), bump: texture(canvases[2]) };
  shellMaps.set(key, maps);
  return maps;
}

/** Cached 8-variant semi-transparent chalcedony silk-band & warm caustic glow texture for jade-agate white stones. */
function getJadeAgateWhiteTexture(seed: number, size = 256): THREE.CanvasTexture {
  const variant = ((seed % 8) + 8) % 8;
  const key = `${variant}:${size}`;
  const existing = jadeAgateWhiteMaps.get(key);
  if (existing) return existing;

  const canvas = Object.assign(document.createElement('canvas'), { width: size, height: size });
  const ctx = canvas.getContext('2d');
  if (ctx && typeof ctx.createRadialGradient === 'function') {
    const cx = size / 2;
    const cy = size / 2;
    const r = size * 0.48;
    const mode = variant % 4;

    const baseGrad = ctx.createRadialGradient(cx - r * 0.22, cy - r * 0.24, r * 0.05, cx, cy, r);
    baseGrad.addColorStop(0, mode === 1 ? 'rgba(255, 252, 245, 0.94)' : 'rgba(248, 253, 251, 0.92)');
    baseGrad.addColorStop(0.65, mode === 1 ? 'rgba(244, 238, 224, 0.89)' : 'rgba(235, 245, 241, 0.88)');
    baseGrad.addColorStop(1, 'rgba(208, 222, 216, 0.86)');
    ctx.fillStyle = baseGrad;
    ctx.fillRect(0, 0, size, size);

    // Misty cloud inclusions & concentric chalcedony silk bands
    const cloudAngle = (variant * Math.PI) / 4;
    const cloudGrad = ctx.createRadialGradient(
      cx + Math.cos(cloudAngle) * r * 0.18,
      cy + Math.sin(cloudAngle) * r * 0.18,
      r * 0.04,
      cx,
      cy,
      r * 0.55,
    );
    cloudGrad.addColorStop(0, 'rgba(255, 255, 255, 0.35)');
    cloudGrad.addColorStop(1, 'rgba(255, 255, 255, 0)');
    ctx.fillStyle = cloudGrad;
    ctx.fillRect(0, 0, size, size);

    ctx.save();
    ctx.translate(cx + ((variant % 3) - 1) * 3, cy + ((variant % 2) - 0.5) * 3);
    ctx.rotate(cloudAngle);
    for (const factor of [0.38, 0.56, 0.72]) {
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.24)';
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.ellipse?.(0, 0, r * factor, r * factor * 0.88, 0, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.restore();

    // Warm lower-right subsurface lens caustic glow
    const caustic = ctx.createRadialGradient(
      cx + r * 0.22,
      cy + r * 0.24,
      r * 0.04,
      cx + r * 0.16,
      cy + r * 0.18,
      r * 0.65,
    );
    caustic.addColorStop(0, 'rgba(255, 244, 214, 0.45)');
    caustic.addColorStop(1, 'rgba(255, 244, 214, 0)');
    ctx.fillStyle = caustic;
    ctx.fillRect(0, 0, size, size);
  }

  const map = texture(canvas, true);
  jadeAgateWhiteMaps.set(key, map);
  return map;
}

/** Cached 8-variant warm ivory porcelain texture for yunzi white stones. */
function getYunziWhiteTexture(seed: number, size = 256): THREE.CanvasTexture {
  const variant = ((seed % 8) + 8) % 8;
  const key = `${variant}:${size}`;
  const existing = yunziWhiteMaps.get(key);
  if (existing) return existing;

  const canvas = Object.assign(document.createElement('canvas'), { width: size, height: size });
  const ctx = canvas.getContext('2d');
  if (ctx && typeof ctx.createRadialGradient === 'function') {
    const cx = size / 2;
    const cy = size / 2;
    const r = size * 0.48;
    const angle = (variant / 8) * Math.PI * 2;
    const ox = Math.cos(angle) * 3;
    const oy = Math.sin(angle) * 3;

    const grad = ctx.createRadialGradient(cx - r * 0.24 + ox, cy - r * 0.26 + oy, r * 0.06, cx, cy, r);
    grad.addColorStop(0, '#fcf9f0');
    grad.addColorStop(0.68, '#f5efe0');
    grad.addColorStop(1, '#e2dac6');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, size, size);
  }

  const map = texture(canvas, true);
  yunziWhiteMaps.set(key, map);
  return map;
}

export function createStoneMaterial(
  color: StoneColor,
  seed = 17,
  plain = false,
  textureSize = 768,
  stoneStyle: StoneStyleId | string = 'clamshell-slate',
) {
  const resolvedStyle = normalizeStoneStyleId(stoneStyle);
  const variant = ((seed % 8) + 8) % 8;

  if (resolvedStyle === 'yunzi') {
    if (color === 'B') {
      return new THREE.MeshPhysicalMaterial({
        color: '#101815',
        roughness: 0.22,
        metalness: 0.02,
        clearcoat: 0.65,
        clearcoatRoughness: 0.2,
        sheen: 0.35,
        sheenColor: new THREE.Color('#10b981'),
        attenuationColor: new THREE.Color('#0d9488'),
        attenuationDistance: 1.4,
      });
    }
    return new THREE.MeshPhysicalMaterial({
      color: '#f8f4e8',
      map: plain ? null : getYunziWhiteTexture(variant, textureSize),
      roughness: 0.16,
      metalness: 0,
      clearcoat: 0.72,
      clearcoatRoughness: 0.18,
      transmission: 0.14,
      ior: 1.52,
      thickness: 1.2,
    });
  }

  if (resolvedStyle === 'jade-agate') {
    if (color === 'B') {
      return new THREE.MeshPhysicalMaterial({
        color: '#0e1116',
        roughness: 0.06,
        metalness: 0.02,
        clearcoat: 1.0,
        clearcoatRoughness: 0.04,
      });
    }
    return new THREE.MeshPhysicalMaterial({
      color: '#f6faf9',
      map: plain ? null : getJadeAgateWhiteTexture(variant, textureSize),
      transmission: 0.52,
      ior: 1.544,
      thickness: 1.8,
      roughness: 0.07,
      metalness: 0,
      clearcoat: 0.98,
      clearcoatRoughness: 0.05,
      transparent: true,
      opacity: 0.9,
      attenuationColor: new THREE.Color('#fff6e0'),
      attenuationDistance: 1.6,
    });
  }

  if (resolvedStyle === 'minimal') {
    return new THREE.MeshPhysicalMaterial({
      color: color === 'B' ? '#1e2229' : '#f4f2ed',
      roughness: 0.78,
      metalness: 0.02,
      clearcoat: 0.0,
      clearcoatRoughness: 1.0,
    });
  }

  if (color === 'B') return new THREE.MeshPhysicalMaterial(recipe.materials.black);
  if (plain) return new THREE.MeshPhysicalMaterial({
    color: 0xf5f2e9, metalness: 0, roughness: .34,
    clearcoat: .18, clearcoatRoughness: .35, envMapIntensity: .75,
  });
  const maps = createShellMaps(variant, textureSize);
  return new THREE.MeshPhysicalMaterial({
    color: 0xffffff, map: maps.color, roughnessMap: maps.roughness, roughness: .36,
    emissive: 0xffffff, emissiveMap: maps.color, emissiveIntensity: .12,
    bumpMap: maps.bump, bumpScale: .0012, metalness: 0, ior: 1.53,
    clearcoat: .1, clearcoatRoughness: .38, envMapIntensity: .6,
  });
}

export function createStone(color: StoneColor, seed = 17, plain = false) {
  const stone = new THREE.Mesh(createStoneGeometry(color), createStoneMaterial(color, seed, plain));
  stone.position.y = STONE_DIMENSIONS[color].thickness / STONE_DIMENSIONS.W.diameter;
  stone.castShadow = true;
  stone.receiveShadow = true;
  stone.name = color === 'W' ? 'clamshell-white' : 'nachi-black';
  return stone;
}

export function createBoardTexture() {
  const canvas = Object.assign(document.createElement('canvas'), { width: 1024, height: 768 });
  const context = canvas.getContext('2d')!;
  context.fillStyle = '#c9a676'; context.fillRect(0, 0, canvas.width, canvas.height);
  const rng = random(6017);
  for (let i = 0; i < 2100; i++) {
    const x = rng() * canvas.width;
    context.strokeStyle = `rgba(${rng() > .5 ? '90,59,27' : '255,232,192'},${.025 + rng() * .055})`;
    context.lineWidth = .3 + rng() * .8;
    context.beginPath(); context.moveTo(x, 0);
    context.bezierCurveTo(x + 3, 250, x - 4, 480, x + (rng() - .5) * 10, 768); context.stroke();
  }
  context.strokeStyle = 'rgba(61,44,26,.48)'; context.lineWidth = 1.25;
  for (let x = 0; x <= 1024; x += 128) { context.beginPath(); context.moveTo(x, 0); context.lineTo(x, 768); context.stroke(); }
  for (let y = 0; y <= 768; y += 128) { context.beginPath(); context.moveTo(0, y); context.lineTo(1024, y); context.stroke(); }
  return texture(canvas, true);
}
