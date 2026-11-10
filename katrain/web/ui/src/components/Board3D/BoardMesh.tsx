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
  }
> = {
  kaya: {
    topColor: '#e5ba70',
    sideColor: '#cc9c52',
    bottomColor: '#b08040',
  },
  'shin-kaya': {
    topColor: '#e5c687',
    sideColor: '#cca666',
    bottomColor: '#b89b62',
  },
  bamboo: {
    topColor: '#c78c46',
    sideColor: '#b07634',
    bottomColor: '#8c5820',
  },
  walnut: {
    topColor: '#876244',
    sideColor: '#6b472e',
    bottomColor: '#4a3221',
  },
};

function drawBakedGridOnTopCanvas(
  ctx: CanvasRenderingContext2D,
  size: number,
  boardSize: number,
  dims: ReturnType<typeof getBoardDimensions>,
  starPoints: [number, number][],
  gridColor: string,
  starColor: string,
) {
  const scale = size / dims.boardWidth;
  const halfExtent = dims.boardExtent / 2;
  const origin = (dims.boardWidth / 2 - halfExtent) * scale;
  const step = dims.gridSpacing * scale;
  const extentPx = dims.boardExtent * scale;

  ctx.save();
  ctx.strokeStyle = gridColor;
  ctx.lineWidth = Math.max(2.2, size * 0.0014);
  for (let i = 0; i < boardSize; i++) {
    const pos = origin + i * step;
    ctx.beginPath();
    ctx.moveTo(pos, origin);
    ctx.lineTo(pos, origin + extentPx);
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(origin, pos);
    ctx.lineTo(origin + extentPx, pos);
    ctx.stroke();
  }

  ctx.fillStyle = starColor;
  const starRadius = Math.max(5.5, size * 0.0036);
  for (const [col, row] of starPoints) {
    const x = origin + col * step;
    const y = origin + row * step;
    ctx.beginPath();
    ctx.arc(x, y, starRadius, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}

/** Real 2K wood-veneer texture with stripe-free canvas fallback supporting all 4 board styles. */
function createWoodTexture(
  width: number,
  height: number,
  baseColor: string,
  boardStyle: BoardStyleId = 'kaya',
  onPaintOverlay?: (ctx: CanvasRenderingContext2D) => void,
  onLoad?: () => void,
): THREE.CanvasTexture {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');

  if (ctx) {
    ctx.fillStyle = baseColor;
    ctx.fillRect(0, 0, width, height);
    onPaintOverlay?.(ctx);
  }

  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 16;
  tex.generateMipmaps = true;

  if (typeof Image !== 'undefined' && ctx) {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      ctx.drawImage(img, 0, 0, width, height);
      onPaintOverlay?.(ctx);
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
    const topTex = createWoodTexture(
      2048,
      2048,
      cfg.topColor,
      resolvedBoardStyle,
      (ctx) => drawBakedGridOnTopCanvas(ctx, 2048, boardSize, dims, starPoints, palette.gridColor, palette.starColor),
      handleTextureLoaded,
    );
    const sideTex = createWoodTexture(1024, 256, cfg.sideColor, resolvedBoardStyle, undefined, handleTextureLoaded);

    // Do NOT multiply map by cfg.topColor (keep color #ffffff) so 2K wood veneer preserves 100% natural brightness
    const topMat = new THREE.MeshPhysicalMaterial({
      map: topTex,
      color: '#ffffff',
      roughness: 0.36,
      clearcoat: 0.18,
      clearcoatRoughness: 0.28,
      metalness: 0.0,
    });
    const sideMat = new THREE.MeshPhysicalMaterial({
      map: sideTex,
      color: '#ffffff',
      roughness: 0.52,
      metalness: 0.0,
    });
    const bottomMat = new THREE.MeshStandardMaterial({
      color: cfg.bottomColor,
      roughness: 0.7,
      metalness: 0.02,
    });

    // BoxGeometry face order: +x, -x, +y, -y, +z, -z
    return {
      materials: [sideMat, sideMat, topMat, bottomMat, sideMat, sideMat],
      textures: [topTex, sideTex],
      allMaterials: [topMat, sideMat, bottomMat],
    };
  }, [boardSize, solidWood, resolvedBoardStyle, dims, starPoints, palette.gridColor, palette.starColor]);

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
        <lineBasicMaterial color={palette.gridColor} transparent opacity={0.95} />
      </lineSegments>

      {/* Star points */}
      {starPoints.map(([col, row], i) => {
        const x = -halfExtent + col * dims.gridSpacing;
        const z = -halfExtent + row * dims.gridSpacing;
        return (
          <mesh key={`star-${i}`} position={[x, BOARD_SURFACE_Y + SURFACE_EPSILON, z]} rotation={[-Math.PI / 2, 0, 0]}>
            <circleGeometry args={[0.08, 16]} />
            <meshBasicMaterial color={palette.starColor} opacity={0.95} transparent />
          </mesh>
        );
      })}

      {/* Coordinate labels — lazy-loaded to avoid troika CDN dependency in headless mode */}
      {showCoordinates && (
        <Suspense fallback={null}>
          <CoordinateLabels labels={coordLabels} color={palette.coordColor} />
        </Suspense>
      )}
    </group>
  );
};

export default memo(BoardMesh);
