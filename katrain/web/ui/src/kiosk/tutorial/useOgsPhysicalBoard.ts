import { useCallback, useMemo } from 'react';
import type { OgsStep } from '../../types/ogsCourse';
import type { OgsExerciseState, OgsPoint } from './ogsExercise';
import { useVision } from '../context/VisionContext';
import { useOptionalGeometry } from '../context/GeometryContext';
import { useVisionSync } from '../hooks/useVisionSync';
import { usePhysicalTsumego, type PhysicalTsumegoState } from '../hooks/usePhysicalTsumego';
import type { MoveResult, Stone } from '../../hooks/useTsumegoProblem';

function toStones(state: OgsExerciseState): Stone[] {
  return state.board.flatMap((row, y) => row.flatMap((player, x) => player ? [{ player, coords: [x, state.step.size - 1 - y] as [number, number] }] : []));
}
function toVisionBoard(state: OgsExerciseState): number[][] {
  return state.board.map((row) => row.map((stone) => stone === 'B' ? 1 : stone === 'W' ? 2 : 0));
}

interface Options {
  step: OgsStep | null;
  state: OgsExerciseState | null;
  enabled: boolean;
  revision: number;
  playPoint: (point: OgsPoint) => { next: OgsExerciseState; previous: OgsExerciseState } | null;
  undoWrong: () => void;
}

export function useOgsPhysicalBoard({ step, state, enabled, revision, playPoint, undoWrong }: Options) {
  const { visionStatus } = useVision();
  const geometry = useOptionalGeometry();
  const sync = useVisionSync(null);
  const isBoardPuzzle = step?.exercise.kind === 'puzzle';
  const geometryConfirmed = !geometry?.status || geometry.status.phase === 'disabled' ||
    (geometry.status.phase === 'ready' && geometry.status.session_calibrated && geometry.status.capabilities.geometry_ready);
  const calibrate = Boolean(step?.size === 19 && isBoardPuzzle && visionStatus.enabled && !geometryConfirmed);
  const available = Boolean(isBoardPuzzle && step?.size === 19 && visionStatus.enabled && visionStatus.recognitionReady && geometryConfirmed);
  const reason = !step ? '正在读取练习' : !isBoardPuzzle ? '本步骤请在屏幕完成' : step.size !== 19
    ? '实体盘当前支持 19 路练习' : !visionStatus.enabled ? '未检测到摄像头 / 视觉服务未启用'
      : !geometryConfirmed ? geometry?.status.phase === 'degraded' || geometry?.status.phase === 'failed'
        ? '棋盘标定已失效，请重新标定棋盘' : '物理棋盘需先确认棋盘标定'
        : !visionStatus.recognitionReady
        ? '正在连接摄像头与识别模型，请稍候…' : '';
  const active = enabled && available && !!state;
  const stones = useMemo(() => state ? toStones(state) : [], [state]);
  const placeStone = useCallback((x: number, bottomY: number): MoveResult | null => {
    if (!step) return null;
    const transition = playPoint([x, step.size - 1 - bottomY]);
    if (!transition) return null;
    return moveResult(transition.next, transition.previous, step.size);
  }, [playPoint, step]);
  const physical = usePhysicalTsumego({
    enabled: active,
    visionConnected: sync.connected,
    problemKey: step ? `${step.page}:${revision}` : null,
    resyncKey: 0,
    boardSize: 19,
    stones,
    isSolved: state?.status === 'correct',
    showHint: false,
    hintCoords: null,
    isTryMode: false,
    autoAdvance: false,
    syncEvents: sync.syncEvents,
    placeStone,
    undo: undoWrong,
    playMoveSound: () => {},
    onAdvance: () => {},
  });
  const onScreenMove = useCallback((next: OgsExerciseState, previous: OgsExerciseState) => {
    if (!active || physical.phase !== 'ready') return;
    physical.onScreenMove(moveResult(next, previous, step!.size), toVisionBoard(previous));
  }, [active, physical, step]);
  const extra = active ? physical.extra.map(([row, col]): OgsPoint => [col, 18 - row]) : [];
  return { available, reason, calibrate, active, physical, onScreenMove, extra };
}

function moveResult(next: OgsExerciseState, previous: OgsExerciseState, size: number): MoveResult | null {
  const transition = next.lastTransition;
  if (next === previous || !transition) return null;
  const reply = transition.automaticResponses.at(-1);
  const captured = transition.playerMove.captured.length + transition.automaticResponses.reduce((count, move) => count + move.captured.length, 0);
  return {
    type: next.status === 'wrong' ? 'incorrect' : next.status === 'correct' ? 'solved' : 'correct',
    captured,
    scheduledReply: reply ? { player: reply.player, coords: [reply.point[0], size - 1 - reply.point[1]] } : undefined,
  };
}

export type OgsPhysicalState = PhysicalTsumegoState;
