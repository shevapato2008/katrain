import { describe, expect, it } from 'vitest';
import type { GeometryAnchor, GeometryLayout } from '../../../api/geometryApi';
import {
  buildAnchorGeometryModel,
  buildRawGeometryModel,
  buildWarpedGeometryModel,
  fitContain,
} from './geometryOverlay';

const points = Array.from({ length: 19 }, (_, row) =>
  Array.from({ length: 19 }, (_, col) => [col * (1920 / 18), row * (1080 / 18)] as [number, number]),
);

const layout: GeometryLayout = {
  revision: 1,
  phase: 'ready',
  stale: false,
  frame: { width: 1920, height: 1080 },
  out_size: 950,
  corners: [
    { row: 0, col: 0, label: '左上', x: 0, y: 0 },
    { row: 0, col: 18, label: '右上', x: 1920, y: 0 },
    { row: 18, col: 18, label: '右下', x: 1920, y: 1080 },
    { row: 18, col: 0, label: '左下', x: 0, y: 1080 },
  ],
  points,
};

describe('geometry overlay model', () => {
  it('fits the source inside the viewport while preserving letterbox offsets', () => {
    expect(fitContain(1000, 600, 1920, 1080)).toEqual({
      scale: 1000 / 1920,
      offsetX: 0,
      offsetY: 18.75,
    });
  });

  it('builds the complete raw-camera grid in seated-human orientation', () => {
    const model = buildRawGeometryModel(layout, 'ready', { width: 1000, height: 600 });

    expect(model.tone).toBe('normal');
    expect(model.lines).toHaveLength(38);
    expect(model.points).toHaveLength(361);
    expect(model.corners.map((corner) => corner.label)).toEqual(['左上', '右上', '右下', '左下']);
    expect(model.starPoints).toHaveLength(9);
  });

  it('marks retained geometry as stale after displacement', () => {
    expect(buildRawGeometryModel(layout, 'degraded', { width: 1000, height: 600 }).tone).toBe('stale');
  });

  it('shows only anchors while calibration is active', () => {
    const anchors: GeometryAnchor[] = [
      { row: 0, col: 0, x: 100, y: 200, color: 'green' },
      { row: 0, col: 18, x: 800, y: 220, color: 'red' },
    ];

    const model = buildAnchorGeometryModel(anchors, layout.frame, { width: 1000, height: 600 });

    expect(model.tone).toBe('partial');
    expect(model.anchors).toHaveLength(2);
    expect(model.lines).toHaveLength(0);
    expect(model.points).toHaveLength(0);
  });

  it('builds a complete evenly-spaced grid for the warped preview', () => {
    const model = buildWarpedGeometryModel(950, 'ready', { width: 500, height: 400 });

    expect(model.lines).toHaveLength(38);
    expect(model.points).toHaveLength(361);
    expect(model.starPoints).toHaveLength(9);
    expect(model.corners.map((corner) => corner.label)).toEqual(['A19', 'T19', 'T1', 'A1']);
  });
});
