/**
 * Frontend SGF Parser for Tsumego Problems
 *
 * Parses SGF (Smart Game Format) strings into a tree structure for move validation.
 * Designed for tsumego problems where we need to validate user moves against
 * correct/incorrect solution paths.
 */

export interface SGFNode {
  move: { player: 'B' | 'W'; coords: [number, number] | null } | null;
  properties: Record<string, string[]>;
  children: SGFNode[];
  parent: SGFNode | null;
  comment?: string;
}

export interface ParsedSGF {
  root: SGFNode;
  boardSize: number;
  initialBlack: [number, number][];
  initialWhite: [number, number][];
  nextPlayer: 'B' | 'W';
}

// SGF coordinate letters (lowercase a-z, then uppercase A-Z for boards > 26)
const SGF_COORD = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ';

/**
 * Convert SGF coordinate string to [x, y] tuple
 * SGF uses 'aa' for top-left, but we use [0, boardSize-1] for top-left
 */
export function sgfToCoords(sgf: string, boardSize: number): [number, number] | null {
  if (!sgf || sgf === 'tt' || sgf.length < 2) return null; // pass or empty
  const x = SGF_COORD.indexOf(sgf[0]);
  const y = boardSize - 1 - SGF_COORD.indexOf(sgf[1]);
  if (x < 0 || x >= boardSize || y < 0 || y >= boardSize) return null;
  return [x, y];
}

/**
 * Convert [x, y] coordinates to SGF string
 */
export function coordsToSgf(coords: [number, number], boardSize: number): string {
  const [x, y] = coords;
  return SGF_COORD[x] + SGF_COORD[boardSize - 1 - y];
}

/**
 * Parse SGF property values - handles escaping and multiple values
 */
function parsePropertyValues(valueStr: string): string[] {
  const values: string[] = [];
  const regex = /\[([^\]\\]|\\.)*\]/g;
  let match;
  while ((match = regex.exec(valueStr)) !== null) {
    // Remove brackets and unescape
    const value = match[0].slice(1, -1).replace(/\\(.)/g, '$1');
    values.push(value);
  }
  return values;
}

/**
 * Parse an SGF string into a tree structure
 */
export function parseSGF(sgfContent: string): ParsedSGF {
  // Find the SGF content (between outermost parentheses)
  const match = sgfContent.match(/\(;[\s\S]*\)/);
  if (!match) {
    throw new Error('Invalid SGF: No valid SGF content found');
  }

  const content = match[0];
  let index = 1; // Skip opening '('

  // Helper to get board size from root
  function getBoardSize(node: SGFNode): number {
    const sz = node.properties['SZ'];
    if (sz && sz[0]) {
      const size = sz[0].includes(':')
        ? parseInt(sz[0].split(':')[0])
        : parseInt(sz[0]);
      return size || 19;
    }
    return 19;
  }

  // Parse the tree recursively
  function parseNode(parent: SGFNode | null): SGFNode {
    const node: SGFNode = {
      move: null,
      properties: {},
      children: [],
      parent
    };

    // Skip whitespace
    while (index < content.length && /\s/.test(content[index])) index++;

    // Expect ';' for node start
    if (content[index] === ';') {
      index++;
    }

    // Parse properties
    while (index < content.length) {
      // Skip whitespace
      while (index < content.length && /\s/.test(content[index])) index++;

      // Check for special characters
      if (content[index] === '(' || content[index] === ')' || content[index] === ';') {
        break;
      }

      // Parse property name (uppercase letters)
      let propName = '';
      while (index < content.length && /[A-Z]/.test(content[index])) {
        propName += content[index];
        index++;
      }

      if (!propName) break;

      // Parse property values (everything in brackets)
      let valueStr = '';
      while (index < content.length && content[index] === '[') {
        const start = index;
        index++; // Skip '['
        while (index < content.length) {
          if (content[index] === '\\' && index + 1 < content.length) {
            index += 2; // Skip escaped character
          } else if (content[index] === ']') {
            index++;
            break;
          } else {
            index++;
          }
        }
        valueStr += content.slice(start, index);
      }

      const values = parsePropertyValues(valueStr);
      node.properties[propName] = values;

      // Extract move if B or W property
      if (propName === 'B' || propName === 'W') {
        // For board size, traverse up to root
        let rootNode: SGFNode = node;
        while (rootNode.parent) rootNode = rootNode.parent;
        const boardSize = getBoardSize(rootNode);
        const coords = sgfToCoords(values[0], boardSize);
        node.move = { player: propName as 'B' | 'W', coords };
      }

      // Extract comment
      if (propName === 'C') {
        node.comment = values[0];
      }
    }

    // Parse children (variations)
    while (index < content.length) {
      // Skip whitespace
      while (index < content.length && /\s/.test(content[index])) index++;

      if (content[index] === '(') {
        // Start of variation
        index++; // Skip '('
        const child = parseNode(node);
        node.children.push(child);
        // Skip closing ')' handled inside
      } else if (content[index] === ';') {
        // Continuation node (not a variation)
        const child = parseNode(node);
        node.children.push(child);
      } else if (content[index] === ')') {
        index++; // Skip ')'
        break;
      } else {
        break;
      }
    }

    return node;
  }

  // Parse starting from root
  const parsedRoot = parseNode(null);

  // Extract board size
  const boardSize = getBoardSize(parsedRoot);

  // Extract initial stones (AB/AW properties from root)
  const initialBlack: [number, number][] = [];
  const initialWhite: [number, number][] = [];

  const abProps = parsedRoot.properties['AB'] || [];
  const awProps = parsedRoot.properties['AW'] || [];

  for (const sgf of abProps) {
    const coords = sgfToCoords(sgf, boardSize);
    if (coords) initialBlack.push(coords);
  }

  for (const sgf of awProps) {
    const coords = sgfToCoords(sgf, boardSize);
    if (coords) initialWhite.push(coords);
  }

  // Determine next player
  let nextPlayer: 'B' | 'W' = 'B';
  const pl = parsedRoot.properties['PL'];
  if (pl && pl[0]) {
    nextPlayer = pl[0].toUpperCase() === 'W' ? 'W' : 'B';
  } else if (initialBlack.length > 0 && initialWhite.length === 0) {
    // Handicap-like setup: black stones placed, white to play
    nextPlayer = 'W';
  } else if (awProps.length > abProps.length) {
    nextPlayer = 'B';
  }

  return {
    root: parsedRoot,
    boardSize,
    initialBlack,
    initialWhite,
    nextPlayer
  };
}

