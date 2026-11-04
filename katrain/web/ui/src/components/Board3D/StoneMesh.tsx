import { useMemo, useEffect, memo, forwardRef } from 'react';
import * as THREE from 'three';
import type { Mesh } from 'three';
import { DEFAULT_STONE_APPEARANCE, getStoneAppearance } from '../board/stoneAppearance';
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

/** Local contact shadow for the overhead still; shared by its stones only. */
let contactTexture: THREE.CanvasTexture | null = null;
function getContactTexture() {
  if (contactTexture) return contactTexture;
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 64;
  const ctx = canvas.getContext('2d')!;
  const gradient = ctx.createRadialGradient(32, 32, 18, 32, 32, 32);
  gradient.addColorStop(0, 'rgba(0,0,0,.32)');
  gradient.addColorStop(.55, 'rgba(0,0,0,.16)');
  gradient.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, 64, 64);
  contactTexture = new THREE.CanvasTexture(canvas);
  return contactTexture;
}

const StoneMesh = forwardRef<Mesh, StoneMeshProps>(({ color, position, opacity = 1, variant = 0, angle = 0, scale = 1, satinFinish = false, contactOpacity = 1, spriteTexture, diameterRatio = 1 }, ref) => {
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
    const appearance = getStoneAppearance();
    if (appearance.id === DEFAULT_STONE_APPEARANCE.id) {
      // The 3D shell recipe has eight seeds, independent of the 2D sprite count.
      const material = createStoneMaterial(color, variant % 8, false, 256);
      material.transparent = opacity < 1;
      material.opacity = opacity;
      return material;
    }
    const recipe = appearance.material3d?.[color] ?? DEFAULT_STONE_APPEARANCE.material3d[color];
    return new THREE.MeshPhysicalMaterial({ ...recipe, transparent: opacity < 1, opacity });
  }, [color, opacity, variant, satinFinish, spriteTexture]);

  // Dispose per-stone material, not the shared procedural maps.
  useEffect(() => {
    return () => { material.dispose(); };
  }, [material]);

  return (
    <>
      {satinFinish && <mesh position={[position[0] + .035, BOARD_SURFACE_Y + .009, position[2] + .035]} rotation={[-Math.PI / 2, 0, 0]} raycast={noopRaycast}>
        <planeGeometry args={[1.06, 1.06]} />
        <meshBasicMaterial map={getContactTexture()} opacity={contactOpacity} transparent depthWrite={false} />
      </mesh>}
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
    </>
  );
});

StoneMesh.displayName = 'StoneMesh';
export default memo(StoneMesh);
