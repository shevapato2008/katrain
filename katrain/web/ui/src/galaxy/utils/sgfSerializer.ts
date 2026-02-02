/**
 * SGF Serializer: Converts moves[] ↔ SGF format for the Research module.
 *
 * Handles standard alternating moves and non-linear edits
 * (continuous same-color, handicap stones, etc).
 */

// ── Coordinate conversion ──

/** Convert board (x, y) to SGF coordinate pair, e.g. (0,0) → "aa", (3,15) → "dp" */
function toSgfCoord(x: number, y: number, boardSize: number): string {
  const col = String.fromCharCode(97 + x);          // a-s
  const row = String.fromCharCode(97 + (boardSize - 1 - y)); // SGF: a=top
  return col + row;
}

/** Convert display notation like "Q16" to (x, y) board coords */
function parseDisplayMove(move: string, boardSize: number): [number, number] | null {
  if (!move || move.toLowerCase() === 'pass') return null;
  const col = move[0].toUpperCase();
  const row = parseInt(move.slice(1), 10);
  if (isNaN(row)) return null;
  const letters = 'ABCDEFGHJKLMNOPQRSTUVWXYZ'; // skip I
  const x = letters.indexOf(col);
  if (x < 0 || x >= boardSize) return null;
  const y = row - 1;
  if (y < 0 || y >= boardSize) return null;
  return [x, y];
}

/** Convert SGF coord pair "dp" to (x, y) board coords */
function fromSgfCoord(sgf: string, boardSize: number): [number, number] | null {
  if (!sgf || sgf.length < 2) return null;
  const x = sgf.charCodeAt(0) - 97;
  const y = boardSize - 1 - (sgf.charCodeAt(1) - 97);
  if (x < 0 || x >= boardSize || y < 0 || y >= boardSize) return null;
  return [x, y];
}

/** Convert (x, y) to display notation like "Q16" */
function toDisplayMove(x: number, y: number): string {
  const letters = 'ABCDEFGHJKLMNOPQRSTUVWXYZ';
  return `${letters[x]}${y + 1}`;
}

// ── Core types ──

export interface SerializedSGF {
  sgf: string;
  moveCount: number;
}

export interface SGFMetadata {
  boardSize: number;
  komi: number;
  handicap: number;
  rules: string;
  playerBlack: string;
  playerWhite: string;
}

// ── Serialization: moves[] → SGF ──

/**
 * Serialize a moves array + metadata into a valid SGF string.
 *
 * For standard alternating play, generates ;B[xx];W[yy] nodes.
 * For continuous same-color play (place mode), uses AB[]/AW[] setup properties.
 * Handles passes as B[] / W[].
 */
export function movesToSGF(
  moves: string[],
  metadata: SGFMetadata,
  stoneColors?: ('B' | 'W')[],
): SerializedSGF {
  const { boardSize, komi, handicap, rules, playerBlack, playerWhite } = metadata;

  // Root node properties
  let root = `FF[4]GM[1]SZ[${boardSize}]KM[${komi}]RU[${rules}]`;
  if (playerBlack) root += `PB[${escapeSGF(playerBlack)}]`;
  if (playerWhite) root += `PW[${escapeSGF(playerWhite)}]`;
  if (handicap > 0) root += `HA[${handicap}]`;

  // Build move nodes
  const nodes: string[] = [];
  let moveCount = 0;

  for (let i = 0; i < moves.length; i++) {
    const move = moves[i];
    const player = stoneColors?.[i] ?? (i % 2 === 0 ? 'B' : 'W');

    if (move.toLowerCase() === 'pass') {
      nodes.push(`;${player}[]`);
      moveCount++;
    } else {
      const coords = parseDisplayMove(move, boardSize);
      if (coords) {
        const sgfCoord = toSgfCoord(coords[0], coords[1], boardSize);
        nodes.push(`;${player}[${sgfCoord}]`);
        moveCount++;
      }
    }
  }

  const sgf = `(;${root}${nodes.join('')})`;
  return { sgf, moveCount };
}

// ── Deserialization: SGF → moves[] ──

/**
 * Parse an SGF string and extract the main variation's moves as display notation.
 * Returns the moves array and metadata extracted from root properties.
 */
