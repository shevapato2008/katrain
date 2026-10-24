export type OgsStone = 'B' | 'W';
export type OgsPoint = [number, number];
export type OgsBoard = (OgsStone | null)[][];

export interface OgsTreeNode {
  point: OgsPoint | null;
  correct: boolean;
  wrong: boolean;
  children: OgsTreeNode[];
}

export type OgsExercise =
  | { kind: 'puzzle'; tree: OgsTreeNode }
  | { kind: 'choice'; choices: { value: string; label_key: string }[]; correct_choice: string }
  | { kind: 'remove'; remove_targets: OgsPoint[] }
  | { kind: 'pass' }
  | { kind: 'finish' };

export interface OgsExerciseStep {
  size: number;
  initial_player: OgsStone;
  stones: { B: OgsPoint[]; W: OgsPoint[] };
  exercise: OgsExercise;
}

export interface OgsMoveRecord {
  point: OgsPoint;
  player: OgsStone;
  captured: OgsPoint[];
}

export interface OgsExerciseState {
  step: OgsExerciseStep;
  board: OgsBoard;
  player: OgsStone;
  treeCursor: OgsTreeNode | null;
  status: 'active' | 'correct' | 'wrong';
  selectedRemoval: OgsPoint[];
  previousBoard: OgsBoard | null;
  /** The most recent legal learner move and its source-tree reply, if any. */
  lastTransition: { playerMove: OgsMoveRecord; automaticResponses: OgsMoveRecord[] } | null;
}

const other = (stone: OgsStone): OgsStone => stone === 'B' ? 'W' : 'B';
const onBoard = (board: OgsBoard, [x, y]: OgsPoint): boolean =>
  Number.isInteger(x) && Number.isInteger(y) && y >= 0 && y < board.length && x >= 0 && x < board[y].length;
const neighbors = ([x, y]: OgsPoint): OgsPoint[] => [[x - 1, y], [x + 1, y], [x, y - 1], [x, y + 1]];
const pointKey = ([x, y]: OgsPoint): string => `${x},${y}`;
const samePoint = (a: OgsPoint | null, b: OgsPoint): boolean => a?.[0] === b[0] && a?.[1] === b[1];

function groupAt(board: OgsBoard, point: OgsPoint): { stones: OgsPoint[]; hasLiberty: boolean } {
  const color = board[point[1]][point[0]];
  if (!color) return { stones: [], hasLiberty: false };
  const seen = new Set<string>([pointKey(point)]);
  const stones: OgsPoint[] = [point];
  let hasLiberty = false;
  for (let i = 0; i < stones.length; i += 1) {
    for (const neighbor of neighbors(stones[i])) {
      if (!onBoard(board, neighbor)) continue;
      const value = board[neighbor[1]][neighbor[0]];
      if (value === null) hasLiberty = true;
      else if (value === color && !seen.has(pointKey(neighbor))) {
        seen.add(pointKey(neighbor));
        stones.push(neighbor);
      }
    }
  }
  return { stones, hasLiberty };
}

function boardsEqual(a: OgsBoard, b: OgsBoard): boolean {
  return a.length === b.length && a.every((row, y) => row.length === b[y].length && row.every((stone, x) => stone === b[y][x]));
}

function moveRecord(before: OgsBoard, after: OgsBoard, point: OgsPoint, player: OgsStone): OgsMoveRecord {
  const captured: OgsPoint[] = [];
  for (let y = 0; y < before.length; y += 1) {
    for (let x = 0; x < before[y].length; x += 1) {
      if (before[y][x] === other(player) && after[y][x] === null) captured.push([x, y]);
    }
  }
  return { point, player, captured };
}

function hasCorrectContinuation(node: OgsTreeNode): boolean {
  return node.correct || node.children.some(hasCorrectContinuation);
}

export function createOgsExercise(step: OgsExerciseStep): OgsExerciseState {
  const board: OgsBoard = Array.from({ length: step.size }, () => Array<OgsStone | null>(step.size).fill(null));
  for (const stone of ['B', 'W'] as const) {
    for (const [x, y] of step.stones[stone]) {
      if (onBoard(board, [x, y])) board[y][x] = stone;
    }
  }
  return {
    step,
    board,
    player: step.initial_player,
    treeCursor: step.exercise.kind === 'puzzle' ? step.exercise.tree : null,
    status: 'active',
    selectedRemoval: [],
    previousBoard: null,
    lastTransition: null,
  };
}

