import * as THREE from 'three';

/** Millimetres from the manufacturer's size 32 reference; shape is an artistic approximation. */
export const STONE_DIMENSIONS = {
  W: { diameter: 21.9, thickness: 8.8 },
  B: { diameter: 22.2, thickness: 9.1 },
} as const;
export type StoneColor = keyof typeof STONE_DIMENSIONS;

function random(seed: number) {
  return () => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    return seed / 4294967296;
  };
}

/** A closed, symmetric lens: a broad dome flowing into a narrow, rounded equator. */
export function createStoneGeometry(color: StoneColor) {
  const { diameter, thickness } = STONE_DIMENSIONS[color];
  const radius = diameter / STONE_DIMENSIONS.W.diameter;
  const halfHeight = thickness / STONE_DIMENSIONS.W.diameter;
  const dome = new THREE.CubicBezierCurve(
    new THREE.Vector2(0, halfHeight), new THREE.Vector2(.43 * radius, halfHeight),
    new THREE.Vector2(.79 * radius, .76 * halfHeight), new THREE.Vector2(.94 * radius, .32 * halfHeight),
  );
  const edge = new THREE.CubicBezierCurve(
    new THREE.Vector2(.94 * radius, .32 * halfHeight), new THREE.Vector2(.975 * radius, .224 * halfHeight),
    new THREE.Vector2(radius, .07 * halfHeight), new THREE.Vector2(radius, 0),
  );
  const upper = [...dome.getPoints(38), ...edge.getPoints(12).slice(1)];
  // Lathe winds from the lower pole to the upper pole. Both poles lie on the rotation axis.
  const profile = [...upper.map(p => new THREE.Vector2(p.x, -p.y)), ...upper.slice(0, -1).reverse()];
  const geometry = new THREE.LatheGeometry(profile, 128);
  const positions = geometry.getAttribute('position');
  const uv = geometry.getAttribute('uv');
  for (let i = 0; i < positions.count; i++) {
    uv.setXY(i, positions.getX(i) / (2 * radius) + .5, positions.getZ(i) / (2 * radius) + .5);
  }
  geometry.computeVertexNormals();
  return geometry;
}

interface ShellMaps { color: THREE.CanvasTexture; roughness: THREE.CanvasTexture; bump: THREE.CanvasTexture }
const shellMaps = new Map<number, ShellMaps>();

function texture(canvas: HTMLCanvasElement, color = false) {
  const map = new THREE.CanvasTexture(canvas);
  map.colorSpace = color ? THREE.SRGBColorSpace : THREE.NoColorSpace;
  map.anisotropy = 4;
  return map;
}

/** Original fine growth lines, fixed in stone space: no photos, random frames, or polar rings. */
function createShellMaps(seed: number): ShellMaps {
  const existing = shellMaps.get(seed);
  if (existing) return existing;
  const rng = random(seed);
  const size = 768;
  const canvases = Array.from({ length: 3 }, () => Object.assign(document.createElement('canvas'), { width: size, height: size }));
  const contexts = canvases.map(c => c.getContext('2d')!);
  const images = contexts.map(c => c.createImageData(size, size));
  const bands: { position: number; width: number; strength: number }[] = [];
  for (let position = -1.65; position < 1.7; position += .067 + rng() * .025) {
    bands.push({ position, width: .009 + rng() * .006, strength: .48 + rng() * .48 });
  }
  const angle = .63 + (rng() - .5) * .18;
  const cs = Math.cos(angle), sn = Math.sin(angle);
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const u = x / (size - 1) * 2 - 1, v = y / (size - 1) * 2 - 1;
    const along = -u * sn + v * cs;
    const across = u * cs + v * sn + .055 * along * along + .014 * Math.sin(along * 3.2 + seed);
    let grain = 0;
    for (const band of bands) {
      const distance = (across - band.position) / band.width;
      if (Math.abs(distance) < 3) grain += Math.exp(-distance * distance) * band.strength;
    }
    const pearl = 1.8 * Math.sin(across * 8 + along * .7) + .7 * Math.sin(along * 5.1);
    const micro = (rng() - .5) * .6;
    const base = 239 + pearl - grain * 9 + micro;
    const offset = (y * size + x) * 4;
    images[0].data.set([base + 1.4, base + 1.1, base - 1.4, 255], offset);
    const roughness = 219 + grain * 13 + micro * 2;
    images[1].data.set([roughness, roughness, roughness, 255], offset);
    const relief = 128 + grain * 8;
    images[2].data.set([relief, relief, relief, 255], offset);
  }
  contexts.forEach((ctx, i) => ctx.putImageData(images[i], 0, 0));
  const maps = { color: texture(canvases[0], true), roughness: texture(canvases[1]), bump: texture(canvases[2]) };
  shellMaps.set(seed, maps);
  return maps;
}

export function createStoneMaterial(color: StoneColor, seed = 17, plain = false) {
  if (color === 'B') return new THREE.MeshPhysicalMaterial({
    color: 0x090b0d, metalness: 0, roughness: .46, ior: 1.5,
    clearcoat: .04, clearcoatRoughness: .55, envMapIntensity: .7,
  });
  if (plain) return new THREE.MeshPhysicalMaterial({
    color: 0xf5f2e9, metalness: 0, roughness: .34,
    clearcoat: .18, clearcoatRoughness: .35, envMapIntensity: .75,
  });
  const maps = createShellMaps(seed);
  return new THREE.MeshPhysicalMaterial({
    color: 0xffffff, map: maps.color, roughnessMap: maps.roughness, roughness: .36,
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
