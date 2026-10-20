import { render } from '@testing-library/react';
import { Texture } from 'three';
import { afterEach, expect, it, vi } from 'vitest';
import type { GameState } from '../../api';
import { stoneVariant, TUTORIAL_STONE_DIAMETER_RATIO } from '../tutorials/tutorialStoneSprites';
import StoneGroup from './StoneGroup';
import StoneMesh from './StoneMesh';
import { gridToWorld } from './constants';

vi.mock('@react-three/fiber', () => ({ useFrame: () => {} }));
vi.mock('./StoneMesh', () => ({ default: vi.fn(() => null) }));
afterEach(() => vi.clearAllMocks());

it('maps game Y back to full-board top-left coordinates once and keeps texture through replay order changes', () => {
  const sprites = { B: new Texture(), W: Array.from({ length: 32 }, () => new Texture()) };
  const gameState = { board_size: [19, 19], current_node_index: 1, last_move: null,
    stones: [['W', [15, 4]], ['B', [14, 16]]],
  } as unknown as GameState;
  const { rerender } = render(<StoneGroup gameState={gameState} recordingStoneSprites={sprites} recordingVisualSeed="1030" />);
  const whiteTexture = sprites.W[stoneVariant('1030', 15, 14)];
  expect(vi.mocked(StoneMesh).mock.calls[0][0]).toMatchObject({ color: 'W', spriteTexture: whiteTexture, diameterRatio: 1 });
  expect(vi.mocked(StoneMesh).mock.calls[1][0]).toMatchObject({ color: 'B', spriteTexture: sprites.B, diameterRatio: TUTORIAL_STONE_DIAMETER_RATIO.B });
  vi.mocked(StoneMesh).mockClear();
  rerender(<StoneGroup gameState={{ ...gameState, current_node_index: 0, stones: [...gameState.stones].reverse() }} recordingStoneSprites={sprites} recordingVisualSeed="1030" />);
  expect(vi.mocked(StoneMesh).mock.calls.find(([props]) => props.color === 'W')?.[0].spriteTexture).toBe(whiteTexture);
  vi.mocked(StoneMesh).mockClear();
  rerender(<StoneGroup gameState={gameState} />);
  expect(vi.mocked(StoneMesh).mock.calls.every(([props]) => props.spriteTexture === undefined && props.diameterRatio === 1)).toBe(true);
});

it('applies all grouped recorder poses and keeps existing single-pose callers compatible', () => {
  const gameState = { board_size: [9, 9], current_node_index: 1, last_move: null,
    stones: [['B', [2, 8]], ['W', [3, 8]], ['B', [8, 0]]],
  } as unknown as GameState;
  const poses = [{ point: [2, 8] as [number, number], lift: .25, scale: .96 }, { point: [3, 8] as [number, number], lift: .25, scale: .96 }];
  const { rerender } = render(<StoneGroup gameState={gameState} recordingPlacement={poses} />);
  expect(vi.mocked(StoneMesh).mock.calls.slice(-3).map(([props]) => props.scale)).toEqual([.96, .96, 1]);
  expect(vi.mocked(StoneMesh).mock.calls.slice(-3).map(([props]) => props.position[1])).toEqual([gridToWorld(2, 8, 9)[1] + .25, gridToWorld(3, 8, 9)[1] + .25, gridToWorld(8, 0, 9)[1]]);
  vi.mocked(StoneMesh).mockClear();
  rerender(<StoneGroup gameState={gameState} recordingPlacement={poses[0]} />);
  expect(vi.mocked(StoneMesh).mock.calls.map(([props]) => props.scale)).toEqual([.96, 1, 1]);
  vi.mocked(StoneMesh).mockClear();
  rerender(<StoneGroup gameState={{ ...gameState, current_node_index: 2 }} recordingPlacement={[]} />);
  expect(vi.mocked(StoneMesh).mock.calls.map(([props]) => props.scale)).toEqual([1, 1, 1]);
});
