import { describe, expect, it } from 'vitest';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { buildReplayBoardState, buildReplayPosition, parseMove } from './goReplay';
import { buildReplayBoardState as buildResearchReplayBoardState } from './researchBoardReplay';
import { sgfToMoves } from './sgfSerializer';
import kifu140859 from './__fixtures__/kifu-140859.sgf?raw';
import kifu124442 from './__fixtures__/kifu-124442.sgf?raw';
import kifu118394 from './__fixtures__/kifu-118394.sgf?raw';

type ReplayPosition = { black: string[]; white: string[]; last?: string };
// Independent sgfmill diagnostic oracle; provenance is kept in the shared fixture.
const golden = JSON.parse(readFileSync(resolve(process.cwd(), '../../../tests/data/baipu_ff4_golden.json'), 'utf8')) as {
  games: Array<{ id: number; sgf_sha256: string; steps: number; hashes: string[] }>;
};
function matrixPosition(state: ReturnType<typeof buildReplayBoardState>): ReplayPosition {
  const position: ReplayPosition = { black: [], white: [] };
  const columns = 'ABCDEFGHJKLMNOPQRST';
  state.board.forEach((row, y) => row.forEach((stone, x) => {
    if (stone) position[stone === 'B' ? 'black' : 'white'].push(`${columns[x]}${y + 1}`);
  }));
  if (state.lastMove) position.last = `${columns[state.lastMove[0]]}${state.lastMove[1] + 1}`;
  return position;
}

const records = [
  { id: 140859, sgf: kifu140859, moveCount: 345, setupCount: 2, overwriteMove: 224, point: 'A5', before: 'W', after: 'B', finalCount: 232 },
  { id: 124442, sgf: kifu124442, moveCount: 488, setupCount: 0, overwriteMove: 250, point: 'T10', before: 'B', after: 'W', finalCount: 259 },
  { id: 118394, sgf: kifu118394, moveCount: 304, setupCount: 0, overwriteMove: 191, point: 'C9', before: 'W', after: 'B', finalCount: 202 },
] as const;

