import { STONE_DIMENSIONS } from '../tutorials/stoneModel';
import { STONE_HEIGHT, STONE_RADIUS } from './constants';

/** The authored lathe has unit radius; static and animated stones share this scale. */
export function stoneMeshScale(color: 'B' | 'W', factor = 1): [number, number, number] {
  return [
    factor * STONE_RADIUS,
    factor * STONE_HEIGHT / (STONE_DIMENSIONS[color].thickness / STONE_DIMENSIONS.W.diameter),
    factor * STONE_RADIUS,
  ];
}
