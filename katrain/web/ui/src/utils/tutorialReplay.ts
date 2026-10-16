/** Tutorial coordinates are zero-based, from the top-left of the full board. */
export type Point = [number, number];
export type StoneColor = 'B' | 'W';

export interface SourceRegion {
  col: number;
  row: number;
  cols: number;
  rows: number;
  confirmed: boolean;
}

export interface UnknownStone {
  point: Point;
  color: null;
  evidence?: string;
}

interface DiagramPayload {
  size: number;
  stones: { B: Point[]; W: Point[] };
  labels?: Record<string, string>;
  letters?: Record<string, string>;
  shapes?: Record<string, string>;
  highlights?: Point[];
  viewport?: { col: number; row: number; size?: number; cols?: number; rows?: number } | null;
}

export interface ReplayMove {
  kind: 'move' | 'pass';
  color: StoneColor | null;
  point: Point | null;
  printed_number: string | null;
}

export interface ReplayInitial {
  stones: { B: Point[]; W: Point[] };
  unknown_stones: UnknownStone[];
  labels?: Record<string, string>;
  letters?: Record<string, string>;
  shapes?: Record<string, string>;
  known_region: Omit<SourceRegion, 'confirmed'> | null;
  to_play: StoneColor | null;
}

export interface ReplayEvidence {
  kind: 'source' | 'linked_record';
  source_pointer: string;
  description: string;
  reference_sha256?: string | null;
}

export interface DiagramV2 extends DiagramPayload {
  schema_version: 2;
  unknown_stones: UnknownStone[];
  source_region: SourceRegion | null;
  replay: {
    status: 'complete' | 'needs_calibration';
    initial: ReplayInitial | null;
    moves: ReplayMove[];
    evidence?: ReplayEvidence | null;
  } | null;
}

export interface ReplayFrame {
  step: number;
  payload: DiagramPayload & { unknown_stones: UnknownStone[] };
  captured: Point[];
  last: Point | null;
  currentMove: ReplayMove | null;
  nextColor: StoneColor | null;
}

export interface ReplayResult {
  status: 'complete' | 'needs_calibration';
  issues: string[];
  frames: ReplayFrame[];
  totalSteps: number;
}

type TutorialDiagram = DiagramPayload & Partial<Pick<DiagramV2, 'schema_version' | 'unknown_stones' | 'source_region' | 'replay'>>;

type KnownRegion = ReplayInitial['known_region'];
type Board = Map<string, StoneColor>;
const pointKey = ([col, row]: Point) => `${col},${row}`;
const fromKey = (key: string): Point => key.split(',').map(Number) as Point;
const opposite = (color: StoneColor): StoneColor => color === 'B' ? 'W' : 'B';
const copyPoint = (point: Point): Point => [point[0], point[1]];

function inBounds(point: Point, size: number): boolean {
  return Array.isArray(point) && point.length === 2 && point.every(value => Number.isInteger(value) && value >= 0 && value < size);
}

function validRegion(region: KnownRegion, size: number): boolean {
  return !!region && [region.col, region.row, region.cols, region.rows].every(Number.isInteger)
    && region.col >= 0 && region.row >= 0 && region.cols > 0 && region.rows > 0
    && region.col + region.cols <= size && region.row + region.rows <= size;
}

function inRegion([col, row]: Point, region: KnownRegion): boolean {
  return !!region && col >= region.col && col < region.col + region.cols
    && row >= region.row && row < region.row + region.rows;
}

function copyPayload(payload: DiagramPayload, unknown: UnknownStone[] = []): ReplayFrame['payload'] {
  return {
    size: payload.size,
    stones: { B: payload.stones.B.map(copyPoint), W: payload.stones.W.map(copyPoint) },
    labels: { ...payload.labels }, letters: { ...payload.letters }, shapes: { ...payload.shapes },
    highlights: payload.highlights?.map(copyPoint),
    viewport: payload.viewport ? { ...payload.viewport } : payload.viewport,
    unknown_stones: unknown.map(stone => ({ ...stone, point: copyPoint(stone.point) })),
  };
}

