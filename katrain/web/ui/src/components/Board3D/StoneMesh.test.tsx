import { render } from '@testing-library/react';
import { MeshPhysicalMaterial, Texture } from 'three';
import { expect, it, vi } from 'vitest';
import StoneMesh from './StoneMesh';
import { createStoneMaterial } from '../tutorials/stoneModel';

vi.mock('../tutorials/stoneModel', async (importOriginal) => ({
  ...await importOriginal<typeof import('../tutorials/stoneModel')>(),
  createStoneGeometry: vi.fn(() => null),
  createStoneMaterial: vi.fn(() => new MeshPhysicalMaterial()),
}));

it('keeps the coordinate angle and eight procedural seeds on actual 3D stones', () => {
  const { container } = render(<StoneMesh color="W" position={[1, 2, 3]} variant={31} angle={1.2} />);
  expect(createStoneMaterial).toHaveBeenCalledWith('W', 7, false, 256);
  expect(container.querySelector('mesh')).toHaveAttribute('rotation', '0,-1.2,0');
});

it('lays recording sprites flat without applying the 3D stone angle', () => {
  const { container } = render(<StoneMesh color="W" position={[1, 2, 3]} spriteTexture={new Texture()} angle={1.2} />);
  expect(container.querySelector('mesh')).toHaveAttribute('rotation', `${-Math.PI / 2},0,0`);
});
