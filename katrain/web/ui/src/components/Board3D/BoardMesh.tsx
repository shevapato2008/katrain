import { useMemo, useEffect, memo, Suspense, lazy } from 'react';
import { useThree } from '@react-three/fiber';
import * as THREE from 'three';
import {
  type BoardStyleId,
  getBoardStylePalette,
  getBoardTextureUrl,
  normalizeBoardStyleId,
  useBoardAppearance,
} from '../board/stoneAppearance';
import SolidWoodSlab from './SolidWoodSlab';
import {
  getBoardDimensions,
  getStarPoints,
  getColumnLabel,
  getRowLabel,
  BOARD_SURFACE_Y,
  SURFACE_EPSILON,
} from './constants';

// Lazy-load coordinate labels so troika-three-text (used by drei <Text>) is only
// fetched when coordinates are actually displayed.  This prevents troika's Web Worker
// from firing CDN requests in headless/offline recording environments.
const CoordinateLabels = lazy(() => import('./CoordinateLabels'));

interface BoardMeshProps {
  boardSize: number;
  showCoordinates: boolean;
  solidWood?: boolean;
}

const BOARD_3D_STYLE_CONFIG: Record<
  BoardStyleId,
  {
    topColor: string;
    sideColor: string;
    bottomColor: string;
    grainColor: [number, number, number];
    bandColor: [number, number, number];
    grainCount: number;
  }
> = {
  kaya: {
    topColor: '#DBA85A',
    sideColor: '#C89848',
    bottomColor: '#B08040',
    grainColor: [120, 75, 30],
    bandColor: [180, 140, 70],
    grainCount: 150,
  },
  'shin-kaya': {
    topColor: '#EDD39C',
    sideColor: '#DFC184',
    bottomColor: '#B89B62',
    grainColor: [140, 102, 48],
    bandColor: [210, 175, 115],
    grainCount: 180,
  },
  bamboo: {
    topColor: '#C88C46',
    sideColor: '#B57835',
    bottomColor: '#8C5820',
    grainColor: [85, 48, 16],
    bandColor: [150, 95, 40],
    grainCount: 140,
  },
  walnut: {
    topColor: '#5C402C',
    sideColor: '#4A3221',
    bottomColor: '#2E1D11',
    grainColor: [24, 14, 7],
    bandColor: [42, 26, 15],
    grainCount: 160,
  },
};

