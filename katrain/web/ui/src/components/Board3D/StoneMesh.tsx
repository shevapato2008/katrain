import { useMemo, useEffect, memo, forwardRef } from 'react';
import * as THREE from 'three';
import type { Mesh } from 'three';
import { STONE_RADIUS, STONE_HEIGHT } from './constants';

interface StoneMeshProps {
  color: 'B' | 'W';
  position: [number, number, number];
  opacity?: number;
  scale?: number;
}

// Shared geometry — all stones use the same sphere (1 geometry, not 361)
const sharedGeometry = new THREE.SphereGeometry(STONE_RADIUS, 48, 32);

// Noop raycast — prevents stones from intercepting pointer events
const noopRaycast = () => {};

/** Shell texture for Hamaguri white stones. Cached at module level. */
let cachedShellTexture: THREE.CanvasTexture | null = null;

function getShellTexture(): THREE.CanvasTexture {
  if (cachedShellTexture) return cachedShellTexture;
  const size = 512;
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  ctx.fillStyle = '#f5edd8';
  ctx.fillRect(0, 0, size, size);

  const cx = size * 0.48, cy = size * 0.7;
  for (let i = 0; i < 40; i++) {
    const r = 6 + i * (size * 0.024);
    const dark = i % 2 === 0;
    ctx.strokeStyle = dark
      ? `rgba(110, 80, 30, ${0.7 + Math.random() * 0.3})`
      : `rgba(150, 120, 60, ${0.5 + Math.random() * 0.3})`;
    ctx.lineWidth = dark ? 3 + Math.random() * 3 : 1.5 + Math.random() * 2;
    ctx.beginPath();
    ctx.arc(cx + (Math.random() - 0.5) * 4, cy + (Math.random() - 0.5) * 3, r, Math.PI * 0.08, Math.PI * 0.92);
    ctx.stroke();
  }

  const cx2 = size * 0.55, cy2 = size * 0.75;
  for (let i = 0; i < 15; i++) {
    const r = 10 + i * (size * 0.035);
    ctx.strokeStyle = `rgba(130, 100, 45, ${0.2 + Math.random() * 0.2})`;
    ctx.lineWidth = 1 + Math.random() * 1.5;
    ctx.beginPath();
    ctx.arc(cx2, cy2, r, Math.PI * 0.15, Math.PI * 0.85);
    ctx.stroke();
  }

  const g = ctx.createRadialGradient(size * 0.38, size * 0.3, size * 0.02, size * 0.45, size * 0.4, size * 0.2);
  g.addColorStop(0, 'rgba(255, 252, 240, 0.35)');
  g.addColorStop(1, 'rgba(255, 252, 240, 0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);

  cachedShellTexture = new THREE.CanvasTexture(canvas);
  return cachedShellTexture;
}

const StoneMesh = forwardRef<Mesh, StoneMeshProps>(({ color, position, opacity = 1, scale = 1 }, ref) => {
  const material = useMemo(() => {
    if (color === 'B') {
      return new THREE.MeshStandardMaterial({
        color: 0x0a0a0a, roughness: 0.06, metalness: 0.15,
        transparent: opacity < 1, opacity,
      });
    } else {
      return new THREE.MeshStandardMaterial({
        map: getShellTexture(), color: 0xf5edd8, roughness: 0.1, metalness: 0.04,
        transparent: opacity < 1, opacity,
      });
    }
  }, [color, opacity]);

  // Dispose material on change/unmount (but NOT the shared shell texture)
  useEffect(() => {
    return () => { material.dispose(); };
  }, [material]);

  const scaleY = STONE_HEIGHT / STONE_RADIUS;

  return (
    <mesh
      ref={ref}
      position={position}
      scale={[scale, scale * scaleY, scale]}
      geometry={sharedGeometry}
      material={material}
      castShadow
      receiveShadow
      raycast={noopRaycast}
    />
  );
});

StoneMesh.displayName = 'StoneMesh';
export default memo(StoneMesh);