export function sgfToMoves(sgfContent: string): {
  moves: string[];
  stoneColors: ('B' | 'W')[];
  metadata: Partial<SGFMetadata>;
} {
  // Strip outer parentheses
  let content = sgfContent.trim();
  if (content.startsWith('(')) content = content.slice(1);
  if (content.endsWith(')')) content = content.slice(0, -1);

  // Split into nodes by semicolons (respecting brackets)
  const nodes = splitNodes(content);
  const moves: string[] = [];
  const stoneColors: ('B' | 'W')[] = [];
  const metadata: Partial<SGFMetadata> = {};

  for (const node of nodes) {
    const props = parseNode(node);

    // Extract metadata from root node
    if (props.SZ) metadata.boardSize = parseInt(props.SZ[0], 10);
    if (props.KM) metadata.komi = parseFloat(props.KM[0]);
    if (props.HA) metadata.handicap = parseInt(props.HA[0], 10);
    if (props.RU) metadata.rules = props.RU[0];
    if (props.PB) metadata.playerBlack = props.PB[0];
    if (props.PW) metadata.playerWhite = props.PW[0];

    const boardSize = metadata.boardSize || 19;

    // Extract moves
    for (const color of ['B', 'W'] as const) {
      if (props[color]) {
        const val = props[color][0];
        if (!val || val === '') {
          moves.push('pass');
        } else {
          const coords = fromSgfCoord(val, boardSize);
          if (coords) {
            moves.push(toDisplayMove(coords[0], coords[1]));
          }
        }
        stoneColors.push(color);
      }
    }

    // Handle setup stones (AB/AW) - convert to moves for simplicity
    for (const [prop, color] of [['AB', 'B'], ['AW', 'W']] as const) {
      if (props[prop]) {
        for (const val of props[prop]) {
          const coords = fromSgfCoord(val, boardSize);
          if (coords) {
            moves.push(toDisplayMove(coords[0], coords[1]));
            stoneColors.push(color);
          }
        }
      }
    }
  }

  return { moves, stoneColors, metadata };
}

// ── Round-trip validation ──

/**
 * Validate SGF by doing moves → SGF → moves round-trip.
 * Returns true if the round-trip produces the same moves array.
 */
export function validateSGFRoundTrip(
  moves: string[],
  metadata: SGFMetadata,
): { valid: boolean; error?: string } {
  try {
    const { sgf } = movesToSGF(moves, metadata);
    const { moves: parsedMoves } = sgfToMoves(sgf);

    // Compare move arrays
    if (parsedMoves.length !== moves.length) {
      return {
        valid: false,
        error: `Move count mismatch: original ${moves.length}, parsed ${parsedMoves.length}`,
      };
    }
    for (let i = 0; i < moves.length; i++) {
      if (parsedMoves[i] !== moves[i]) {
        return {
          valid: false,
          error: `Move ${i + 1} mismatch: original "${moves[i]}", parsed "${parsedMoves[i]}"`,
        };
      }
    }
    return { valid: true };
  } catch (e) {
    return { valid: false, error: String(e) };
  }
}

// ── Internal helpers ──

function escapeSGF(s: string): string {
  return s.replace(/\\/g, '\\\\').replace(/\]/g, '\\]');
}

function splitNodes(content: string): string[] {
  const nodes: string[] = [];
  let current = '';
  let depth = 0;

  for (let i = 0; i < content.length; i++) {
    const ch = content[i];
    if (ch === '[') depth++;
    if (ch === ']') depth--;
    if (ch === ';' && depth === 0) {
      if (current.trim()) nodes.push(current.trim());
      current = '';
    } else {
      current += ch;
    }
  }
  if (current.trim()) nodes.push(current.trim());
  return nodes;
}

function parseNode(nodeStr: string): Record<string, string[]> {
  const props: Record<string, string[]> = {};
  let i = 0;

  while (i < nodeStr.length) {
    // Skip whitespace
    while (i < nodeStr.length && /\s/.test(nodeStr[i])) i++;
    if (i >= nodeStr.length) break;

    // Read property identifier (uppercase letters)
    let propId = '';
    while (i < nodeStr.length && /[A-Z]/.test(nodeStr[i])) {
      propId += nodeStr[i];
      i++;
    }
    if (!propId) { i++; continue; }

    // Read property values [...]
    const values: string[] = [];
    while (i < nodeStr.length && nodeStr[i] === '[') {
      i++; // skip [
      let val = '';
      while (i < nodeStr.length && nodeStr[i] !== ']') {
        if (nodeStr[i] === '\\' && i + 1 < nodeStr.length) {
          i++; // skip escape
        }
        val += nodeStr[i];
        i++;
      }
      if (i < nodeStr.length) i++; // skip ]
      values.push(val);
    }

    if (props[propId]) {
      props[propId].push(...values);
    } else {
      props[propId] = values;
    }
  }

  return props;
}