function readStones(stones: DiagramPayload['stones'], size: number, issues: string[], scope: string): Board {
  const board: Board = new Map();
  for (const color of ['B', 'W'] as const) {
    const points = stones?.[color];
    if (!Array.isArray(points)) { issues.push(`${scope}: ${color} stone list is missing or invalid.`); continue; }
    for (const point of points) {
      if (!inBounds(point, size)) issues.push(`${scope}: stone is out of bounds.`);
      else if (board.has(pointKey(point))) issues.push(`${scope}: duplicate occupied point.`);
      else board.set(pointKey(point), color);
    }
  }
  return board;
}

function readUnknown(stones: UnknownStone[], board: Board, size: number, issues: string[], scope: string): Set<string> {
  const unknown = new Set<string>();
  for (const stone of stones) {
    const key = pointKey(stone.point);
    if (!inBounds(stone.point, size)) issues.push(`${scope}: unknown stone is out of bounds.`);
    else if (stone.color !== null || board.has(key) || unknown.has(key)) issues.push(`${scope}: unknown stone conflicts with a known point.`);
    else unknown.add(key);
  }
  return unknown;
}

// Adapted from katrain/web/ui/src/components/live/LiveBoard.tsx:
// getNeighbors, findGroup, countLiberties, removeCaptures. A missing map entry is
// empty only inside known_region; outside it, or at an unknown stone, it is unknown.
function getNeighbors(x: number, y: number, size: number): Point[] {
  const neighbors: Point[] = [];
  if (x > 0) neighbors.push([x - 1, y]);
  if (x < size - 1) neighbors.push([x + 1, y]);
  if (y > 0) neighbors.push([x, y - 1]);
  if (y < size - 1) neighbors.push([x, y + 1]);
  return neighbors;
}

function findGroup(board: Board, x: number, y: number, size: number): Set<string> {
  const color = board.get(pointKey([x, y]));
  const group = new Set<string>();
  if (!color) return group;
  const stack: Point[] = [[x, y]];
  while (stack.length > 0) {
    const [cx, cy] = stack.pop()!;
    const key = pointKey([cx, cy]);
    if (group.has(key) || board.get(key) !== color) continue;
    group.add(key);
    for (const neighbor of getNeighbors(cx, cy, size)) {
      if (!group.has(pointKey(neighbor)) && board.get(pointKey(neighbor)) === color) stack.push(neighbor);
    }
  }
  return group;
}

function countLiberties(board: Board, group: Set<string>, size: number, region: KnownRegion, unknown: Set<string>) {
  const liberties = new Set<string>();
  let hasUnknownNeighbor = false;
  for (const key of group) {
    const [x, y] = fromKey(key);
    for (const neighbor of getNeighbors(x, y, size)) {
      const neighborKey = pointKey(neighbor);
      if (board.has(neighborKey)) continue;
      if (inRegion(neighbor, region) && !unknown.has(neighborKey)) liberties.add(neighborKey);
      else hasUnknownNeighbor = true;
    }
  }
  return { known: liberties.size, hasUnknownNeighbor };
}

function removeCaptures(board: Board, point: Point, size: number, region: KnownRegion, unknown: Set<string>) {
  const captured: Point[] = [];
  const checkedGroups = new Set<string>();
  const opponent = opposite(board.get(pointKey(point))!);
  for (const [nx, ny] of getNeighbors(...point, size)) {
    const key = pointKey([nx, ny]);
    if (board.get(key) !== opponent || checkedGroups.has(key)) continue;
    const group = findGroup(board, nx, ny, size);
    for (const groupKey of group) checkedGroups.add(groupKey);
    const liberties = countLiberties(board, group, size, region, unknown);
    if (liberties.known > 0) continue;
    if (liberties.hasUnknownNeighbor) return { captured, uncertain: true };
    for (const groupKey of group) {
      board.delete(groupKey);
      captured.push(fromKey(groupKey));
    }
  }
  return { captured, uncertain: false };
}

