import { useRef, useEffect, useState, memo } from 'react';
import { useFrame } from '@react-three/fiber';
import type { Mesh } from 'three';
import StoneMesh from './StoneMesh';
import { gridToWorld, DROP_HEIGHT, STONE_HEIGHT } from './constants';
import type { GameState } from '../../api';

interface StoneGroupProps {
  gameState: GameState;
  enableDropEffect?: boolean;
}

interface DropAnim {
  yOffset: number;
  velocity: number;
  scaleFactor: number;
  done: boolean;
  targetX: number;
  targetY: number;
  targetZ: number;
}

const StoneGroup = ({ gameState, enableDropEffect = false }: StoneGroupProps) => {
  const boardSize = gameState.board_size[0];
  const prevNodeIndexRef = useRef(gameState.current_node_index);
  const prevLastMoveRef = useRef<[number, number] | null>(gameState.last_move);
  const animRef = useRef<DropAnim | null>(null);
  const animMeshRef = useRef<Mesh>(null);
  const animInitialPosRef = useRef<[number, number, number] | null>(null);
  const [, setAnimTick] = useState(0);

  // Stabilize last_move as primitives to avoid re-firing on every WebSocket update
  // (gameState.last_move is a new array reference on each game_update message)
  const lastMoveX = gameState.last_move?.[0] ?? -1;
  const lastMoveY = gameState.last_move?.[1] ?? -1;

  // Detect new move vs navigation
  // Uses last_move comparison instead of stone count (captures reduce stone count)
  useEffect(() => {
    const prevLastMove = prevLastMoveRef.current;
    const currLastMove = gameState.last_move;
    const prevIndex = prevNodeIndexRef.current;
    const currIndex = gameState.current_node_index;

    const isNewMove =
      currIndex > prevIndex &&
      currLastMove != null &&
      (prevLastMove == null ||
        currLastMove[0] !== prevLastMove[0] ||
        currLastMove[1] !== prevLastMove[1]);

    if (isNewMove && currLastMove) {
      if (enableDropEffect) {
        const targetPos = gridToWorld(currLastMove[0], currLastMove[1], boardSize);
        animInitialPosRef.current = [targetPos[0], targetPos[1] + DROP_HEIGHT, targetPos[2]];
        animRef.current = {
          yOffset: DROP_HEIGHT,
          velocity: 0,
          scaleFactor: 0.5,
          done: false,
          targetX: targetPos[0],
          targetY: targetPos[1],
          targetZ: targetPos[2],
        };
        setAnimTick(n => n + 1);
      }
      // else: stone appears instantly (no animation)
    } else if (currIndex !== prevIndex) {
      // Navigation (undo/redo/jump) — cancel any in-progress animation
      animRef.current = null;
    }
    // Analysis-only updates (same position): leave animation alone

    prevNodeIndexRef.current = currIndex;
    prevLastMoveRef.current = currLastMove;
  }, [gameState.current_node_index, lastMoveX, lastMoveY, boardSize]);

  // Animate the drop each frame — directly mutates mesh ref (correct R3F pattern)
  useFrame((_, delta) => {
    const anim = animRef.current;
    const mesh = animMeshRef.current;
    if (!anim || anim.done) return;

    // Canvas was hidden (display:none) — complete animation instantly
    if (!mesh || delta > 0.5) {
      anim.yOffset = 0;
      anim.scaleFactor = 1;
      anim.done = true;
      if (mesh) {
        mesh.position.set(anim.targetX, anim.targetY, anim.targetZ);
        mesh.scale.set(1, STONE_HEIGHT / 0.42, 1);
      }
      setAnimTick(n => n + 1);
      return;
    }

    const dt = Math.min(delta, 0.05);
    anim.velocity += 40 * dt;
    anim.yOffset -= anim.velocity * dt;

    if (anim.scaleFactor < 1) {
      anim.scaleFactor = Math.min(1, anim.scaleFactor + dt * 3);
    }

    if (anim.yOffset <= 0) {
      anim.yOffset = 0;
      anim.scaleFactor = 1;
      anim.done = true;
      setAnimTick(n => n + 1); // trigger re-render to swap to static stone
    }

    // Directly mutate mesh transform (bypasses React render — correct for useFrame)
    mesh.position.set(anim.targetX, anim.targetY + anim.yOffset, anim.targetZ);
    const scaleY = (STONE_HEIGHT / 0.42) * anim.scaleFactor; // 0.42 = STONE_RADIUS
    mesh.scale.set(anim.scaleFactor, scaleY, anim.scaleFactor);
  });

  // Find the animating stone's coords (if any)
  const animCoords = !animRef.current?.done && gameState.last_move ? gameState.last_move : null;

  return (
    <group>
      {gameState.stones.map(([player, coords], index) => {
        if (!coords) return null;
        const [x, y] = coords;

        // Skip the animating stone — it's rendered separately with a mesh ref
        if (animCoords && x === animCoords[0] && y === animCoords[1] && !animRef.current?.done && animMeshRef.current) {
          return null;
        }

        const basePos = gridToWorld(x, y, boardSize);
        return (
          <StoneMesh
            key={`stone-${x}-${y}-${index}`}
            color={player as 'B' | 'W'}
            position={basePos}
          />
        );
      })}

      {/* Animating stone — uses mesh ref for direct useFrame mutation */}
      {animCoords && !animRef.current?.done && animInitialPosRef.current && (() => {
        const animStone = gameState.stones.find(
          s => s[1] && s[1][0] === animCoords[0] && s[1][1] === animCoords[1]
        );
        if (!animStone || !animStone[1]) return null;
        return (
          <StoneMesh
            key="animating-stone"
            ref={animMeshRef}
            color={animStone[0] as 'B' | 'W'}
            position={animInitialPosRef.current!}
            scale={0.5}
          />
        );
      })()}
    </group>
  );
};

export default memo(StoneGroup);