/** Real 2K wood-veneer texture with stripe-free canvas fallback supporting all 4 board styles. */
function createWoodTexture(
  width: number,
  height: number,
  baseColor: string,
  grainColor: [number, number, number],
  _bandColor: [number, number, number],
  grainCount: number,
  boardStyle: BoardStyleId = 'kaya',
  onLoad?: () => void,
): THREE.CanvasTexture {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');

  if (ctx && typeof ctx.createLinearGradient === 'function') {
    ctx.fillStyle = baseColor;
    ctx.fillRect(0, 0, width, height);

    if (boardStyle === 'bamboo') {
      // Subtle bamboo strip seams without dark node blocks
      const stripCount = 12;
      const stripH = height / stripCount;
      for (let s = 0; s < stripCount; s++) {
        const y0 = s * stripH;
        ctx.strokeStyle = 'rgba(68, 36, 10, 0.14)';
        ctx.lineWidth = 1.0;
        ctx.beginPath();
        ctx.moveTo(0, y0);
        ctx.lineTo(width, y0);
        ctx.stroke();
      }
    }

    for (let i = 0; i < grainCount; i++) {
      const y = Math.random() * height;
      const alpha = boardStyle === 'shin-kaya' ? 0.03 + Math.random() * 0.07 : 0.04 + Math.random() * 0.1;
      ctx.strokeStyle = `rgba(${grainColor[0]}, ${grainColor[1]}, ${grainColor[2]}, ${alpha})`;
      ctx.lineWidth = boardStyle === 'shin-kaya' ? 0.4 + Math.random() * 1.4 : 0.5 + Math.random() * 2.5;
      ctx.beginPath();
      ctx.moveTo(0, y);
      const freq = 0.01 + Math.random() * 0.03;
      const amp = boardStyle === 'shin-kaya' || boardStyle === 'bamboo' ? 1 + Math.random() * 4 : 3 + Math.random() * 12;
      for (let x = 0; x < width; x += 8) {
        ctx.lineTo(x, y + Math.sin(x * freq) * amp + Math.sin(x * 0.005) * 3 + (Math.random() - 0.5) * 1.5);
      }
      ctx.stroke();
    }

    for (let i = 0; i < grainCount / 3; i++) {
      const y = Math.random() * height;
      ctx.strokeStyle = `rgba(${grainColor[0]}, ${grainColor[1]}, ${grainColor[2]}, ${0.03 + Math.random() * 0.05})`;
      ctx.lineWidth = 2 + Math.random() * 4;
      ctx.beginPath();
      ctx.moveTo(0, y);
      for (let x = 0; x < width; x += 15) {
        ctx.lineTo(x, y + Math.sin(x * 0.015) * 8 + (Math.random() - 0.5) * 2);
      }
      ctx.stroke();
    }

    if (typeof ctx.getImageData === 'function' && typeof ctx.putImageData === 'function') {
      const imgData = ctx.getImageData(0, 0, width, height);
      const pixels = imgData.data;
      const noiseCount = width * height * 0.3;
      for (let i = 0; i < noiseCount; i++) {
        const idx = Math.floor(Math.random() * width * height) * 4;
        const noise = (Math.random() - 0.5) * 14;
        pixels[idx] = Math.max(0, Math.min(255, pixels[idx] + noise));
        pixels[idx + 1] = Math.max(0, Math.min(255, pixels[idx + 1] + noise));
        pixels[idx + 2] = Math.max(0, Math.min(255, pixels[idx + 2] + noise * 0.5));
      }
      ctx.putImageData(imgData, 0, 0);
    }
  }

  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.wrapS = THREE.RepeatWrapping;
  tex.wrapT = THREE.RepeatWrapping;

  if (typeof Image !== 'undefined' && ctx) {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      ctx.drawImage(img, 0, 0, width, height);
      tex.needsUpdate = true;
      onLoad?.();
    };
    img.src = getBoardTextureUrl(boardStyle);
  }

  return tex;
}

