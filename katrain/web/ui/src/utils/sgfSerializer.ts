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

/** Convert SGF coord pair "dp" to (x, y) board coords, or 'pass' for pass notation */
function fromSgfCoord(sgf: string, boardSize: number): [number, number] | 'pass' | null {
  if (!sgf || sgf.length < 2) return null;
  // "tt" is a standard SGF pass notation for boards ≤ 19×19
  if (sgf === 'tt' && boardSize <= 19) return 'pass';
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

  // Determine how many leading moves are handicap setup stones.
  // These are emitted as AB[] in the root node (per SGF standard),
  // not as B[] move nodes.
  let setupCount = 0;
  if (handicap > 0 && stoneColors) {
    for (let i = 0; i < Math.min(handicap, moves.length); i++) {
      if (stoneColors[i] === 'B' && moves[i].toLowerCase() !== 'pass') {
        setupCount++;
      } else {
        break;
      }
    }
  }

  // Emit handicap stones as AB[] in root node
  if (setupCount > 0) {
    const abCoords: string[] = [];
    for (let i = 0; i < setupCount; i++) {
      const coords = parseDisplayMove(moves[i], boardSize);
      if (coords) {
        abCoords.push(toSgfCoord(coords[0], coords[1], boardSize));
      }
    }
    if (abCoords.length > 0) {
      root += `AB${abCoords.map(c => `[${c}]`).join('')}`;
    }
  }

  // Build move nodes (skip handicap setup stones)
  const nodes: string[] = [];
  let moveCount = 0;

  for (let i = setupCount; i < moves.length; i++) {
    const move = moves[i];
    // In handicap games (setupCount > 0), first game move = White.
    // In non-handicap games, first move = Black (standard alternation).
    const player = stoneColors?.[i] ?? (setupCount > 0
      ? ((i - setupCount) % 2 === 0 ? 'W' : 'B')
      : (i % 2 === 0 ? 'B' : 'W'));

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
 *
 * Correctly handles:
 * - Variations/branches: only follows the main line (first variation)
 * - AB/AW setup stones: converted to moves, placed before B/W moves per node
 * - Pass notation: empty B[]/W[] and B[tt]/W[tt] for ≤19×19 boards
 * - Escaped characters in property values
 */
export function sgfToMoves(sgfContent: string): {
  moves: string[];
  stoneColors: ('B' | 'W')[];
  metadata: Partial<SGFMetadata>;
} {
  const nodes = extractMainLine(sgfContent);
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

    // Process setup stones (AB/AW) BEFORE moves — handicap stones get lower numbers
    for (const [prop, color] of [['AB', 'B'], ['AW', 'W']] as const) {
      if (props[prop]) {
        for (const val of props[prop]) {
          const coords = fromSgfCoord(val, boardSize);
          if (coords && coords !== 'pass') {
            moves.push(toDisplayMove(coords[0], coords[1]));
            stoneColors.push(color);
          }
        }
      }
    }

    // Extract moves (B/W)
    for (const color of ['B', 'W'] as const) {
      if (props[color]) {
        const val = props[color][0];
        if (!val || val === '') {
          moves.push('pass');
          stoneColors.push(color);
        } else {
          const coords = fromSgfCoord(val, boardSize);
          if (coords === 'pass') {
            moves.push('pass');
            stoneColors.push(color);
          } else if (coords) {
            moves.push(toDisplayMove(coords[0], coords[1]));
            stoneColors.push(color);
          }
          // If coords is null (unparseable), skip both to keep arrays in sync
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

/**
 * Extract the main-line node strings from an SGF.
 *
 * SGF grammar (simplified):
 *   GameTree = "(" Sequence { GameTree } ")"
 *   Sequence = Node { Node }
 *   Node     = ";" { Property }
 *
 * At every branch point we follow only the FIRST GameTree (main variation).
 */
function extractMainLine(sgfContent: string): string[] {
  const s = sgfContent.trim();
  let i = 0;
  const len = s.length;

  // Skip to the opening '(' of the root GameTree
  while (i < len && s[i] !== '(') i++;
  if (i >= len) return [];
  i++; // skip '('

  const nodes: string[] = [];

  // Recursive descent: parse one sequence + optionally enter first variation
  function parseSequence(): void {
    while (i < len) {
      skipWhitespace();
      if (i >= len) return;

      if (s[i] === ';') {
        i++; // skip ';'
        // Collect everything until next ';', '(', or ')'
        let nodeStr = '';
        while (i < len && s[i] !== ';' && s[i] !== '(' && s[i] !== ')') {
          if (s[i] === '[') {
            nodeStr += s[i++]; // '['
            while (i < len) {
              if (s[i] === '\\' && i + 1 < len) {
                nodeStr += s[i++]; // backslash
                nodeStr += s[i++]; // escaped char
              } else if (s[i] === ']') {
                nodeStr += s[i++]; // ']'
                break;
              } else {
                nodeStr += s[i++];
              }
            }
          } else {
            nodeStr += s[i++];
          }
        }
        if (nodeStr.trim()) nodes.push(nodeStr.trim());
      } else if (s[i] === '(') {
        // Branch point — enter the FIRST variation only
        i++; // skip '('
        parseSequence();
        // Skip the closing ')' of the first variation
        if (i < len && s[i] === ')') i++;
        // Skip all remaining sibling variations
        skipWhitespace();
        while (i < len && s[i] === '(') {
          skipVariation();
        }
        return; // done with this level
      } else if (s[i] === ')') {
        return; // end of current GameTree
      } else {
        i++; // skip unexpected character
      }
    }
  }

  function skipWhitespace(): void {
    while (i < len && /\s/.test(s[i])) i++;
  }

  /** Skip a complete (...) variation, handling nested parens and brackets */
  function skipVariation(): void {
    if (i >= len || s[i] !== '(') return;
    i++; // skip '('
    let depth = 1;
    while (i < len && depth > 0) {
      if (s[i] === '[') {
        i++; // skip '['
        while (i < len) {
          if (s[i] === '\\' && i + 1 < len) { i += 2; }
          else if (s[i] === ']') { i++; break; }
          else { i++; }
        }
      } else {
        if (s[i] === '(') depth++;
        else if (s[i] === ')') depth--;
        i++;
      }
    }
  }

  parseSequence();
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
          i++; // skip backslash, keep the escaped char
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