/** Returns a fresh board, or null for occupied, off-board, suicide, or immediate ko. */
export function applyGoMove(board: OgsBoard, point: OgsPoint, player: OgsStone, previousBoard?: OgsBoard | null): OgsBoard | null {
  if (!onBoard(board, point) || board[point[1]][point[0]] !== null) return null;
  const next = board.map((row) => [...row]);
  next[point[1]][point[0]] = player;
  for (const neighbor of neighbors(point)) {
    if (!onBoard(next, neighbor) || next[neighbor[1]][neighbor[0]] !== other(player)) continue;
    const group = groupAt(next, neighbor);
    if (!group.hasLiberty) {
      for (const [x, y] of group.stones) next[y][x] = null;
    }
  }
  if (!groupAt(next, point).hasLiberty || (previousBoard && boardsEqual(next, previousBoard))) return null;
  return next;
}

/** Board clicks answer puzzles and remove exercises. Other kinds ignore them. */
export function playOgsPoint(state: OgsExerciseState, point: OgsPoint): OgsExerciseState {
  if (state.status !== 'active' || !onBoard(state.board, point)) return state;
  if (state.step.exercise.kind === 'remove') {
    if (!state.board[point[1]][point[0]]) return state;
    const group = groupAt(state.board, point).stones.sort(([ax, ay], [bx, by]) => ax - bx || ay - by);
    const toggled = new Set(group.map(pointKey));
    const selectedRemoval = state.selectedRemoval.some((selected) => toggled.has(pointKey(selected)))
      ? state.selectedRemoval.filter((selected) => !toggled.has(pointKey(selected)))
      : [...state.selectedRemoval, ...group];
    const selected = new Set(selectedRemoval.map(pointKey));
    const targets = state.step.exercise.remove_targets;
    const correct = selected.size === targets.length && targets.every((target) => selected.has(pointKey(target)));
    return { ...state, selectedRemoval, status: correct ? 'correct' : 'active' };
  }
  if (state.step.exercise.kind !== 'puzzle') return state;
  const afterMove = applyGoMove(state.board, point, state.player, state.previousBoard);
  if (!afterMove) return state;

  const child = state.treeCursor?.children.find((candidate) => samePoint(candidate.point, point));
  const playerMove = moveRecord(state.board, afterMove, point, state.player);
  let next: OgsExerciseState = {
    ...state,
    board: afterMove,
    previousBoard: state.board,
    player: other(state.player),
    treeCursor: child ?? state.treeCursor,
    status: child?.correct ? 'correct' : child?.wrong || !child ? 'wrong' : 'active',
    lastTransition: { playerMove, automaticResponses: [] },
  };
  if (next.status !== 'active' || !child?.children.length) return next;

  // One opponent reply follows each player move. Prefer a source reply that can
  // still lead to success; some imported trees list a failing reply first.
  const solvable = child.children.filter(hasCorrectContinuation);
  const replies = [...solvable, ...child.children.filter((reply) => !hasCorrectContinuation(reply))];
  for (const reply of replies) {
    if (!reply.point) continue;
    const afterReply = applyGoMove(next.board, reply.point, next.player, next.previousBoard);
    if (!afterReply) continue;
    const response = moveRecord(next.board, afterReply, reply.point, next.player);
    next = {
      ...next,
      board: afterReply,
      previousBoard: next.board,
      player: other(next.player),
      treeCursor: reply,
      status: reply.correct ? 'correct' : reply.wrong ? 'wrong' : 'active',
      lastTransition: { playerMove, automaticResponses: [response] },
    };
    break;
  }
  return next;
}

export function chooseOgsAnswer(state: OgsExerciseState, value: string): OgsExerciseState {
  const exercise = state.step.exercise;
  if (state.status !== 'active' || exercise.kind !== 'choice' || !exercise.choices.some((choice) => choice.value === value)) return state;
  return { ...state, status: value === exercise.correct_choice ? 'correct' : 'wrong' };
}

export function actOgsExercise(state: OgsExerciseState, action: 'pass' | 'finish'): OgsExerciseState {
  if (state.status !== 'active' || state.step.exercise.kind !== action) return state;
  return { ...state, status: 'correct' };
}

export function retryOgsExercise(state: OgsExerciseState): OgsExerciseState {
  return createOgsExercise(state.step);
}