function boardSignature(board: Board): string {
  return [...board].map(([key, color]) => `${key}:${color}`).sort().join(';');
}

/** Build detached snapshots from explicit initial state and moves, never final labels. */
export function buildTutorialReplay(diagram: TutorialDiagram): ReplayResult {
  const issues: string[] = [];
  const replay = diagram.replay;
  const totalSteps = replay?.moves.length ?? 0;
  const result = (frames: ReplayFrame[]): ReplayResult => ({
    status: issues.length ? 'needs_calibration' : 'complete', issues, frames, totalSteps,
  });
  const staticFrame = (): ReplayFrame => ({
    step: 0, payload: copyPayload(diagram, diagram.unknown_stones), captured: [],
    last: null, currentMove: null, nextColor: null,
  });
  if (!Number.isInteger(diagram.size) || diagram.size <= 0) {
    issues.push('Board size must be a positive integer.');
    return result([staticFrame()]);
  }
  const finalBoard = readStones(diagram.stones, diagram.size, issues, 'Static diagram');
  readUnknown(diagram.unknown_stones ?? [], finalBoard, diagram.size, issues, 'Static diagram');
  if (diagram.unknown_stones?.length) issues.push('Static diagram contains unknown stones.');
  if (!replay) {
    issues.push('Explicit replay initial state and moves are required.');
    return result([staticFrame()]);
  }
  if (diagram.schema_version !== 2) issues.push('Replay requires schema version 2.');
  if (replay.status !== 'complete') issues.push('Replay has not been explicitly declared complete.');
  if (totalSteps === 0) issues.push('A static final position with zero moves is not a replay.');
  const evidence = replay.evidence;
  if (!evidence || !['source', 'linked_record'].includes(evidence.kind)
    || typeof evidence.source_pointer !== 'string' || !evidence.source_pointer.trim()
    || typeof evidence.description !== 'string' || !evidence.description.trim()) {
    issues.push('Source evidence for initial state and ordered moves is required.');
  }
  if (evidence?.kind === 'linked_record'
    && (typeof evidence.reference_sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(evidence.reference_sha256))) {
    issues.push('Linked record evidence requires its immutable SHA256.');
  }
  const source = diagram.source_region;
  const confirmedSource = source?.confirmed && validRegion(source, diagram.size) ? source : null;
  if (!confirmedSource) issues.push('A confirmed source region is required.');
  const initial = replay.initial;
  if (!initial) {
    issues.push('A known initial state is required.');
    return result([staticFrame()]);
  }
  const beforeInitial = issues.length;
  let board = readStones(initial.stones, diagram.size, issues, 'Initial state');
  const unknown = readUnknown(initial.unknown_stones, board, diagram.size, issues, 'Initial state');
  let invalidInitial = issues.length > beforeInitial;
  if (initial.unknown_stones.length) issues.push('Initial state contains unknown stones.');
  const knownRegion = validRegion(initial.known_region, diagram.size) ? initial.known_region : null;
  if (!knownRegion) issues.push('Initial known_region must explicitly declare the known empty extent.');
  if (knownRegion) {
    const checked = new Set<string>();
    for (const [coordinate] of board) {
      if (checked.has(coordinate)) continue;
      const group = findGroup(board, ...fromKey(coordinate), diagram.size);
      for (const member of group) checked.add(member);
      const liberties = countLiberties(board, group, diagram.size, knownRegion, unknown);
      if (liberties.known === 0 && !liberties.hasUnknownNeighbor) {
        issues.push('Initial state: a fully known group has no liberties.');
        invalidInitial = true;
      }
    }
  }
  let nextColor = initial.to_play;
  if (nextColor !== 'B' && nextColor !== 'W') {
    nextColor = null;
    issues.push('Initial to_play must explicitly declare B or W.');
  }
  let labels = { ...initial.labels };
  const snapshot = (step: number, move: ReplayMove | null, captured: Point[]): ReplayFrame => {
    const stones: DiagramPayload['stones'] = { B: [], W: [] };
    for (const [key, color] of board) stones[color].push(fromKey(key));
    return {
      step,
      payload: copyPayload({ size: diagram.size, stones, labels, letters: initial.letters, shapes: initial.shapes, viewport: diagram.viewport }, initial.unknown_stones),
      captured: captured.map(copyPoint),
      last: move?.kind === 'move' && move.point ? copyPoint(move.point) : null,
      currentMove: move ? { ...move, point: move.point ? copyPoint(move.point) : null } : null,
      nextColor,
    };
  };
  const frames = [snapshot(0, null, [])];
  if (invalidInitial || !nextColor) return result(frames);
  const signatures = [boardSignature(board)];
  for (const [index, move] of replay.moves.entries()) {
    const step = index + 1;
    const fail = (message: string) => issues.push(`Step ${step}: ${message}`);
    if (move.color !== 'B' && move.color !== 'W') { fail('explicit color is required.'); break; }
    if (move.color !== nextColor) { fail('color alternation does not match to_play.'); break; }
    let captured: Point[] = [];
    if (move.kind === 'pass') {
      if (move.point !== null) { fail('a pass must have a null point.'); break; }
    } else if (move.kind === 'move') {
      if (!move.point) { fail('a move needs a point; a draft null point is not a pass.'); break; }
      if (!inBounds(move.point, diagram.size)) { fail('point is out of bounds.'); break; }
      const key = pointKey(move.point);
      if (board.has(key)) { fail('point is occupied.'); break; }
      if (!inRegion(move.point, knownRegion) || unknown.has(key)) { fail('point occupancy is unknown.'); break; }
      const candidate = new Map(board);
      candidate.set(key, move.color);
      const capture = removeCaptures(candidate, move.point, diagram.size, knownRegion, unknown);
      if (capture.uncertain) { fail('capture depends on unknown neighboring points.'); break; }
      captured = capture.captured;
      const ownLiberties = countLiberties(candidate, findGroup(candidate, ...move.point, diagram.size), diagram.size, knownRegion, unknown);
      if (ownLiberties.known === 0) {
        fail(ownLiberties.hasUnknownNeighbor ? 'own group survival depends on unknown neighboring points.' : 'suicide is not legal.');
        break;
      }
      if (signatures.length >= 2 && boardSignature(candidate) === signatures[signatures.length - 2]) {
        fail('simple ko recapture is not legal.'); break;
      }
      board = candidate;
      labels = { ...labels };
      for (const point of captured) delete labels[pointKey(point)];
      if (move.printed_number !== null) labels[key] = move.printed_number;
      else delete labels[key];
    } else { fail('move kind must be move or pass.'); break; }
    nextColor = opposite(move.color);
    frames.push(snapshot(step, move, captured));
    signatures.push(boardSignature(board));
  }
  if (frames.length === totalSteps + 1 && confirmedSource) {
    let matches = true;
    for (let row = confirmedSource.row; row < confirmedSource.row + confirmedSource.rows; row++) {
      for (let col = confirmedSource.col; col < confirmedSource.col + confirmedSource.cols; col++) {
        const key = pointKey([col, row]);
        // Unknown empty extent cannot establish final occupancy either.
        if (!board.has(key) && (!inRegion([col, row], knownRegion) || unknown.has(key))) matches = false;
        if (board.get(key) !== finalBoard.get(key)) matches = false;
      }
    }
    if (!matches) issues.push('Replay final occupancy does not match the known static source region.');
  }
  return result(frames);
}

export function validateTutorialReplay(diagram: TutorialDiagram): Pick<ReplayResult, 'status' | 'issues'> {
  const { status, issues } = buildTutorialReplay(diagram);
  return { status, issues };
}