describe('Galaxy SGF replay compatibility', () => {
  it('removes 124442’s suicidal C8 at step 394 even though its terminal count stays 259', () => {
    const { moves, stoneColors } = sgfToMoves(kifu124442);
    const state = buildReplayBoardState(moves, 394, 19, stoneColors);
    expect(state.board[7][2]).toBeNull();
    expect(state.moveNumbers[7][2]).toBeNull();
    expect(state.lastMove).toEqual([2, 7]);
  });

  it('matches the frozen FF4 final coordinates for the original records', () => {
    const finalPositions = Object.fromEntries(records.map(record => {
      const { moves, stoneColors, metadata, setupCount } = sgfToMoves(record.sgf);
      const position = matrixPosition(buildReplayBoardState(moves, moves.length, metadata.boardSize ?? 19, stoneColors, setupCount));
      return [record.id, { black: position.black.join(' '), white: position.white.join(' '), last: position.last }];
    }));
    expect(finalPositions).toMatchInlineSnapshot(`
      {
        "118394": {
          "black": "B1 O1 B2 C2 D2 L2 O2 Q2 B3 C3 K3 O3 Q3 C4 E4 F4 L4 N4 P4 Q4 D5 K5 L5 M5 O5 Q5 R5 S5 D6 E6 F6 K6 N6 P6 Q6 D7 L7 O7 P7 C8 D8 E8 O8 C9 E9 F9 G9 H9 J9 N9 O9 B10 C10 D10 E10 N10 P10 Q10 D11 E11 L11 M11 P11 Q11 T11 D12 H12 J12 K12 M12 Q12 R12 S12 T12 D13 H13 K13 M13 P13 Q13 H14 N14 O14 Q14 R14 H15 R15 H16 K16 L16 O16 P16 Q16 C17 F17 H17 L17 N17 R17 B18 G18 K18 L18 N18 O18 K19",
          "last": "K10",
          "white": "P1 Q1 A2 M2 N2 P2 R2 D3 L3 N3 P3 S3 B4 D4 G4 J4 K4 M4 S4 C5 E5 F5 C6 J6 M6 R6 S6 B7 C7 G7 Q7 R7 B8 P8 Q8 P9 F10 G10 H10 J10 K10 O10 R10 T10 B11 G11 H11 K11 N11 O11 R11 S11 E12 F12 G12 L12 N12 P12 G13 J13 L13 N13 R13 G14 J14 K14 L14 M14 P14 C15 G15 J15 M15 N15 O15 P15 Q15 B16 D16 G16 J16 M16 N16 B17 D17 G17 J17 K17 M17 O17 D18 F18 H18 J18 M18 J19",
        },
        "124442": {
          "black": "J1 K1 L1 M1 A2 D2 F2 H2 K2 N2 O2 Q2 R2 B3 F3 H3 O3 Q3 S3 D4 E4 G4 H4 K4 N4 O4 P4 R4 A5 B5 D5 H5 K5 R5 S5 T5 C6 D6 E6 H6 J6 K6 L6 M6 T6 D7 E7 F7 L7 P7 S7 D8 H8 M8 O8 P8 Q8 S8 C9 D9 G9 H9 J9 L9 M9 O9 Q9 S9 A10 B10 F10 J10 K10 M10 O10 P10 S10 D11 E11 J11 N11 Q11 A12 F12 G12 J12 L12 M12 Q12 K13 O13 Q13 D14 F14 G14 K14 M14 O14 Q14 T14 B15 C15 D15 H15 O15 P15 R15 S15 B16 D16 E16 J16 N16 P16 Q16 R16 G17 H17 O17 P17 A18 C18 H18 K18 C19 D19 J19",
          "last": "F17",
          "white": "C1 B2 C2 E2 G2 J2 M2 P2 C3 D3 E3 G3 K3 L3 M3 N3 P3 B4 C4 F4 M4 Q4 C5 F5 G5 N5 O5 Q5 A6 B6 G6 O6 P6 Q6 R6 S6 A7 B7 C7 J7 M7 N7 O7 Q7 R7 B8 C8 E8 F8 K8 R8 B9 E9 F9 R9 C10 D10 E10 L10 N10 Q10 R10 T10 B11 F11 K11 L11 M11 R11 S11 B12 D12 E12 H12 N12 S12 A13 C13 D13 F13 G13 L13 M13 N13 R13 A14 B14 C14 E14 H14 J14 P14 R14 S14 E15 G15 N15 C16 F16 G16 H16 K16 L16 M16 S16 B17 C17 D17 E17 F17 J17 K17 M17 N17 Q17 R17 S17 T17 B18 D18 G18 L18 O18 P18 R18 S18 E19 K19 M19 N19 Q19 R19",
        },
        "140859": {
          "black": "D1 K1 L1 D2 J2 L2 P2 Q2 S2 B3 G3 H3 M3 N3 Q3 S3 A4 B4 C4 D4 H4 K4 L4 M4 N4 O4 P4 Q4 R4 T4 A5 D5 F5 H5 L5 Q5 R5 T5 A6 C6 D6 E6 F6 H6 L6 O6 Q6 T6 F7 G7 K7 Q7 R7 S7 F8 J8 K8 M8 N8 Q8 M9 Q9 C10 D10 E10 G10 J10 M10 R10 G11 H11 J11 K11 M11 R11 S11 G12 H12 J12 L12 Q12 C13 F13 G13 J13 M13 N13 J14 S14 T14 J15 K15 O15 R15 S15 K16 L16 P16 Q16 R16 D17 J17 K17 M17 P17 R17 K18 M18 N18 J19 K19 N19",
          "last": "F16",
          "white": "E1 F1 H1 J1 N1 S1 E2 F2 G2 K2 M2 N2 R2 T2 C3 D3 F3 J3 K3 L3 O3 P3 R3 E4 F4 J4 B5 C5 E5 G5 K5 N5 S5 B6 J6 K6 S6 A7 E7 H7 J7 T7 A8 B8 C8 D8 E8 G8 P8 S8 T8 E9 F9 G9 H9 J9 K9 N9 P9 R9 T9 F10 N10 Q10 S10 T10 D11 E11 F11 Q11 D12 F12 K12 P12 R12 S12 T12 E13 K13 L13 O13 P13 R13 S13 T13 F14 G14 H14 L14 M14 N14 P14 Q14 R14 C15 H15 L15 N15 P15 T15 F16 H16 J16 M16 O16 S16 T16 H17 N17 O17 Q17 S17 T17 H18 J18 O18 P18 H19 O19 Q19",
        },
      }
    `);
  });

  for (const record of records) {
    describe(`album ${record.id}`, () => {
      const { moves, stoneColors, metadata, setupCount } = sgfToMoves(record.sgf);
      const size = metadata.boardSize ?? 19;
      const stateAt = (cursor: number) => buildReplayBoardState(moves, setupCount + cursor, size, stoneColors, setupCount);
      const positionAt = (cursor: number) => buildReplayPosition(moves, setupCount + cursor, size, stoneColors, setupCount);

      it.each([
        ['shared', buildReplayBoardState],
        ['research', buildResearchReplayBoardState],
      ] as const)('%s replay matches the independent FF4 oracle at every original dense step', (_surface, buildState) => {
        const reference = golden.games.find(game => game.id === record.id)!;
        expect(createHash('sha256').update(record.sgf).digest('hex')).toBe(reference.sgf_sha256);
        expect(moves).toHaveLength(reference.steps);
        for (let k = 0; k <= moves.length; k += 1) {
          const position = matrixPosition(buildState(moves, k, size, stoneColors, setupCount));
          const stones = [...position.black.map(point => `B:${point}`), ...position.white.map(point => `W:${point}`)].sort();
          expect(createHash('sha256').update(stones.join('\n')).digest('hex'), `record ${record.id}, dense step ${k}`)
            .toBe(reference.hashes[k]);
        }
      });

      it('retains every recorded move and the initial setup stones', () => {
        expect(moves).toHaveLength(record.moveCount + record.setupCount);
        expect(setupCount).toBe(record.setupCount);
        const initial = stateAt(0);
        const expected = record.setupCount ? { black: ['D4', 'Q16'], white: [] } : { black: [], white: [] };
        expect(matrixPosition(initial)).toEqual(expected);
        expect(positionAt(0)).toEqual(expected);
        expect(initial.lastMove).toBeNull();
        expect(initial.moveNumbers.flat().every(number => number === null)).toBe(true);
      });

      it('overwrites the occupied point at the first conflicting recorded move', () => {
        const [x, y] = parseMove(record.point)!;
        const index = setupCount + record.overwriteMove - 1;
        expect(moves[index]).toBe(record.point);
        expect(stoneColors[index]).toBe(record.after);
        expect(stateAt(record.overwriteMove - 1).board[y][x]).toBe(record.before);
        const state = stateAt(record.overwriteMove);
        expect(state.board[y][x]).toBe(record.after);
        expect(state.moveNumbers[y][x]).toBe(record.overwriteMove);
        expect(state.lastMove).toEqual([x, y]);
        expect(positionAt(record.overwriteMove)).toEqual(matrixPosition(state));
      });

      it('renders the FF4 final position at every occupied coordinate', () => {
        const expected = matrixPosition(stateAt(record.moveCount));
        expect(expected.black.length + expected.white.length).toBe(record.finalCount);
        expect(positionAt(record.moveCount)).toEqual(expected);
      });
    });
  }
});

