import { memo, useEffect, useMemo } from 'react';
import { useThree } from '@react-three/fiber';
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import {
  type BoardStyleId,
  normalizeBoardStyleId,
  useBoardAppearance,
} from '../board/stoneAppearance';
import { BOARD_SURFACE_Y } from './constants';

// Extend downward: the established grid, stone and annotation coordinates stay fixed.
const SLAB_DEPTH = 2.5;

const SLAB_PALETTES: Record<
  BoardStyleId,
  {
    top: string;
    side: string;
    bottom: string;
    grainRgb: string;
  }
> = {
  kaya: {
    top: '#d4aa66',
    side: '#bd8d49',
    bottom: '#9d703b',
    grainRgb: '104, 63, 24',
  },
  'shin-kaya': {
    top: '#edd39c',
    side: '#dfc184',
    bottom: '#b89b62',
    grainRgb: '140, 102, 48',
  },
  bamboo: {
    top: '#c88c46',
    side: '#b57835',
    bottom: '#8c5820',
    grainRgb: '85, 48, 16',
  },
  walnut: {
    top: '#5c402c',
    side: '#4a3221',
    bottom: '#2e1d11',
    grainRgb: '24, 14, 7',
  },
};

/** Subtle continuous grain; fixed seed keeps saved preview frames reproducible. */
function woodTexture(face: 'top' | 'side' | 'end', boardStyle: BoardStyleId = 'kaya') {
  const canvas = document.createElement('canvas');
  canvas.width = 1024;
  canvas.height = face === 'top' ? 1024 : 256;
  const ctx = canvas.getContext('2d');
  const { width, height } = canvas;
  let seed = 28417;
  const random = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
  const cfg = SLAB_PALETTES[boardStyle];

  if (ctx) {
    ctx.fillStyle = face === 'top' ? cfg.top : cfg.side;
    ctx.fillRect(0, 0, width, height);
    if (face === 'end') {
      // End grain is cut across the longitudinal fibers, with broad, quiet growth rings.
      for (let ring = 0; ring < 95; ring++) {
        ctx.beginPath();
        ctx.strokeStyle = `rgba(${cfg.grainRgb}, ${.055 + random() * .065})`;
        ctx.lineWidth = .7 + random();
        ctx.ellipse?.(width * .42, height * 2.8, 100 + ring * 19, 35 + ring * 7, .025, 0, Math.PI * 2);
        ctx.stroke();
      }
    } else {
      const transverse = face === 'top' ? width : height;
      const longitudinal = face === 'top' ? height : width;

      if (boardStyle === 'bamboo' && face === 'top' && typeof ctx.createLinearGradient === 'function') {
        const stripW = width / 16;
        for (let s = 0; s < 16; s++) {
          const x0 = s * stripW;
          ctx.strokeStyle = 'rgba(68, 36, 10, 0.22)';
          ctx.lineWidth = 1.4;
          ctx.beginPath();
          ctx.moveTo(x0, 0);
          ctx.lineTo(x0, height);
          ctx.stroke();

          const nodeY = ((s * 241 + 113) % (height - 96)) + 48;
          const nodeGrad = ctx.createLinearGradient(0, nodeY - 8, 0, nodeY + 8);
          nodeGrad.addColorStop(0, 'rgba(68, 36, 10, 0)');
          nodeGrad.addColorStop(0.5, 'rgba(68, 36, 10, 0.28)');
          nodeGrad.addColorStop(1, 'rgba(255, 224, 178, 0.14)');
          ctx.fillStyle = nodeGrad;
          ctx.fillRect(x0 + 1, nodeY - 8, stripW - 2, 16);
        }
      }

      for (let i = 0; i < 320; i++) {
        const origin = random() * transverse;
        const amplitude = boardStyle === 'shin-kaya' || boardStyle === 'bamboo' ? 0.5 + random() * 1.8 : 1 + random() * 4;
        const phase = random() * Math.PI * 2;
        ctx.strokeStyle = `rgba(${cfg.grainRgb}, ${.025 + random() * .07})`;
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
    if (typeof ctx.getImageData === 'function' && typeof ctx.putImageData === 'function') {
      const pixels = ctx.getImageData(0, 0, width, height);
      for (let offset = 0; offset < pixels.data.length; offset += 4) {
        const noise = (random() - .5) * 5;
        for (let channel = 0; channel < 3; channel++) pixels.data[offset + channel] += noise;
      }
      ctx.putImageData(pixels, 0, 0);
    }
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 8;
  return texture;
}

/** Tutorial recording only: a beveled solid board and the surface supporting it. */
function SolidWoodSlab({ width }: { width: number }) {
  const { boardStyle } = useBoardAppearance();
  const resolvedBoardStyle = normalizeBoardStyleId(boardStyle);
  let invalidate: (() => void) | undefined;
  try {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    invalidate = useThree()?.invalidate;
  } catch {
    // Rendered outside R3F Canvas in unit tests
  }

  useEffect(() => {
    invalidate?.();
  }, [resolvedBoardStyle, invalidate]);

  const resources = useMemo(() => {
    const cfg = SLAB_PALETTES[resolvedBoardStyle];
    const textures = [
      woodTexture('top', resolvedBoardStyle),
      woodTexture('side', resolvedBoardStyle),
      woodTexture('end', resolvedBoardStyle),
    ];
    const top = new THREE.MeshStandardMaterial({ map: textures[0], roughness: .48, metalness: 0 });
    const side = new THREE.MeshStandardMaterial({ map: textures[1], roughness: .57, metalness: 0 });
    const end = new THREE.MeshStandardMaterial({ map: textures[2], roughness: .6, metalness: 0 });
    const bottom = new THREE.MeshStandardMaterial({ color: cfg.bottom, roughness: .7 });
    const geometry = new RoundedBoxGeometry(width, SLAB_DEPTH, width, 4, .12);
    // BoxGeometry face order: right, left, top, bottom, front, back.
    return { textures, geometry, materials: [side, side, top, bottom, end, end] };
  }, [width, resolvedBoardStyle]);
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
