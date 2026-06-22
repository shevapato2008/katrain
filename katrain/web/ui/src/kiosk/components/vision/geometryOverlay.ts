import type { GeometryAnchor, GeometryCorner, GeometryLayout, GeometryPhase } from '../../../api/geometryApi';

export interface OverlayViewport {
  width: number;
  height: number;
}

export interface OverlayPoint {
  row: number;
  col: number;
  x: number;
  y: number;
}

export interface OverlayLine {
  from: OverlayPoint;
  to: OverlayPoint;
}

export interface OverlayCorner extends OverlayPoint {
  label: string;
}

export interface OverlayAnchor extends OverlayPoint {
  color: string;
}

export interface GeometryOverlayModel {
  tone: 'normal' | 'stale' | 'partial';
  lines: OverlayLine[];
  points: OverlayPoint[];
  starPoints: OverlayPoint[];
  corners: OverlayCorner[];
  anchors: OverlayAnchor[];
}

export const fitContain = (
  containerWidth: number,
  containerHeight: number,
  sourceWidth: number,
  sourceHeight: number,
) => {
  if (containerWidth <= 0 || containerHeight <= 0 || sourceWidth <= 0 || sourceHeight <= 0) {
    return { scale: 0, offsetX: 0, offsetY: 0 };
  }
  const scale = Math.min(containerWidth / sourceWidth, containerHeight / sourceHeight);
  const offsetX = (containerWidth - sourceWidth * scale) / 2;
  const offsetY = (containerHeight - sourceHeight * scale) / 2;
  return {
    scale,
    offsetX: Math.abs(offsetX) < Number.EPSILON * containerWidth ? 0 : offsetX,
    offsetY: Math.abs(offsetY) < Number.EPSILON * containerHeight ? 0 : offsetY,
  };
};

const mapPoint = (
  row: number,
  col: number,
  x: number,
  y: number,
  transform: ReturnType<typeof fitContain>,
): OverlayPoint => ({
  row,
  col,
  x: transform.offsetX + x * transform.scale,
  y: transform.offsetY + y * transform.scale,
});

const gridModel = (
  points: [number, number][][],
  corners: GeometryCorner[],
  source: { width: number; height: number },
  viewport: OverlayViewport,
  tone: GeometryOverlayModel['tone'],
): GeometryOverlayModel => {
  const transform = fitContain(viewport.width, viewport.height, source.width, source.height);
  const mapped = points.map((rowPoints, row) =>
    rowPoints.map(([x, y], col) => mapPoint(row, col, x, y, transform)),
  );
  const lines: OverlayLine[] = [];
  for (let row = 0; row < 19; row += 1) {
    lines.push({ from: mapped[row][0], to: mapped[row][18] });
  }
  for (let col = 0; col < 19; col += 1) {
    lines.push({ from: mapped[0][col], to: mapped[18][col] });
  }
  const flatPoints = mapped.flat();
  const starPoints = flatPoints.filter(
    (point) => [3, 9, 15].includes(point.row) && [3, 9, 15].includes(point.col),
  );
  return {
    tone,
    lines,
    points: flatPoints,
    starPoints,
    corners: corners.map((corner) => ({
      ...mapPoint(corner.row, corner.col, corner.x, corner.y, transform),
      label: corner.label,
    })),
    anchors: [],
  };
};

export const buildRawGeometryModel = (
  layout: GeometryLayout,
  phase: GeometryPhase,
  viewport: OverlayViewport,
): GeometryOverlayModel => gridModel(
  layout.points,
  layout.corners,
  layout.frame,
  viewport,
  phase === 'degraded' || layout.stale ? 'stale' : 'normal',
);

export const buildAnchorGeometryModel = (
  anchors: GeometryAnchor[],
  frame: { width: number; height: number },
  viewport: OverlayViewport,
): GeometryOverlayModel => {
  const transform = fitContain(viewport.width, viewport.height, frame.width, frame.height);
  return {
    tone: 'partial',
    lines: [],
    points: [],
    starPoints: [],
    corners: [],
    anchors: anchors.map((anchor) => ({
      ...mapPoint(anchor.row, anchor.col, anchor.x, anchor.y, transform),
      color: anchor.color,
    })),
  };
};

export const buildWarpedGeometryModel = (
  outSize: number,
  phase: GeometryPhase,
  viewport: OverlayViewport,
): GeometryOverlayModel => {
  const last = outSize - 1;
  const points = Array.from({ length: 19 }, (_, row) =>
    Array.from({ length: 19 }, (_, col) => [col * last / 18, row * last / 18] as [number, number]),
  );
  const corners: GeometryCorner[] = [
    { row: 0, col: 0, label: 'A19', x: 0, y: 0 },
    { row: 0, col: 18, label: 'T19', x: last, y: 0 },
    { row: 18, col: 18, label: 'T1', x: last, y: last },
    { row: 18, col: 0, label: 'A1', x: 0, y: last },
  ];
  return gridModel(
    points,
    corners,
    { width: outSize, height: outSize },
    viewport,
    phase === 'degraded' ? 'stale' : 'normal',
  );
};
