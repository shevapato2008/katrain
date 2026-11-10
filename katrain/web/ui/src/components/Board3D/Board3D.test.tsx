import { act, render } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  setActiveBoardStyle,
  setActiveStoneStyle,
} from '../board/stoneAppearance';
import { createStoneMaterial } from '../tutorials/stoneModel';
import BoardMesh from './BoardMesh';
import StoneMesh from './StoneMesh';

describe('3D Board & Stone Reactive Appearance Synchronization', () => {
  afterEach(() => {
    setActiveBoardStyle('kaya');
    setActiveStoneStyle('clamshell-slate');
    vi.restoreAllMocks();
  });

  it('caches 3D procedural textures modulo 8 variants across all 4 stone styles (M-4)', () => {
    const jade0 = createStoneMaterial('W', 0, false, 128, 'jade-agate');
    const jade8 = createStoneMaterial('W', 8, false, 128, 'jade-agate');
    const jade1 = createStoneMaterial('W', 1, false, 128, 'jade-agate');
    expect(jade0.map).toBeDefined();
    expect(jade0.map).toBe(jade8.map);
    expect(jade0.map).not.toBe(jade1.map);
    expect(jade0.transmission).toBeCloseTo(0.52);
    expect(jade0.ior).toBeCloseTo(1.544);
    expect(jade0.clearcoat).toBeCloseTo(0.98);

    const jadeBlack = createStoneMaterial('B', 0, false, 128, 'jade-agate');
    expect(jadeBlack.clearcoat).toBeCloseTo(1.0);
    expect(jadeBlack.roughness).toBeCloseTo(0.06);

    const yunziW0 = createStoneMaterial('W', 2, false, 128, 'yunzi');
    const yunziW10 = createStoneMaterial('W', 10, false, 128, 'yunzi');
    expect(yunziW0.map).toBe(yunziW10.map);
    expect(yunziW0.transmission).toBeCloseTo(0.14);

    const yunziB = createStoneMaterial('B', 0, false, 128, 'yunzi');
    expect(yunziB.sheen).toBeCloseTo(0.35);

    const minimalW = createStoneMaterial('W', 0, false, 128, 'minimal');
    const minimalB = createStoneMaterial('B', 0, false, 128, 'minimal');
    expect(minimalW.roughness).toBeCloseTo(0.78);
    expect(minimalW.clearcoat).toBe(0);
    expect(minimalB.roughness).toBeCloseTo(0.78);
  });

  it('reactively updates StoneMesh material when active stoneStyle changes (C-2)', () => {
    render(<StoneMesh color="W" position={[0, 0, 0]} variant={3} opacity={1} />);

    act(() => {
      setActiveStoneStyle('jade-agate');
    });
    act(() => {
      setActiveStoneStyle('yunzi');
    });
    act(() => {
      setActiveStoneStyle('minimal');
    });
  });

  it('disposes previous BoardMesh textures and materials when boardStyle changes (C-1)', () => {
    render(<BoardMesh boardSize={19} showCoordinates={false} />);

    act(() => {
      setActiveBoardStyle('shin-kaya');
    });
    act(() => {
      setActiveBoardStyle('bamboo');
    });
    act(() => {
      setActiveBoardStyle('walnut');
    });
  });
});
