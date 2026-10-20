import { memo, useEffect, useMemo } from 'react';
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { BOARD_SURFACE_Y } from './constants';

// Extend downward: the established grid, stone and annotation coordinates stay fixed.
const SLAB_DEPTH = 2.5;

/** Subtle continuous grain; fixed seed keeps saved preview frames reproducible. */
function woodTexture(face: 'top' | 'side' | 'end') {
  const canvas = document.createElement('canvas');
  canvas.width = 1024;
  canvas.height = face === 'top' ? 1024 : 256;
  const ctx = canvas.getContext('2d')!;
  const { width, height } = canvas;
  let seed = 28417;
  const random = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
  ctx.fillStyle = face === 'top' ? '#d4aa66' : '#bd8d49';
  ctx.fillRect(0, 0, width, height);
  if (face === 'end') {
    // End grain is cut across the longitudinal fibers, with broad, quiet growth rings.
    for (let ring = 0; ring < 95; ring++) {
      ctx.beginPath();
      ctx.strokeStyle = `rgba(91, 53, 20, ${.055 + random() * .065})`;
      ctx.lineWidth = .7 + random();
      ctx.ellipse(width * .42, height * 2.8, 100 + ring * 19, 35 + ring * 7, .025, 0, Math.PI * 2);
      ctx.stroke();
    }
  } else {
    const transverse = face === 'top' ? width : height;
    const longitudinal = face === 'top' ? height : width;
    for (let i = 0; i < 320; i++) {
      const origin = random() * transverse;
      const amplitude = 1 + random() * 4;
      const phase = random() * Math.PI * 2;
      ctx.strokeStyle = `rgba(104, 63, 24, ${.025 + random() * .07})`;
      ctx.lineWidth = .45 + random() * 1.5;
      ctx.beginPath();
      for (let along = 0; along <= longitudinal; along += 8) {
        const across = origin + Math.sin(along * .009 + phase) * amplitude + Math.sin(along * .024 + phase) * .7;
        const x = face === 'top' ? across : along;
        const y = face === 'top' ? along : across;
        if (along === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }
  }
  const pixels = ctx.getImageData(0, 0, width, height);
  for (let offset = 0; offset < pixels.data.length; offset += 4) {
    const noise = (random() - .5) * 5;
    for (let channel = 0; channel < 3; channel++) pixels.data[offset + channel] += noise;
  }
  ctx.putImageData(pixels, 0, 0);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 8;
  return texture;
}

/** Tutorial recording only: a beveled solid board and the surface supporting it. */
function SolidWoodSlab({ width }: { width: number }) {
  const resources = useMemo(() => {
    const textures = [woodTexture('top'), woodTexture('side'), woodTexture('end')];
    const top = new THREE.MeshStandardMaterial({ map: textures[0], roughness: .48, metalness: 0 });
    const side = new THREE.MeshStandardMaterial({ map: textures[1], roughness: .57, metalness: 0 });
    const end = new THREE.MeshStandardMaterial({ map: textures[2], roughness: .6, metalness: 0 });
    const bottom = new THREE.MeshStandardMaterial({ color: '#9d703b', roughness: .7 });
    const geometry = new RoundedBoxGeometry(width, SLAB_DEPTH, width, 4, .12);
    // BoxGeometry face order: right, left, top, bottom, front, back.
    return { textures, geometry, materials: [side, side, top, bottom, end, end] };
  }, [width]);
  useEffect(() => () => {
    resources.geometry.dispose();
    resources.textures.forEach(texture => texture.dispose());
    new Set(resources.materials).forEach(material => material.dispose());
  }, [resources]);
  return <group>
    <mesh name="tutorial-solid-wood-slab" position={[0, BOARD_SURFACE_Y - SLAB_DEPTH / 2, 0]}
      geometry={resources.geometry} material={resources.materials} castShadow receiveShadow />
    <mesh position={[0, BOARD_SURFACE_Y - SLAB_DEPTH - .015, 0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
      <planeGeometry args={[160, 160]} />
      <shadowMaterial color="#000" transparent opacity={.25} depthWrite={false} />
    </mesh>
  </group>;
}

export default memo(SolidWoodSlab);