/**
 * Find a child node matching the given move
 */
export function findChildMove(
  node: SGFNode,
  player: 'B' | 'W',
  coords: [number, number]
): SGFNode | null {
  for (const child of node.children) {
    if (child.move &&
        child.move.player === player &&
        child.move.coords &&
        child.move.coords[0] === coords[0] &&
        child.move.coords[1] === coords[1]) {
      return child;
    }
  }
  return null;
}

/**
 * Check if a node represents a "correct" path
 * Correct paths are typically the main line (first child) or marked with 'TE' (tesuji) or 'GB' (good for black/white)
 * Wrong paths often have 'BM' (bad move) or comments indicating wrong
 */
export function isCorrectPath(node: SGFNode): boolean {
  // Check for "correct" markers
  if (node.properties['TE'] || node.properties['GB'] || node.properties['GW']) {
    return true;
  }

  // Check for "wrong" markers
  if (node.properties['BM'] || node.properties['DO']) {
    return false;
  }

  // Check comment for common wrong indicators
  const comment = node.comment?.toLowerCase() || '';
  if (comment.includes('wrong') || comment.includes('incorrect') ||
      comment.includes('失败') || comment.includes('错') ||
      comment.includes('bad')) {
    return false;
  }

  // Check comment for correct indicators
  if (comment.includes('correct') || comment.includes('right') ||
      comment.includes('成功') || comment.includes('正解') ||
      comment.includes('good')) {
    return true;
  }

  // Default: first child in main line is typically correct
  return true;
}

/**
 * Check if we've reached the end of the solution (problem solved)
 */
export function isSolutionComplete(node: SGFNode): boolean {
  // No more moves in this branch
  if (node.children.length === 0) {
    return isCorrectPath(node);
  }

  // Check for explicit "solved" markers
  const comment = node.comment?.toLowerCase() || '';
  if (comment.includes('solved') || comment.includes('完成') ||
      comment.includes('success') || comment.includes('正解')) {
    return true;
  }

  return false;
}

/**
 * Get the AI response move (opponent's move after user's correct move)
 */
export function getAIResponse(node: SGFNode): { player: 'B' | 'W'; coords: [number, number] } | null {
  if (node.children.length === 0) return null;

  // Get the first child (main line response)
  const response = node.children[0];
  if (response.move && response.move.coords) {
    return {
      player: response.move.player,
      coords: response.move.coords
    };
  }

  return null;
}

/**
 * Get all valid moves at current node (for hint system)
 */
export function getValidMoves(node: SGFNode): Array<{ player: 'B' | 'W'; coords: [number, number]; isCorrect: boolean }> {
  const moves: Array<{ player: 'B' | 'W'; coords: [number, number]; isCorrect: boolean }> = [];

  for (let i = 0; i < node.children.length; i++) {
    const child = node.children[i];
    if (child.move && child.move.coords) {
      moves.push({
        player: child.move.player,
        coords: child.move.coords,
        isCorrect: i === 0 || isCorrectPath(child) // First move or explicitly marked correct
      });
    }
  }

  return moves;
}