const BoardMesh = ({ boardSize, showCoordinates, solidWood = false }: BoardMeshProps) => {
  const { boardStyle } = useBoardAppearance();
  const resolvedBoardStyle = normalizeBoardStyleId(boardStyle);
  const palette = getBoardStylePalette(resolvedBoardStyle);
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

  const dims = useMemo(() => getBoardDimensions(boardSize), [boardSize]);
  const starPoints = useMemo(() => getStarPoints(boardSize), [boardSize]);
  const halfExtent = dims.boardExtent / 2;

  const resources = useMemo(() => {
    if (solidWood) {
      return {
        materials: [] as THREE.Material[],
        textures: [] as THREE.CanvasTexture[],
        allMaterials: [] as THREE.Material[],
      };
    }
    const cfg = BOARD_3D_STYLE_CONFIG[resolvedBoardStyle];
    const handleTextureLoaded = () => invalidate?.();
    const topTex = createWoodTexture(1024, 1024, cfg.topColor, cfg.grainColor, cfg.bandColor, cfg.grainCount, resolvedBoardStyle, handleTextureLoaded);
    const sideTex = createWoodTexture(1024, 256, cfg.sideColor, cfg.grainColor, cfg.bandColor, Math.round(cfg.grainCount * 0.8), resolvedBoardStyle, handleTextureLoaded);

    const topMat = new THREE.MeshStandardMaterial({
      map: topTex, roughness: 0.4, metalness: 0.02, color: cfg.topColor,
    });
    const sideMat = new THREE.MeshStandardMaterial({
      map: sideTex, roughness: 0.5, metalness: 0.03, color: cfg.sideColor,
    });
    const bottomMat = new THREE.MeshStandardMaterial({
      color: cfg.bottomColor, roughness: 0.7, metalness: 0.02,
    });

    // BoxGeometry face order: +x, -x, +y, -y, +z, -z
    return {
      materials: [sideMat, sideMat, topMat, bottomMat, sideMat, sideMat],
      textures: [topTex, sideTex],
      allMaterials: [topMat, sideMat, bottomMat],
    };
  }, [boardSize, solidWood, resolvedBoardStyle]);

  // Dispose textures and materials whenever resources change or on unmount (Finding C-1)
  useEffect(() => {
    return () => {
      resources.textures.forEach(t => t.dispose());
      resources.allMaterials.forEach(m => m.dispose());
    };
  }, [resources]);

  // Grid lines as a single LineSegments geometry (1 draw call instead of 38)
  const gridGeometry = useMemo(() => {
    const lineY = BOARD_SURFACE_Y + SURFACE_EPSILON;
    const vertices: number[] = [];

    for (let i = 0; i < boardSize; i++) {
      const pos = -halfExtent + i * dims.gridSpacing;
      // Vertical line (pair of endpoints)
      vertices.push(pos, lineY, -halfExtent, pos, lineY, halfExtent);
      // Horizontal line
      vertices.push(-halfExtent, lineY, pos, halfExtent, lineY, pos);
    }
    const geom = new THREE.BufferGeometry();
    geom.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
    return geom;
  }, [boardSize, dims, halfExtent]);

  useEffect(() => {
    return () => { gridGeometry.dispose(); };
  }, [gridGeometry]);

  // Coordinate label data
  const coordLabels = useMemo(() => {
    if (!showCoordinates) return [];
    const labelOffset = 0.4; // Center of board padding zone (BOARD_PADDING/2)
    const labelY = BOARD_SURFACE_Y + SURFACE_EPSILON;
    const labels: { text: string; position: [number, number, number] }[] = [];

    for (let i = 0; i < boardSize; i++) {
      const xPos = -halfExtent + i * dims.gridSpacing;
      const zPos = halfExtent - i * dims.gridSpacing; // Inverted Z to match gridToWorld convention

      // Column labels (A-T) along near and far edges
      labels.push({ text: getColumnLabel(i), position: [xPos, labelY, halfExtent + labelOffset] });
      labels.push({ text: getColumnLabel(i), position: [xPos, labelY, -halfExtent - labelOffset] });
      // Row labels (1-19) along left and right edges — Z inverted so "1" is near camera
      labels.push({ text: getRowLabel(i), position: [-halfExtent - labelOffset, labelY, zPos] });
      labels.push({ text: getRowLabel(i), position: [halfExtent + labelOffset, labelY, zPos] });
    }
    return labels;
  }, [boardSize, dims, halfExtent, showCoordinates]);

  return (
    <group>
      {/* Board slab */}
      {solidWood ? <SolidWoodSlab width={dims.boardWidth} /> : <mesh
        position={[0, dims.boardHeight / 2, 0]}
        material={resources.materials}
        castShadow
        receiveShadow={false}
      >
        <boxGeometry args={[dims.boardWidth, dims.boardHeight, dims.boardWidth]} />
      </mesh>}

      {/* Grid lines — single LineSegments for efficiency (1 draw call) */}
      <lineSegments geometry={gridGeometry}>
        <lineBasicMaterial color={palette.gridColor} transparent opacity={0.78} />
      </lineSegments>

      {/* Star points */}
      {starPoints.map(([col, row], i) => {
        const x = -halfExtent + col * dims.gridSpacing;
        const z = -halfExtent + row * dims.gridSpacing;
        return (
          <mesh key={`star-${i}`} position={[x, BOARD_SURFACE_Y + SURFACE_EPSILON, z]} rotation={[-Math.PI / 2, 0, 0]}>
            <circleGeometry args={[0.08, 16]} />
            <meshBasicMaterial color={palette.starColor} opacity={0.88} transparent />
          </mesh>
        );
      })}

      {/* Coordinate labels — lazy-loaded to avoid troika CDN dependency in headless mode */}
      {showCoordinates && (
        <Suspense fallback={null}>
          <CoordinateLabels labels={coordLabels} />
        </Suspense>
      )}
    </group>
  );
};

export default memo(BoardMesh);