describe('shared replay rules and coordinates', () => {
  it('removes a zero-liberty placed stone after checking opponent captures', () => {
    const state = buildReplayBoardState(['A2', 'B1', 'A1'], 3, 9, ['W', 'W', 'B'], 2);
    expect(matrixPosition(state)).toEqual({ black: [], white: ['B1', 'A2'], last: 'A1' });
    expect(state.moveNumbers[0][0]).toBeNull();
  });

  it('removes the whole own group when the recorded move has no liberties', () => {
    const state = buildReplayBoardState(['A1', 'B1', 'B2', 'A3', 'A2'], 5, 9, ['B', 'W', 'W', 'W', 'B'], 4);
    expect(matrixPosition(state)).toEqual({ black: [], white: ['B1', 'B2', 'A3'], last: 'A2' });
    expect(state.moveNumbers.flat().every(number => number === null)).toBe(true);
  });

  it('assigns initial setup stones directly without taking neighboring groups', () => {
    const state = buildReplayBoardState(['A1', 'B1', 'A2'], 3, 9, ['B', 'W', 'W'], 3);
    expect(matrixPosition(state)).toEqual({ black: ['A1'], white: ['B1', 'A2'] });
    expect(state.moveNumbers.flat().every(number => number === null)).toBe(true);
  });

  it('retains the recorded player on a pass', () => {
    const state = buildReplayBoardState(['A1', 'pass'], 2, 9, ['B', 'W']);
    expect(state.lastPlayer).toBe('W');
    expect(state.lastMove).toEqual([0, 0]);
  });

  it('parses GTP columns with I skipped and bottom-origin rows', () => {
    expect(parseMove('Q16')).toEqual([15, 15]);
    expect(parseMove('t19')).toEqual([18, 18]);
    expect(parseMove('A1')).toEqual([0, 0]);
    expect(parseMove('pass')).toBeNull();
    expect(parseMove('')).toBeNull();
  });

  it('removes a captured stone and its move number', () => {
    const { moves, stoneColors } = sgfToMoves('(;SZ[9];B[bb];W[ab];W[ba];W[cb];W[bc])');
    const state = buildReplayBoardState(moves, moves.length, 9, stoneColors);
    expect(state.board[7][1]).toBeNull();
    expect(state.moveNumbers[7][1]).toBeNull();
    expect(buildReplayPosition(moves, moves.length, 9, stoneColors)).toEqual({
      black: [], white: ['B7', 'A8', 'C8', 'B9'], last: 'B7',
    });
  });

  it('keeps empty and tt SGF passes in the cursor without adding stones', () => {
    const { moves, stoneColors } = sgfToMoves('(;SZ[9];B[aa];W[];B[tt];W[ii])');
    expect(moves).toEqual(['A9', 'pass', 'pass', 'J1']);
    const afterPasses = buildReplayBoardState(moves, 3, 9, stoneColors);
    expect(matrixPosition(afterPasses)).toEqual({ black: ['A9'], white: [], last: 'A9' });
    expect(afterPasses.lastPlayer).toBe('B');
    const final = buildReplayBoardState(moves, 4, 9, stoneColors);
    expect(final.moveNumbers[0][8]).toBe(4);
    expect(buildReplayPosition(moves, 4, 9, stoneColors)).toEqual({ black: ['A9'], white: ['J1'], last: 'J1' });
  });

  it('uses explicit colors for consecutive same-color records', () => {
    const { moves, stoneColors } = sgfToMoves('(;SZ[9];W[aa];W[bb];B[cc];B[dd])');
    const state = buildReplayBoardState(moves, moves.length, 9, stoneColors);
    expect(state.lastPlayer).toBe('B');
    expect(buildReplayPosition(moves, moves.length, 9, stoneColors)).toEqual({
      black: ['D6', 'C7'], white: ['B8', 'A9'], last: 'D6',
    });
  });

  it.each([9, 13, 19])('keeps top and bottom oriented correctly on a %i board', size => {
    const lastSgfCoordinate = String.fromCharCode(97 + size - 1).repeat(2);
    const { moves, stoneColors } = sgfToMoves(`(;SZ[${size}];B[aa];W[${lastSgfCoordinate}])`);
    const state = buildReplayBoardState(moves, 2, size, stoneColors);
    expect(state.board[size - 1][0]).toBe('B');
    expect(state.board[0][size - 1]).toBe('W');
    const bottomRight = `${'ABCDEFGHJKLMNOPQRST'[size - 1]}1`;
    expect(buildReplayPosition(moves, 2, size, stoneColors)).toEqual({
      black: [`A${size}`], white: [bottomRight], last: bottomRight,
    });
  });
});
