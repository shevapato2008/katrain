/** Shared display replay. Setup stones are simultaneous placements, not turns. */
export function parseMove(move: string): [number, number] | null {
  if (!move || move.length < 2) return null;
  if (move.toLowerCase() === 'pass') return null;

  const col = move[0].toUpperCase();
  const row = parseInt(move.slice(1), 10);

  if (isNaN(row)) return null;

  // Column: A=0, B=1, ..., H=7, J=8 (skip I)
  let x = col.charCodeAt(0) - 'A'.charCodeAt(0);
  if (col > 'I') x -= 1;

  // Row: 1=bottom, 19=top → invert for array index
  const y = row - 1; // Now y=0 is bottom (row 1)

  if (x < 0 || x >= 19 || y < 0 || y >= 19) return null;

  return [x, y];
}

// Get adjacent positions (up, down, left, right)
function getNeighbors(x: number, y: number, size: number): [number, number][] {
  const neighbors: [number, number][] = [];
  if (x > 0) neighbors.push([x - 1, y]);
  if (x < size - 1) neighbors.push([x + 1, y]);
  if (y > 0) neighbors.push([x, y - 1]);
  if (y < size - 1) neighbors.push([x, y + 1]);
  return neighbors;
}

// Find all stones in a connected group starting from (x, y)
function findGroup(
  board: (string | null)[][],
  x: number,
  y: number,
  size: number
): Set<string> {
  const color = board[y][x];
  if (!color) return new Set();

  const group = new Set<string>();
  const stack: [number, number][] = [[x, y]];

  while (stack.length > 0) {
    const [cx, cy] = stack.pop()!;
    const key = `${cx},${cy}`;

    if (group.has(key)) continue;
    if (board[cy][cx] !== color) continue;

    group.add(key);

    for (const [nx, ny] of getNeighbors(cx, cy, size)) {
      if (!group.has(`${nx},${ny}`) && board[ny][nx] === color) {
        stack.push([nx, ny]);
      }
    }
  }

  return group;
}

// Count liberties (empty adjacent points) of a group
function countLiberties(
  board: (string | null)[][],
  group: Set<string>,
  size: number
): number {
  const liberties = new Set<string>();

  for (const key of group) {
    const [x, y] = key.split(',').map(Number);
    for (const [nx, ny] of getNeighbors(x, y, size)) {
      if (board[ny][nx] === null) {
        liberties.add(`${nx},${ny}`);
      }
    }
  }

  return liberties.size;
}

// Remove captured stones (groups with zero liberties)
// Returns array of captured positions for move number clearing
function removeCaptures(
  board: (string | null)[][],
  lastX: number,
  lastY: number,
  size: number
): [number, number][] {
  const captured: [number, number][] = [];
  const lastColor = board[lastY][lastX];
  if (!lastColor) return captured;

  const opponentColor = lastColor === 'B' ? 'W' : 'B';
  const checkedGroups = new Set<string>();

  // Check all neighbors of the last move for opponent groups
  for (const [nx, ny] of getNeighbors(lastX, lastY, size)) {
    if (board[ny][nx] === opponentColor) {
      const groupKey = `${nx},${ny}`;
      if (checkedGroups.has(groupKey)) continue;

      const group = findGroup(board, nx, ny, size);
      for (const key of group) {
        checkedGroups.add(key);
      }

      const liberties = countLiberties(board, group, size);
      if (liberties === 0) {
        // Remove captured stones
        for (const key of group) {
          const [gx, gy] = key.split(',').map(Number);
          board[gy][gx] = null;
          captured.push([gx, gy]);
        }
      }
    }
  }
  return captured;
}

export function buildReplayBoardState(moves: string[], currentMove: number, boardSize: number, stoneColors?: ('B' | 'W')[], handicapCount = 0) {
  const board: (string | null)[][] = Array.from({ length: boardSize }, () => Array(boardSize).fill(null));
  const moveNumbers: (number | null)[][] = Array.from({ length: boardSize }, () => Array(boardSize).fill(null));
  let lastMove: [number, number] | null = null;
  let lastPlayer: 'B' | 'W' = 'B';
  for (let i = 0; i < Math.min(currentMove, moves.length); i++) {
    const coords = parseMove(moves[i]);
    if (!coords) continue;
    const [x, y] = coords;
    if (x >= boardSize || y >= boardSize) continue;
    const player = stoneColors?.[i] ?? (i % 2 === 0 ? 'B' : 'W');
    board[y][x] = player;
    moveNumbers[y][x] = i < handicapCount ? null : i + 1 - handicapCount;
    const captured = i < handicapCount ? [] : removeCaptures(board, x, y, boardSize);
    for (const [cx, cy] of captured) moveNumbers[cy][cx] = null;
    if (i >= handicapCount) lastMove = coords;
    lastPlayer = player;
  }
  return { board, moveNumbers, lastMove, lastPlayer };
}

/** Explicit editing starts a new setup from the visible board, including captures. */
export function researchSetupAtCursor(moves: string[], stoneColors: ('B' | 'W')[], currentMove: number, size: number, setupCount: number) {
  const { board } = buildReplayBoardState(moves, currentMove, size, stoneColors, setupCount);
  const setupMoves: string[] = [];
  const setupColors: ('B' | 'W')[] = [];
  const columns = 'ABCDEFGHJKLMNOPQRSTUVWXYZ';
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const color = board[y][x];
    if (color === 'B' || color === 'W') { setupMoves.push(`${columns[x]}${y + 1}`); setupColors.push(color); }
  }
  return { moves: setupMoves, stoneColors: setupColors };
}

export function researchPlayerAtCursor(stoneColors: ('B' | 'W')[], currentMove: number, setupCount: number, initialPlayer: 'B' | 'W'): 'B' | 'W' {
  if (currentMove <= setupCount) return initialPlayer;
  return stoneColors[currentMove - 1] === 'B' ? 'W' : 'B';
}
