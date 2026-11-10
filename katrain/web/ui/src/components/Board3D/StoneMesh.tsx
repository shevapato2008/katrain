import { useMemo, useEffect, memo, forwardRef } from 'react';
import { useThree } from '@react-three/fiber';
import * as THREE from 'three';
import type { Mesh } from 'three';
import { DEFAULT_STONE_APPEARANCE, useBoardAppearance } from '../board/stoneAppearance';
import { createStoneGeometry, createStoneMaterial } from '../tutorials/stoneModel';
import { STONE_RADIUS, STONE_HEIGHT, BOARD_SURFACE_Y } from './constants';
import { stoneMeshScale } from './stoneScale';

interface StoneMeshProps {
  color: 'B' | 'W';
  position: [number, number, number];
  opacity?: number;
  /** Stable full-board coordinate variation, shared by static, drop and ghost stones. */
  variant?: number;
  angle?: number;
  scale?: number;
  satinFinish?: boolean;
  contactOpacity?: number;
  spriteTexture?: THREE.Texture;
  diameterRatio?: number;
}

// Board-resolution copies of the existing clamshell/slate model's authored shape.
// Each color shares one geometry across all stones; the full-detail tutorial model is unchanged.
const boardDetail = { radialSegments: 48, domeSegments: 18, edgeSegments: 6 };
const sharedGeometry = {
  B: createStoneGeometry('B', boardDetail),
  W: createStoneGeometry('W', boardDetail),
};
const sharedSpriteGeometry = new THREE.PlaneGeometry(STONE_RADIUS * 2, STONE_RADIUS * 2);

// Noop raycast — prevents stones from intercepting pointer events
const noopRaycast = () => {};

/** Local contact shadow beneath 3D stones (eliminates need for receiveShadow on the flat board surface). */
let contactTexture: THREE.CanvasTexture | null = null;
function getContactTexture() {
  if (contactTexture) return contactTexture;
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 128;
  const ctx = canvas.getContext('2d');
  if (ctx && typeof ctx.createRadialGradient === 'function') {
    const gradient = ctx.createRadialGradient(64, 64, 12, 64, 64, 60);
    gradient.addColorStop(0, 'rgba(12, 8, 3, 0.36)');
    gradient.addColorStop(0.55, 'rgba(12, 8, 3, 0.16)');
    gradient.addColorStop(1, 'rgba(12, 8, 3, 0)');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, 128, 128);
  }
  contactTexture = new THREE.CanvasTexture(canvas);
  contactTexture.colorSpace = THREE.SRGBColorSpace;
  return contactTexture;
}

/** Warm lower-right refractive caustic glow decal for translucent white jade-agate stones. */
let causticTexture: THREE.CanvasTexture | null = null;
function getCausticTexture() {
  if (causticTexture) return causticTexture;
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 128;
  const ctx = canvas.getContext('2d');
  if (ctx && typeof ctx.createRadialGradient === 'function') {
    const g = ctx.createRadialGradient(74, 76, 4, 64, 64, 58);
    g.addColorStop(0, 'rgba(255, 244, 214, 0.58)');
    g.addColorStop(0.45, 'rgba(255, 232, 185, 0.24)');
    g.addColorStop(1, 'rgba(255, 232, 185, 0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, 128, 128);
  }
  causticTexture = new THREE.CanvasTexture(canvas);
  causticTexture.colorSpace = THREE.SRGBColorSpace;
  return causticTexture;
}

const StoneMesh = forwardRef<Mesh, StoneMeshProps>(({ color, position, opacity = 1, variant = 0, angle = 0, scale = 1, satinFinish = false, contactOpacity = 1, spriteTexture, diameterRatio = 1 }, ref) => {
  const { stoneStyle } = useBoardAppearance();
  let invalidate: (() => void) | undefined;
  try {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    invalidate = useThree()?.invalidate;
  } catch {
    // Rendered outside R3F Canvas in unit tests
  }

  useEffect(() => {
    invalidate?.();
  }, [stoneStyle, invalidate]);

  const material = useMemo(() => {
    if (spriteTexture) return new THREE.MeshBasicMaterial({
      map: spriteTexture, transparent: true, opacity, depthWrite: false, toneMapped: false, fog: false,
    });
    if (satinFinish) return new THREE.MeshPhysicalMaterial({
      color: color === 'B' ? 0x111418 : 0xf5f2e9,
      roughness: color === 'B' ? .29 : .34, metalness: 0,
      clearcoat: .18, clearcoatRoughness: .35,
      transparent: opacity < 1, opacity,
    });
    if (stoneStyle === DEFAULT_STONE_APPEARANCE.id) {
      // The 3D shell recipe has eight seeds, independent of the 2D sprite count.
      const mat = createStoneMaterial(color, variant % 8, false, 256);
      mat.transparent = opacity < 1;
      mat.opacity = opacity;
      return mat;
    }
    const mat = createStoneMaterial(color, variant % 8, false, 256, stoneStyle);
    mat.transparent = opacity < 1;
    mat.opacity = opacity;
    return mat;
  }, [color, opacity, variant, satinFinish, spriteTexture, stoneStyle]);

  // Dispose per-stone material, not the shared procedural maps.
  useEffect(() => {
    return () => { material.dispose(); };
  }, [material]);

  const showContactDisc = !spriteTexture && opacity >= 0.85;
  const showJadeCaustic = !spriteTexture && !satinFinish && stoneStyle === 'jade-agate' && color === 'W' && opacity >= 0.85;

  return (
    <>
      <mesh
        ref={ref}
        position={spriteTexture ? [position[0], position[1] + STONE_HEIGHT * scale, position[2]] : position}
        rotation={spriteTexture ? [-Math.PI / 2, 0, 0] : [0, -angle, 0]}
        scale={spriteTexture ? [scale * diameterRatio, scale * diameterRatio, 1] : stoneMeshScale(color, scale)}
        geometry={spriteTexture ? sharedSpriteGeometry : sharedGeometry[color]}
        material={material}
        castShadow={!spriteTexture}
        receiveShadow={!spriteTexture}
        raycast={noopRaycast}
      />
      {showContactDisc && <mesh position={[position[0] + 0.035, BOARD_SURFACE_Y + 0.008, position[2] + 0.035]} rotation={[-Math.PI / 2, 0, 0]} raycast={noopRaycast}>
        <planeGeometry args={[1.08 * scale, 1.08 * scale]} />
        <meshBasicMaterial map={getContactTexture()} opacity={contactOpacity * opacity} transparent depthWrite={false} />
      </mesh>}
      {showJadeCaustic && <mesh position={[position[0] + 0.06, BOARD_SURFACE_Y + 0.009, position[2] + 0.06]} rotation={[-Math.PI / 2, 0, 0]} raycast={noopRaycast}>
        <planeGeometry args={[0.96 * scale, 0.96 * scale]} />
        <meshBasicMaterial map={getCausticTexture()} opacity={0.85 * opacity} transparent depthWrite={false} />
      </mesh>}
    </>
  );
});

StoneMesh.displayName = 'StoneMesh';
export default memo(StoneMesh);
